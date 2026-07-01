"""Direct file-based parser for EMERGING Zenodo MATLAB bundles."""

from __future__ import annotations

from dataclasses import dataclass
import functools
import logging
from pathlib import Path
import re

import h5py
import numpy as np
import pandas as pd
import yaml
from scipy.io import loadmat
from scipy.sparse import coo_matrix

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    EMERGING_CO2_LABELS,
    EMERGING_CONCEPT_DOI,
    EMERGING_E_CONCEPT_DOI,
    EMERGING_E_DATASET_CITATION,
    EMERGING_E_SOURCE,
    EMERGING_E_V3_ZENODO_URL,
    EMERGING_FACTOR_LABEL,
    EMERGING_MONETARY_UNIT,
    EMERGING_PAPER_CITATION,
    EMERGING_SATELLITE_PLACEHOLDER,
    EMERGING_SATELLITE_UNIT,
    EMERGING_SOURCE,
    EMERGING_V1_ZENODO_URL,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_EMERGING_MAIN_PATTERNS = (
    (
        re.compile(r"global_mrio_(?P<year>\d{4})\.mat$", flags=re.IGNORECASE),
        "1.0",
        EMERGING_V1_ZENODO_URL,
    ),
    (
        re.compile(r"EMERGING_V\d+_(?P<year>\d{4})_m\.mat$", flags=re.IGNORECASE),
        "2.x",
        None,
    ),
    (
        re.compile(r"EMERGING_V\d+_(?P<year>\d{4})\.mat$", flags=re.IGNORECASE),
        "2.x",
        None,
    ),
)
_EMERGING_CO2_RE = re.compile(r"EMERGING_CO2_(?P<year>\d{4})(?:_IEA)?\.mat$", flags=re.IGNORECASE)
_EMERGING_LABELS_RE = re.compile(r"EMERGING.*Sector&Country list\.xlsx$", flags=re.IGNORECASE)
_EMERGING_E_MAIN_PATTERNS = (
    (
        re.compile(r"EMERGING_E_(?P<year>\d{4})\.mat$", flags=re.IGNORECASE),
        "E",
        EMERGING_E_V3_ZENODO_URL,
    ),
)
_EMERGING_E_CO2_RE = re.compile(r"EMERGING_E_CO2_(?P<year>\d{4})\.mat$", flags=re.IGNORECASE)
_EMERGING_E_FIGURE_DATA_RE = re.compile(r"Figure data\.xlsx$", flags=re.IGNORECASE)
_EMERGING_STANDARD_VARIANTS = {"standard", "default", "base", "core"}
_EMERGING_E_SECTORS_FILE = "emerging_e_sectors.yaml"
_EMERGING_STANDARD_SECTOR_COUNT = 133
_EMERGING_STANDARD_ELECTRICITY_INDEX = 96
_EMERGING_E_FUEL_TO_SECTOR_INDEX = {
    0: 96,   # Coal -> production of electricity by coal
    1: 97,   # Natural gas -> production of electricity by gas
    2: 101,  # Oil products -> production of electricity by petroleum and other oil derivatives
    3: 101,  # Crude, NGL, Ref Feeds. -> production of electricity by petroleum and other oil derivatives
    4: 107,  # Other -> production of electricity nec
    5: 101,  # Oil shale & oil sands -> production of electricity by petroleum and other oil derivatives
    6: 102,  # Peat & Peat products -> production of electricity by biomass and waste
}


@dataclass(frozen=True)
class EMERGINGLayout:
    """Filesystem layout and metadata for one EMERGING bundle."""

    root: Path
    data_path: Path
    year: int
    bundle_version: str
    record_url: str | None = None
    co2_path: Path | None = None
    labels_path: Path | None = None
    figure_data_path: Path | None = None
    variant: str = "standard"

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        if self.variant == "E":
            return f"EMERGING-E {self.year}"
        return f"EMERGING {self.year}"

    @property
    def price(self) -> str:
        """Return the price metadata stored in MARIO."""
        return "Current prices"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        if self.variant == "E":
            source_parts = [EMERGING_E_SOURCE]
            if self.record_url is not None:
                source_parts.append(f"({self.record_url}; concept DOI {EMERGING_E_CONCEPT_DOI})")
            else:
                source_parts.append(f"(concept DOI {EMERGING_E_CONCEPT_DOI})")
            source_parts.append(EMERGING_E_DATASET_CITATION)
            return "; ".join(source_parts)

        source_parts = [EMERGING_SOURCE]
        if self.record_url is not None:
            source_parts.append(f"({self.record_url}; concept DOI {EMERGING_CONCEPT_DOI})")
        else:
            source_parts.append(f"(concept DOI {EMERGING_CONCEPT_DOI})")
        source_parts.append(EMERGING_PAPER_CITATION)
        return "; ".join(source_parts)


def _normalize_emerging_variant(variant: str | None) -> str:
    """Normalize one public EMERGING parser variant selector."""
    if variant is None:
        return "standard"

    normalized = str(variant).strip()
    if normalized.lower() in _EMERGING_STANDARD_VARIANTS:
        return "standard"
    if normalized.upper() == "E":
        return "E"

    raise WrongInput("Supported EMERGING parser variants are 'standard' and 'E'.")


def _normalize_region_request(regions) -> list[str] | None:
    """Normalize a region selector into a list or ``None`` for all regions."""
    if regions is None or regions == "all":
        return None
    if isinstance(regions, str):
        return [regions]
    return list(regions)


def detect_emerging_layout(
    path: str | Path,
    *,
    year: int | None = None,
    load_co2: bool = True,
    co2_path: str | Path | None = None,
    labels_path: str | Path | None = None,
    variant: str = "standard",
) -> EMERGINGLayout:
    """Resolve the EMERGING MATLAB bundle selected for one parse request."""
    variant = _normalize_emerging_variant(variant)
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    main_patterns = _EMERGING_E_MAIN_PATTERNS if variant == "E" else _EMERGING_MAIN_PATTERNS
    co2_pattern = _EMERGING_E_CO2_RE if variant == "E" else _EMERGING_CO2_RE

    def _match_layout(candidate: Path) -> tuple[int, str, str | None]:
        for pattern, bundle_version, record_url in main_patterns:
            match = pattern.match(candidate.name)
            if match is not None:
                return int(match.group("year")), bundle_version, record_url
        if variant == "E":
            raise WrongInput(
                "EMERGING-E parsing expects a main MATLAB file named like "
                "'EMERGING_E_<year>.mat'."
            )
        raise WrongInput(
            "EMERGING parsing expects a main MATLAB file named like "
            "'global_mrio_<year>.mat', 'EMERGING_V2_<year>_m.mat' or "
            "'EMERGING_V2_<year>.mat'."
        )

    def _build(candidate: Path) -> EMERGINGLayout:
        parsed_year, bundle_version, record_url = _match_layout(candidate)
        if year is not None and parsed_year != int(year):
            raise WrongInput(
                f"The selected EMERGING file contains year {parsed_year}, not {year}."
            )
        detected_co2 = None
        if co2_path is not None:
            detected_co2 = Path(co2_path)
            if not detected_co2.exists():
                raise FileNotFoundError(detected_co2)
        elif load_co2:
            for other in candidate.parent.iterdir():
                if (
                    other.is_file()
                    and co2_pattern.match(other.name)
                    and int(co2_pattern.match(other.name).group("year")) == parsed_year
                ):
                    detected_co2 = other
                    break
        detected_labels = None
        if labels_path is not None:
            detected_labels = Path(labels_path)
            if not detected_labels.exists():
                raise FileNotFoundError(detected_labels)
        figure_data_path = None
        for other in candidate.parent.iterdir():
            if detected_labels is None and variant != "E" and other.is_file() and _EMERGING_LABELS_RE.match(other.name):
                detected_labels = other
            if variant == "E" and other.is_file() and _EMERGING_E_FIGURE_DATA_RE.match(other.name):
                figure_data_path = other
        return EMERGINGLayout(
            root=candidate.parent,
            data_path=candidate,
            year=parsed_year,
            bundle_version=bundle_version,
            record_url=record_url,
            co2_path=detected_co2,
            labels_path=detected_labels,
            figure_data_path=figure_data_path,
            variant=variant,
        )

    if source.is_file():
        return _build(source)

    candidates = sorted(
        child
        for child in source.rglob("*.mat")
        if child.is_file() and any(pattern.match(child.name) for pattern, _, _ in main_patterns)
    )
    if not candidates:
        if variant == "E":
            raise WrongInput(
                "No EMERGING-E main MATLAB file matching 'EMERGING_E_<year>.mat' "
                "was found in the selected directory."
            )
        raise WrongInput(
            "No EMERGING main MATLAB file matching 'global_mrio_<year>.mat', "
            "'EMERGING_V2_<year>_m.mat' or 'EMERGING_V2_<year>.mat' was found "
            "in the selected directory."
        )
    if year is not None:
        candidates = [child for child in candidates if _match_layout(child)[0] == int(year)]
        if not candidates:
            raise WrongInput(f"No EMERGING MATLAB bundle was found for year {year}.")
    if len(candidates) > 1:
        years = sorted(_match_layout(child)[0] for child in candidates)
        raise WrongInput(
            "More than one EMERGING MATLAB bundle matches the selected directory. "
            f"Please specify year or point to one file. Available years: {years}"
        )
    return _build(candidates[0])


def _read_hdf5_string(file_handle: h5py.File, ref) -> str:
    """Decode one MATLAB char array stored through an HDF5 object reference."""
    target = file_handle[ref]
    values = target[()]
    return "".join(chr(int(item)) for item in values.reshape(-1) if int(item) != 0)


def _read_hdf5_string_list(group: h5py.Group | h5py.File, name: str) -> list[str]:
    """Read one MATLAB cellstr list stored as object references."""
    refs = group[name][()].reshape(-1)
    file_handle = group.file
    return [_read_hdf5_string(file_handle, ref) for ref in refs]


def _resolve_emerging_container(handle: h5py.File) -> h5py.Group | h5py.File:
    """Return the HDF5 object that actually stores the EMERGING datasets."""
    required = {"z", "f", "va", "X", "country_list", "sector_list", "final_list"}
    if required.issubset(handle.keys()):
        return handle

    group_candidates = [
        item for key, item in handle.items() if key != "#refs#" and isinstance(item, h5py.Group)
    ]
    if len(group_candidates) == 1 and required.issubset(group_candidates[0].keys()):
        return group_candidates[0]

    raise WrongFormat("The EMERGING MATLAB bundle contains an unexpected top-level structure.")


def _resolve_emerging_e_container(handle: h5py.File) -> h5py.Group | h5py.File:
    """Return the HDF5 object that actually stores the EMERGING-E datasets."""
    required = {"MRIO_Z_E", "MRIO_F_E", "MRIO_VA_E", "MRIO_X_E"}
    if required.issubset(handle.keys()):
        return handle

    group_candidates = [
        item for key, item in handle.items() if key != "#refs#" and isinstance(item, h5py.Group)
    ]
    if len(group_candidates) == 1 and required.issubset(group_candidates[0].keys()):
        return group_candidates[0]

    raise WrongFormat("The EMERGING-E MATLAB bundle contains an unexpected top-level structure.")


def _read_emerging_labels(layout: EMERGINGLayout, sector_count: int) -> tuple[list[str] | None, list[str] | None]:
    """Read optional sector/country labels from the companion Excel workbook."""
    if layout.labels_path is None:
        return None, None
    try:
        sector_frame = pd.read_excel(layout.labels_path, sheet_name="Sector")
        country_frame = pd.read_excel(layout.labels_path, sheet_name="Country")
    except Exception as exc:
        log_time(
            logger,
            f"Parser: could not read EMERGING labels workbook {layout.labels_path.name}: {exc}",
            "debug",
        )
        return None, None

    sector_labels = None
    if {"Sector"}.issubset(sector_frame.columns):
        values = sector_frame["Sector"].dropna().astype(str).tolist()
        if len(values) == sector_count:
            sector_labels = values

    country_codes = None
    if {"ISO3"}.issubset(country_frame.columns):
        values = country_frame["ISO3"].dropna().astype(str).tolist()
        if values:
            country_codes = values

    return sector_labels, country_codes


def _coerce_sector_labels(raw_labels: list[str], workbook_labels: list[str] | None) -> list[str]:
    """Choose the most readable sector labels available in the EMERGING bundle."""
    if workbook_labels is not None and len(workbook_labels) == len(raw_labels):
        return workbook_labels
    return [value.split(" ", 1)[1] if " " in value else value for value in raw_labels]


def _select_regions(
    all_regions: list[str],
    *,
    regions=None,
) -> tuple[list[str], list[int]]:
    """Resolve the region subset requested by the caller."""
    requested = _normalize_region_request(regions)
    if requested is None:
        return list(all_regions), list(range(len(all_regions)))

    missing = [region for region in requested if region not in all_regions]
    if missing:
        raise WrongInput(
            f"Unknown EMERGING region codes requested: {missing}. "
            f"Available examples: {all_regions[:10]}"
        )
    positions = [all_regions.index(region) for region in requested]
    return requested, positions


def _block_positions(region_positions: list[int], *, block_size: int) -> np.ndarray:
    """Expand one list of region positions into flat sector/final-demand positions."""
    pieces = [
        np.arange(region * block_size, (region + 1) * block_size, dtype=np.int64)
        for region in region_positions
    ]
    if not pieces:
        return np.array([], dtype=np.int64)
    return np.concatenate(pieces)


def _dense_or_sparse_frame_from_hdf5(
    dataset: h5py.Dataset,
    *,
    row_positions: np.ndarray,
    column_positions: np.ndarray,
    index,
    columns,
    block_size: int = 64,
) -> pd.DataFrame:
    """Read one large HDF5 matrix into a pandas sparse dataframe block by block."""
    row_all = np.array_equal(row_positions, np.arange(dataset.shape[0], dtype=np.int64))
    data_chunks: list[np.ndarray] = []
    row_chunks: list[np.ndarray] = []
    col_chunks: list[np.ndarray] = []

    for local_start in range(0, len(column_positions), block_size):
        local_stop = min(local_start + block_size, len(column_positions))
        column_block = column_positions[local_start:local_stop]
        block = dataset[:, column_block]
        if not row_all:
            block = block[row_positions, :]
        nz_rows, nz_cols = np.nonzero(block)
        if nz_rows.size == 0:
            continue
        data_chunks.append(block[nz_rows, nz_cols])
        row_chunks.append(nz_rows.astype(np.int64))
        col_chunks.append((local_start + nz_cols).astype(np.int64))

    if data_chunks:
        data = np.concatenate(data_chunks)
        rows = np.concatenate(row_chunks)
        cols = np.concatenate(col_chunks)
    else:
        data = np.array([], dtype=float)
        rows = np.array([], dtype=np.int64)
        cols = np.array([], dtype=np.int64)

    matrix = coo_matrix((data, (rows, cols)), shape=(len(index), len(columns))).tocsr()
    return pd.DataFrame.sparse.from_spmatrix(matrix, index=index, columns=columns).fillna(0.0)


def _dense_or_sparse_frame_from_array(array: np.ndarray, *, index, columns) -> pd.DataFrame:
    """Convert one dense array to a sparse-backed dataframe when appropriate."""
    nz_rows, nz_cols = np.nonzero(array)
    matrix = coo_matrix((array[nz_rows, nz_cols], (nz_rows, nz_cols)), shape=array.shape).tocsr()
    return pd.DataFrame.sparse.from_spmatrix(matrix, index=index, columns=columns).fillna(0.0)


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate a zero-filled dataframe with the requested index and columns."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def _generic_labels(prefix: str, count: int) -> list[str]:
    """Return deterministic fallback labels when the bundle ships no metadata."""
    width = max(3, len(str(count)))
    return [f"{prefix} {index:0{width}d}" for index in range(1, count + 1)]


def _infer_emerging_e_dimensions(group: h5py.Group | h5py.File) -> tuple[int, int, int]:
    """Infer region, sector and final-demand counts from one EMERGING-E bundle."""
    z_rows, z_cols = group["MRIO_Z_E"].shape
    f_rows, f_cols = group["MRIO_F_E"].shape
    if z_rows != z_cols:
        raise WrongFormat("EMERGING-E requires a square MRIO_Z_E matrix.")
    if f_cols != z_cols:
        raise WrongFormat("EMERGING-E requires MRIO_F_E columns to match MRIO_Z_E dimensions.")

    final_demand_count = 3
    if f_rows % final_demand_count != 0:
        raise WrongFormat(
            "EMERGING-E expects three final-demand categories per region in MRIO_F_E."
        )

    region_count = f_rows // final_demand_count
    if z_rows % region_count != 0:
        raise WrongFormat(
            "EMERGING-E dimensions do not factor into consistent region and sector blocks."
        )

    return region_count, z_rows // region_count, final_demand_count


def _read_emerging_e_region_codes(layout: EMERGINGLayout, region_count: int) -> list[str]:
    """Read EMERGING-E region ISO3 codes from the companion figure workbook when available."""
    if layout.figure_data_path is not None:
        try:
            frame = pd.read_excel(layout.figure_data_path, sheet_name="Figure S4")
        except Exception as exc:
            log_time(
                logger,
                f"Parser: could not read EMERGING-E figure workbook {layout.figure_data_path.name}: {exc}",
                "debug",
            )
        else:
            if "ISO3" in frame.columns:
                values = frame["ISO3"].dropna().astype(str).tolist()
                if len(values) == region_count:
                    return values

    return _generic_labels("R", region_count)


def _read_emerging_e_sector_labels_from_workbook(
    workbook_path: Path,
    *,
    sector_count: int,
) -> list[str] | None:
    """Read EMERGING-E sector labels from one workbook when its structure is compatible."""
    candidate_sheets = (
        ("Sector", "Sector"),
        ("Sheet1", "Sector"),
        ("Sheet1", "Label"),
        ("Sheet1", "Name"),
        ("Sheet2", "Sector"),
        ("Sheet2", "Label"),
        ("Sheet2", "Name"),
    )
    for sheet_name, column_name in candidate_sheets:
        try:
            frame = pd.read_excel(workbook_path, sheet_name=sheet_name)
        except Exception:
            continue
        if column_name not in frame.columns:
            continue
        values = frame[column_name].dropna().astype(str).tolist()
        if len(values) == sector_count:
            return values

    try:
        all_sheets = pd.read_excel(workbook_path, sheet_name=None)
    except Exception as exc:
        log_time(
            logger,
            f"Parser: could not read EMERGING-E sector labels workbook {workbook_path.name}: {exc}",
            "debug",
        )
        return None

    for frame in all_sheets.values():
        for column_name in ("Sector", "Label", "Name"):
            if column_name not in frame.columns:
                continue
            values = frame[column_name].dropna().astype(str).tolist()
            if len(values) == sector_count:
                return values

    return None


@functools.lru_cache(maxsize=1)
def _load_emerging_e_builtin_sectors() -> tuple[str, ...]:
    """Load the EMERGING-E sector classification shipped with MARIO."""
    path = Path(__file__).with_name(_EMERGING_E_SECTORS_FILE)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    sectors = data.get("sectors") if isinstance(data, dict) else None
    if not sectors:
        return ()
    return tuple(str(value) for value in sectors)


def _builtin_emerging_e_sector_labels(sector_count: int) -> list[str] | None:
    """Return the built-in EMERGING-E sector labels when they match the bundle size."""
    sectors = _load_emerging_e_builtin_sectors()
    if len(sectors) == sector_count:
        return list(sectors)
    return None


def _read_emerging_e_sector_labels(layout: EMERGINGLayout, sector_count: int) -> list[str] | None:
    """Read EMERGING-E sector labels from one explicit or auto-detected workbook."""
    if layout.labels_path is not None:
        values = _read_emerging_e_sector_labels_from_workbook(
            layout.labels_path,
            sector_count=sector_count,
        )
        if values is None:
            log_time(
                logger,
                (
                    "Parser: EMERGING-E sector labels workbook "
                    f"{layout.labels_path.name} does not expose {sector_count} sector labels; "
                    "using generic sector identifiers."
                ),
                "debug",
            )
        return values

    workbook_candidates = sorted(
        path
        for path in layout.root.glob("*.xlsx")
        if path.is_file()
        and (layout.figure_data_path is None or path != layout.figure_data_path)
    )
    for workbook_path in workbook_candidates:
        values = _read_emerging_e_sector_labels_from_workbook(
            workbook_path,
            sector_count=sector_count,
        )
        if values is not None:
            log_time(
                logger,
                f"Parser: auto-detected EMERGING-E sector labels workbook {workbook_path.name}.",
                "debug",
            )
            return values

    if workbook_candidates:
        searched = ", ".join(path.name for path in workbook_candidates)
        log_time(
            logger,
            (
                "Parser: checked EMERGING-E workbook candidates for sector labels but found no "
                f"compatible file among: {searched}."
            ),
            "debug",
        )
    return None


def _read_emerging_e_vector(dataset: h5py.Dataset, *, expected_size: int) -> np.ndarray:
    """Read one EMERGING-E vector stored either as row or column matrix."""
    values = np.asarray(dataset[()], dtype=float).reshape(-1)
    if values.size != expected_size:
        raise WrongFormat(
            f"EMERGING-E dataset '{dataset.name}' exposes {values.size} values, expected {expected_size}."
        )
    return values


def _load_emerging_companion_co2(path: Path, *, expected_rows: int) -> np.ndarray:
    """Load one companion CO2 matrix with the expected row count from a MAT file."""
    data = loadmat(path)
    candidates = [
        value
        for key, value in data.items()
        if not key.startswith("__") and isinstance(value, np.ndarray) and value.ndim == 2
    ]
    for candidate in candidates:
        if candidate.shape[0] == expected_rows:
            return np.asarray(candidate, dtype=float)

    raise WrongFormat(
        f"No 2-D CO2 matrix with {expected_rows} rows was found in companion file '{path.name}'."
    )


def _load_emerging_companion_co2_candidates(path: Path) -> list[np.ndarray]:
    """Load every 2-D numeric candidate matrix exposed by one companion MAT file."""
    data = loadmat(path)
    candidates = [
        np.asarray(value, dtype=float)
        for key, value in data.items()
        if not key.startswith("__") and isinstance(value, np.ndarray) and value.ndim == 2
    ]
    if not candidates:
        raise WrongFormat(f"The companion CO2 file '{path.name}' exposes no 2-D numeric matrix.")
    return candidates


def _project_standard_emerging_power_co2_to_emerging_e(
    co2: np.ndarray,
    *,
    region_positions: list[int],
    sector_count: int,
) -> np.ndarray:
    """Project one standard 133-sector EMERGING companion onto the 146-sector EMERGING-E layout."""
    if co2.shape[1] != len(EMERGING_CO2_LABELS):
        raise WrongFormat(
            "Standard EMERGING CO2 projection to EMERGING-E requires one 7-column fuel matrix."
        )
    if sector_count < 146:
        raise WrongFormat(
            "Standard EMERGING CO2 projection to EMERGING-E requires the full 146-sector layout."
        )

    projected = np.zeros((len(EMERGING_CO2_LABELS), len(region_positions) * sector_count), dtype=float)
    for selected_region_position, region in enumerate(region_positions):
        source_offset = region * _EMERGING_STANDARD_SECTOR_COUNT
        target_offset = selected_region_position * sector_count

        # Standard sectors 1..96 map directly to EMERGING-E sectors 1..96.
        projected[:, target_offset : target_offset + _EMERGING_STANDARD_ELECTRICITY_INDEX] = co2[
            source_offset : source_offset + _EMERGING_STANDARD_ELECTRICITY_INDEX,
            :,
        ].T

        # Split the standard aggregated electricity sector across the 14 EMERGING-E
        # electricity sub-sectors using the fixed fuel-to-technology mapping.
        source_row = source_offset + _EMERGING_STANDARD_ELECTRICITY_INDEX
        electricity_fuels = co2[source_row, :]
        for fuel_index, target_sector_index in _EMERGING_E_FUEL_TO_SECTOR_INDEX.items():
            projected[fuel_index, target_offset + target_sector_index] = electricity_fuels[fuel_index]

        # Standard sectors 98..133 shift after the 14 EMERGING-E electricity sectors.
        projected[:, target_offset + 110 : target_offset + 146] = co2[
            source_offset + 97 : source_offset + _EMERGING_STANDARD_SECTOR_COUNT,
            :,
        ].T

    return projected


def parse_emerging_iot(
    path: str | Path,
    *,
    year: int | None = None,
    regions=None,
    load_co2: bool = True,
    co2_path: str | Path | None = None,
    labels_path: str | Path | None = None,
    variant: str = "standard",
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    EMERGINGLayout,
]:
    """Parse one EMERGING Zenodo MATLAB bundle into canonical MARIO IOT blocks."""
    layout = detect_emerging_layout(
        path,
        year=year,
        load_co2=load_co2,
        co2_path=co2_path,
        labels_path=labels_path,
        variant=variant,
    )
    if layout.variant == "E":
        log_time(logger, f"Parser: reading EMERGING-E bundle {layout.data_path.name}.", "info")

        with h5py.File(layout.data_path, "r") as handle:
            group = _resolve_emerging_e_container(handle)
            required = {"MRIO_Z_E", "MRIO_F_E", "MRIO_VA_E", "MRIO_X_E"}
            missing = required.difference(group.keys())
            if missing:
                raise WrongFormat(f"The EMERGING-E bundle is missing required datasets: {sorted(missing)}.")

            region_count, sector_count, final_count = _infer_emerging_e_dimensions(group)
            region_codes = _read_emerging_e_region_codes(layout, region_count)
            sector_labels = _read_emerging_e_sector_labels(layout, sector_count)
            if sector_labels is None:
                sector_labels = _builtin_emerging_e_sector_labels(sector_count)
                if sector_labels is not None:
                    log_time(
                        logger,
                        "Parser: applied the MARIO built-in EMERGING-E "
                        f"{sector_count}-sector classification.",
                        "info",
                    )
            if sector_labels is None:
                sector_labels = _generic_labels("Sector", sector_count)
            final_labels = _generic_labels("Final demand", final_count)
            selected_regions, region_positions = _select_regions(region_codes, regions=regions)

            if layout.figure_data_path is None:
                log_time(
                    logger,
                    "Parser: EMERGING-E figure workbook not found; using generic region identifiers.",
                    "debug",
                )
            if layout.labels_path is None:
                log_time(
                    logger,
                    "Parser: EMERGING-E sector labels workbook not provided; "
                    "falling back to the built-in classification when available.",
                    "debug",
                )

            sector_positions = _block_positions(region_positions, block_size=sector_count)
            final_positions = _block_positions(region_positions, block_size=final_count)

            sector_axis = pd.MultiIndex.from_arrays(
                [
                    np.repeat(selected_regions, len(sector_labels)),
                    [_MASTER_INDEX["s"]] * len(sector_positions),
                    sector_labels * len(selected_regions),
                ]
            )
            final_axis = pd.MultiIndex.from_arrays(
                [
                    np.repeat(selected_regions, len(final_labels)),
                    [_MASTER_INDEX["n"]] * len(final_positions),
                    final_labels * len(selected_regions),
                ]
            )
            factor_axis = pd.Index([EMERGING_FACTOR_LABEL], name=None)

            z_dataset = group["MRIO_Z_E"]
            y_dataset = group["MRIO_F_E"]
            va_dataset = group["MRIO_VA_E"]

            full_sector_positions = np.arange(z_dataset.shape[0], dtype=np.int64)
            full_final_positions = np.arange(y_dataset.shape[0], dtype=np.int64)
            row_positions = (
                sector_positions
                if not np.array_equal(sector_positions, full_sector_positions)
                else full_sector_positions
            )
            fd_positions = (
                final_positions
                if not np.array_equal(final_positions, full_final_positions)
                else full_final_positions
            )

            Z = _dense_or_sparse_frame_from_hdf5(
                z_dataset,
                row_positions=row_positions,
                column_positions=sector_positions,
                index=sector_axis,
                columns=sector_axis,
            )

            Y_raw = _dense_or_sparse_frame_from_hdf5(
                y_dataset,
                row_positions=fd_positions,
                column_positions=sector_positions,
                index=final_axis,
                columns=sector_axis,
                block_size=128,
            )
            Y = Y_raw.T
            Y.index = sector_axis
            Y.columns = final_axis

            total_sectors = region_count * sector_count
            va_values = _read_emerging_e_vector(va_dataset, expected_size=total_sectors)[sector_positions]
            V = pd.DataFrame(va_values.reshape(1, -1), index=factor_axis, columns=sector_axis)

        satellite_axis = pd.Index([EMERGING_SATELLITE_PLACEHOLDER], name=None)
        if layout.co2_path is not None:
            log_time(logger, f"Parser: reading EMERGING-E CO2 file {layout.co2_path.name}.", "info")
            co2_candidates = _load_emerging_companion_co2_candidates(layout.co2_path)
            co2_selected = None
            full_emerging_e_rows = region_count * sector_count
            standard_emerging_rows = region_count * _EMERGING_STANDARD_SECTOR_COUNT
            for candidate in co2_candidates:
                if candidate.shape[0] == full_emerging_e_rows:
                    co2_selected = np.asarray(candidate[sector_positions, :], dtype=float).T
                    break
                if candidate.shape[0] == standard_emerging_rows:
                    co2_selected = _project_standard_emerging_power_co2_to_emerging_e(
                        np.asarray(candidate, dtype=float),
                        region_positions=region_positions,
                        sector_count=sector_count,
                    )
                    break

            if co2_selected is None:
                raise WrongFormat(
                    (
                        f"No EMERGING-E-compatible CO2 matrix was found in '{layout.co2_path.name}'. "
                        f"Expected either {full_emerging_e_rows} rows (full EMERGING-E companion) "
                        f"or {standard_emerging_rows} rows (standard EMERGING companion)."
                    )
                )

            if co2_selected.shape[0] == len(EMERGING_CO2_LABELS):
                satellite_labels = list(EMERGING_CO2_LABELS)
            else:
                satellite_labels = _generic_labels("Satellite", co2_selected.shape[0])
            satellite_axis = pd.Index(satellite_labels, name=None)
            E = pd.DataFrame(co2_selected, index=satellite_axis, columns=sector_axis)
            EY = _zero_frame(satellite_axis, final_axis)
            satellite_units = [EMERGING_SATELLITE_UNIT] * len(satellite_axis)
        else:
            E = _zero_frame(satellite_axis, sector_axis)
            EY = _zero_frame(satellite_axis, final_axis)
            satellite_units = ["None"]

        matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
        units = {
            _MASTER_INDEX["s"]: pd.DataFrame(
                {"unit": [EMERGING_MONETARY_UNIT] * len(sector_labels)},
                index=pd.Index(sector_labels, name=None),
            ),
            _MASTER_INDEX["f"]: pd.DataFrame(
                {"unit": [EMERGING_MONETARY_UNIT]},
                index=factor_axis,
            ),
            _MASTER_INDEX["k"]: pd.DataFrame(
                {"unit": satellite_units},
                index=satellite_axis,
            ),
        }
        indeces = {
            "r": {"main": selected_regions},
            "s": {"main": sector_labels},
            "f": {"main": list(factor_axis)},
            "k": {"main": list(satellite_axis)},
            "n": {"main": final_labels},
        }

        rename_index(matrices["baseline"])
        log_time(
            logger,
            (
                "Parser: EMERGING-E parsed with "
                f"{len(selected_regions)} regions, "
                f"{len(sector_labels)} sectors, "
                f"{len(final_axis)} final-demand columns and "
                f"{len(satellite_axis)} satellite rows."
            ),
            "info",
        )
        return matrices, indeces, units, layout

    log_time(logger, f"Parser: reading EMERGING bundle {layout.data_path.name}.", "info")

    with h5py.File(layout.data_path, "r") as handle:
        group = _resolve_emerging_container(handle)
        required = {"z", "f", "va", "X", "country_list", "sector_list", "final_list"}
        missing = required.difference(group.keys())
        if missing:
            raise WrongFormat(f"The EMERGING bundle is missing required datasets: {sorted(missing)}.")

        region_codes = _read_hdf5_string_list(group, "country_list")
        sector_labels_raw = _read_hdf5_string_list(group, "sector_list")
        final_labels = _read_hdf5_string_list(group, "final_list")

        workbook_sector_labels, workbook_country_codes = _read_emerging_labels(layout, len(sector_labels_raw))
        if workbook_country_codes is not None and len(workbook_country_codes) == len(region_codes):
            if workbook_country_codes != region_codes:
                log_time(
                    logger,
                    "Parser: EMERGING country workbook order differs from MATLAB bundle; keeping MATLAB order.",
                    "debug",
                )

        sector_labels = _coerce_sector_labels(sector_labels_raw, workbook_sector_labels)
        selected_regions, region_positions = _select_regions(region_codes, regions=regions)

        sector_positions = _block_positions(region_positions, block_size=len(sector_labels))
        final_positions = _block_positions(region_positions, block_size=len(final_labels))

        sector_axis = pd.MultiIndex.from_arrays(
            [
                np.repeat(selected_regions, len(sector_labels)),
                [_MASTER_INDEX["s"]] * len(sector_positions),
                sector_labels * len(selected_regions),
            ]
        )
        final_axis = pd.MultiIndex.from_arrays(
            [
                np.repeat(selected_regions, len(final_labels)),
                [_MASTER_INDEX["n"]] * len(final_positions),
                final_labels * len(selected_regions),
            ]
        )
        factor_axis = pd.Index([EMERGING_FACTOR_LABEL], name=None)

        z_dataset = group["z"]
        f_dataset = group["f"]
        va_dataset = group["va"]

        full_sector_positions = np.arange(z_dataset.shape[0], dtype=np.int64)
        full_final_positions = np.arange(f_dataset.shape[0], dtype=np.int64)
        row_positions = sector_positions if not np.array_equal(sector_positions, full_sector_positions) else full_sector_positions
        fd_positions = final_positions if not np.array_equal(final_positions, full_final_positions) else full_final_positions

        Z = _dense_or_sparse_frame_from_hdf5(
            z_dataset,
            row_positions=row_positions,
            column_positions=sector_positions,
            index=sector_axis,
            columns=sector_axis,
        )

        Y_raw = _dense_or_sparse_frame_from_hdf5(
            f_dataset,
            row_positions=fd_positions,
            column_positions=sector_positions,
            index=final_axis,
            columns=sector_axis,
            block_size=128,
        )
        Y = Y_raw.T
        Y.index = sector_axis
        Y.columns = final_axis

        va_values = np.asarray(va_dataset[0, sector_positions], dtype=float).reshape(1, -1)
        V = pd.DataFrame(va_values, index=factor_axis, columns=sector_axis)

    satellite_axis = pd.Index([EMERGING_SATELLITE_PLACEHOLDER], name=None)
    if layout.co2_path is not None:
        log_time(logger, f"Parser: reading EMERGING CO2 file {layout.co2_path.name}.", "info")
        co2 = loadmat(layout.co2_path)["CO2"]
        co2_selected = np.asarray(co2[sector_positions, :], dtype=float).T
        satellite_axis = pd.Index(list(EMERGING_CO2_LABELS), name=None)
        E = pd.DataFrame(co2_selected, index=satellite_axis, columns=sector_axis)
        EY = _zero_frame(satellite_axis, final_axis)
        satellite_units = [EMERGING_SATELLITE_UNIT] * len(satellite_axis)
    else:
        E = _zero_frame(satellite_axis, sector_axis)
        EY = _zero_frame(satellite_axis, final_axis)
        satellite_units = ["None"]

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [EMERGING_MONETARY_UNIT] * len(sector_labels)},
            index=pd.Index(sector_labels, name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [EMERGING_MONETARY_UNIT]},
            index=factor_axis,
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {"unit": satellite_units},
            index=satellite_axis,
        ),
    }
    indeces = {
        "r": {"main": selected_regions},
        "s": {"main": sector_labels},
        "f": {"main": list(factor_axis)},
        "k": {"main": list(satellite_axis)},
        "n": {"main": final_labels},
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: EMERGING parsed with "
            f"{len(selected_regions)} regions, "
            f"{len(sector_labels)} sectors, "
            f"{len(final_axis)} final-demand columns and "
            f"{len(satellite_axis)} satellite rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout
