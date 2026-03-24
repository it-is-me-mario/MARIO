"""Direct file-based parser for EMERGING Zenodo MATLAB bundles."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re

import h5py
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.sparse import coo_matrix

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    EMERGING_CO2_LABELS,
    EMERGING_FACTOR_LABEL,
    EMERGING_MONETARY_UNIT,
    EMERGING_PAPER_CITATION,
    EMERGING_SATELLITE_PLACEHOLDER,
    EMERGING_SATELLITE_UNIT,
    EMERGING_SOURCE,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_EMERGING_MAIN_RE = re.compile(r"EMERGING_V\d+_(?P<year>\d{4})\.mat$", flags=re.IGNORECASE)
_EMERGING_CO2_RE = re.compile(r"EMERGING_CO2_(?P<year>\d{4})_IEA\.mat$", flags=re.IGNORECASE)
_EMERGING_LABELS_RE = re.compile(r"EMERGING.*Sector&Country list\.xlsx$", flags=re.IGNORECASE)


@dataclass(frozen=True)
class EMERGINGLayout:
    """Filesystem layout and metadata for one EMERGING bundle."""

    root: Path
    data_path: Path
    year: int
    co2_path: Path | None = None
    labels_path: Path | None = None

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        return f"EMERGING {self.year}"

    @property
    def price(self) -> str:
        """Return the price metadata stored in MARIO."""
        return "Current prices"

    @property
    def source(self) -> str:
        """Return the canonical source string stored in MARIO metadata."""
        return f"{EMERGING_SOURCE}; {EMERGING_PAPER_CITATION}"


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
) -> EMERGINGLayout:
    """Resolve the EMERGING MATLAB bundle selected for one parse request."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    def _match_year(candidate: Path) -> int:
        match = _EMERGING_MAIN_RE.match(candidate.name)
        if match is None:
            raise WrongInput(
                "EMERGING parsing expects the Zenodo v1 main MATLAB file named "
                "like EMERGING_V2_<year>.mat."
            )
        return int(match.group("year"))

    def _build(candidate: Path) -> EMERGINGLayout:
        parsed_year = _match_year(candidate)
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
            sibling = candidate.parent / f"EMERGING_CO2_{parsed_year}_IEA.mat"
            if sibling.exists():
                detected_co2 = sibling
        labels_path = None
        for other in candidate.parent.iterdir():
            if other.is_file() and _EMERGING_LABELS_RE.match(other.name):
                labels_path = other
                break
        return EMERGINGLayout(
            root=candidate.parent,
            data_path=candidate,
            year=parsed_year,
            co2_path=detected_co2,
            labels_path=labels_path,
        )

    if source.is_file():
        return _build(source)

    candidates = sorted(
        child
        for child in source.rglob("*.mat")
        if child.is_file() and _EMERGING_MAIN_RE.match(child.name)
    )
    if not candidates:
        raise WrongInput(
            "No EMERGING Zenodo v1 main MATLAB file matching EMERGING_V2_<year>.mat "
            "was found in the selected directory."
        )
    if year is not None:
        candidates = [child for child in candidates if _match_year(child) == int(year)]
        if not candidates:
            raise WrongInput(f"No EMERGING MATLAB bundle was found for year {year}.")
    if len(candidates) > 1:
        years = sorted(_match_year(child) for child in candidates)
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


def _read_hdf5_string_list(group: h5py.Group, name: str) -> list[str]:
    """Read one MATLAB cellstr list stored as object references."""
    refs = group[name][0]
    file_handle = group.file
    return [_read_hdf5_string(file_handle, ref) for ref in refs]


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
    return pd.DataFrame.sparse.from_spmatrix(matrix, index=index, columns=columns)


def _dense_or_sparse_frame_from_array(array: np.ndarray, *, index, columns) -> pd.DataFrame:
    """Convert one dense array to a sparse-backed dataframe when appropriate."""
    nz_rows, nz_cols = np.nonzero(array)
    matrix = coo_matrix((array[nz_rows, nz_cols], (nz_rows, nz_cols)), shape=array.shape).tocsr()
    return pd.DataFrame.sparse.from_spmatrix(matrix, index=index, columns=columns)


def _zero_frame(index, columns) -> pd.DataFrame:
    """Allocate a zero-filled dataframe with the requested index and columns."""
    return pd.DataFrame(np.zeros((len(index), len(columns))), index=index, columns=columns)


def parse_emerging_iot(
    path: str | Path,
    *,
    year: int | None = None,
    regions=None,
    load_co2: bool = True,
    co2_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    EMERGINGLayout,
]:
    """Parse one EMERGING Zenodo MATLAB bundle into canonical MARIO IOT blocks."""
    layout = detect_emerging_layout(path, year=year, load_co2=load_co2, co2_path=co2_path)
    log_time(logger, f"Parser: reading EMERGING bundle {layout.data_path.name}.", "info")

    with h5py.File(layout.data_path, "r") as handle:
        top_level = [key for key in handle.keys() if key != "#refs#"]
        if len(top_level) != 1:
            raise WrongFormat("The EMERGING MATLAB bundle contains an unexpected top-level structure.")
        group = handle[top_level[0]]

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
