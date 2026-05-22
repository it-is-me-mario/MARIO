"""Direct file-based parser for GLORIA monetary multi-regional SUT bundles."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
import logging
from pathlib import Path
import re
import zipfile

import numpy as np
import pandas as pd
from scipy import sparse

from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.specs import (
    GLORIA_MONETARY_UNIT,
    GLORIA_SATELLITE_PLACEHOLDER,
    GLORIA_SATELLITE_UNIT,
    GLORIA_SOURCE,
    GLORIA_VALUATION_MARKUPS,
)
from mario.utils import rename_index

logger = logging.getLogger(__name__)

_GLORIA_FILE_RE = re.compile(
    r"(?P<prefix>.+)_(?P<var>T|Y|V|TQ|YQ)-Results_"
    r"(?P<year>\d{4})_(?P<release>\d{3})_Markup(?P<markup>\d{3})\(full\)\.csv$",
    flags=re.IGNORECASE,
)
_GLORIA_DATA_DIR_RE = re.compile(
    r"GLORIA_MRIOs_(?P<release>\d+)_(?P<year>\d{4})$",
    flags=re.IGNORECASE,
)
_GLORIA_SAT_DIR_RE = re.compile(
    r"GLORIA_SatelliteAccounts_(?P<release>\d+)_(?P<year>\d{4})$",
    flags=re.IGNORECASE,
)
_GLORIA_README_RE = re.compile(r"GLORIA_ReadMe_\d+\.xlsx$", flags=re.IGNORECASE)

_VALUATION_ALIASES = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "basic": 1,
    "basic prices": 1,
    "trade": 2,
    "trade margins": 2,
    "transport": 3,
    "transport margins": 3,
    "taxes": 4,
    "taxes on products": 4,
    "subsidies": 5,
    "subsidies on products": 5,
}


@dataclass(frozen=True)
class GloriaResource:
    """One GLORIA file stored either on disk or inside one zip archive."""

    container: Path
    member: str | None = None

    @property
    def name(self) -> str:
        """Return the basename used for file-pattern matching and logs."""
        if self.member is None:
            return self.container.name
        return Path(self.member).name

    @property
    def location(self) -> str:
        """Return a stable location string for logs and cache signatures."""
        if self.member is None:
            return str(self.container)
        return f"{self.container}!{self.member}"


def gloria_resource_signature(resource: GloriaResource) -> dict[str, object]:
    """Return cache-relevant identity data for one GLORIA resource."""
    stats = resource.container.stat()
    payload: dict[str, object] = {
        "path": str(resource.container),
        "size": stats.st_size,
        "mtime_ns": stats.st_mtime_ns,
    }
    if resource.member is None:
        return payload

    with zipfile.ZipFile(resource.container) as archive:
        info = archive.getinfo(resource.member)
    payload.update(
        {
            "member": resource.member,
            "member_size": info.file_size,
            "member_crc": info.CRC,
        }
    )
    return payload


@dataclass(frozen=True)
class GloriaMetadata:
    """ReadMe-derived structural metadata for one GLORIA release."""

    region_codes: tuple[str, ...]
    region_names: tuple[str, ...]
    sector_names: tuple[str, ...]
    factor_names: tuple[str, ...]
    final_demand_names: tuple[str, ...]
    valuation_names: dict[int, str]
    satellite_heads: tuple[str, ...]
    satellite_names: tuple[str, ...]
    satellite_units: tuple[str, ...]


@dataclass(frozen=True)
class GloriaLayout:
    """Filesystem layout and metadata for one GLORIA SUT bundle."""

    root: Path
    data_root: Path
    readme_path: Path
    satellite_root: Path | None
    year: int
    release: str
    markup: int
    valuation_name: str
    T_path: GloriaResource
    Y_path: GloriaResource
    V_path: GloriaResource
    TQ_path: GloriaResource | None
    YQ_path: GloriaResource | None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def dataset_name(self) -> str:
        """Return a compact dataset label suitable for ``Database.name``."""
        return f"GLORIA SUT {self.year} {self.valuation_name}"

    @property
    def price(self) -> str:
        """Return the valuation label stored in metadata."""
        return self.valuation_name

    @property
    def source(self) -> str:
        """Return the canonical source string stored in metadata."""
        return (
            f"{GLORIA_SOURCE} "
            f"(release {self.release}; docs: {self.readme_path.name} and GLORIA_ReleaseNotes_{self.release}.pdf)"
        )


def _normalize_valuation(value: str | int) -> int:
    """Normalize user-facing GLORIA valuation selectors into one markup id."""
    key = value if isinstance(value, int) else str(value).strip().lower()
    if key not in _VALUATION_ALIASES:
        accepted = [
            "basic",
            "trade",
            "transport",
            "taxes",
            "subsidies",
            "1",
            "2",
            "3",
            "4",
            "5",
        ]
        raise WrongInput(f"GLORIA valuation should be one of {accepted}.")
    return _VALUATION_ALIASES[key]


def _is_gloria_part_i_dir(path: Path) -> bool:
    """Return whether ``path`` looks like the Google Drive part I container."""
    name = path.name.lower()
    return "part_i" in name and "mrio" in name


def _is_gloria_part_iii_dir(path: Path) -> bool:
    """Return whether ``path`` looks like the Google Drive part III container."""
    name = path.name.lower()
    return "part_iii" in name and "satellite" in name


def _is_zip_path(path: Path) -> bool:
    """Return whether ``path`` is one zip archive."""
    return path.is_file() and path.suffix.lower() == ".zip"


def _container_name(path: Path) -> str:
    """Return the logical container name for directories and zip archives."""
    if _is_zip_path(path):
        return path.stem
    return path.name


def _match_gloria_data_container(path: Path) -> re.Match[str] | None:
    """Match one GLORIA data container name, including zipped variants."""
    return _GLORIA_DATA_DIR_RE.match(_container_name(path))


def _match_gloria_satellite_container(path: Path) -> re.Match[str] | None:
    """Match one GLORIA satellite container name, including zipped variants."""
    return _GLORIA_SAT_DIR_RE.match(_container_name(path))


def _iter_gloria_resources(path: Path) -> list[GloriaResource]:
    """Return direct file resources available under one directory or zip archive."""
    if not path.exists():
        return []
    if path.is_dir():
        return [GloriaResource(child) for child in path.iterdir() if child.is_file()]
    if _is_zip_path(path):
        with zipfile.ZipFile(path) as archive:
            return [
                GloriaResource(path, info.filename)
                for info in archive.infolist()
                if not info.is_dir()
            ]
    return []


def _gloria_file_resources(
    path: Path,
    variables: set[str] | None = None,
) -> list[tuple[re.Match[str], GloriaResource]]:
    """Return GLORIA raw-file matches found directly under one container."""
    matches: list[tuple[re.Match[str], GloriaResource]] = []
    for resource in _iter_gloria_resources(path):
        match = _GLORIA_FILE_RE.match(resource.name)
        if match is None:
            continue
        if variables is not None and match.group("var").upper() not in variables:
            continue
        matches.append((match, resource))
    return matches


@contextmanager
def _open_gloria_resource(resource: GloriaResource):
    """Yield a readable binary stream for one GLORIA resource."""
    if resource.member is None:
        with resource.container.open("rb") as stream:
            yield stream
        return

    with zipfile.ZipFile(resource.container) as archive:
        with archive.open(resource.member, "r") as stream:
            yield stream


def _gloria_file_matches(path: Path, variables: set[str] | None = None) -> list[re.Match[str]]:
    """Return GLORIA raw-file matches found directly under ``path``."""
    return [match for match, _ in _gloria_file_resources(path, variables)]


def _gloria_candidate_matches_year(candidate: Path, year: int | None) -> bool:
    """Return whether one candidate data directory is compatible with ``year``."""
    if year is None:
        return True

    dir_match = _match_gloria_data_container(candidate)
    if dir_match is not None:
        return int(dir_match.group("year")) == year

    return any(int(match.group("year")) == year for match in _gloria_file_matches(candidate))


def _candidate_data_roots(container: Path) -> list[Path]:
    """Return GLORIA data directories available directly under ``container``."""
    candidates: list[Path] = []
    if _gloria_file_matches(container, {"T", "Y", "V"}):
        candidates.append(container)

    candidates.extend(
        child
        for child in container.iterdir()
        if (child.is_dir() or _is_zip_path(child)) and _match_gloria_data_container(child)
    )
    return candidates


def _select_gloria_data_root(candidates: list[Path], *, year: int | None) -> Path:
    """Select one GLORIA data root, using ``year`` when several are available."""
    unique_candidates = sorted(set(candidates))
    if year is not None:
        unique_candidates = [
            candidate for candidate in unique_candidates if _gloria_candidate_matches_year(candidate, year)
        ]

    if len(unique_candidates) == 1:
        return unique_candidates[0]

    if not unique_candidates:
        if year is None:
            raise WrongInput("Could not find a GLORIA MRIO directory or GLORIA csv files in the selected path.")
        raise WrongInput(f"Could not find a GLORIA MRIO directory or csv files for year {year}.")

    raise WrongInput(
        "More than one GLORIA MRIO directory was found. Please specify year or point the parser to one dataset directory."
    )


def _resolve_gloria_roots(path: str | Path, *, year: int | None = None) -> tuple[Path, Path]:
    """Resolve the GLORIA dataset root and the directory containing csv files."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)

    if source.is_file():
        if _is_zip_path(source) and _match_gloria_data_container(source):
            root = source.parent.parent if _is_gloria_part_i_dir(source.parent) else source.parent
            return root, source
        return source.parent.parent, source.parent

    if _is_gloria_part_i_dir(source):
        candidates = _candidate_data_roots(source)
        if candidates:
            return source.parent, _select_gloria_data_root(candidates, year=year)

    if _gloria_file_matches(source, {"T", "Y", "V"}):
        return source.parent, source

    candidates = _candidate_data_roots(source)
    if candidates:
        return source, _select_gloria_data_root(candidates, year=year)

    part_i_dirs = [
        child for child in source.iterdir() if child.is_dir() and _is_gloria_part_i_dir(child)
    ]
    part_i_candidates: list[Path] = []
    for part_i_dir in part_i_dirs:
        part_i_candidates.extend(_candidate_data_roots(part_i_dir))
    if part_i_candidates:
        return source, _select_gloria_data_root(part_i_candidates, year=year)

    raise WrongInput("Could not find a GLORIA MRIO directory or GLORIA csv files in the selected path.")


