"""Downloader helpers for selected MARIO-supported datasets.

The functions in this module are intentionally selective. MARIO only ships
automatic download helpers when the source is stable enough to be worth
supporting directly.
"""

from __future__ import annotations

from email.message import Message
import io
from pathlib import Path
import re
import shutil
import zipfile

import requests

from mario.log_exc.exceptions import NotImplementable, Rewrite, WrongInput
from mario.parsers.specs import (
    EMERGING_V1_CONCEPT_DOI,
    EMERGING_V1_RECORD_ID,
    EMERGING_V1_ZENODO_URL,
    EUROSTAT_IOT_DATAFLOWS,
    EUROSTAT_IOT_MODES,
    EUROSTAT_SDMX_BASE_URL,
    EUROSTAT_SUT_DATAFLOWS,
    EUROSTAT_SUT_UNITS,
    EXIOBASE_HYBRID_3318_RECORD_ID,
    EXIOBASE_HYBRID_3318_SOURCE,
    EXIOBASE_HYBRID_3318_ZENODO_URL,
    EXIOBASE_MONETARY_ZENODO_RECORDS,
    FIGARO_SOURCE,
    OECD_ICIO_SOURCE_URL,
    STATCAN_TABLES,
    STATCAN_WDS_BASE_URL,
    WIOD_2016_RELEASE_URL,
    WIOD_IOT_FILE_URL,
    WIOD_SUT_FILE_URL,
)

__all__ = [
    "download_eurostat",
    "download_statcan",
    "download_figaro",
    "download_wiod2016",
    "download_emerging",
    "download_hybrid_exiobase",
    "download_exiobase3",
    "download_exiobase_monetary",
    "download_oecd_icio",
    "download_gloria",
    "download_adb",
]


_ZENODO_API = "https://zenodo.org/api/records/{record_id}"
_REQUEST_TIMEOUT = 120
_WIOD_URLS = {"IOT": WIOD_IOT_FILE_URL, "SUT": WIOD_SUT_FILE_URL}
_HYBRID_REQUIRED_FILES = {
    "SUT": (
        "MR_HSUP_2011_v3_3_18.csv",
        "MR_HUSE_2011_v3_3_18.csv",
        "MR_HSUTs_2011_v3_3_18_FD.csv",
        "MR_HSUTs_2011_v3_3_18_extensions.xlsx",
        "MR_HIOT_2011_v3_3_18_extensions.xlsx",
        "Classifications_v_3_3_18.xlsx",
    ),
    "IOT": (
        "MR_HIOT_2011_v3_3_18_by_product_technology.csv",
        "MR_HIOT_2011_v3_3_18_FD.csv",
        "MR_HIOT_2011_v3_3_18_principal_production.csv",
        "MR_HIOT_2011_v3_3_18_extensions.xlsx",
        "Classifications_v_3_3_18.xlsx",
    ),
}


def _coerce_years(years) -> list[int]:
    """Normalize one year selection to a sorted list of unique integers."""
    if years is None:
        raise WrongInput("'years' should be provided explicitly.")

    if isinstance(years, int):
        values = [years]
    else:
        try:
            values = list(years)
        except TypeError as exc:
            raise WrongInput("'years' should be an int or an iterable of ints.") from exc

    normalized: list[int] = []
    for value in values:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError) as exc:
            raise WrongInput(f"Invalid year value: {value!r}") from exc

    return sorted(dict.fromkeys(normalized))


def _ensure_directory(path: str | Path) -> Path:
    """Create one directory when needed and return it as a ``Path``."""
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _reset_target(path: Path, *, overwrite: bool) -> None:
    """Ensure one destination path can be written safely."""
    if not path.exists():
        return

    if not overwrite:
        raise Rewrite(f"{path} already exists. Pass overwrite=True to replace it.")

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _iter_content(response: requests.Response, *, chunk_size: int = 1024 * 1024):
    """Yield non-empty response chunks."""
    for chunk in response.iter_content(chunk_size=chunk_size):
        if chunk:
            yield chunk


def _download_to_path(url: str, destination: Path, *, overwrite: bool) -> Path:
    """Download one remote file to ``destination``."""
    if destination.exists() and not overwrite:
        return destination
    _reset_target(destination, overwrite=overwrite)
    destination.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, stream=True, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()
    with destination.open("wb") as stream:
        for chunk in _iter_content(response):
            stream.write(chunk)
    response.close()
    return destination


def _download_json(url: str) -> dict[str, object]:
    """Download one JSON document."""
    response = requests.get(url, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _zenodo_record(record_id: str) -> dict[str, object]:
    """Fetch one Zenodo record payload."""
    return _download_json(_ZENODO_API.format(record_id=record_id))


def _zenodo_files(record_id: str) -> dict[str, dict[str, object]]:
    """Return Zenodo files keyed by their original filename."""
    data = _zenodo_record(record_id)
    return {item["key"]: item for item in data.get("files", [])}


def _flatten_single_subdirectory(path: Path) -> Path:
    """Flatten one extraction directory when it only contains one nested folder."""
    children = list(path.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        return path

    nested = children[0]
    for item in nested.iterdir():
        shutil.move(str(item), path / item.name)
    nested.rmdir()
    return path


def _extract_zip(archive_path: Path, extract_dir: Path, *, overwrite: bool, keep_archive: bool) -> Path:
    """Extract one zip archive into a dedicated directory."""
    if extract_dir.exists() and not overwrite:
        if not keep_archive and archive_path.exists():
            archive_path.unlink()
        return extract_dir
    _reset_target(extract_dir, overwrite=overwrite)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(extract_dir)

    _flatten_single_subdirectory(extract_dir)
    if not keep_archive:
        archive_path.unlink()
    return extract_dir


def _content_disposition_filename(header: str | None) -> str | None:
    """Parse a filename from a Content-Disposition header."""
    if not header:
        return None

    message = Message()
    message["content-disposition"] = header
    filename = message.get_filename()
    if filename:
        return filename

    match = re.search(r'filename="?([^";]+)"?', header)
    return match.group(1) if match else None


def _download_zenodo_selection(
    *,
    record_id: str,
    root: Path,
    file_names: list[str],
    overwrite: bool,
) -> list[Path]:
    """Download selected files from one Zenodo record into ``root``."""
    files = _zenodo_files(record_id)
    missing = sorted(set(file_names).difference(files))
    if missing:
        raise WrongInput(
            f"Zenodo record {record_id} does not contain the requested files: {missing}"
        )

    downloaded: list[Path] = []
    for file_name in file_names:
        item = files[file_name]
        destination = root / file_name
        downloaded.append(
            _download_to_path(item["links"]["self"], destination, overwrite=overwrite)
        )
    return downloaded


def _eurostat_sut_key(country: str, unit: str) -> str:
    """Return the wildcard SDMX key used by Eurostat SUT downloads."""
    return f"A.{unit}.TOTAL...{country}"


def _eurostat_iot_key(country: str, unit: str, mode: str) -> str:
    """Return the wildcard SDMX key used by Eurostat IOT downloads."""
    if mode == "industry":
        return f"A.{unit}...TOTAL.{country}"
    return f"A.{unit}.TOTAL...{country}"


def _eurostat_local_paths(
    root: str | Path,
    *,
    country: str,
    year: int,
    table: str,
    unit: str,
    iot_mode: str,
) -> dict[str, Path]:
    """Return deterministic local file paths for one Eurostat raw slice."""
    base = _ensure_directory(root)
    geo = str(country).upper()
    table = table.upper()

    if table == "SUT":
        return {
            "supply": base / f"{EUROSTAT_SUT_DATAFLOWS['supply']}_{geo}_{year}_{unit}.csv",
            "use": base / f"{EUROSTAT_SUT_DATAFLOWS['use']}_{geo}_{year}_{unit}.csv",
        }

    return {
        "iot": base
        / f"{EUROSTAT_IOT_DATAFLOWS[iot_mode]}_{geo}_{year}_{unit}_{iot_mode}.csv"
    }


def _statcan_local_csv_path(root: str | Path, *, table: str, level: str) -> Path:
    """Return the deterministic local CSV path for one StatCan full table."""
    table = table.upper()
    pid = STATCAN_TABLES[table][level]["pid"]
    return _ensure_directory(root) / f"statcan_{pid}_{table.lower()}_{level}.csv"


def download_eurostat(
    path: str | Path,
    *,
    country: str,
    year: int,
    table: str = "SUT",
    iot_mode: str = "product",
    unit: str = "MIO_EUR",
    timeout: int = 60,
    overwrite: bool = False,
) -> dict[str, object]:
    """Download one Eurostat SDMX slice to local CSV files."""
    table = table.upper()
    if table not in {"SUT", "IOT"}:
        raise WrongInput("'table' should be either 'SUT' or 'IOT'.")
    if unit not in EUROSTAT_SUT_UNITS:
        raise WrongInput(f"'unit' should be one of {list(EUROSTAT_SUT_UNITS)}.")
    if table == "IOT" and iot_mode not in EUROSTAT_IOT_MODES:
        raise WrongInput(f"'iot_mode' should be one of {list(EUROSTAT_IOT_MODES)}.")

    geo = str(country).upper()
    local_paths = _eurostat_local_paths(
        path,
        country=geo,
        year=year,
        table=table,
        unit=unit,
        iot_mode=iot_mode,
    )

    downloads: dict[str, str] = {}
    if table == "SUT":
        targets = {
            "supply": (
                EUROSTAT_SUT_DATAFLOWS["supply"],
                _eurostat_sut_key(geo, unit),
                local_paths["supply"],
            ),
            "use": (
                EUROSTAT_SUT_DATAFLOWS["use"],
                _eurostat_sut_key(geo, unit),
                local_paths["use"],
            ),
        }
    else:
        targets = {
            "iot": (
                EUROSTAT_IOT_DATAFLOWS[iot_mode],
                _eurostat_iot_key(geo, unit, iot_mode),
                local_paths["iot"],
            )
        }

    for label, (dataflow, key, destination) in targets.items():
        if destination.exists() and not overwrite:
            downloads[label] = str(destination)
            continue
        url = f"{EUROSTAT_SDMX_BASE_URL}/{dataflow}/{key}"
        response = requests.get(
            url,
            params={"startPeriod": year, "endPeriod": year, "format": "SDMX-CSV"},
            timeout=timeout,
        )
        response.raise_for_status()
        _reset_target(destination, overwrite=overwrite)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(response.text)
        response.close()
        downloads[label] = str(destination)

    return {
        "table": table,
        "country": geo,
        "year": int(year),
        "unit": unit,
        "iot_mode": iot_mode if table == "IOT" else None,
        "files": downloads,
    }


def download_statcan(
    path: str | Path,
    *,
    table: str = "SUT",
    level: str = "summary",
    timeout: int = 60,
    overwrite: bool = False,
) -> dict[str, object]:
    """Download one StatCan full-table CSV to a local file."""
    table = table.upper()
    try:
        spec = STATCAN_TABLES[table][level]
    except KeyError as exc:
        raise WrongInput("Invalid StatCan table/level combination.") from exc

    destination = _statcan_local_csv_path(path, table=table, level=level)
    if destination.exists() and not overwrite:
        return {"table": table, "level": level, "pid": spec["pid"], "csv": str(destination)}

    meta_url = f"{STATCAN_WDS_BASE_URL}/getFullTableDownloadCSV/{spec['pid']}/en"
    response = requests.get(meta_url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "SUCCESS" or "object" not in payload:
        raise WrongInput(
            f"Statistics Canada did not return a downloadable CSV for table {spec['pid']}."
        )

    csv_url = str(payload["object"])
    with requests.get(csv_url, timeout=timeout, stream=True) as zip_response:
        zip_response.raise_for_status()
        archive_bytes = b"".join(_iter_content(zip_response))

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        csv_members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv") and "metadata" not in name.casefold()
        ]
        if not csv_members:
            raise WrongInput(
                f"Statistics Canada ZIP payload for table {spec['pid']} contains no CSV table."
            )
        with archive.open(csv_members[0]) as csv_stream:
            content = csv_stream.read()

    if destination.exists() and overwrite:
        _reset_target(destination, overwrite=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)

    return {"table": table, "level": level, "pid": spec["pid"], "csv": str(destination)}


def download_figaro(*args, **kwargs):
    """FIGARO automatic download is intentionally not supported.

    The current FIGARO parser is file-based and expects locally downloaded
    flat files. Use the documented CIRCABC links instead.
    """
    raise NotImplementable(
        "Automatic FIGARO download is intentionally not supported. "
        f"Use the CIRCABC links documented in the parser docs/specs ({FIGARO_SOURCE})."
    )


def download_wiod2016(
    path: str | Path,
    table: str = "IOT",
    *,
    extract: bool = True,
    keep_archive: bool = False,
    overwrite: bool = False,
) -> dict[str, object]:
    """Download one WIOD 2016 multiregional workbook from the official release links.

    Parameters
    ----------
    path : str or Path
        destination directory where the downloaded archive and extracted files
        should be stored.
    table : str, optional
        one of ``"IOT"`` or ``"SUT"``.
    extract : bool, optional
        when ``True`` extract the downloaded zip archive.
    keep_archive : bool, optional
        when ``extract=True``, keep the zip archive after extraction.
    overwrite : bool, optional
        overwrite existing files/directories when present.
    """
    if table not in _WIOD_URLS:
        raise WrongInput("'table' should be either 'IOT' or 'SUT'.")

    root = _ensure_directory(path)
    filename = "WIOTS_in_EXCEL.zip" if table == "IOT" else "SUT_international.zip"
    archive_path = root / filename
    extracted_path = None
    workbooks: list[str] = []
    if extract:
        extract_dir = root / archive_path.stem
        if extract_dir.exists() and not overwrite:
            extracted_path = str(extract_dir)
            workbooks = sorted(str(item) for item in extract_dir.rglob("*.xlsb"))
            return {
                "source": WIOD_2016_RELEASE_URL,
                "table": table,
                "archive": str(archive_path) if archive_path.exists() else None,
                "extracted_path": extracted_path,
                "workbooks": workbooks,
            }
    elif archive_path.exists() and not overwrite:
        return {
            "source": WIOD_2016_RELEASE_URL,
            "table": table,
            "archive": str(archive_path),
            "extracted_path": None,
            "workbooks": [],
        }

    response = requests.get(
        _WIOD_URLS[table],
        stream=True,
        timeout=_REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    header_filename = _content_disposition_filename(
        response.headers.get("content-disposition")
    )
    if header_filename and header_filename != filename:
        archive_path = root / header_filename
    _reset_target(archive_path, overwrite=overwrite)
    with archive_path.open("wb") as stream:
        for chunk in _iter_content(response):
            stream.write(chunk)
    response.close()

    if extract and archive_path.suffix.lower() == ".zip":
        extract_dir = root / archive_path.stem
        extracted = _extract_zip(
            archive_path,
            extract_dir,
            overwrite=overwrite,
            keep_archive=keep_archive,
        )
        extracted_path = str(extracted)
        workbooks = sorted(str(item) for item in extracted.rglob("*.xlsb"))

    return {
        "source": WIOD_2016_RELEASE_URL,
        "table": table,
        "archive": str(archive_path) if archive_path.exists() else None,
        "extracted_path": extracted_path,
        "workbooks": workbooks,
    }


def download_emerging(
    path: str | Path,
    *,
    version: str = "1.0",
    overwrite: bool = False,
) -> dict[str, object]:
    """Download the EMERGING Zenodo bundle supported by MARIO.

    At the moment MARIO only targets the accessible v1.0 bundle. The concept
    DOI is ``10.5281/zenodo.14258421``, but the actual downloadable versioned
    record used by MARIO is ``10.5281/zenodo.14258422``.
    """
    if version != "1.0":
        raise NotImplementable("Only EMERGING v1.0 is currently supported for automatic download.")

    root = _ensure_directory(path)
    files = _zenodo_files(EMERGING_V1_RECORD_ID)
    downloaded: list[Path] = []
    for file_name, item in files.items():
        downloaded.append(
            _download_to_path(item["links"]["self"], root / file_name, overwrite=overwrite)
        )

    return {
        "source": EMERGING_V1_CONCEPT_DOI,
        "version_record": EMERGING_V1_ZENODO_URL,
        "download_dir": str(root),
        "files": [str(item) for item in downloaded],
    }


def download_hybrid_exiobase(
    path: str | Path,
    table: str = "all",
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    """Download the EXIOBASE hybrid v3.3.18 files needed by MARIO.

    Parameters
    ----------
    path : str or Path
        destination directory where the selected files should be stored.
    table : str, optional
        choose ``"SUT"``, ``"IOT"`` or ``"all"``. MARIO downloads only the
        files required by the corresponding parser branch.
    overwrite : bool, optional
        overwrite existing files when present.
    """
    table = table.upper()
    if table not in {"SUT", "IOT", "ALL"}:
        raise WrongInput("'table' should be one of 'SUT', 'IOT' or 'all'.")

    root = _ensure_directory(path)
    if table == "ALL":
        requested = sorted(set(_HYBRID_REQUIRED_FILES["SUT"]).union(_HYBRID_REQUIRED_FILES["IOT"]))
    else:
        requested = list(_HYBRID_REQUIRED_FILES[table])

    downloaded = _download_zenodo_selection(
        record_id=EXIOBASE_HYBRID_3318_RECORD_ID,
        root=root,
        file_names=requested,
        overwrite=overwrite,
    )

    return {
        "source": EXIOBASE_HYBRID_3318_SOURCE,
        "record": EXIOBASE_HYBRID_3318_ZENODO_URL,
        "table": table,
        "download_dir": str(root),
        "files": [str(item) for item in downloaded],
    }


def download_exiobase3(
    path: str | Path,
    *,
    years,
    system: str | None = "ixi",
    table: str = "IOT",
    version: str = "3.8.2",
    extract: bool = True,
    keep_archives: bool = False,
    overwrite: bool = False,
) -> dict[str, object]:
    """Download a selected monetary EXIOBASE 3 release from Zenodo.

    Parameters
    ----------
    path : str or Path
        destination directory where downloaded archives and extracted folders
        should be stored.
    years : int or iterable of int
        years to download.
    system : str, optional
        required for ``table="IOT"``. One of ``"ixi"`` or ``"pxp"``.
    table : str, optional
        one of ``"IOT"`` or ``"SUT"``.
    version : str, optional
        one of ``"3.10.1"``, ``"3.9.6"``, ``"3.9.5"``, ``"3.9.4"`` or
        ``"3.8.2"``.
    extract : bool, optional
        when ``True`` extract zip archives after download.
    keep_archives : bool, optional
        when extracting, keep the downloaded zip archives.
    overwrite : bool, optional
        overwrite existing files/directories when present.
    """
    if version not in EXIOBASE_MONETARY_ZENODO_RECORDS:
        raise WrongInput(
            f"Unsupported EXIOBASE monetary version: {version}. "
            f"Valid options are: {sorted(EXIOBASE_MONETARY_ZENODO_RECORDS)}"
        )

    table = table.upper()
    record_info = EXIOBASE_MONETARY_ZENODO_RECORDS[version]
    if table not in record_info["tables"]:
        raise NotImplementable(
            f"EXIOBASE {version} automatic download supports only {record_info['tables']}."
        )

    normalized_years = _coerce_years(years)
    if table == "IOT":
        if system is None:
            raise WrongInput("'system' should be provided for IOT downloads.")
        system = system.lower()
        if system not in {"ixi", "pxp"}:
            raise WrongInput("'system' should be either 'ixi' or 'pxp'.")
        file_names = [f"IOT_{year}_{system}.zip" for year in normalized_years]
    else:
        file_names = [f"MRSUT_{year}.zip" for year in normalized_years]

    root = _ensure_directory(path)
    downloaded = _download_zenodo_selection(
        record_id=record_info["record_id"],
        root=root,
        file_names=file_names,
        overwrite=overwrite,
    )

    extracted: list[str] = []
    if extract:
        for archive_path in downloaded:
            extract_dir = root / archive_path.stem
            extracted_dir = _extract_zip(
                archive_path,
                extract_dir,
                overwrite=overwrite,
                keep_archive=keep_archives,
            )
            extracted.append(str(extracted_dir))

    return {
        "source": record_info["doi"],
        "version": version,
        "table": table,
        "system": system if table == "IOT" else None,
        "years": normalized_years,
        "download_dir": str(root),
        "archives": [str(item) for item in downloaded if item.exists()],
        "extracted": extracted,
    }


def download_exiobase_monetary(*args, **kwargs):
    """Alias for :func:`download_exiobase3`."""
    return download_exiobase3(*args, **kwargs)


def download_oecd_icio(*args, **kwargs):
    """OECD ICIO automatic download is intentionally not supported."""
    raise NotImplementable(
        "Automatic OECD ICIO download is intentionally not supported. "
        f"Use the official dataset page instead ({OECD_ICIO_SOURCE_URL})."
    )


def download_gloria(*args, **kwargs):
    """GLORIA automatic download is intentionally not supported."""
    raise NotImplementable(
        "Automatic GLORIA download is intentionally not supported because the source requires login."
    )


def download_adb(*args, **kwargs):
    """ADB automatic download is intentionally not supported."""
    raise NotImplementable(
        "Automatic ADB download is intentionally not supported. Download the workbook manually from the official ADB page."
    )
