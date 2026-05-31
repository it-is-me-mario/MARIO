"""Direct monetary EXIOBASE SUT parser for the 3.8.2 MRSUT text layout."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
import tempfile
import zipfile

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.exiobase_iot import detect_exiobase_iot_layout, read_exiobase_iot_extensions
from mario.utils import delete_duplicates, rename_index

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExiobaseSUTLayout:
    """Filesystem layout and metadata detected for one monetary EXIOBASE SUT package."""

    root: Path
    version: str | None
    year: int | None
    system: str | None
    currency: str | None
    price: str | None
    dataset_name: str | None

    @property
    def source(self) -> str:
        """Return a human-readable source string for MARIO metadata."""
        details = []
        if self.version:
            details.append(f"version {self.version}")
        if self.system:
            details.append(self.system)
        suffix = f" ({', '.join(details)})" if details else ""
        return f"EXIOBASE monetary SUT{suffix} @ https://www.exiobase.eu/"


def _read_json(path: Path) -> dict[str, object]:
    """Read a JSON document when present and return an empty mapping otherwise."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _normalize_version(value: object) -> str | None:
    """Normalize version strings such as ``3.8.2``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d+\.\d+\.\d+)", text)
    if match:
        return match.group(1)
    return text


def _looks_like_exiobase_sut_root(root: Path) -> bool:
    """Return whether one directory looks like an EXIOBASE SUT bundle root."""
    if not root.is_dir():
        return False

    required_files = ("supply.csv", "use.csv", "final_demand.csv", "value_added.csv")
    return all((root / file_name).exists() for file_name in required_files)


def _resolve_extracted_sut_root(root: Path) -> Path:
    """Resolve the bundle root after extracting one EXIOBASE SUT archive."""
    if _looks_like_exiobase_sut_root(root):
        return root

    candidates = [candidate for candidate in root.rglob("*") if _looks_like_exiobase_sut_root(candidate)]
    if not candidates:
        return root

    candidates.sort(key=lambda candidate: (len(candidate.relative_to(root).parts), str(candidate)))
    return candidates[0]


@contextmanager
def _open_exiobase_sut_root(path: str | Path):
    """Yield an EXIOBASE SUT directory, extracting zip archives on demand."""
    root = Path(path)
    if root.suffix.lower() != ".zip":
        yield root
        return

    if not root.exists():
        raise FileNotFoundError(root)

    with tempfile.TemporaryDirectory(prefix="mario_exiobase_sut_") as extracted_dir:
        extraction_root = Path(extracted_dir)
        log_time(logger, f"Parser: extracting EXIOBASE SUT archive {root}.", "debug")
        with zipfile.ZipFile(root) as archive:
            archive.extractall(extraction_root)
        yield _resolve_extracted_sut_root(extraction_root)


def _detect_exiobase_sut_layout(root: Path) -> ExiobaseSUTLayout:
    """Inspect one EXIOBASE monetary SUT folder and detect its parse layout."""
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise WrongInput("EXIOBASE monetary SUT parsing expects a directory path.")

    required_files = ("supply.csv", "use.csv", "final_demand.csv", "value_added.csv")
    for file_name in required_files:
        if not (root / file_name).exists():
            raise WrongInput(f"Missing required EXIOBASE SUT file: {file_name}")

    metadata = _read_json(root / "meta.json")
    version = _normalize_version(re.search(r"(\d+\.\d+\.\d+)", root.name).group(1)) if re.search(r"(\d+\.\d+\.\d+)", root.name) else None
    system_match = re.search(r"(i[xp]i)\s*$", root.name, flags=re.IGNORECASE)
    system = system_match.group(1).lower() if system_match else None
    year = metadata.get("year")
    if year is not None:
        year = int(year)
    dataset_name = root.name.replace(" - ", " ")

    layout = ExiobaseSUTLayout(
        root=root,
        version=version,
        year=year,
        system=system,
        currency=str(metadata.get("currency")) if metadata.get("currency") is not None else None,
        price=str(metadata.get("price")) if metadata.get("price") is not None else None,
        dataset_name=dataset_name,
    )
    log_time(
        logger,
        (
            "Parser: detected EXIOBASE SUT layout "
            f"version={layout.version or 'unknown'} "
            f"year={layout.year or 'unknown'} "
            f"system={layout.system or 'unknown'} "
            f"currency={layout.currency or 'unknown'} "
            f"price={layout.price or 'unknown'}"
        ),
        "debug",
    )
    return layout


def detect_exiobase_sut_layout(path: str | Path) -> ExiobaseSUTLayout:
    """Inspect one EXIOBASE monetary SUT folder and detect its parse layout."""
    return _detect_exiobase_sut_layout(Path(path))


def _read_numeric_matrix(path: Path, *, index_col, header) -> pd.DataFrame:
    """Read one numeric EXIOBASE TSV file and fill sparse missing cells with zero."""
    log_time(logger, f"Parser: reading {path.name} from {path.parent}.", "debug")
    frame = pd.read_csv(path, sep="\t", index_col=index_col, header=header)
    nan_count = int(frame.isna().sum().sum())
    if nan_count:
        log_time(
            logger,
            f"Parser: {path.name} contains {nan_count} missing numeric cells; filling with zero.",
            "debug",
        )
        frame = frame.fillna(0)
    return frame


def _commodity_axis(axis: pd.MultiIndex) -> pd.MultiIndex:
    """Promote raw commodity axes to canonical MARIO three-level commodity indexes."""
    return pd.MultiIndex.from_arrays(
        [
            axis.get_level_values(0),
            [_MASTER_INDEX["c"]] * len(axis),
            axis.get_level_values(1),
        ]
    )


def _activity_axis(axis: pd.MultiIndex) -> pd.MultiIndex:
    """Promote raw activity axes to canonical MARIO three-level activity indexes."""
    return pd.MultiIndex.from_arrays(
        [
            axis.get_level_values(0),
            [_MASTER_INDEX["a"]] * len(axis),
            axis.get_level_values(1),
        ]
    )


def _final_demand_axis(axis: pd.MultiIndex) -> pd.MultiIndex:
    """Promote raw final-demand axes to canonical MARIO three-level final-demand indexes."""
    return pd.MultiIndex.from_arrays(
        [
            axis.get_level_values(0),
            [_MASTER_INDEX["n"]] * len(axis),
            axis.get_level_values(1),
        ]
    )


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate a zero-filled dataframe with the given index and columns."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def _currency_unit(label: str | None) -> str:
    """Normalize the currency label used for SUT monetary units."""
    if label is None:
        return "EUR"
    text = str(label).strip()
    if text.lower() == "euro":
        return "EUR"
    return text


def _validate_axis_coverage(
    parsed_axis: pd.MultiIndex,
    target_axis: pd.MultiIndex,
    *,
    label: str,
) -> None:
    """Require one parsed EXIOBASE axis to cover the corresponding SUT target axis."""
    missing = target_axis.difference(parsed_axis)
    extra = parsed_axis.difference(target_axis)
    if len(missing) or len(extra):
        details = []
        if len(missing):
            details.append(f"missing {label}: {missing.tolist()[:5]}")
        if len(extra):
            details.append(f"unexpected {label}: {extra.tolist()[:5]}")
        raise WrongInput(
            "The IOT passed via add_extensions does not match the SUT structure; "
            + "; ".join(details)
        )


def _load_extensions_from_iot(
    path: str | Path,
    *,
    activity_axis: pd.MultiIndex,
    commodity_axis: pd.MultiIndex,
    final_demand_axis: pd.MultiIndex,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Index]:
    """Read matching satellite extensions from the corresponding EXIOBASE IOT."""
    extension_E, extension_EY, extension_units, _ = read_exiobase_iot_extensions(path)

    iot_activity_axis = _activity_axis(extension_E.columns)
    iot_final_demand_axis = _final_demand_axis(extension_EY.columns)

    _validate_axis_coverage(iot_activity_axis, activity_axis, label="activities")
    _validate_axis_coverage(iot_final_demand_axis, final_demand_axis, label="final demand categories")

    Ea = extension_E.copy()
    Ea.columns = iot_activity_axis
    Ea = Ea.reindex(columns=activity_axis)

    Ec = _zero_frame(pd.Index(Ea.index.tolist(), name=None), commodity_axis)

    EY = extension_EY.copy()
    EY.columns = iot_final_demand_axis
    EY = EY.reindex(columns=final_demand_axis)

    return Ea, Ec, extension_units, pd.Index(Ea.index.tolist(), name=None), EY


def parse_exiobase_sut_monetary(
    path: str | Path,
    *,
    add_extensions: str | Path | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], ExiobaseSUTLayout]:
    """Parse an EXIOBASE monetary SUT folder into split-native MARIO blocks.

    When ``add_extensions`` points to the corresponding monetary EXIOBASE IOT,
    the parser reads only the IOT satellite blocks and maps them onto the SUT
    activity/final-demand axes.
    """
    if add_extensions is not None:
        detect_exiobase_iot_layout(add_extensions)
    with _open_exiobase_sut_root(path) as root:
        layout = _detect_exiobase_sut_layout(root)
        log_time(logger, f"Parser: reading EXIOBASE SUT from {layout.root}.", "info")

        supply = _read_numeric_matrix(layout.root / "supply.csv", index_col=[0, 1], header=[0, 1])
        use = _read_numeric_matrix(layout.root / "use.csv", index_col=[0, 1], header=[0, 1])
        final_demand = _read_numeric_matrix(layout.root / "final_demand.csv", index_col=[0, 1], header=[0, 1])
        value_added = _read_numeric_matrix(layout.root / "value_added.csv", index_col=[0], header=[0, 1])

        commodity_axis = _commodity_axis(use.index)
        activity_axis = _activity_axis(supply.columns)
        final_demand_axis = _final_demand_axis(final_demand.columns)
        factor_axis = pd.Index(value_added.index.tolist(), name=None)
        satellite_axis = pd.Index(["-"], name=None)

        U = use.copy()
        U.index = commodity_axis
        U.columns = activity_axis

        S = supply.copy().T
        S.index = activity_axis
        S.columns = commodity_axis

        Yc = final_demand.copy()
        Yc.index = commodity_axis
        Yc.columns = final_demand_axis

        Ya = _zero_frame(activity_axis, final_demand_axis)

        Va = value_added.copy()
        Va.columns = activity_axis

        Vc = _zero_frame(factor_axis, commodity_axis)
        if add_extensions is None:
            Ea = _zero_frame(satellite_axis, activity_axis)
            Ec = _zero_frame(satellite_axis, commodity_axis)
            EY = _zero_frame(satellite_axis, final_demand_axis)
            extension_units = pd.DataFrame({"unit": ["None"]}, index=satellite_axis)
            log_time(
                logger,
                "Parser: no matching IOT provided; using empty satellite extensions.",
                "info",
            )
        else:
            log_time(
                logger,
                f"Parser: importing satellite extensions from matching IOT at {add_extensions}.",
                "info",
            )
            Ea, Ec, extension_units, satellite_axis, EY = _load_extensions_from_iot(
                add_extensions,
                activity_axis=activity_axis,
                commodity_axis=commodity_axis,
                final_demand_axis=final_demand_axis,
            )

        matrices = {
            "baseline": {
                "U": U,
                "S": S,
                "Ya": Ya,
                "Yc": Yc,
                "Va": Va,
                "Vc": Vc,
                "Ea": Ea,
                "Ec": Ec,
                "EY": EY,
            }
        }

        unit_label = _currency_unit(layout.currency)
        units = {
            _MASTER_INDEX["a"]: pd.DataFrame({"unit": [unit_label] * len(activity_axis.unique(2))}, index=delete_duplicates(list(activity_axis.get_level_values(2)))),
            _MASTER_INDEX["c"]: pd.DataFrame({"unit": [unit_label] * len(commodity_axis.unique(2))}, index=delete_duplicates(list(commodity_axis.get_level_values(2)))),
            _MASTER_INDEX["f"]: pd.DataFrame({"unit": [unit_label] * len(factor_axis)}, index=factor_axis),
            _MASTER_INDEX["k"]: extension_units,
        }

        indeces = {
            "r": {"main": delete_duplicates(list(commodity_axis.get_level_values(0)))},
            "n": {"main": delete_duplicates(list(final_demand_axis.get_level_values(2)))},
            "k": {"main": list(satellite_axis)},
            "f": {"main": list(factor_axis)},
            "a": {"main": delete_duplicates(list(activity_axis.get_level_values(2)))},
            "c": {"main": delete_duplicates(list(commodity_axis.get_level_values(2)))},
            "s": {
                "main": delete_duplicates(list(activity_axis.get_level_values(2)))
                + delete_duplicates(list(commodity_axis.get_level_values(2)))
            },
        }

        rename_index(matrices["baseline"])
        log_time(
            logger,
            (
                "Parser: EXIOBASE SUT parsed with "
                f"{len(indeces['a']['main'])} activities, "
                f"{len(indeces['c']['main'])} commodities, "
                f"{len(indeces['f']['main'])} value-added rows."
            ),
            "info",
        )
        return matrices, indeces, units, layout