def _find_gloria_readme(root: Path, data_root: Path) -> Path:
    """Locate the GLORIA ReadMe workbook used to reconstruct labels."""
    candidates = []
    for base in (root, data_root, data_root.parent, root.parent):
        if base.exists() and base.is_dir():
            candidates.extend(
                child for child in base.iterdir() if child.is_file() and _GLORIA_README_RE.match(child.name)
            )

    if not candidates:
        raise WrongInput("Could not find GLORIA_ReadMe_*.xlsx next to the dataset.")

    return sorted(set(candidates))[0]


def _find_gloria_satellite_root(root: Path, data_root: Path, *, year: int, release: str) -> Path | None:
    """Locate the optional GLORIA satellite-account directory when present."""
    expected = f"GLORIA_SatelliteAccounts_{release}_{year}"
    candidates: list[Path] = []

    for base in (root, data_root.parent, root.parent):
        if not base.exists() or not base.is_dir():
            continue
        direct = base / expected
        if direct.exists() and direct.is_dir():
            candidates.append(direct)
        direct_zip = base / f"{expected}.zip"
        if _is_zip_path(direct_zip):
            candidates.append(direct_zip)
        candidates.extend(
            child
            for child in base.iterdir()
            if (child.is_dir() or _is_zip_path(child))
            and _match_gloria_satellite_container(child)
            and int(_match_gloria_satellite_container(child).group("year")) == year
            and _match_gloria_satellite_container(child).group("release") == release
        )
        for part_iii_dir in (
            child for child in base.iterdir() if child.is_dir() and _is_gloria_part_iii_dir(child)
        ):
            direct = part_iii_dir / expected
            if direct.exists() and direct.is_dir():
                candidates.append(direct)
            direct_zip = part_iii_dir / f"{expected}.zip"
            if _is_zip_path(direct_zip):
                candidates.append(direct_zip)
            candidates.extend(
                child
                for child in part_iii_dir.iterdir()
                if (child.is_dir() or _is_zip_path(child))
                and _match_gloria_satellite_container(child)
                and int(_match_gloria_satellite_container(child).group("year")) == year
                and _match_gloria_satellite_container(child).group("release") == release
            )
            if any(
                int(match.group("year")) == year and match.group("release") == release
                for match in _gloria_file_matches(part_iii_dir, {"TQ", "YQ"})
            ):
                candidates.append(part_iii_dir)

    if not candidates:
        return None

    return sorted(set(candidates))[0]


def _make_unique_labels(base_labels: list[str], ids: list[int]) -> tuple[str, ...]:
    """Return human-readable labels that remain unique when raw labels collide."""
    counts: dict[str, int] = {}
    for label in base_labels:
        counts[label] = counts.get(label, 0) + 1

    seen: dict[str, int] = {}
    labels: list[str] = []
    for label, identifier in zip(base_labels, ids):
        seen[label] = seen.get(label, 0) + 1
        if counts[label] == 1:
            labels.append(label)
        else:
            labels.append(f"{label} [{identifier}]")
    return tuple(labels)


@lru_cache(maxsize=8)
def load_gloria_metadata(readme_path: str | Path) -> GloriaMetadata:
    """Load structural metadata from the GLORIA ReadMe workbook."""
    readme = Path(readme_path)
    workbook = pd.ExcelFile(readme)

    regions = workbook.parse("Regions")
    sectors = workbook.parse("Sectors")
    value_added = workbook.parse("Value added and final demand")
    valuations = workbook.parse("Valuations")
    satellites = workbook.parse("Satellites")

    region_codes = tuple(regions["Region_acronyms"].astype(str).tolist())
    region_names = tuple(regions["Region_names"].astype(str).tolist())
    sector_names = tuple(sectors["Sector_names"].astype(str).tolist())
    factor_names = tuple(value_added["Value_added_names"].astype(str).tolist())
    final_demand_names = tuple(value_added["Final_demand_names"].astype(str).tolist())

    valuation_names = {
        int(number): str(name)
        for number, name in zip(valuations["Lfd_Nr"], valuations["Valuation_names"])
    }
    if not valuation_names:
        valuation_names = dict(GLORIA_VALUATION_MARKUPS)

    satellite_heads = tuple(satellites["Sat_head_indicator"].astype(str).tolist())
    satellite_base_labels = [
        f"{head} | {indicator}"
        for head, indicator in zip(
            list(satellite_heads),
            satellites["Sat_indicator"].astype(str).tolist(),
        )
    ]
    satellite_ids = satellites["Lfd_Nr"].astype(int).tolist()
    satellite_names = _make_unique_labels(satellite_base_labels, satellite_ids)
    satellite_units = tuple(satellites["Sat_unit"].astype(str).tolist())

    return GloriaMetadata(
        region_codes=region_codes,
        region_names=region_names,
        sector_names=sector_names,
        factor_names=factor_names,
        final_demand_names=final_demand_names,
        valuation_names=valuation_names,
        satellite_heads=satellite_heads,
        satellite_names=satellite_names,
        satellite_units=satellite_units,
    )


def detect_gloria_layout(
    path: str | Path,
    *,
    valuation: str | int = "basic",
    year: int | None = None,
) -> tuple[GloriaLayout, GloriaMetadata]:
    """Resolve the GLORIA files and metadata used for one SUT parse request."""
    root, data_root = _resolve_gloria_roots(path, year=year)
    readme_path = _find_gloria_readme(root, data_root)
    metadata = load_gloria_metadata(readme_path)

    markup = _normalize_valuation(valuation)
    by_var_and_markup: dict[tuple[str, int], Path] = {}
    years: set[int] = set()
    release = None

    for match, resource in _gloria_file_resources(data_root):
        parsed_year = int(match.group("year"))
        if year is not None and parsed_year != year:
            continue
        years.add(parsed_year)
        by_var_and_markup[(match.group("var").upper(), int(match.group("markup")))] = resource
        release = match.group("release")

    if year is None:
        if len(years) > 1:
            raise WrongInput(
                f"More than one GLORIA year is available in {data_root}. Please specify year."
            )
        if not years:
            raise WrongInput("No GLORIA result files were found in the selected directory.")
        year = next(iter(years))

    try:
        T_path = by_var_and_markup[("T", markup)]
        Y_path = by_var_and_markup[("Y", markup)]
    except KeyError as exc:
        raise WrongInput(
            f"Could not find GLORIA T and Y files for valuation markup {markup:03d} and year {year}."
        ) from exc

    V_path = by_var_and_markup.get(("V", markup)) or by_var_and_markup.get(("V", 1))
    if V_path is None:
        raise WrongInput(f"Could not find a GLORIA V file for year {year}.")

    notes: list[str] = []
    if markup != 1 and _GLORIA_FILE_RE.match(V_path.name).group("markup") != f"{markup:03d}":
        notes.append("No markup-specific GLORIA V file was found; value added was read from Markup001.")

    satellite_root = _find_gloria_satellite_root(root, data_root, year=year, release=release or "unknown")
    TQ_path = None
    YQ_path = None
    if satellite_root is not None:
        for match, resource in _gloria_file_resources(satellite_root):
            if int(match.group("year")) != year:
                continue
            if match.group("var").upper() == "TQ" and int(match.group("markup")) == 1:
                TQ_path = resource
            if match.group("var").upper() == "YQ" and int(match.group("markup")) == 1:
                YQ_path = resource
        if TQ_path is None or YQ_path is None:
            notes.append("GLORIA satellite-account directory found, but TQ/YQ files were incomplete.")

    layout = GloriaLayout(
        root=root,
        data_root=data_root,
        readme_path=readme_path,
        satellite_root=satellite_root,
        year=year,
        release=release or "unknown",
        markup=markup,
        valuation_name=metadata.valuation_names.get(markup, GLORIA_VALUATION_MARKUPS[markup]),
        T_path=T_path,
        Y_path=Y_path,
        V_path=V_path,
        TQ_path=TQ_path,
        YQ_path=YQ_path,
        notes=tuple(notes),
    )
    log_time(
        logger,
        (
            "Parser: detected GLORIA SUT layout "
            f"year={layout.year} release={layout.release} valuation={layout.valuation_name} "
            f"T={layout.T_path.name} Y={layout.Y_path.name} V={layout.V_path.name} "
            f"TQ={layout.TQ_path.name if layout.TQ_path else 'none'} "
            f"YQ={layout.YQ_path.name if layout.YQ_path else 'none'}"
        ),
        "debug",
    )
    return layout, metadata


def _normalize_region_selection(
    metadata: GloriaMetadata,
    regions: str | list[str] | tuple[str, ...] | None,
) -> tuple[list[int], list[str]]:
    """Normalize and validate the requested GLORIA region subset."""
    available = list(metadata.region_codes)
    if regions is None or regions == "all":
        return list(range(len(available))), available

    requested = [regions] if isinstance(regions, str) else list(regions)
    invalid = sorted(set(requested).difference(available))
    if invalid:
        raise WrongInput(f"Unknown GLORIA regions: {invalid}")

    selected_positions = [available.index(code) for code in requested]
    ordered_codes = [available[position] for position in selected_positions]
    return selected_positions, ordered_codes


def _normalize_satellite_request(
    satellites: str | list[str] | tuple[str, ...] | None,
) -> str | list[str]:
    """Normalize one GLORIA satellite selector into a stable request payload."""
    if satellites is None or satellites == "all":
        return "all"
    if isinstance(satellites, str):
        return [satellites]
    return [str(value) for value in satellites]


def _select_gloria_satellites(
    metadata: GloriaMetadata,
    satellites: str | list[str] | tuple[str, ...] | None,
) -> tuple[list[int], pd.Index, pd.DataFrame]:
    """Resolve one satellite selection request to raw row positions and units.

    The request can reference either full satellite labels
    (for example ``"Emissions | CO2"``) or whole satellite groups from the
    ``Sat_head_indicator`` column (for example ``"Emissions"``).
    """
    request = _normalize_satellite_request(satellites)
    names = list(metadata.satellite_names)
    heads = list(metadata.satellite_heads)
    units = list(metadata.satellite_units)

    if request == "all":
        positions = list(range(len(names)))
    else:
        label_map = {label.casefold(): position for position, label in enumerate(names)}
        head_map: dict[str, list[int]] = {}
        for position, head in enumerate(heads):
            head_map.setdefault(head.casefold(), []).append(position)

        selected: set[int] = set()
        invalid: list[str] = []
        for token in request:
            key = str(token).strip().casefold()
            if not key:
                continue
            if key == "all":
                selected.update(range(len(names)))
                continue
            if key in label_map:
                selected.add(label_map[key])
                continue
            if key in head_map:
                selected.update(head_map[key])
                continue
            fuzzy_positions = [
                position
                for position, (label, head) in enumerate(zip(names, heads))
                if key in label.casefold() or key in head.casefold()
            ]
            if fuzzy_positions:
                selected.update(fuzzy_positions)
                continue
            invalid.append(str(token))

        if invalid:
            raise WrongInput(
                f"Unknown GLORIA satellites/groups: {invalid}. "
                "Use full labels such as 'Emissions | CO2' or group names such as 'Emissions'."
            )

        positions = sorted(selected)

    if not positions:
        raise WrongInput("GLORIA satellite selection produced no rows.")

    satellite_axis = pd.Index([names[position] for position in positions], name=None)
    satellite_units = pd.DataFrame({"unit": [units[position] for position in positions]}, index=satellite_axis)
    return positions, satellite_axis, satellite_units


def _activity_positions(region_positions: list[int], sector_count: int) -> np.ndarray:
    """Return the raw column positions for activity blocks of the selected regions."""
    return np.concatenate(
        [
            np.arange(position * sector_count * 2, position * sector_count * 2 + sector_count)
            for position in region_positions
        ]
    ).astype(np.int32)


def _commodity_positions(region_positions: list[int], sector_count: int) -> np.ndarray:
    """Return the raw column positions for commodity blocks of the selected regions."""
    return np.concatenate(
        [
            np.arange(
                position * sector_count * 2 + sector_count,
                position * sector_count * 2 + sector_count * 2,
            )
            for position in region_positions
        ]
    ).astype(np.int32)


def _final_demand_positions(region_positions: list[int], fd_count: int) -> np.ndarray:
    """Return the raw final-demand column positions for the selected regions."""
    return np.concatenate(
        [np.arange(position * fd_count, position * fd_count + fd_count) for position in region_positions]
    ).astype(np.int32)


def _row_maps(region_positions: list[int], sector_count: int) -> tuple[dict[int, int], dict[int, int]]:
    """Return raw-row to canonical-row maps for activity and commodity rows."""
    activity_rows: dict[int, int] = {}
    commodity_rows: dict[int, int] = {}
    for local_region, absolute_region in enumerate(region_positions):
        base = absolute_region * sector_count * 2
        for sector in range(sector_count):
            activity_rows[base + sector] = local_region * sector_count + sector
            commodity_rows[base + sector_count + sector] = local_region * sector_count + sector
    return activity_rows, commodity_rows


def _build_axes(
    region_codes: list[str],
    sector_names: tuple[str, ...],
    factor_names: tuple[str, ...],
    final_demand_names: tuple[str, ...],
    satellite_names: tuple[str, ...],
) -> tuple[pd.MultiIndex, pd.MultiIndex, pd.MultiIndex, pd.Index, pd.Index]:
    """Build canonical MARIO axes for split-native GLORIA SUT blocks."""
    activity_axis = pd.MultiIndex.from_product([region_codes, [_MASTER_INDEX["a"]], list(sector_names)])
    commodity_axis = pd.MultiIndex.from_product([region_codes, [_MASTER_INDEX["c"]], list(sector_names)])
    final_demand_axis = pd.MultiIndex.from_product(
        [region_codes, [_MASTER_INDEX["n"]], list(final_demand_names)]
    )
    factor_axis = pd.Index(list(factor_names), name=None)
    satellite_axis = pd.Index(list(satellite_names), name=None)
    return activity_axis, commodity_axis, final_demand_axis, factor_axis, satellite_axis


def _iter_csv_batches(
    path: GloriaResource,
    *,
    columns: np.ndarray | list[int] | tuple[int, ...],
    dtype: np.dtype,
    batch_size: int,
):
    """Yield ``(row_numbers, values)`` batches from one wide GLORIA csv file."""
    column_numbers = [int(value) for value in columns]
    if not column_numbers:
        raise ValueError("At least one column should be selected.")
    contiguous_full_width = column_numbers == list(range(column_numbers[-1] + 1))
    offset = 0
    with _open_gloria_resource(path) as stream:
        for chunk in pd.read_csv(
            stream,
            header=None,
            usecols=None if contiguous_full_width else column_numbers,
            dtype=dtype.name,
            chunksize=batch_size,
            engine="c",
            na_filter=False,
        ):
            values = chunk.to_numpy(copy=False)
            row_numbers = np.arange(offset, offset + len(chunk), dtype=np.int64)
            offset += len(chunk)
            yield row_numbers, values


def _recommended_batch_size(column_count: int, dtype: np.dtype, *, target_mb: int = 64) -> int:
    """Choose a batch size that keeps one Polars chunk within a rough memory target."""
    if column_count <= 0:
        return 256
    bytes_per_row = max(1, column_count * np.dtype(dtype).itemsize)
    target_bytes = target_mb * 1024 * 1024
    rows = max(64, target_bytes // bytes_per_row)
    return int(min(4096, rows))


def _coo_from_triplets(
    rows: list[np.ndarray],
    cols: list[np.ndarray],
    values: list[np.ndarray],
    *,
    shape: tuple[int, int],
    dtype: np.dtype,
) -> sparse.csr_matrix:
    """Build one CSR matrix from sparse triplets accumulated across batches."""
    if not values:
        return sparse.csr_matrix(shape, dtype=dtype)
    return sparse.coo_matrix(
        (np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))),
        shape=shape,
        dtype=dtype,
    ).tocsr()


def _read_transaction_blocks(
    path: Path,
    *,
    activity_columns: np.ndarray,
    commodity_columns: np.ndarray,
    activity_row_map: dict[int, int],
    commodity_row_map: dict[int, int],
    s_shape: tuple[int, int],
    u_shape: tuple[int, int],
    dtype: np.dtype,
) -> tuple[sparse.csr_matrix, np.ndarray]:
    """Read one GLORIA ``T`` file once and derive both ``S`` and ``U`` blocks."""
    combined_columns = np.sort(np.concatenate([activity_columns, commodity_columns]).astype(np.int32, copy=False))
    activity_take = np.searchsorted(combined_columns, activity_columns)
    commodity_take = np.searchsorted(combined_columns, commodity_columns)
    batch_size = _recommended_batch_size(len(combined_columns), dtype)

    s_rows: list[np.ndarray] = []
    s_cols: list[np.ndarray] = []
    s_values: list[np.ndarray] = []
    u_data = np.zeros(u_shape, dtype=dtype)

    for row_numbers, block in _iter_csv_batches(path, columns=combined_columns, dtype=dtype, batch_size=batch_size):
        activity_block = block[:, activity_take]
        commodity_block = block[:, commodity_take]
        for raw_row, activity_values, commodity_values in zip(row_numbers.tolist(), activity_block, commodity_block):
            raw_row = int(raw_row)
            activity_row = activity_row_map.get(raw_row)
            if activity_row is not None:
                nonzero = np.flatnonzero(commodity_values)
                if len(nonzero) > 0:
                    s_rows.append(np.full(len(nonzero), activity_row, dtype=np.int32))
                    s_cols.append(nonzero.astype(np.int32, copy=False))
                    s_values.append(commodity_values[nonzero].astype(dtype, copy=False))
                continue

            commodity_row = commodity_row_map.get(raw_row)
            if commodity_row is not None:
                u_data[commodity_row, :] = activity_values

    return _coo_from_triplets(s_rows, s_cols, s_values, shape=s_shape, dtype=dtype), u_data


def _read_final_demand_blocks(
    path: Path,
    *,
    final_demand_columns: np.ndarray,
    activity_row_map: dict[int, int],
    commodity_row_map: dict[int, int],
    ya_shape: tuple[int, int],
    yc_shape: tuple[int, int],
    dtype: np.dtype,
) -> tuple[sparse.csr_matrix, np.ndarray]:
    """Read one GLORIA ``Y`` file once and derive both ``Ya`` and ``Yc`` blocks."""
    batch_size = _recommended_batch_size(len(final_demand_columns), dtype)
    ya_rows: list[np.ndarray] = []
    ya_cols: list[np.ndarray] = []
    ya_values: list[np.ndarray] = []
    yc_data = np.zeros(yc_shape, dtype=dtype)

    for row_numbers, block in _iter_csv_batches(
        path,
        columns=final_demand_columns,
        dtype=dtype,
        batch_size=batch_size,
    ):
        for raw_row, raw_values in zip(row_numbers.tolist(), block):
            raw_row = int(raw_row)
            activity_row = activity_row_map.get(raw_row)
            if activity_row is not None:
                nonzero = np.flatnonzero(raw_values)
                if len(nonzero) > 0:
                    ya_rows.append(np.full(len(nonzero), activity_row, dtype=np.int32))
                    ya_cols.append(nonzero.astype(np.int32, copy=False))
                    ya_values.append(raw_values[nonzero].astype(dtype, copy=False))
                continue

            commodity_row = commodity_row_map.get(raw_row)
            if commodity_row is not None:
                yc_data[commodity_row, :] = raw_values

    return _coo_from_triplets(ya_rows, ya_cols, ya_values, shape=ya_shape, dtype=dtype), yc_data


def _read_value_added_blocks(
    path: Path,
    *,
    activity_columns: np.ndarray,
    commodity_columns: np.ndarray,
    factor_count: int,
    selected_positions: list[int],
    va_shape: tuple[int, int],
    vc_shape: tuple[int, int],
    dtype: np.dtype,
) -> tuple[np.ndarray, sparse.csr_matrix]:
    """Read one GLORIA ``V`` file once and derive both ``Va`` and ``Vc`` blocks."""
    combined_columns = np.sort(np.concatenate([activity_columns, commodity_columns]).astype(np.int32, copy=False))
    activity_take = np.searchsorted(combined_columns, activity_columns)
    commodity_take = np.searchsorted(combined_columns, commodity_columns)
    batch_size = _recommended_batch_size(len(combined_columns), dtype)
    selected = set(selected_positions)

    va_data = np.zeros(va_shape, dtype=dtype)
    vc_rows: list[np.ndarray] = []
    vc_cols: list[np.ndarray] = []
    vc_values: list[np.ndarray] = []

    for row_numbers, block in _iter_csv_batches(path, columns=combined_columns, dtype=dtype, batch_size=batch_size):
        activity_block = block[:, activity_take]
        commodity_block = block[:, commodity_take]
        for raw_row, activity_values, commodity_values in zip(row_numbers.tolist(), activity_block, commodity_block):
            raw_row = int(raw_row)
            region_position = raw_row // factor_count
            if region_position not in selected:
                continue
            factor_position = raw_row % factor_count
            va_data[factor_position, :] += activity_values
            nonzero = np.flatnonzero(commodity_values)
            if len(nonzero) == 0:
                continue
            vc_rows.append(np.full(len(nonzero), factor_position, dtype=np.int32))
            vc_cols.append(nonzero.astype(np.int32, copy=False))
            vc_values.append(commodity_values[nonzero].astype(dtype, copy=False))

    return va_data, _coo_from_triplets(vc_rows, vc_cols, vc_values, shape=vc_shape, dtype=dtype)


def _read_satellite_transaction_blocks(
    path: Path,
    *,
    activity_columns: np.ndarray,
    commodity_columns: np.ndarray,
    row_map: dict[int, int],
    dtype: np.dtype,
) -> tuple[sparse.csr_matrix, sparse.csr_matrix]:
    """Read one GLORIA ``TQ`` file once and derive both ``Ea`` and ``Ec`` blocks."""
    combined_columns = np.sort(np.concatenate([activity_columns, commodity_columns]).astype(np.int32, copy=False))
    activity_take = np.searchsorted(combined_columns, activity_columns)
    commodity_take = np.searchsorted(combined_columns, commodity_columns)
    batch_size = _recommended_batch_size(len(combined_columns), dtype)

    ea_rows: list[np.ndarray] = []
    ea_cols: list[np.ndarray] = []
    ea_values: list[np.ndarray] = []
    ec_rows: list[np.ndarray] = []
    ec_cols: list[np.ndarray] = []
    ec_values: list[np.ndarray] = []

    for row_numbers, block in _iter_csv_batches(path, columns=combined_columns, dtype=dtype, batch_size=batch_size):
        activity_block = block[:, activity_take]
        commodity_block = block[:, commodity_take]
        for raw_row, activity_values, commodity_values in zip(row_numbers.tolist(), activity_block, commodity_block):
            raw_row = int(raw_row)
            local_row = row_map.get(raw_row)
            if local_row is None:
                continue

            activity_nonzero = np.flatnonzero(activity_values)
            if len(activity_nonzero) > 0:
                ea_rows.append(np.full(len(activity_nonzero), local_row, dtype=np.int32))
                ea_cols.append(activity_nonzero.astype(np.int32, copy=False))
                ea_values.append(activity_values[activity_nonzero].astype(dtype, copy=False))

            commodity_nonzero = np.flatnonzero(commodity_values)
            if len(commodity_nonzero) > 0:
                ec_rows.append(np.full(len(commodity_nonzero), local_row, dtype=np.int32))
                ec_cols.append(commodity_nonzero.astype(np.int32, copy=False))
                ec_values.append(commodity_values[commodity_nonzero].astype(dtype, copy=False))

    ea = _coo_from_triplets(ea_rows, ea_cols, ea_values, shape=(len(row_map), len(activity_columns)), dtype=dtype)
    ec = _coo_from_triplets(ec_rows, ec_cols, ec_values, shape=(len(row_map), len(commodity_columns)), dtype=dtype)
    return ea, ec


def _read_sparse_all_rows(
    path: Path,
    *,
    columns: np.ndarray,
    row_map: dict[int, int],
    dtype: np.dtype,
) -> sparse.csr_matrix:
    """Read all rows from one GLORIA file into a sparse block."""
    columns = np.sort(np.asarray(columns, dtype=np.int32))
    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    values: list[np.ndarray] = []
    batch_size = _recommended_batch_size(len(columns), dtype)

    for row_numbers, block in _iter_csv_batches(path, columns=columns, dtype=dtype, batch_size=batch_size):
        for raw_row, raw_values in zip(row_numbers.tolist(), block):
            raw_row = int(raw_row)
            local_row = row_map.get(raw_row)
            if local_row is None:
                continue
            nonzero = np.flatnonzero(raw_values)
            if len(nonzero) == 0:
                continue
            rows.append(np.full(len(nonzero), local_row, dtype=np.int32))
            cols.append(nonzero.astype(np.int32, copy=False))
            values.append(raw_values[nonzero].astype(dtype, copy=False))

    return _coo_from_triplets(rows, cols, values, shape=(len(row_map), len(columns)), dtype=dtype)


def _sparse_dataframe(matrix: sparse.csr_matrix, index, columns) -> pd.DataFrame:
    """Wrap a SciPy sparse matrix in a pandas sparse dataframe."""
    return pd.DataFrame.sparse.from_spmatrix(matrix, index=index, columns=columns).fillna(0.0)


def _dense_frame(data: np.ndarray, index, columns) -> pd.DataFrame:
    """Wrap a dense numpy array in a dataframe without altering the dtype."""
    return pd.DataFrame(data, index=index, columns=columns, copy=False)


def _empty_satellite_payload(
    activity_axis: pd.MultiIndex,
    commodity_axis: pd.MultiIndex,
    final_demand_axis: pd.MultiIndex,
    dtype: np.dtype,
) -> tuple[pd.Index, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return placeholder zero-valued satellite blocks when no TQ/YQ files exist."""
    satellite_axis = pd.Index([GLORIA_SATELLITE_PLACEHOLDER], name=None)
    units = pd.DataFrame({"unit": [GLORIA_SATELLITE_UNIT]}, index=satellite_axis)
    zero_ea = _sparse_dataframe(
        sparse.csr_matrix((len(satellite_axis), len(activity_axis)), dtype=dtype),
        satellite_axis,
        activity_axis,
    )
    zero_ec = _sparse_dataframe(
        sparse.csr_matrix((len(satellite_axis), len(commodity_axis)), dtype=dtype),
        satellite_axis,
        commodity_axis,
    )
    zero_ey = _sparse_dataframe(
        sparse.csr_matrix((len(satellite_axis), len(final_demand_axis)), dtype=dtype),
        satellite_axis,
        final_demand_axis,
    )
    return satellite_axis, units, zero_ea, zero_ec, zero_ey


def parse_gloria_sut(
    path: str | Path,
    *,
    valuation: str | int = "basic",
    year: int | None = None,
    regions: str | list[str] | tuple[str, ...] | None = None,
    satellites: str | list[str] | tuple[str, ...] | None = "all",
    dtype: str | np.dtype = np.float32,
    layout: GloriaLayout | None = None,
    metadata: GloriaMetadata | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], GloriaLayout]:
    """Parse one GLORIA SUT release into split-native MARIO blocks.

    The GLORIA backend streams the very wide raw csv files in chunks and
    constructs split-native MARIO blocks without materializing the full raw
    matrices in memory.
    """
    if layout is None or metadata is None:
        layout, metadata = detect_gloria_layout(path, valuation=valuation, year=year)
    dtype = np.dtype(dtype)

    selected_positions, selected_codes = _normalize_region_selection(metadata, regions)
    if selected_codes != list(metadata.region_codes):
        log_time(logger, f"Parser: restricting GLORIA parsing to regions {selected_codes}.", "info")
    satellite_positions, satellite_axis, satellite_units = _select_gloria_satellites(metadata, satellites)
    if len(satellite_positions) != len(metadata.satellite_names):
        log_time(
            logger,
            f"Parser: restricting GLORIA satellites to {len(satellite_positions)} rows from request {satellites}.",
            "info",
        )

    sector_count = len(metadata.sector_names)
    factor_count = len(metadata.factor_names)
    final_demand_count = len(metadata.final_demand_names)
    satellite_row_map = {raw_row: local_row for local_row, raw_row in enumerate(satellite_positions)}

    activity_positions = _activity_positions(selected_positions, sector_count)
    commodity_positions = _commodity_positions(selected_positions, sector_count)
    final_demand_positions = _final_demand_positions(selected_positions, final_demand_count)
    activity_row_map, commodity_row_map = _row_maps(selected_positions, sector_count)

    activity_axis, commodity_axis, final_demand_axis, factor_axis, satellite_axis = _build_axes(
        selected_codes,
        metadata.sector_names,
        metadata.factor_names,
        metadata.final_demand_names,
        tuple(satellite_axis.tolist()),
    )

    if len(commodity_axis) * len(activity_axis) * dtype.itemsize > 1_500_000_000:
        log_time(
            logger,
            (
                "Parser: GLORIA use block is very large; parsing all regions may require several GB of RAM. "
                "Consider the regions=... argument for smaller subsets."
            ),
            "warning",
        )

    log_time(logger, f"Parser: reading GLORIA transactions from {layout.T_path.name} in CSV chunks.", "info")
    S_matrix, U_data = _read_transaction_blocks(
        layout.T_path,
        activity_columns=activity_positions,
        commodity_columns=commodity_positions,
        activity_row_map=activity_row_map,
        commodity_row_map=commodity_row_map,
        s_shape=(len(activity_axis), len(commodity_axis)),
        u_shape=(len(commodity_axis), len(activity_axis)),
        dtype=dtype,
    )

    log_time(logger, f"Parser: reading GLORIA final demand from {layout.Y_path.name} in CSV chunks.", "info")
    Ya_matrix, Yc_data = _read_final_demand_blocks(
        layout.Y_path,
        final_demand_columns=final_demand_positions,
        activity_row_map=activity_row_map,
        commodity_row_map=commodity_row_map,
        ya_shape=(len(activity_axis), len(final_demand_axis)),
        yc_shape=(len(commodity_axis), len(final_demand_axis)),
        dtype=dtype,
    )

    log_time(logger, f"Parser: reading GLORIA value added from {layout.V_path.name} in CSV chunks.", "info")
    Va_data, Vc_matrix = _read_value_added_blocks(
        layout.V_path,
        activity_columns=activity_positions,
        commodity_columns=commodity_positions,
        factor_count=factor_count,
        selected_positions=selected_positions,
        va_shape=(len(factor_axis), len(activity_axis)),
        vc_shape=(len(factor_axis), len(commodity_axis)),
        dtype=dtype,
    )

    if layout.TQ_path is not None and layout.YQ_path is not None:
        log_time(
            logger,
            (
                "Parser: reading GLORIA satellite accounts from "
                f"{layout.TQ_path.name} and {layout.YQ_path.name} in CSV chunks."
            ),
            "info",
        )
        Ea_matrix, Ec_matrix = _read_satellite_transaction_blocks(
            layout.TQ_path,
            activity_columns=activity_positions,
            commodity_columns=commodity_positions,
            row_map=satellite_row_map,
            dtype=dtype,
        )
        EY_matrix = _read_sparse_all_rows(
            layout.YQ_path,
            columns=final_demand_positions,
            row_map=satellite_row_map,
            dtype=dtype,
        )
        Ea = _sparse_dataframe(Ea_matrix, satellite_axis, activity_axis)
        Ec = _sparse_dataframe(Ec_matrix, satellite_axis, commodity_axis)
        EY = _sparse_dataframe(EY_matrix, satellite_axis, final_demand_axis)
    else:
        if layout.satellite_root is None:
            log_time(logger, "Parser: no GLORIA satellite-account directory found; using empty extensions.", "info")
        satellite_axis, satellite_units, Ea, Ec, EY = _empty_satellite_payload(
            activity_axis,
            commodity_axis,
            final_demand_axis,
            dtype,
        )

    S = _sparse_dataframe(S_matrix, activity_axis, commodity_axis)
    U = _dense_frame(U_data, commodity_axis, activity_axis)
    Ya = _sparse_dataframe(Ya_matrix, activity_axis, final_demand_axis)
    Yc = _dense_frame(Yc_data, commodity_axis, final_demand_axis)
    Va = _dense_frame(Va_data, factor_axis, activity_axis)
    Vc = _sparse_dataframe(Vc_matrix, factor_axis, commodity_axis)

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

    units = {
        _MASTER_INDEX["a"]: pd.DataFrame({"unit": [GLORIA_MONETARY_UNIT] * sector_count}, index=list(metadata.sector_names)),
        _MASTER_INDEX["c"]: pd.DataFrame({"unit": [GLORIA_MONETARY_UNIT] * sector_count}, index=list(metadata.sector_names)),
        _MASTER_INDEX["f"]: pd.DataFrame({"unit": [GLORIA_MONETARY_UNIT] * factor_count}, index=list(metadata.factor_names)),
        _MASTER_INDEX["k"]: satellite_units,
    }
    indeces = {
        "r": {"main": selected_codes},
        "a": {"main": list(metadata.sector_names)},
        "c": {"main": list(metadata.sector_names)},
        "s": {"main": list(metadata.sector_names)},
        "f": {"main": list(metadata.factor_names)},
        "n": {"main": list(metadata.final_demand_names)},
        "k": {"main": list(satellite_axis)},
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: GLORIA SUT parsed with "
            f"{len(selected_codes)} regions, {sector_count} sectors, {factor_count} value-added rows "
            f"and {len(satellite_axis)} satellite rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout
