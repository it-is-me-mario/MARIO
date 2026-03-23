"""Direct parsers for EORA single-region tables and Eora26 MRIO folders."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import re

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import IOT, SUT, _MASTER_INDEX
from mario.utils import delete_duplicates, rename_index

logger = logging.getLogger(__name__)

EORA_SOURCE = "Eora website @ https://www.worldmrio.com/"
_SINGLE_REGION_FILE_RE = re.compile(
    r"^IO_(?P<country>[A-Z0-9]+)_(?P<year>\d{4})_(?P<price>BasicPrice|PurchasersPrice)\.txt$"
)
_EORA26_DATA_RE = re.compile(
    r"^Eora26_(?P<year>\d{4})_(?P<price>[A-Za-z]+)_(?P<kind>T|FD|VA|Q|QY)\.txt$"
)
_NAME_CONVENTIONS = {"full_name": 1, "abbreviation": 2}


@dataclass(frozen=True)
class EoraSingleRegionLayout:
    """Filesystem layout and metadata for one EORA single-region table file."""

    path: Path
    year: int
    price: str
    country: str

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        return self.path.stem

    @property
    def source(self) -> str:
        """Return the canonical source string stored in metadata."""
        return EORA_SOURCE


@dataclass(frozen=True)
class Eora26Layout:
    """Filesystem layout and metadata for one Eora26 directory."""

    root: Path
    year: int
    price: str
    index_root: Path
    notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "ROW deleted from database due to inconsistency.",
            "Intermediate imports from ROW added to VA matrix.",
            "Intermediate exports to ROW added to Y matrix.",
        )
    )

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        return self.root.name

    @property
    def source(self) -> str:
        """Return the canonical source string stored in metadata."""
        return EORA_SOURCE


def _normalize_name_convention(name_convention: str) -> int:
    """Return the raw EORA level index used for one region naming policy."""
    key = str(name_convention).strip().lower()
    if key not in _NAME_CONVENTIONS:
        raise WrongInput(
            "name_convention should be one of {}".format(sorted(_NAME_CONVENTIONS))
        )
    return _NAME_CONVENTIONS[key]


def _extract_unit(label: object) -> str:
    """Extract the unit token from one EORA extension group label when possible."""
    text = str(label)
    match = re.search(r"\(([^()]*)\)\s*$", text)
    return match.group(1).strip() if match else text


def _select_axis_labels(frame: pd.DataFrame, axis: int, groups: set[str]) -> np.ndarray:
    """Return a boolean mask selecting one or more EORA top-level groups."""
    labels = frame.index.get_level_values(0) if axis == 0 else frame.columns.get_level_values(0)
    return labels.isin(groups)


def _detect_single_region_table(data: pd.DataFrame) -> str:
    """Infer whether a single-region EORA file is IOT-like or SUT-like."""
    row_groups = set(data.index.get_level_values(0))
    col_groups = set(data.columns.get_level_values(0))

    has_industries = "Industries" in row_groups and "Industries" in col_groups
    has_commodities = "Commodities" in row_groups and "Commodities" in col_groups

    if has_industries and has_commodities:
        return SUT
    if has_industries and not has_commodities:
        return IOT

    raise WrongFormat("Could not detect whether the EORA single-region file is IOT or SUT.")


def resolve_eora_single_region_file(
    path: str | Path,
    *,
    country: str | None = None,
    year: int | None = None,
    price: str | None = None,
) -> EoraSingleRegionLayout:
    """Resolve one single-region EORA file from either a file path or dataset folder."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    if source.is_file():
        match = _SINGLE_REGION_FILE_RE.match(source.name)
        if match is None:
            raise WrongInput(
                "Single-region EORA files should look like IO_<country>_<year>_<price>.txt."
            )
        layout = EoraSingleRegionLayout(
            path=source,
            country=match.group("country"),
            year=int(match.group("year")),
            price=match.group("price"),
        )
    else:
        if country is None:
            raise WrongInput(
                "When path points to an EORA single-region directory, country should be provided."
            )

        candidates = sorted(
            child
            for child in source.iterdir()
            if child.is_file() and _SINGLE_REGION_FILE_RE.match(child.name)
        )
        if year is not None:
            candidates = [child for child in candidates if f"_{year}_" in child.name]
        if price is not None:
            candidates = [child for child in candidates if price.lower() in child.name.lower()]
        candidates = [child for child in candidates if f"IO_{country}_" in child.name]

        if not candidates:
            raise WrongInput("No EORA single-region file matches the requested country/year/price.")
        if len(candidates) > 1:
            raise WrongInput(
                "More than one EORA single-region file matches the request. "
                "Please specify year and/or price."
            )

        return resolve_eora_single_region_file(candidates[0])

    if year is not None and layout.year != year:
        raise WrongInput(
            f"The resolved EORA single-region file is for year {layout.year}, not {year}."
        )
    if price is not None and layout.price.lower() != str(price).lower():
        raise WrongInput(
            f"The resolved EORA single-region file uses price {layout.price}, not {price}."
        )
    return layout


def detect_eora26_layout(path: str | Path, *, index_path: str | Path | None = None) -> Eora26Layout:
    """Detect one Eora26 dataset directory and infer year/price from filenames."""
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise WrongInput("Eora26 parsing expects a directory path.")

    data_files = sorted(
        child for child in root.iterdir() if child.is_file() and _EORA26_DATA_RE.match(child.name)
    )
    if not data_files:
        raise WrongInput("No Eora26 data files were found in the selected directory.")

    match = _EORA26_DATA_RE.match(data_files[0].name)
    year = int(match.group("year"))
    price = match.group("price")

    label_root = Path(index_path) if index_path is not None else root
    for required in ("labels_T.txt", "labels_FD.txt", "labels_VA.txt", "labels_Q.txt"):
        if not (label_root / required).exists():
            raise WrongInput(f"Missing required Eora26 index file: {required}")

    log_time(
        logger,
        f"Parser: detected Eora26 layout version year={year} price={price}.",
        "debug",
    )
    return Eora26Layout(root=root, year=year, price=price, index_root=label_root)


def parse_eora_single_region(
    path: str | Path,
    *,
    table: str | None = None,
    name_convention: str = "full_name",
    aggregate_trade: bool = True,
    country: str | None = None,
    year: int | None = None,
    price: str | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], EoraSingleRegionLayout]:
    """Parse one EORA single-region file into canonical MARIO blocks."""
    layout = resolve_eora_single_region_file(path, country=country, year=year, price=price)
    region_level = _normalize_name_convention(name_convention)

    log_time(logger, f"Parser: reading EORA single-region file {layout.path.name}.", "info")
    data = pd.read_csv(
        layout.path,
        sep="\t",
        index_col=[2, 0, 1, 3],
        header=[2, 0, 1, 3],
        low_memory=False,
    )

    detected_table = _detect_single_region_table(data)
    if table is None:
        table = detected_table
    elif table != detected_table:
        raise WrongFormat(
            f"The parsed EORA single-region file appears to be a {detected_table}, not a {table}."
        )

    native_groups = {"Industries"} if table == IOT else {"Industries", "Commodities"}
    native_row_mask = _select_axis_labels(data, 0, native_groups)
    native_col_mask = _select_axis_labels(data, 1, native_groups)

    Z = data.loc[native_row_mask, native_col_mask].copy()
    Y_fd = data.loc[native_row_mask, _select_axis_labels(data, 1, {"Final Demand"})].copy()
    Y_exp = data.loc[native_row_mask, _select_axis_labels(data, 1, {"ExportsTo"})].copy()
    primary = data.loc[_select_axis_labels(data, 0, {"Primary Inputs"}), native_col_mask].copy()
    imports = data.loc[_select_axis_labels(data, 0, {"ImportsFrom"}), native_col_mask].copy()

    excluded_groups = native_groups | {"Primary Inputs", "ImportsFrom"}
    satellite_mask = ~_select_axis_labels(data, 0, excluded_groups)
    E = data.loc[satellite_mask, native_col_mask].copy()
    EY_fd = data.loc[satellite_mask, _select_axis_labels(data, 1, {"Final Demand"})].copy()
    EY_exp = data.loc[satellite_mask, _select_axis_labels(data, 1, {"ExportsTo"})].copy()

    regions = delete_duplicates(Z.index.get_level_values(region_level).tolist())
    if len(regions) != 1:
        raise WrongFormat("Single-region EORA parsing expects exactly one domestic region.")
    domestic_region = regions[0]

    if table == IOT:
        sector_items = Z.index.get_level_values(3).tolist()
        native_axis = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["s"]], sector_items])
        units = {
            _MASTER_INDEX["s"]: pd.DataFrame("USD", index=sector_items, columns=["unit"]),
        }
        indexes = {
            "r": {"main": regions},
            "s": {"main": sector_items},
        }
    else:
        activity_items = delete_duplicates(
            Z.index[Z.index.get_level_values(0) == "Industries"].get_level_values(3).tolist()
        )
        commodity_items = delete_duplicates(
            Z.index[Z.index.get_level_values(0) == "Commodities"].get_level_values(3).tolist()
        )
        activity_axis = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["a"]], activity_items])
        commodity_axis = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["c"]], commodity_items])
        native_axis = activity_axis.append(commodity_axis)
        units = {
            _MASTER_INDEX["a"]: pd.DataFrame("USD", index=activity_items, columns=["unit"]),
            _MASTER_INDEX["c"]: pd.DataFrame("USD", index=commodity_items, columns=["unit"]),
        }
        indexes = {
            "r": {"main": regions},
            "a": {"main": activity_items},
            "c": {"main": commodity_items},
            "s": {"main": activity_items + commodity_items},
        }

    Z.index = native_axis
    Z.columns = native_axis

    primary.index = pd.Index(primary.index.get_level_values(3).tolist(), name=None)
    primary.columns = native_axis

    if aggregate_trade:
        import_total = imports.sum(axis=0).to_frame().T.astype(float)
        import_total.index = pd.Index(["Imports"], name=None)
        import_total.columns = native_axis
        V = pd.concat([primary, import_total], axis=0)
        factor_labels = primary.index.tolist() + ["Imports"]
    else:
        import_labels = [
            f"Import from {label}"
            for label in imports.index.get_level_values(region_level).tolist()
        ]
        imports.index = pd.Index(import_labels, name=None)
        imports.columns = native_axis
        V = pd.concat([primary, imports], axis=0)
        factor_labels = primary.index.tolist() + import_labels

    V.index = pd.Index(factor_labels, name=None)

    fd_labels = Y_fd.columns.get_level_values(3).tolist()
    Y_fd.columns = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["n"]], fd_labels])
    Y_fd.index = native_axis
    Y_exp.index = native_axis

    if aggregate_trade:
        export_total = Y_exp.sum(axis=1).to_frame().astype(float)
        export_total.columns = pd.MultiIndex.from_tuples(
            [(domestic_region, _MASTER_INDEX["n"], "Exports")]
        )
        Y = pd.concat([Y_fd, export_total], axis=1)
        final_labels = fd_labels + ["Exports"]
    else:
        export_labels = [
            f"Export to {label}"
            for label in Y_exp.columns.get_level_values(region_level).tolist()
        ]
        Y_exp.columns = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["n"]], export_labels])
        Y = pd.concat([Y_fd, Y_exp], axis=1)
        final_labels = fd_labels + export_labels

    Y.index = native_axis

    extension_labels = pd.Index(
        [
            f"{item} ({code})"
            for code, item in zip(E.index.get_level_values(2), E.index.get_level_values(3))
        ],
        name=None,
    )
    extension_units = pd.DataFrame(
        {"unit": [_extract_unit(label) for label in E.index.get_level_values(0)]},
        index=extension_labels,
    )
    E.index = extension_labels
    E.columns = native_axis

    EY_fd.columns = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["n"]], fd_labels])
    EY_fd.index = extension_labels
    EY_exp.index = extension_labels

    if aggregate_trade:
        export_total = EY_exp.sum(axis=1).to_frame().astype(float)
        export_total.columns = pd.MultiIndex.from_tuples(
            [(domestic_region, _MASTER_INDEX["n"], "Exports")]
        )
        EY = pd.concat([EY_fd, export_total], axis=1)
    else:
        export_labels = [
            f"Export to {label}"
            for label in EY_exp.columns.get_level_values(region_level).tolist()
        ]
        EY_exp.columns = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["n"]], export_labels])
        EY_exp.index = extension_labels
        EY = pd.concat([EY_fd, EY_exp], axis=1)

    units.update(
        {
            _MASTER_INDEX["f"]: pd.DataFrame("USD", index=V.index.tolist(), columns=["unit"]),
            _MASTER_INDEX["k"]: extension_units,
        }
    )
    indexes.update(
        {
            "n": {"main": final_labels},
            "f": {"main": V.index.tolist()},
            "k": {"main": extension_labels.tolist()},
        }
    )

    matrices = {"baseline": {"Z": Z, "V": V, "E": E, "Y": Y, "EY": EY}}
    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: EORA single-region parsed as "
            f"{table} with {len(indexes['f']['main'])} factor rows and "
            f"{len(indexes['k']['main'])} extension rows."
        ),
        "info",
    )
    return matrices, indexes, units, layout


def _read_eora26_labels(path: Path) -> pd.DataFrame:
    """Read one Eora26 label file."""
    return pd.read_csv(path, sep="\t", header=None)


def _build_eora26_sector_axis(labels: pd.DataFrame) -> pd.MultiIndex:
    """Build the canonical sector axis from the Eora26 sector label file."""
    return pd.MultiIndex.from_arrays(
        [labels[0].tolist(), [_MASTER_INDEX["s"]] * len(labels), labels[3].tolist()]
    )


def _build_eora26_final_demand_axis(labels: pd.DataFrame) -> pd.MultiIndex:
    """Build the canonical final-demand axis from the Eora26 FD label file."""
    return pd.MultiIndex.from_arrays(
        [labels[0].tolist(), [_MASTER_INDEX["n"]] * len(labels), labels[3].tolist()]
    )


def _build_eora26_extension_index(labels: pd.DataFrame) -> tuple[pd.Index, pd.DataFrame]:
    """Build extension labels and units from the Eora26 Q label file."""
    index = pd.Index(
        [f"{group} - {item}" for group, item in zip(labels[0].tolist(), labels[1].tolist())],
        name=None,
    )
    units = pd.DataFrame({"unit": [_extract_unit(group) for group in labels[0].tolist()]}, index=index)
    return index, units


def parse_eora26(
    path: str | Path,
    *,
    index_path: str | Path | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], Eora26Layout]:
    """Parse an Eora26 directory into canonical MARIO IOT blocks."""
    layout = detect_eora26_layout(path, index_path=index_path)
    log_time(logger, f"Parser: reading Eora26 from {layout.root}.", "info")

    labels_t = _read_eora26_labels(layout.index_root / "labels_T.txt")
    labels_fd = _read_eora26_labels(layout.index_root / "labels_FD.txt")
    labels_va = _read_eora26_labels(layout.index_root / "labels_VA.txt")
    labels_q = _read_eora26_labels(layout.index_root / "labels_Q.txt")

    sector_axis = _build_eora26_sector_axis(labels_t)
    final_demand_axis = _build_eora26_final_demand_axis(labels_fd)
    extension_index, extension_units = _build_eora26_extension_index(labels_q)

    Z = pd.read_csv(layout.root / f"Eora26_{layout.year}_{layout.price}_T.txt", sep="\t", header=None, dtype=float)
    Y = pd.read_csv(layout.root / f"Eora26_{layout.year}_{layout.price}_FD.txt", sep="\t", header=None, dtype=float)
    V = pd.read_csv(layout.root / f"Eora26_{layout.year}_{layout.price}_VA.txt", sep="\t", header=None, dtype=float)
    E = pd.read_csv(layout.root / f"Eora26_{layout.year}_{layout.price}_Q.txt", sep="\t", header=None, dtype=float)
    EY = pd.read_csv(layout.root / f"Eora26_{layout.year}_{layout.price}_QY.txt", sep="\t", header=None, dtype=float)

    Z.index = sector_axis
    Z.columns = sector_axis
    Y.index = sector_axis
    Y.columns = final_demand_axis
    V.index = pd.Index(labels_va[1].tolist(), name=None)
    V.columns = sector_axis
    E.index = extension_index
    E.columns = sector_axis
    EY.index = extension_index
    EY.columns = final_demand_axis

    row_key = ("ROW", _MASTER_INDEX["s"], "TOTAL")
    if row_key in Z.index and row_key in Z.columns:
        row_import = Z.loc[row_key].drop(row_key)
        row_export = Z.loc[:, row_key].drop(row_key)

        Z = Z.drop(index=row_key, columns=row_key)
        row_mask = Y.index.get_level_values(0) != "ROW"
        col_mask = Y.columns.get_level_values(0) != "ROW"
        Y = Y.loc[row_mask, col_mask]
        EY = EY.loc[:, col_mask]
        V = V.loc[:, Z.columns]
        E = E.loc[:, Z.columns]

        regions = delete_duplicates(Z.index.get_level_values(0).tolist())
        export_axis = pd.MultiIndex.from_product(
            [regions, [_MASTER_INDEX["n"]], ["Export to ROW"]]
        )
        Y_columns = Y.columns.append(export_axis)
        new_Y = pd.DataFrame(0.0, index=Z.index, columns=Y_columns)
        new_Y.loc[Y.index, Y.columns] = Y.values

        for idx, value in row_export.items():
            new_Y.loc[idx, (idx[0], _MASTER_INDEX["n"], "Export to ROW")] = float(value)

        new_EY = pd.DataFrame(0.0, index=EY.index, columns=Y_columns)
        new_EY.loc[EY.index, EY.columns] = EY.values

        V.loc["Import from ROW", Z.columns] = row_import.values.astype(float)
        Y = new_Y
        EY = new_EY
    else:
        regions = delete_duplicates(Z.index.get_level_values(0).tolist())

    sector_items = [item for item in delete_duplicates(Z.index.get_level_values(2).tolist()) if item != "TOTAL"]
    factor_units = pd.DataFrame("M EUR", index=V.index.tolist(), columns=["unit"])
    sector_units = pd.DataFrame("M EUR", index=sector_items, columns=["unit"])

    matrices = {"baseline": {"Z": Z, "V": V, "E": E, "Y": Y, "EY": EY}}
    rename_index(matrices["baseline"])

    indexes = {
        "r": {"main": regions},
        "n": {"main": delete_duplicates(Y.columns.get_level_values(2).tolist())},
        "k": {"main": E.index.tolist()},
        "f": {"main": V.index.tolist()},
        "s": {"main": sector_items},
    }
    units = {
        _MASTER_INDEX["s"]: sector_units,
        _MASTER_INDEX["f"]: factor_units,
        _MASTER_INDEX["k"]: extension_units,
    }

    log_time(
        logger,
        (
            "Parser: Eora26 parsed with "
            f"{len(indexes['r']['main'])} regions, {len(indexes['s']['main'])} sectors, "
            f"{len(indexes['f']['main'])} factor rows and {len(indexes['k']['main'])} extension rows."
        ),
        "info",
    )
    return matrices, indexes, units, layout
