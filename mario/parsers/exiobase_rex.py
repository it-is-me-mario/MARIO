"""Parser for the REX3 global monetary MRIO MATLAB bundles."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re

import h5py
import numpy as np
import pandas as pd
from scipy.io import loadmat

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    REX3_GHG_UNIT,
    REX3_MONETARY_UNIT,
    REX3_SOURCE,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

REX3_GHG_LABELS = (
    "GHG emissions from coal",
    "GHG emissions from oil",
    "GHG emissions from gas",
    "GHG emissions from biogenic sources",
    "GHG emissions from calcination",
    "Land use change climate impacts (Blue model)",
)

_YEAR_RE = re.compile(r"REX3_(?P<year>\d{4})", flags=re.IGNORECASE)
_YEAR_FILES = ("T_REX3.mat", "Y_REX3.mat", "Q_REX3.mat", "Q_Y_REX3.mat")
_LABEL_FILES = (
    "Labels_Countries_REX3.mat",
    "Labels_Sectors_REX3.mat",
    "Labels_T_REX3.mat",
    "Labels_Q_REX3.mat",
)
_GHG_FILES = (
    "d_CC_REX3_timeline.mat",
    "Q_LULUCF_REX3_timeline.mat",
    "Q_Y_LULUCF_REX3_timeline.mat",
    "Labels/Labels_years.mat",
    "Labels/Labels_Countrysector_combinations.mat",
)


@dataclass(frozen=True)
class REX3Layout:
    """Resolved locations and metadata for one REX3 yearly bundle."""

    root: Path
    year_dir: Path
    labels_dir: Path
    ghg_dir: Path
    year: int

    @property
    def dataset_name(self) -> str:
        return f"EXIOBASE REX3 {self.year}"

    @property
    def source(self) -> str:
        return REX3_SOURCE

    @property
    def price(self) -> str:
        return "Current basic prices"

    @property
    def notes(self) -> tuple[str, ...]:
        return (
            "REX3 base environmental accounts were imported as published flows.",
            "Detailed coal, oil, gas, biogenic, and calcination GHG flows were reconstructed as d_CC times full REX3 output before creating the MARIO database.",
            "Published LULUCF flows were imported directly instead of reconstructing them from d_CC, preserving positive flows assigned to zero-output sectors.",
        )


def _contains_files(path: Path, names: tuple[str, ...]) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in names)


def _find_bundle_dirs(search_root: Path, names: tuple[str, ...]) -> list[Path]:
    candidates = {candidate.parent for candidate in search_root.rglob(names[0])}
    return sorted(path for path in candidates if _contains_files(path, names))


def _infer_year(path: Path) -> int | None:
    for candidate in (path, *path.parents):
        match = _YEAR_RE.search(candidate.name)
        if match is not None:
            return int(match.group("year"))
    return None


def detect_rex3_layout(
    path: str | Path,
    *,
    year: int | None = None,
    labels_path: str | Path | None = None,
    ghg_path: str | Path | None = None,
) -> REX3Layout:
    """Resolve one local REX3 year plus its mandatory label/GHG companions."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.is_file():
        raise WrongInput("Extract the REX3 ZIP archives before parsing, or use download=True.")

    if year is not None and (int(year) != year or not 1995 <= int(year) <= 2022):
        raise WrongInput(f"REX3 covers 1995 through 2022, not {year}.")

    search_root = source if not _contains_files(source, _YEAR_FILES) else source.parent
    year_dirs = (
        [source]
        if _contains_files(source, _YEAR_FILES)
        else _find_bundle_dirs(search_root, _YEAR_FILES)
    )
    if year is not None:
        year_dirs = [
            candidate for candidate in year_dirs if _infer_year(candidate) in (None, int(year))
        ]
    if not year_dirs:
        suffix = f" for year {year}" if year is not None else ""
        raise WrongInput(
            f"No complete REX3 yearly bundle was found{suffix} under {source}."
        )
    if len(year_dirs) > 1:
        available = sorted(str(_infer_year(candidate) or "unknown") for candidate in year_dirs)
        raise WrongInput(
            "More than one REX3 yearly bundle was found. "
            f"Specify year explicitly; available years: {available}."
        )
    year_dir = year_dirs[0]
    detected_year = _infer_year(year_dir)
    if detected_year is None:
        if year is None:
            raise WrongInput(
                "Could not infer the REX3 year from its directory; pass year explicitly."
            )
        detected_year = int(year)
    if detected_year < 1995 or detected_year > 2022:
        raise WrongInput(f"REX3 covers 1995 through 2022, not {detected_year}.")

    def _resolve_companion(
        explicit: str | Path | None,
        names: tuple[str, ...],
        label: str,
    ) -> Path:
        if explicit is not None:
            candidate = Path(explicit)
            if _contains_files(candidate, names):
                return candidate
            candidates = _find_bundle_dirs(candidate, names) if candidate.is_dir() else []
            if len(candidates) == 1:
                return candidates[0]
            raise WrongInput(
                f"The selected REX3 {label} directory must contain exactly one complete bundle: {candidate}."
            )
        candidates = _find_bundle_dirs(search_root, names)
        # A direct year-folder path may sit inside the user's version wrapper,
        # with the environmental release in a sibling wrapper. Do not scan
        # arbitrary parent directories or the whole external drive.
        if not candidates and search_root.name == "Version REX3 database":
            sibling = search_root.parent / "Version GHG extension (+LULUCF)"
            if sibling.is_dir():
                candidates = _find_bundle_dirs(sibling, names)
        if len(candidates) != 1:
            raise WrongInput(
                f"Expected exactly one REX3 {label} directory under {search_root}, found {len(candidates)}. "
                f"Pass {label}_path explicitly."
            )
        return candidates[0]

    labels_dir = _resolve_companion(labels_path, _LABEL_FILES, "labels")
    ghg_dir = _resolve_companion(ghg_path, _GHG_FILES, "ghg")
    return REX3Layout(
        root=search_root,
        year_dir=year_dir,
        labels_dir=labels_dir,
        ghg_dir=ghg_dir,
        year=detected_year,
    )


def _decode_hdf5_char(handle: h5py.File, reference) -> str:
    values = handle[reference][()]
    return "".join(chr(int(value)) for value in values.ravel(order="F") if value)


def _read_hdf5_cellstr(path: Path, dataset_name: str) -> np.ndarray:
    with h5py.File(path, "r") as handle:
        if dataset_name not in handle:
            raise WrongFormat(
                f"MATLAB file {path.name} has no dataset {dataset_name!r}."
            )
        references = handle[dataset_name][()]
        strings = np.empty(references.shape, dtype=object)
        for index, reference in np.ndenumerate(references):
            strings[index] = _decode_hdf5_char(handle, reference)
    return strings


def _read_v73_numeric(path: Path, dataset_name: str) -> np.ndarray:
    """Read and orient one complete numeric MATLAB v7.3 matrix."""
    with h5py.File(path, "r") as handle:
        dataset = handle[dataset_name]
        return np.asarray(dataset[()], dtype=np.float64).T


def _matlab_cell_text(value) -> str:
    while isinstance(value, np.ndarray):
        if value.size == 0:
            return ""
        if value.dtype.kind in "US":
            return "".join(value.ravel(order="F").tolist())
        value = value.ravel(order="F")[0]
    return str(value)


def _read_labels(layout: REX3Layout) -> tuple[list[str], list[str], np.ndarray]:
    countries = (
        _read_hdf5_cellstr(
            layout.labels_dir / "Labels_Countries_REX3.mat",
            "Labels_Countries_REX3",
        )
        .ravel(order="F")
        .tolist()
    )
    sectors_with_households = (
        _read_hdf5_cellstr(
            layout.labels_dir / "Labels_Sectors_REX3.mat",
            "Labels_Sectors_REX3",
        )
        .ravel(order="F")
        .tolist()
    )
    transaction_labels = _read_hdf5_cellstr(
        layout.labels_dir / "Labels_T_REX3.mat",
        "Labels_T_REX3",
    )
    if len(sectors_with_households) < 2:
        raise WrongFormat(
            "REX3 sector labels must include sectors and one household label."
        )
    sectors = sectors_with_households[:-1]
    expected_countries = np.repeat(countries, len(sectors))
    expected_sectors = np.tile(sectors, len(countries))
    if transaction_labels.shape != (2, len(expected_countries)):
        raise WrongFormat(
            f"Unexpected Labels_T_REX3 shape: {transaction_labels.shape}."
        )
    if not np.array_equal(transaction_labels[0], expected_countries):
        raise WrongFormat(
            "REX3 transaction country labels do not use country-major ordering."
        )
    if not np.array_equal(transaction_labels[1], expected_sectors):
        raise WrongFormat(
            "REX3 transaction sector labels do not use country-major ordering."
        )
    return countries, sectors, transaction_labels


def _read_transaction_frame(
    path: Path,
    *,
    full_size: int,
    axis: pd.MultiIndex,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Read the complete T matrix and its production-row totals once."""
    with h5py.File(path, "r") as handle:
        dataset = handle["T_REX3"]
        if dataset.shape != (full_size, full_size):
            raise WrongFormat(
                f"Unexpected T_REX3 shape {dataset.shape}; expected {(full_size, full_size)}."
            )
        # MATLAB v7.3 exposes the 2-D matrix transposed through h5py.
        raw = np.asarray(dataset[()], dtype=np.float64)
    output_totals = raw.sum(axis=0, dtype=np.float64)
    return pd.DataFrame(raw.T, index=axis, columns=axis, copy=False), output_totals


def _split_label_and_unit(label: str) -> tuple[str, str]:
    match = re.match(r"^(?P<label>.+?)\s*\[(?P<unit>[^\]]+)\]\s*$", str(label))
    if match is None:
        return str(label), "None"
    return match.group("label").strip(), match.group("unit").strip()


def _year_position(ghg_dir: Path, year: int) -> int:
    years = np.asarray(
        loadmat(ghg_dir / "Labels" / "Labels_years.mat")["Labels_years"]
    ).reshape(-1)
    matches = np.flatnonzero(years.astype(int) == int(year))
    if matches.size != 1:
        raise WrongFormat(f"Year {year} was not found exactly once in REX3 GHG labels.")
    return int(matches[0])


def _validate_ghg_labels(
    ghg_dir: Path,
    transaction_labels: np.ndarray,
) -> None:
    raw = loadmat(ghg_dir / "Labels" / "Labels_Countrysector_combinations.mat")
    labels = raw["Labels_Countrysector_combinations"]
    normalized = np.vectorize(_matlab_cell_text, otypes=[object])(labels)
    if normalized.shape != (transaction_labels.shape[1], 2):
        raise WrongFormat(
            f"Unexpected supplemental REX3 label shape: {normalized.shape}."
        )
    if not np.array_equal(normalized[:, 0], transaction_labels[0]):
        raise WrongFormat(
            "Supplemental REX3 GHG country labels do not match the main bundle."
        )
    if not np.array_equal(normalized[:, 1], transaction_labels[1]):
        raise WrongFormat(
            "Supplemental REX3 GHG sector labels do not match the main bundle."
        )


def parse_rex3_iot(
    path: str | Path,
    *,
    year: int | None = None,
    labels_path: str | Path | None = None,
    ghg_path: str | Path | None = None,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, dict[str, list[str]]],
    dict[str, pd.DataFrame],
    REX3Layout,
]:
    """Parse REX3 directly into flow-form MARIO IOT blocks."""
    layout = detect_rex3_layout(
        path,
        year=year,
        labels_path=labels_path,
        ghg_path=ghg_path,
    )
    countries, sectors, transaction_labels = _read_labels(layout)
    _validate_ghg_labels(layout.ghg_dir, transaction_labels)
    year_position = _year_position(layout.ghg_dir, layout.year)
    full_size = len(countries) * len(sectors)

    sector_axis = pd.MultiIndex.from_arrays(
        [
            np.repeat(countries, len(sectors)),
            [_MASTER_INDEX["s"]] * full_size,
            sectors * len(countries),
        ]
    )
    final_label = _read_hdf5_cellstr(
        layout.labels_dir / "Labels_Sectors_REX3.mat",
        "Labels_Sectors_REX3",
    ).ravel(order="F")[-1]
    final_axis = pd.MultiIndex.from_arrays(
        [
            countries,
            [_MASTER_INDEX["n"]] * len(countries),
            [final_label] * len(countries),
        ]
    )

    log_time(
        logger,
        f"Parser: reading complete REX3 {layout.year} with {len(countries)} regions.",
        "info",
    )
    Z, transaction_output = _read_transaction_frame(
        layout.year_dir / "T_REX3.mat",
        full_size=full_size,
        axis=sector_axis,
    )

    with h5py.File(layout.year_dir / "Y_REX3.mat", "r") as handle:
        raw_y = np.asarray(handle["Y_REX3"][()], dtype=np.float64)
    if raw_y.shape != (len(countries), full_size):
        raise WrongFormat(
            f"Unexpected raw Y_REX3 shape {raw_y.shape}; expected {(len(countries), full_size)}."
        )
    full_final_output = raw_y.sum(axis=0, dtype=np.float64)
    Y = pd.DataFrame(raw_y.T, index=sector_axis, columns=final_axis, copy=False)
    output = transaction_output + full_final_output

    q = _read_v73_numeric(
        layout.year_dir / "Q_REX3.mat",
        "Q_REX3",
    )
    qy = _read_v73_numeric(
        layout.year_dir / "Q_Y_REX3.mat",
        "Q_Y_REX3",
    )
    q_labels_raw = _read_hdf5_cellstr(
        layout.labels_dir / "Labels_Q_REX3.mat",
        "Labels_Q_REX3",
    ).ravel(order="F")
    if q.shape != (len(q_labels_raw), full_size) or qy.shape != (len(q_labels_raw), len(countries)):
        raise WrongFormat(
            f"REX3 Q/Q_Y rows do not match labels: Q={q.shape}, Q_Y={qy.shape}, labels={len(q_labels_raw)}."
        )
    parsed_q_labels = [_split_label_and_unit(value) for value in q_labels_raw]
    value_added_positions = [
        position
        for position, (label, _) in enumerate(parsed_q_labels)
        if label.casefold().startswith("value added")
    ]
    if len(value_added_positions) != 1:
        raise WrongFormat(
            f"Expected one REX3 value-added row, found {value_added_positions}."
        )
    value_added_position = value_added_positions[0]
    base_extension_positions = [
        position
        for position in range(len(parsed_q_labels))
        if position != value_added_position
    ]
    base_extension_labels = [
        parsed_q_labels[position][0] for position in base_extension_positions
    ]
    base_extension_units = [
        parsed_q_labels[position][1] for position in base_extension_positions
    ]

    d_cc_full = np.asarray(
        loadmat(layout.ghg_dir / "d_CC_REX3_timeline.mat")["d_CC_REX3_timeline"][
            :, :, year_position
        ],
        dtype=np.float64,
    )
    lulucf_full = np.asarray(
        loadmat(layout.ghg_dir / "Q_LULUCF_REX3_timeline.mat")[
            "Q_LULUCF_REX3_timeline"
        ][:, year_position],
        dtype=np.float64,
    )
    qy_lulucf_full = np.asarray(
        loadmat(layout.ghg_dir / "Q_Y_LULUCF_REX3_timeline.mat")[
            "Q_Y_LULUCF_REX3_timeline"
        ][:, year_position],
        dtype=np.float64,
    )
    if d_cc_full.shape != (len(REX3_GHG_LABELS), full_size):
        raise WrongFormat(
            f"Unexpected d_CC_REX3_timeline slice shape: {d_cc_full.shape}."
        )
    if lulucf_full.shape != (full_size,) or qy_lulucf_full.shape != (len(countries),):
        raise WrongFormat(
            "Supplemental REX3 LULUCF flows have incompatible dimensions."
        )

    detailed_ghg = d_cc_full * output[np.newaxis, :]
    detailed_ghg[-1, :] = lulucf_full
    detailed_ghg_y = np.zeros((len(REX3_GHG_LABELS), len(countries)), dtype=np.float64)
    detailed_ghg_y[-1, :] = qy_lulucf_full

    extension_axis = pd.Index([*base_extension_labels, *REX3_GHG_LABELS], name=None)
    factor_label, factor_unit = parsed_q_labels[value_added_position]
    factor_axis = pd.Index([factor_label], name=None)
    V = pd.DataFrame(
        q[[value_added_position], :], index=factor_axis, columns=sector_axis
    )
    E = pd.DataFrame(
        np.vstack([q[base_extension_positions, :], detailed_ghg]),
        index=extension_axis,
        columns=sector_axis,
    )
    EY = pd.DataFrame(
        np.vstack([qy[base_extension_positions, :], detailed_ghg_y]),
        index=extension_axis,
        columns=final_axis,
    )

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "EY": EY}}
    units = {
        _MASTER_INDEX["s"]: pd.DataFrame(
            {"unit": [REX3_MONETARY_UNIT] * len(sectors)},
            index=pd.Index(sectors, name=None),
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            {"unit": [factor_unit]},
            index=factor_axis,
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            {
                "unit": [
                    *base_extension_units,
                    *([REX3_GHG_UNIT] * len(REX3_GHG_LABELS)),
                ]
            },
            index=extension_axis,
        ),
    }
    indeces = {
        "r": {"main": countries},
        "s": {"main": sectors},
        "f": {"main": list(factor_axis)},
        "k": {"main": list(extension_axis)},
        "n": {"main": [final_label]},
    }
    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            f"Parser: REX3 {layout.year} parsed with {len(countries)} regions, "
            f"{len(sectors)} sectors and {len(extension_axis)} environmental rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout
