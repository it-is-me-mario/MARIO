"""Direct monetary EXIOBASE IOT parser shared across supported versions."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import EXIO_FACTOR_ROWS
from mario.utils import delete_duplicates, rename_index, sort_frames

logger = logging.getLogger(__name__)

_EXTENSION_DIRECTORY_ORDER = (
    "material",
    "water",
    "employment",
    "labour",
    "air_emissions",
    "energy",
    "land",
    "nutrients",
)
_IGNORED_EXIOBASE_DIRECTORIES = {"impacts"}


@dataclass(frozen=True)
class ExiobaseIOTLayout:
    """Filesystem layout and metadata detected for one monetary EXIOBASE IOT package."""

    root: Path
    version: str | None
    year: int | None
    system: str | None
    dataset_name: str | None
    description: str | None
    factor_directory: str
    extension_directories: tuple[str, ...]

    @property
    def source(self) -> str:
        """Return a human-readable source string for MARIO metadata."""
        details = []
        if self.version:
            details.append(f"version {self.version}")
        if self.system:
            details.append(self.system)
        suffix = f" ({', '.join(details)})" if details else ""
        return f"EXIOBASE monetary IOT{suffix} @ https://www.exiobase.eu/"


def _read_json(path: Path) -> dict[str, object]:
    """Read a JSON document when it exists and return an empty mapping otherwise."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _extract_year(*values: object) -> int | None:
    """Extract the first plausible year from the provided text fragments."""
    for value in values:
        if not value:
            continue
        match = re.search(r"(?<!\d)(19|20)\d{2}(?!\d)", str(value))
        if match:
            return int(match.group(0))
    return None


def _normalize_version(value: object) -> str | None:
    """Normalize version strings such as ``v3.81`` or ``3.10.1``."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    match = re.search(r"(\d+\.\d+\.\d+)", text)
    if match:
        return match.group(1)

    match = re.search(r"v?(\d+)\.(\d{2})$", text)
    if match:
        major = match.group(1)
        middle = match.group(2)[0]
        minor = match.group(2)[1]
        return f"{major}.{middle}.{minor}"

    return text.removeprefix("v")


def _ordered_extension_directories(root: Path, factor_directory: str) -> tuple[str, ...]:
    """Return extension directories in a stable, compatibility-friendly order."""
    discovered = [
        item.name
        for item in root.iterdir()
        if item.is_dir()
        and item.name != factor_directory
        and item.name not in _IGNORED_EXIOBASE_DIRECTORIES
        and (item / "F.txt").exists()
        and (item / "F_Y.txt").exists()
        and (item / "unit.txt").exists()
    ]

    ordered: list[str] = []
    seen: set[str] = set()
    for name in _EXTENSION_DIRECTORY_ORDER:
        if name in discovered:
            ordered.append(name)
            seen.add(name)

    for name in sorted(discovered):
        if name not in seen:
            ordered.append(name)

    return tuple(ordered)


def detect_exiobase_iot_layout(path: str | Path) -> ExiobaseIOTLayout:
    """Inspect one EXIOBASE IOT folder and detect the parse layout."""
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise WrongInput("EXIOBASE monetary IOT parsing expects a directory path.")

    metadata = _read_json(root / "metadata.json")

    folder_version = _normalize_version(re.search(r"(\d+\.\d+\.\d+)", root.name).group(1)) if re.search(r"(\d+\.\d+\.\d+)", root.name) else None
    detected_version = folder_version or _normalize_version(metadata.get("version"))
    factor_directory = None
    if (root / "factor_inputs" / "F.txt").exists():
        factor_directory = "factor_inputs"
    elif (root / "satellite" / "F.txt").exists():
        factor_directory = "satellite"
    else:
        raise WrongInput(
            "Unable to detect EXIOBASE monetary IOT layout. "
            "Expected either factor_inputs/F.txt or satellite/F.txt."
        )

    extension_directories = (
        ()
        if factor_directory == "satellite"
        else _ordered_extension_directories(root, factor_directory)
    )

    for file_name in ("Z.txt", "Y.txt", "unit.txt"):
        if not (root / file_name).exists():
            raise WrongInput(f"Missing required EXIOBASE IOT file: {file_name}")

    layout = ExiobaseIOTLayout(
        root=root,
        version=detected_version,
        year=_extract_year(metadata.get("name"), metadata.get("description"), root.name),
        system=str(metadata.get("system")) if metadata.get("system") is not None else None,
        dataset_name=str(metadata.get("name")) if metadata.get("name") is not None else None,
        description=str(metadata.get("description")) if metadata.get("description") is not None else None,
        factor_directory=factor_directory,
        extension_directories=extension_directories,
    )
    log_time(
        logger,
        (
            "Parser: detected EXIOBASE IOT layout "
            f"version={layout.version or 'unknown'} "
            f"year={layout.year or 'unknown'} "
            f"system={layout.system or 'unknown'} "
            f"factor_dir={layout.factor_directory} "
            f"extensions={list(layout.extension_directories)}"
        ),
        "debug",
    )
    return layout


def _read_matrix(path: Path, *, index_col, header):
    """Read one EXIOBASE TSV file into pandas."""
    log_time(logger, f"Parser: reading {path.name} from {path.parent}.", "debug")
    return pd.read_csv(path, sep="\t", index_col=index_col, header=header)


def _read_numeric_matrix(path: Path, *, index_col, header) -> pd.DataFrame:
    """Read one numeric EXIOBASE TSV file and coerce sparse missing cells to zero."""
    frame = _read_matrix(path, index_col=index_col, header=header)
    nan_count = int(frame.isna().sum().sum())
    if nan_count:
        log_time(
            logger,
            f"Parser: {path.name} contains {nan_count} missing numeric cells; filling with zero.",
            "debug",
        )
    return frame.fillna(0)


def _read_sector_units(path: Path) -> pd.DataFrame:
    """Read top-level sector units and collapse them to one row per sector."""
    raw = _read_matrix(path, index_col=[0], header=[0])
    if not {"sector", "unit"} <= set(raw.columns):
        raise WrongInput(f"Invalid EXIOBASE unit file format: {path}")

    units = raw.reset_index()[["sector", "unit"]].drop_duplicates(subset="sector")
    units = units.set_index("sector")
    units.index.name = None
    return units


def _ensure_unique_index(frame: pd.DataFrame, *, label: str, source: Path) -> None:
    """Raise when a parsed block introduces duplicated stressor names."""
    duplicates = frame.index[frame.index.duplicated()].unique().tolist()
    if duplicates:
        raise WrongInput(
            f"Duplicated rows found while parsing {label} from {source}: {duplicates[:5]}"
        )


def _build_sector_axis(axis: pd.MultiIndex) -> pd.MultiIndex:
    """Promote EXIOBASE sector axes to canonical MARIO three-level indexes."""
    return pd.MultiIndex.from_arrays(
        [
            axis.get_level_values(0),
            [_MASTER_INDEX["s"]] * len(axis),
            axis.get_level_values(1),
        ]
    )


def _build_final_demand_axis(axis: pd.MultiIndex) -> pd.MultiIndex:
    """Promote EXIOBASE final-demand axes to canonical MARIO three-level indexes."""
    return pd.MultiIndex.from_arrays(
        [
            axis.get_level_values(0),
            [_MASTER_INDEX["n"]] * len(axis),
            axis.get_level_values(1),
        ]
    )


def _align_extension_frame(frame: pd.DataFrame, columns: pd.Index | pd.MultiIndex) -> pd.DataFrame:
    """Align one extension block to the canonical sector/final-demand columns."""
    missing_columns = columns.difference(frame.columns)
    if len(missing_columns):
        log_time(
            logger,
            f"Parser: aligning extension frame by adding {len(missing_columns)} missing columns as zero.",
            "debug",
        )
    return frame.reindex(columns=columns, fill_value=0)


def read_exiobase_iot_extensions(
    path: str | Path,
    *,
    version: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, ExiobaseIOTLayout]:
    """Read only extension blocks from a monetary EXIOBASE IOT package.

    The returned matrices keep the raw EXIOBASE two-level column layout
    ``(region, sector/category)`` so callers can remap them to the target
    MARIO table shape they need.
    """
    layout = detect_exiobase_iot_layout(path)
    expected_version = _normalize_version(version)
    if expected_version and layout.version and expected_version != layout.version:
        raise WrongInput(
            f"Requested EXIOBASE version {expected_version!r} does not match detected version {layout.version!r}."
        )

    log_time(
        logger,
        f"Parser: reading EXIOBASE IOT extensions from {layout.root}.",
        "info",
    )

    if layout.factor_directory == "satellite":
        log_time(logger, "Parser: using bundled legacy satellite layout.", "info")
        bundled_F = _read_numeric_matrix(
            layout.root / "satellite" / "F.txt",
            index_col=[0],
            header=[0, 1],
        )
        bundled_FY = _read_numeric_matrix(
            layout.root / "satellite" / "F_Y.txt",
            index_col=[0],
            header=[0, 1],
        )
        bundled_units = _read_matrix(
            layout.root / "satellite" / "unit.txt",
            index_col=[0],
            header=[0],
        )

        E = bundled_F.drop(EXIO_FACTOR_ROWS)
        EY = bundled_FY.drop(EXIO_FACTOR_ROWS)
        extension_units = bundled_units.drop(EXIO_FACTOR_ROWS)
    else:
        factor_root = layout.root / layout.factor_directory
        log_time(
            logger,
            (
                "Parser: using split extension layout with "
                f"{len(layout.extension_directories)} extension directories."
            ),
            "info",
        )
        extension_frames: list[pd.DataFrame] = []
        extension_y_frames: list[pd.DataFrame] = []
        extension_units_frames: list[pd.DataFrame] = []
        for directory in layout.extension_directories:
            ext_root = layout.root / directory
            log_time(logger, f"Parser: loading extension directory {directory}.", "debug")
            extension_frames.append(
                _read_numeric_matrix(ext_root / "F.txt", index_col=[0], header=[0, 1])
            )
            extension_y_frames.append(
                _read_numeric_matrix(ext_root / "F_Y.txt", index_col=[0], header=[0, 1])
            )
            extension_units_frames.append(
                _read_matrix(ext_root / "unit.txt", index_col=[0], header=[0])
            )

        if extension_frames:
            E = pd.concat(extension_frames, axis=0)
            EY = pd.concat(extension_y_frames, axis=0)
            extension_units = pd.concat(extension_units_frames, axis=0)
        else:
            placeholder_columns = pd.MultiIndex.from_arrays([["-"], ["-"]])
            E = pd.DataFrame(np.zeros((1, 1)), index=["-"], columns=placeholder_columns)
            EY = pd.DataFrame(np.zeros((1, 1)), index=["-"], columns=placeholder_columns)
            extension_units = pd.DataFrame({"unit": ["None"]}, index=["-"])
            log_time(
                logger,
                "Parser: no extension directories found; using empty E and EY placeholders.",
                "warning",
            )

    _ensure_unique_index(E, label="extensions", source=layout.root)
    _ensure_unique_index(extension_units, label="extension units", source=layout.root)
    log_time(
        logger,
        (
            "Parser: EXIOBASE IOT extensions loaded with "
            f"{E.shape[0]} extension rows and {EY.shape[0]} final-demand extension rows."
        ),
        "debug",
    )
    return E, EY, extension_units, layout


def parse_exiobase_iot_monetary(
    path: str | Path,
    *,
    version: str | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], ExiobaseIOTLayout]:
    """Parse a monetary EXIOBASE IOT folder into canonical MARIO parser payloads."""
    layout = detect_exiobase_iot_layout(path)
    expected_version = _normalize_version(version)
    if expected_version and layout.version and expected_version != layout.version:
        raise WrongInput(
            f"Requested EXIOBASE version {expected_version!r} does not match detected version {layout.version!r}."
        )

    log_time(logger, f"Parser: reading EXIOBASE IOT from {layout.root}.", "info")

    Z = _read_numeric_matrix(layout.root / "Z.txt", index_col=[0, 1], header=[0, 1])
    Y = _read_numeric_matrix(layout.root / "Y.txt", index_col=[0, 1], header=[0, 1])
    sector_units = _read_sector_units(layout.root / "unit.txt")
    log_time(
        logger,
        f"Parser: top-level blocks loaded Z={Z.shape} Y={Y.shape} sector_units={sector_units.shape}.",
        "debug",
    )

    if layout.factor_directory == "satellite":
        bundled_F = _read_numeric_matrix(layout.root / "satellite" / "F.txt", index_col=[0], header=[0, 1])
        bundled_units = _read_matrix(layout.root / "satellite" / "unit.txt", index_col=[0], header=[0])

        V = bundled_F.loc[EXIO_FACTOR_ROWS, :]
        factor_units = bundled_units.loc[EXIO_FACTOR_ROWS, :]
        E, EY, extension_units, _ = read_exiobase_iot_extensions(path, version=version)
    else:
        factor_root = layout.root / layout.factor_directory
        V = _read_numeric_matrix(factor_root / "F.txt", index_col=[0], header=[0, 1])
        factor_units = _read_matrix(factor_root / "unit.txt", index_col=[0], header=[0])
        E, EY, extension_units, _ = read_exiobase_iot_extensions(path, version=version)
        E = _align_extension_frame(E, Z.columns)
        EY = _align_extension_frame(EY, Y.columns)

    _ensure_unique_index(V, label="value added", source=layout.root)
    _ensure_unique_index(E, label="extensions", source=layout.root)
    _ensure_unique_index(extension_units, label="extension units", source=layout.root)
    log_time(
        logger,
        f"Parser: value added rows={V.shape[0]} extension rows={E.shape[0]} final-demand extension rows={EY.shape[0]}.",
        "debug",
    )

    sector_axis = _build_sector_axis(Z.index)
    final_demand_axis = _build_final_demand_axis(Y.columns)

    Z.index = sector_axis
    Z.columns = sector_axis
    Y.index = sector_axis
    Y.columns = final_demand_axis
    V.columns = sector_axis
    E.columns = sector_axis
    EY.columns = final_demand_axis

    matrices = {"baseline": {"Z": Z, "V": V, "E": E, "Y": Y, "EY": EY}}
    units = {
        _MASTER_INDEX["s"]: sector_units,
        _MASTER_INDEX["f"]: factor_units,
        _MASTER_INDEX["k"]: extension_units,
    }
    indeces = {
        "r": {"main": delete_duplicates(list(Z.index.get_level_values(0)))},
        "n": {"main": delete_duplicates(list(Y.columns.get_level_values(2)))},
        "k": {"main": list(E.index)},
        "f": {"main": list(V.index)},
        "s": {"main": delete_duplicates(list(Z.index.get_level_values(2)))},
    }

    rename_index(matrices["baseline"])
    sort_frames(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: EXIOBASE IOT parsed with "
            f"{len(indeces['s']['main'])} sectors, "
            f"{len(indeces['f']['main'])} value-added rows and "
            f"{len(indeces['k']['main'])} extension rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout
