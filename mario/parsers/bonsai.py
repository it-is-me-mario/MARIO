"""Read BONSAI Balanced hybrid supply-use graph exports as sparse SUT blocks."""

from __future__ import annotations

import ast
from contextlib import ExitStack
from dataclasses import dataclass
import logging
from pathlib import Path, PurePosixPath
import warnings
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd
from scipy import sparse

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.utils import rename_index


_CLASSIFICATION = "classification.csv"
_SUPPLY = "hybrid_supply_w_characteristic_unit.csv"
_USE = "hybrid_use_w_characteristic_unit.csv"
_EXTENSIONS = "all_elementary_flows_AB_and_BB.csv"
_CORE_FILES = (_CLASSIFICATION, _SUPPLY, _USE)
BONSAI_SOURCE = (
    "BONSAI Balanced hybrid supply-use tables; https://gitlab.com/bonsamurais/bonsai"
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BonsaiLayout:
    """Provenance and import diagnostics for one Balanced release."""

    path: Path
    year: int
    notes: tuple[str, ...]
    report: dict
    source: str = BONSAI_SOURCE


class _Bundle:
    """Open only selected CSVs, without extracting or deserializing pickle files."""

    def __init__(self, path, stack):
        self.path = Path(path).expanduser()
        self.archive = None
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        if self.path.is_dir():
            candidates = list(self.path.rglob(_CLASSIFICATION))
            roots = [
                p.parent
                for p in candidates
                if all((p.parent / n).is_file() for n in _CORE_FILES)
            ]
            if len(roots) != 1:
                raise WrongInput(
                    "Expected exactly one BONSAI Balanced directory containing "
                    + ", ".join(_CORE_FILES)
                )
            self.files = {p.name: p for p in roots[0].iterdir() if p.is_file()}
        else:
            try:
                self.archive = stack.enter_context(ZipFile(self.path))
            except BadZipFile as exc:
                raise WrongInput(
                    "BONSAI input is not a complete, valid ZIP archive."
                ) from exc
            members = self.archive.namelist()
            roots = {
                str(PurePosixPath(n).parent)
                for n in members
                if PurePosixPath(n).name == _CLASSIFICATION
                and "__MACOSX" not in PurePosixPath(n).parts
                and all(
                    str(PurePosixPath(n).parent / f) in members for f in _CORE_FILES
                )
            }
            if len(roots) != 1:
                raise WrongInput(
                    "Expected exactly one BONSAI Balanced bundle containing "
                    + ", ".join(_CORE_FILES)
                )
            root = roots.pop()
            self.files = {
                PurePosixPath(n).name: n
                for n in members
                if str(PurePosixPath(n).parent) == root
            }
            if any(members.count(self.files[n]) != 1 for n in _CORE_FILES):
                raise WrongInput("Duplicate BONSAI CSV members in ZIP archive.")

    def open(self, name):
        if name not in self.files:
            raise WrongInput(f"Missing BONSAI Balanced file: {name}")
        if self.archive is not None:
            if self.archive.namelist().count(self.files[name]) != 1:
                raise WrongInput(f"Duplicate BONSAI CSV member: {name}")
            return self.archive.open(self.files[name])
        return self.files[name].open("rb")


def _read_csv(bundle, name, columns, *, chunksize=None):
    """Yield selected columns with explicit string identities, including code 'NA'."""
    with bundle.open(name) as handle:
        try:
            reader = pd.read_csv(
                handle,
                usecols=columns,
                dtype=str,
                keep_default_na=False,
                chunksize=chunksize,
            )
            if chunksize is None:
                yield reader
            else:
                with reader:
                    yield from reader
        except (ValueError, pd.errors.ParserError) as exc:
            raise WrongInput(f"Invalid BONSAI CSV {name}: {exc}") from exc


def _properties(value):
    """The graph exporter writes Python dict literals; never evaluate expressions."""
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError) as exc:
        raise WrongInput(
            "Invalid BONSAI classification property: expected a dictionary literal."
        ) from exc
    if not isinstance(parsed, dict):
        raise WrongInput(
            "Invalid BONSAI classification property: expected a dictionary literal."
        )
    return parsed


def _classification(bundle):
    frame = next(
        _read_csv(
            bundle,
            _CLASSIFICATION,
            ["id", "name", "location", "time", "type", "property"],
        )
    )
    if (
        frame.empty
        or frame["id"].duplicated().any()
        or frame[["id", "name", "location", "time", "type"]].eq("").any().any()
    ):
        raise WrongInput(
            "BONSAI classification must contain unique nonempty node IDs and complete labels."
        )
    years = pd.to_numeric(frame["time"], errors="coerce")
    if not np.isfinite(years).all() or (years % 1 != 0).any() or years.nunique() != 1:
        raise WrongInput(
            "BONSAI parsing requires exactly one reference year in classification.csv."
        )
    props = frame["property"].map(_properties)
    is_process = frame["type"].eq("process")
    is_product = frame["type"].eq("object") & props.map(
        lambda p: p.get("object_type") == "product"
    )
    is_substance = frame["type"].eq("object") & props.map(
        lambda p: p.get("object_type") == "substance"
    )
    is_fd = is_process & props.map(lambda p: p.get("activity_type") == "final_demand")
    if not (is_process | is_product | is_substance).all():
        raise WrongInput(
            "Unsupported BONSAI node type or object_type in classification.csv."
        )
    frame["kind"] = np.select(
        [is_fd, is_process, is_product], ["n", "a", "c"], default="substance"
    )
    nodes = {
        kind: frame.loc[frame.kind.eq(kind)].reset_index(drop=True)
        for kind in ("a", "c", "n")
    }
    for kind, group in nodes.items():
        if group.empty or group.duplicated(["location", "name"]).any():
            raise WrongInput(
                f"BONSAI {kind} nodes must have unique (location, name) labels and be nonempty."
            )
    return frame.set_index("id", drop=False), nodes, int(years.iloc[0])


def _axis(nodes, kind):
    return pd.MultiIndex.from_arrays(
        [nodes.location, [_MASTER_INDEX[kind]] * len(nodes), nodes["name"]]
    )


def _values(frame, column, label):
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise WrongInput(f"Non-finite or invalid values in BONSAI {label}.")
    return values


class _SparseEntries:
    """Accumulate O(nonzero flows) triplets, never a dense economic matrix."""

    def __init__(self, shape):
        self.shape = shape
        self.parts = []

    def add(self, rows, columns, values):
        keep = values != 0
        if keep.any():
            self.parts.append(
                (
                    np.asarray(rows, dtype=np.int64)[keep],
                    np.asarray(columns, dtype=np.int64)[keep],
                    values[keep],
                )
            )

    def matrix(self):
        if not self.parts:
            return sparse.csr_matrix(self.shape, dtype=float)
        rows, cols, data = (np.concatenate(p) for p in zip(*self.parts))
        result = sparse.coo_matrix((data, (rows, cols)), shape=self.shape).tocsr()
        result.eliminate_zeros()
        return result


def _frame(matrix, index, columns):
    # pandas 3 uses NaN as the implicit fill value even for a scipy zero matrix.
    return pd.DataFrame.sparse.from_spmatrix(
        matrix, index=index, columns=columns
    ).fillna(0.0)


def _economic_flows(bundle, classification, nodes, *, chunksize):
    positions = {k: pd.Series(np.arange(len(g)), index=g.id) for k, g in nodes.items()}
    entries = {
        "S": _SparseEntries((len(nodes["a"]), len(nodes["c"]))),
        "U": _SparseEntries((len(nodes["c"]), len(nodes["a"]))),
        "Yc": _SparseEntries((len(nodes["c"]), len(nodes["n"]))),
    }
    commodity_units = {}
    counts = {}
    for filename, supply in ((_SUPPLY, True), (_USE, False)):
        logger.info("Parser: reading BONSAI %s.", filename)
        counts[filename] = {"product_rows": 0, "substance_rows": 0}
        for chunk in _read_csv(
            bundle,
            filename,
            ["from_node", "to_node", "value", "unit"],
            chunksize=chunksize,
        ):
            values = _values(chunk, "value", filename)
            source_kind = chunk.from_node.map(classification.kind)
            target_kind = chunk.to_node.map(classification.kind)
            if source_kind.isna().any() or target_kind.isna().any():
                raise WrongInput(f"Unknown node IDs in BONSAI {filename}.")
            product_kind, process_kind = (
                (target_kind, source_kind) if supply else (source_kind, target_kind)
            )
            if (
                not product_kind.isin(["c", "substance"]).all()
                or not process_kind.isin(["a", "n"]).all()
            ):
                raise WrongInput(
                    f"Invalid process/object flow direction in BONSAI {filename}."
                )
            economic = product_kind.eq("c")
            counts[filename]["product_rows"] += int(economic.sum())
            counts[filename]["substance_rows"] += int((~economic).sum())
            data = chunk.loc[economic].copy()
            values = values[economic.to_numpy()]
            product_ids = data.to_node if supply else data.from_node
            process_ids = data.from_node if supply else data.to_node
            unit_pairs = pd.DataFrame(
                {"code": product_ids.map(classification["name"]), "unit": data.unit}
            ).drop_duplicates()
            for code, unit in unit_pairs.itertuples(index=False, name=None):
                if not unit or (
                    code in commodity_units and commodity_units[code] != unit
                ):
                    raise WrongInput(
                        f"Missing or conflicting BONSAI commodity unit for {code!r}."
                    )
                commodity_units[code] = unit
            c = product_ids.map(positions["c"]).to_numpy()
            a = process_ids.map(positions["a"])
            if supply:
                if a.isna().any():
                    raise WrongInput(
                        "BONSAI final-demand supply is unsupported; expected activity-to-product supply."
                    )
                entries["S"].add(a.to_numpy(), c, values)
            else:
                activity = a.notna().to_numpy()
                entries["U"].add(c[activity], a.to_numpy()[activity], values[activity])
                fd = process_ids.map(positions["n"]).to_numpy()[~activity]
                entries["Yc"].add(c[~activity], fd, values[~activity])
    missing_units = set(nodes["c"]["name"]) - commodity_units.keys()
    if missing_units:
        raise WrongInput(
            f"BONSAI products without characteristic units: {sorted(missing_units)[:5]}"
        )
    return entries, commodity_units, counts


def _elementary_flows(bundle, nodes, *, enabled, unmatched):
    """Read the recalculated aggregate once, keeping direct final-demand flows."""
    if not enabled:
        return (
            pd.Index(["-"]),
            pd.DataFrame({"unit": ["None"]}, index=["-"]),
            None,
            None,
            {"extensions_loaded": False},
        )
    columns = [
        "Exio substance",
        "Exio country code",
        "Exio act code",
        "Exio compartment",
        "unit",
        "Value",
        "substance_name",
    ]
    # Keep all original columns for complete diagnostics on unmatched rows.
    raw = next(_read_csv(bundle, _EXTENSIONS, None))
    missing_columns = set(columns) - set(raw.columns)
    if missing_columns:
        raise WrongInput(
            f"Invalid BONSAI CSV {_EXTENSIONS}: missing columns {sorted(missing_columns)}"
        )
    if raw.empty:
        return (
            pd.Index(["-"]),
            pd.DataFrame({"unit": ["None"]}, index=["-"]),
            None,
            None,
            {
                "extensions_loaded": True,
                "elementary_flow_rows": 0,
                "unmatched_extensions": [],
                "satellites": [],
            },
        )
    values = _values(raw, "Value", _EXTENSIONS)
    if (
        raw[["Exio substance", "Exio country code", "Exio act code", "unit"]]
        .eq("")
        .any()
        .any()
    ):
        raise WrongInput("Incomplete BONSAI elementary-flow identities or units.")
    positions = {}
    for kind in ("a", "n"):
        positions[kind] = pd.Series(
            np.arange(len(nodes[kind])),
            index=pd.MultiIndex.from_frame(nodes[kind][["location", "name"]]),
        )
    targets = pd.MultiIndex.from_frame(raw[["Exio country code", "Exio act code"]])
    a = positions["a"].reindex(targets).to_numpy()
    n = positions["n"].reindex(targets).to_numpy()
    missing = np.isnan(a) & np.isnan(n)
    omitted = raw.loc[missing].to_dict("records")
    if missing.any():
        examples = list(
            dict.fromkeys(
                zip(
                    raw.loc[missing, "Exio country code"],
                    raw.loc[missing, "Exio act code"],
                )
            )
        )[:5]
        message = f"BONSAI: {int(missing.sum())} elementary-flow rows have no classified activity/final demand and are omitted; examples: {examples}. Full rows are in the bonsai import report."
        if unmatched == "raise":
            raise WrongInput(message)
        warnings.warn(message, UserWarning, stacklevel=3)
    # Retain the substance identity, compartment and unit, including unnamed flows.
    named = (
        raw.loc[raw.substance_name.ne("")]
        .drop_duplicates("Exio substance")
        .set_index("Exio substance")
        .substance_name
    )
    names = raw["Exio substance"].map(named).fillna(raw["Exio substance"])
    raw["substance_name"] = names
    raw["label"] = (
        names
        + " | "
        + raw["Exio compartment"].replace("", "unspecified")
        + " | "
        + raw.unit
        + " | "
        + raw["Exio substance"]
    )
    identities = raw.drop_duplicates(["Exio substance", "Exio compartment", "unit"])
    if identities.label.duplicated().any():
        raise WrongInput("Ambiguous BONSAI elementary-flow labels.")
    axis = pd.Index(identities.label)
    rows = axis.get_indexer(raw.label)
    ea, ey = _SparseEntries((len(axis), len(nodes["a"]))), _SparseEntries(
        (len(axis), len(nodes["n"]))
    )
    for cols, entries in ((a, ea), (n, ey)):
        matched = ~np.isnan(cols)
        entries.add(rows[matched], cols[matched], values[matched])
    units = pd.DataFrame({"unit": identities.unit.to_numpy()}, index=axis)
    report = {
        "extensions_loaded": True,
        "elementary_flow_rows": len(raw),
        "unmatched_extensions": omitted,
        "satellites": identities[
            ["label", "Exio substance", "substance_name", "Exio compartment", "unit"]
        ].to_dict("records"),
    }
    return axis, units, ea.matrix(), ey.matrix(), report


def parse_bonsai_hsut(
    path, *, extensions=True, unmatched_extensions="warn", chunksize=100_000
):
    """Parse a Balanced ZIP or extracted directory without computing multipliers."""
    if not isinstance(chunksize, int) or isinstance(chunksize, bool) or chunksize < 1:
        raise WrongInput("BONSAI chunksize must be a positive integer.")
    if not isinstance(extensions, bool):
        raise WrongInput("BONSAI extensions must be True or False.")
    if unmatched_extensions not in ("warn", "raise"):
        raise WrongInput("BONSAI unmatched_extensions must be 'warn' or 'raise'.")
    with ExitStack() as stack:
        bundle = _Bundle(path, stack)
        classification, nodes, year = _classification(bundle)
        logger.info(
            "Parser: BONSAI reference year %s, %s activities, %s products.",
            year,
            len(nodes["a"]),
            len(nodes["c"]),
        )
        entries, commodity_units, counts = _economic_flows(
            bundle, classification, nodes, chunksize=chunksize
        )
        k, satellite_units, ea, ey, report = _elementary_flows(
            bundle, nodes, enabled=extensions, unmatched=unmatched_extensions
        )

    axes = {kind: _axis(group, kind) for kind, group in nodes.items()}
    axes.update(k=k, f=pd.Index(["-"]))
    pairs = {
        "S": ("a", "c"),
        "U": ("c", "a"),
        "Ya": ("a", "n"),
        "Yc": ("c", "n"),
        "Va": ("f", "a"),
        "Vc": ("f", "c"),
        "Ea": ("k", "a"),
        "Ec": ("k", "c"),
        "EY": ("k", "n"),
    }
    blocks = {}
    for block, (row, col) in pairs.items():
        if block in entries:
            matrix = entries[block].matrix()
        else:
            matrix = {"Ea": ea, "EY": ey}.get(block)
        if matrix is None:
            matrix = sparse.csr_matrix((len(axes[row]), len(axes[col])), dtype=float)
        blocks[block] = _frame(matrix, axes[row], axes[col])
    rename_index(blocks)
    codes = {kind: list(dict.fromkeys(group["name"])) for kind, group in nodes.items()}
    units = {
        _MASTER_INDEX["a"]: pd.DataFrame({"unit": "None"}, index=codes["a"]),
        _MASTER_INDEX["c"]: pd.DataFrame(
            {"unit": [commodity_units[code] for code in codes["c"]]}, index=codes["c"]
        ),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": ["None"]}, index=["-"]),
        _MASTER_INDEX["k"]: satellite_units,
    }
    indexes = {kind: {"main": labels} for kind, labels in codes.items()}
    regions = list(
        dict.fromkeys(pd.concat([nodes[kind].location for kind in ("a", "c", "n")]))
    )
    indexes.update(
        {
            "r": {"main": regions},
            "s": {"main": codes["a"] + codes["c"]},
            "f": {"main": ["-"]},
            "k": {"main": list(k)},
        }
    )
    report.update(
        {
            "path": str(bundle.path),
            "reference_year": year,
            "files": list(_CORE_FILES) + ([_EXTENSIONS] if extensions else []),
            "economic_flows": counts,
        }
    )
    notes = [
        "BONSAI Balanced: characteristic-unit product flows only; substance graph edges excluded from S/U/Yc.",
        "BONSAI: reference year read from classification.csv, independently of the release folder date.",
        "BONSAI: native hybrid units retained; activity units are unspecified (None). Value added is unavailable; Va/Vc contain a zero placeholder, not estimated value added.",
        "BONSAI: imported as supplied; no automatic balancing or reconstruction of a Cartesian regional classification.",
    ]
    if extensions:
        notes.append(
            "BONSAI: Ea/EY use only all_elementary_flows_AB_and_BB.csv; Ec is zero. Blank compartments remain unspecified."
        )
        notes.append(
            f"BONSAI: {len(report['unmatched_extensions'])} unmatched elementary-flow rows omitted; complete diagnostics retained in the bonsai import report."
        )
    else:
        notes.append(
            "BONSAI: elementary flows were not loaded; Ea/Ec/EY contain zero placeholders."
        )
    layout = BonsaiLayout(bundle.path, year, tuple(notes), report)
    return {"baseline": blocks}, indexes, units, layout
