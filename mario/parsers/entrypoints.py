# -*- coding: utf-8 -*-
"""Parser entry points that return ``mario.Database`` objects."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from mario.api import Database
from mario.download import (
    _eurostat_local_paths,
    _statcan_local_csv_path,
    _statcan_openio_local_xlsx_path,
    download_exiobase3,
    download_eurostat,
    download_hybrid_exiobase,
    download_istat_io,
    download_statcan,
    download_statcan_openio_canada,
)
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.parsers.api import (
    build_database_from_state,
    validate_named_selection,
    validate_parse_request,
)
from mario.parsers.adb import parse_adb_iot
from mario.parsers.bea import parse_bea_sut
from mario.parsers.cepalstat import parse_cepalstat_iot, parse_cepalstat_sut
from mario.parsers.ceads import parse_ceads_iot
from mario.parsers.emerging import parse_emerging_iot
from mario.parsers.excel import parse_state_from_excel
from mario.parsers.parquet import parse_state_from_parquet
from mario.parsers.txt import parse_state_from_txt
from mario.parsers.exiobase_hybrid import (
    parse_exiobase_hybrid_iot,
    parse_exiobase_hybrid_sut,
)
from mario.parsers.exiobase_iot import parse_exiobase_iot_monetary
from mario.parsers.exiobase_sut import parse_exiobase_sut_monetary
from mario.parsers.eora import parse_eora_single_region, parse_eora26
from mario.parsers.eurostat_sdmx import (
    parse_eurostat_iot_sdmx,
    parse_eurostat_sut_sdmx,
)
from mario.parsers.figaro import parse_figaro_iot, parse_figaro_sut
from mario.parsers.gloria import (
    detect_gloria_layout,
    parse_gloria_sut,
    _normalize_satellite_request as _normalize_gloria_satellites,
    _select_gloria_satellites,
)
from mario.parsers.gtap import (
    parse_gtap_mrio_csv,
    parse_gtap_mrio_gdx,
)
from mario.parsers.istat import parse_istat_iot, parse_istat_sut
from mario.parsers.oecd_icio import parse_oecd_icio
from mario.parsers.oecd_iot import parse_oecd_iot_total
from mario.parsers.oecd_sdmx import parse_oecd_sut_sdmx
from mario.parsers.statcan_wds import parse_statcan_iot_wds, parse_statcan_sut_wds
from mario.parsers.tabular import parse_pymrio
from mario.parsers.handshake import parse_exiobase_3_9_4
from mario.parsers.useeio import parse_useeio_sut
from mario.parsers.wiod import parse_wiod_iot, parse_wiod_sut

from mario.parsers.specs import (
    HMRSUT_EXTENSIONS,
    HMIOT_EXTENSIONS,
    INPUT_OPTIONS,
    FIGARO_IOT_MODES,
    FIGARO_IOT_IXI_URL,
    FIGARO_IOT_PXP_URL,
    FIGARO_SUPPLY_URL,
    FIGARO_USE_URL,
    EUROSTAT_IOT_MODES,
    EUROSTAT_SUT_UNITS,
    GTAP_INPUT_FORMATS,
    GTAP_LAYOUTS,
    GTAP_VARIANTS,
    ISTAT_IOT_MODES,
    ISTAT_SUT_LEVELS,
    ISTAT_SUT_PRICES,
    ISTAT_SUT_VALUATIONS,
    CEPALSTAT_IOT_MODES,
    CEADS_FORMATS,
    BEA_LEVELS,
    USEEIO_FORMATS,
    STATCAN_TABLES,
    STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT,
    STATCAN_OPENIO_CANADA_SOURCE,
    STATCAN_VALUATIONS,
)
import pandas as pd

models = {"Database": Database}
logger = logging.getLogger(__name__)
_GLORIA_CACHE_VERSION = "2026-03-25"


def _normalize_gloria_regions(regions):
    """Normalize a region selector into a stable list used for cache keys."""
    if regions is None or regions == "all":
        return "all"
    if isinstance(regions, str):
        return [regions]
    return list(regions)


def _gloria_cache_satellites(satellites):
    """Normalize a satellite selector into a stable cache payload."""
    return _normalize_gloria_satellites(satellites)


def _gloria_cache_signature(layout, *, regions, satellites, dtype):
    """Build a deterministic signature for one GLORIA parse request."""
    file_inputs = []
    for candidate in [layout.T_path, layout.Y_path, layout.V_path, layout.TQ_path, layout.YQ_path]:
        if candidate is None:
            continue
        stats = candidate.stat()
        file_inputs.append(
            {
                "path": str(candidate),
                "size": stats.st_size,
                "mtime_ns": stats.st_mtime_ns,
            }
        )

    payload = {
        "version": _GLORIA_CACHE_VERSION,
        "table": "SUT",
        "year": layout.year,
        "release": layout.release,
        "markup": layout.markup,
        "valuation": layout.valuation_name,
        "dtype": str(dtype),
        "regions": _normalize_gloria_regions(regions),
        "satellites": _gloria_cache_satellites(satellites),
        "files": file_inputs,
    }
    encoded = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _default_gloria_cache_dir(layout, *, regions, satellites, dtype):
    """Return the default on-disk cache directory for one GLORIA parse request."""
    region_part = _normalize_gloria_regions(regions)
    if isinstance(region_part, list):
        region_token = "-".join(region_part)
    else:
        region_token = region_part
    satellite_part = _gloria_cache_satellites(satellites)
    if isinstance(satellite_part, list):
        satellite_token = "-".join(satellite_part)
    else:
        satellite_token = satellite_part
    safe_region_token = (region_token or "all").replace("/", "_").replace(" ", "_")
    safe_satellite_token = (satellite_token or "all").replace("/", "_").replace(" ", "_").replace("|", "_")
    return (
        Path(layout.root)
        / ".mario_cache"
        / f"gloria_sut_{layout.year}_{layout.release}_{layout.markup:03d}_{safe_region_token}_{safe_satellite_token}_{dtype}"
    )


def _read_json_file(path: Path) -> dict:
    """Read one small json file from disk."""
    with path.open("r") as stream:
        return json.load(stream)


def _write_json_file(path: Path, payload: dict) -> None:
    """Write one small json file to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)


def _build_gloria_database(
    *,
    matrices,
    indeces,
    units,
    layout,
    model,
    name,
    calc_all,
    notes,
    kwargs,
):
    """Build the public database returned by ``parse_gloria``."""
    return models[model](
        name=name or layout.dataset_name,
        table="SUT",
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        notes=list(notes),
        **kwargs,
    )

def parse_from_txt(
    path: str,
    table: str,
    mode: str,
    calc_all: bool = False,
    year: int = None,
    name:str = None,
    source:str =None,
    model: str ="Database",
    sep: str = ",",
    _format: str | None = None,
    flat: bool = False,
    matrix_layouts: dict[str, object] | None = None,
    tech_assumption: str | None = None,
    **kwargs,
):
    """Parse a database from a folder of text or CSV files.

    .. note::

        This function works with different files to parse the IO data. Each
        matrix and the units table should be placed in separate delimited
        files.


    Parameters
    ----------
    path : str
        defined the folder that contains data files.

    table : str
        acceptable options are 'IOT' & 'SUT'

    mode : str
        defined the base matrices to parse. The options are:

            * `flows`: needs [Z.*, Y.*, EY.*, V.*, E.*, units.*] in the path
            * `coefficients`: needs [z.*, Y.*, EY.*, v.*, e.*, units.*] in the path

    calc_all : boolean
        if True, by default will calculate z,v,e,V,E,Z after parsing

    year : int, Optional
        optional to the Database (just for recoding the metadata)

    source : str, Optional
        optional to the Database (just for recoding the metadata)

    name : str, Optional
        optional but suggested. is useful for visualization and metadata.

    sep : str, Optional
        separator used in the delimited files.

    _format : str, Optional
        file extension to parse. Use ``"txt"`` or ``"csv"``.
        If omitted, MARIO autodetects the bundle format from the files found
        in ``path``.

    flat : bool, Optional
        if True, parse the canonical long-format MARIO text export made of one
        ``data`` file plus one ``units`` file, or one ``units`` file plus
        separate long-format files per matrix. Otherwise parse the historical
        matrix-per-file layout.
    matrix_layouts : dict, Optional
        optional per-matrix semantic layout declarations for IOT parsers.
        Accepted values are the same as in :func:`parse_from_excel`.

    Returns
    -------
    mario.Database
    """
    validate_parse_request(table=table, mode=mode, model=model)

    state = parse_state_from_txt(
        path=path,
        table=table,
        mode=mode,
        sep=sep,
        _format=_format,
        flat=flat,
        matrix_layouts=matrix_layouts,
        name=name,
        source=source,
        year=year,
        tech_assumption=tech_assumption,
    )
    return build_database_from_state(
        state,
        model=model,
        calc_all=calc_all,
        name=name,
        source=source,
        year=year,
        **kwargs,
    )


def parse_from_parquet(
    path: str,
    table: str,
    mode: str,
    calc_all: bool = False,
    year: int = None,
    name: str = None,
    source: str = None,
    model: str = "Database",
    flat: bool = False,
    matrix_layouts: dict[str, object] | None = None,
    tech_assumption: str | None = None,
    **kwargs,
):
    """Parse a database from a folder of parquet files.

    Parameters
    ----------
    path : str
        directory containing either one parquet file per matrix or one flat
        ``data.parquet`` plus ``units.parquet`` payload, or one
        ``units.parquet`` plus separate long-format parquet files per matrix.
    table : str
        acceptable options are 'IOT' & 'SUT'
    mode : str
        acceptable options are ``flows`` and ``coefficients``
    flat : bool, Optional
        if True, parse the canonical long-format MARIO parquet export, either
        as one combined ``data.parquet`` file or as separate long-format
        matrix files.
        Otherwise parse the matrix-per-file parquet layout.
    matrix_layouts : dict, Optional
        optional per-matrix semantic layout declarations for IOT parsers.
    """
    validate_parse_request(table=table, mode=mode, model=model)

    state = parse_state_from_parquet(
        path=path,
        table=table,
        mode=mode,
        flat=flat,
        matrix_layouts=matrix_layouts,
        name=name,
        source=source,
        year=year,
        tech_assumption=tech_assumption,
    )
    return build_database_from_state(
        state,
        model=model,
        calc_all=calc_all,
        name=name,
        source=source,
        year=year,
        **kwargs,
    )


def parse_from_excel(
    path: str,
    table: str,
    mode: str,
    data_sheet: str = 0,
    unit_sheet: str = "units",
    matrix_layouts: dict[str, object] | None = None,
    tech_assumption: str | None = None,
    calc_all: bool = False,
    year: int = None,
    name: str = None,
    source: str = None,
    model: str ="Database",
    **kwargs,
):
    """Parse a database from a single Excel workbook.

    .. note::

        * This function works with a a single excel that contains data & units
        * The table kind remains ``IOT`` or ``SUT``; ``matrix_layouts`` can be
          used to override the semantic layout of selected matrices
        * workbooks generated by ``mario.write_parse_template(...)`` are
          detected automatically; they do not need ``matrix_layouts``

    Parameters
    ----------
    path : str
        defined the excel file that contains data & units.

    table : str
        acceptable options are 'IOT' & 'SUT'

    mode : str
        defined the base matrices to parse. The options are:

            * `flows`: needs [Z, Y, EY, V, E,] in a singel sheet and unit in another sheet
            * `coefficients`: needs [z, Y, EY, v, e, units.txt] in a singel sheet and unit in another sheet

    data_sheet : str, int
        defines the sheet index/name which the data is located(by defualt the first sheet is considered)

    units_sheet : str,int
        defines the sheet index/name in which the units are located (by default in a sheet named units )

    matrix_layouts : dict, Optional
        optional per-matrix semantic layout declarations. Values can be:

            * a single set name, for example ``{\"E\": \"Region\"}``
            * a tuple/list of set names, for example ``{\"E\": (\"Region\", \"Sector\")}``

        Only canonical MARIO set names are accepted. Matrices omitted from the
        dictionary are treated as standard layouts.

    calc_all : boolean
        if True, by default will calculate z,v,e,Z,V,E after parsing

    year : int, Optional
        optional to the Database (just for recoding the metadata)

    source : str, Optional
        optional to the Database (just for recoding the metadata)

    name : str, Optional
        optional but suggested. is useful for visualization and metadata.

    Returns
    -------
    mario.Database
    """
    validate_parse_request(table=table, mode=mode, model=model)

    state = parse_state_from_excel(
        path=path,
        table=table,
        mode=mode,
        data_sheet=data_sheet,
        unit_sheet=unit_sheet,
        matrix_layouts=matrix_layouts,
        name=name,
        source=source,
        year=year,
        tech_assumption=tech_assumption,
    )
    return build_database_from_state(
        state,
        model=model,
        calc_all=calc_all,
        name=name,
        source=source,
        year=year,
        **kwargs,
    )


def parse_exiobase_sut(
    path: str,
    calc_all: bool =False,
    name: str = None,
    year: int = None,
    add_extensions: str | None = None,
    model: str = "Database",
    version: str | None = None,
    **kwargs,
):
    """Parse the monetary EXIOBASE SUT into a ``Database`` instance.

    .. note::

        The monetary SUT parser is currently tied to EXIOBASE ``3.8.2``
        (`Zenodo 5589597 <https://doi.org/10.5281/zenodo.5589597>`_).

    Parameters
    ----------
    path : str
        path to the EXIOBASE SUT directory

    calc_all : boolean
        if True, by default will calculate z,v,e after parsing

    year : int, Optional
        optional to the Database (just for recoding the metadata)

    add_extensions : str, Optional
        optional path to the corresponding EXIOBASE IOT. When provided, the
        parser reads only the IOT extension blocks and uses them to populate
        ``Ea`` and ``EY`` for the SUT.

    version : str, Optional
        optional compatibility check against the version detected from the
        dataset metadata and folder layout.

    name : str, Optional
        optional but suggested. is useful for visualization and metadata.

    Returns
    -------
    mario.Database
    """

    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    matrices, indeces, units, layout = parse_exiobase_sut_monetary(
        path,
        add_extensions=add_extensions,
    )
    if version is not None and layout.version != version:
        raise WrongInput(
            f"Requested EXIOBASE version {version!r} does not match detected version {layout.version!r}."
        )

    return models[model](
        name=name or layout.dataset_name,
        table="SUT",
        source=layout.source,
        year=year if year is not None else layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_exiobase_3(
    path: str,
    calc_all: bool =False,
    year: int = None,
    name: str = None,
    model: str = "Database",
    version: str | None = None,
    system: str | None = None,
    **kwargs,
):
    """Parse a monetary EXIOBASE IOT folder into a ``Database`` instance.

    .. note::

        The parser auto-detects the EXIOBASE layout from the folder contents and
        ``metadata.json``. The ``version`` argument is kept only as an optional
        compatibility check.

        Monetary IOT releases currently supported through MARIO include
        EXIOBASE ``3.8.2``, ``3.9.4``, ``3.9.5``, ``3.9.6``, and ``3.10.1``.

    Parameters
    ----------

    path : str
        path to the EXIOBASE IOT directory

    calc_all : boolean
        if True, by default will calculate z,v,e after parsing

    year : int, Optional
        optional to the Database (just for recoding the metadata)

    name : str, Optional
        optional but suggested. is useful for visualization and metadata.

    version : str, Optional
        optional compatibility check against the version detected from the
        dataset metadata and folder layout

    system : str, Optional
        optional compatibility check against the system detected from the
        dataset metadata and folder layout, typically ``"ixi"`` or ``"pxp"``.

    Returns
    -------
    mario.Database

    """

    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    matrices, indeces, units, layout = parse_exiobase_iot_monetary(
        path,
        version=version,
    )
    if system is not None and layout.system != str(system).lower():
        raise WrongInput(
            f"Requested EXIOBASE system {system!r} does not match detected system {layout.system!r}."
        )

    return models[model](
        name=name or layout.dataset_name,
        table="IOT",
        source=layout.source,
        year=year if year is not None else layout.year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )



def parse_eora(
    path: str,
    multi_region: bool,
    table: str | None = None,
    indeces: str = None,
    name_convention: str = "full_name",
    aggregate_trade: bool = True,
    year: int = None,
    name: str = None,
    calc_all: bool = False,
    model: str = "Database",
    country: str | None = None,
    price: str | None = None,
    **kwargs,
) -> object:
    """Parse EORA data into a ``Database`` instance.

    .. note::

        * for multi_region database, only `eora26` is acceptable
        * multi_region database has some inconsistencies that are modified when parsed.
        * to see the modifications after parsing call 'meta_history'

    Parameters
    ----------
    path : str
        path to one EORA file or dataset directory

    multi_region : bool
        True for eora26 else False

    table : str, Optional
        for multi-region datasets only ``IOT`` is supported. Single-region
        parsing can infer the table type automatically when omitted.

    indeces : str
        optional path to the Eora26 label files. If omitted, the parser looks
        for ``labels_*.txt`` files in ``path`` itself.

    name_convension : str
        will take the full names of countries if `full_name` otherwise, takes
        the abbreviations

    aggregate_trade : boolean
        if True, will aggregated all the trades into total imports and exports
        in single region database

    country : str, Optional
        when ``multi_region=False`` and ``path`` points to a directory, selects
        the country file to parse.

    price : str, Optional
        optional price filter for single-region folder parsing.

    year : int, Optional
        for recording on the metadata

    name : str, Optional
        for recording on the metadata

    calc_all : boolean
        if True, will calculate the main missing matrices

    Returns
    -------
    mario.Database
    """
    
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    if multi_region:
        if table is None:
            table = "IOT"
        elif table == "SUT":
            raise NotImplementedError(
                "No handling of multiregional SUT from EORA is implemented yet"
            )

        matrices, indeces, units, layout = parse_eora26(path, index_path=indeces)
        if year is not None and layout.year != year:
            raise WrongInput(
                f"The selected Eora26 dataset is for year {layout.year}, not {year}."
            )

        kwargs.setdefault("notes", list(layout.notes))
        year = layout.year if year is None else year
        source = layout.source
        name = name or layout.dataset_name
        price = layout.price

    else:
        matrices, indeces, units, layout = parse_eora_single_region(
            path=path,
            table=table,
            name_convention=name_convention,
            aggregate_trade=aggregate_trade,
            country=country,
            year=year,
            price=price,
        )
        if table is None:
            table = "SUT" if "a" in indeces else "IOT"
        year = layout.year if year is None else year
        source = layout.source
        name = name or layout.dataset_name
        price = layout.price

    return models[model](
        name=name,
        table=table,
        year=year,
        source=source,
        price=price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def _resolve_exiobase_parse_path(
    *,
    table: str,
    unit: str,
    path: str,
    year: int | None,
    download: bool,
    version: str | None,
    system: str | None,
) -> str:
    """Resolve the local path to parse, optionally downloading EXIOBASE first."""
    if not download:
        return path

    if unit == "Monetary":
        if year is None:
            raise WrongInput(
                "parse_exiobase(..., download=True) requires 'year' for monetary EXIOBASE downloads."
            )
        info = download_exiobase3(
            path,
            years=year,
            table=table,
            system=(system or "ixi") if table == "IOT" else None,
            version=version or "3.8.2",
        )
        extracted = info.get("extracted", [])
        if len(extracted) != 1:
            raise WrongInput(
                f"Expected one extracted EXIOBASE dataset for year {year}, got {len(extracted)}."
            )
        return extracted[0]

    download_hybrid_exiobase(path, table=table)
    return path


def parse_exiobase(
    table:str,
    unit:str,
    path:str,
    model:str = "Database",
    name:str = None, 
    year:int = None, 
    calc_all: bool = False,
    download: bool = False,
    **kwargs
):
    """Dispatch to the appropriate EXIOBASE parser.

    Parameters
    ----------
    table : str
        acceptable values are "IOT" or "SUT"
    unit : str
        Acceptable values are "Hybrid" or "Monetary"
    path : str
        path to folder/file of the database (varies by the type of database)
        When ``download=True``, this becomes the local download/cache
        directory where MARIO stores the EXIOBASE files before parsing them.
    calc_all : boolean
        if True, by default will calculate z,v,e after parsing
    download : boolean, Optional
        when ``True``, download the requested EXIOBASE package into ``path``
        and then parse it locally. Monetary downloads require ``year``.
    year : int, Optional
        optional to the Database (just for recoding the metadata)
    name : str, Optional
        optional but suggested. is useful for visualization and metadata.
    **kwargs: dict
        all the specific configuation of single exiobase parsers (please refer to the separat function documentations for more information)

    Returns
    -------
    mario.Database
        returns a mario.Database according to the type of exiobase database specified

    Raises
    ------
    WrongInput
        if non-valid values are passed to the arguments.
    """

    if table not in INPUT_OPTIONS["table"]:
        raise WrongInput("Table can be only chosen among {}".format(INPUT_OPTIONS["table"]))

    if unit not in INPUT_OPTIONS["unit"]:
        raise WrongInput("Unit con be only chosen among {}".format(INPUT_OPTIONS["unit"]))

    version = kwargs.get("version")
    system = kwargs.get("system")

    resolved_path = _resolve_exiobase_parse_path(
        table=table,
        unit=unit,
        path=path,
        year=year,
        download=download,
        version=version,
        system=system,
    )

    if table == "IOT":
        if unit == "Monetary":
            parser = parse_exiobase_3
        else:
            parser = hybrid_iot_exiobase
    else:
        if unit == "Monetary":
            parser = parse_exiobase_sut
        else:
            parser = hybrid_sut_exiobase

    kwargs["path"] = resolved_path
    kwargs["model"] = model
    kwargs["name"] = name
    kwargs["calc_all"] = calc_all
    kwargs["year"] = year

    return parser(**kwargs)


def hybrid_sut_exiobase(
    path:str,
    extensions: list | str | None = None,
    model: str = "Database", 
    name: str = None, 
    calc_all: bool = False, 
    **kwargs
):
    """Parse the hybrid EXIOBASE 3.3.18 SUT.

    Parameters
    ----------
    folder_path : str
        the directory of the folder which contains the following files: [MR_HSUP_2011_v3_3_18.csv,MR_HSUTs_2011_v3_3_18_FD.csv,MR_HUSE_2011_v3_3_18.csv,MR_HSUTs_2011_v3_3_18_extensions.xlsx]
    extensions : list, optional
        the list of extensions that user intend to read, by default []
    model : str, optional
        type of model accepted in mario, by default "Database"
    name : str, optional
        a name for the database, by default None
    calc_all : bool, optional
        if True, will calculate all the missing matrices, by default False

    Returns
    -------
    mario model
        returns the mario model chosen

    .. note::
    1. The name of extensions are changed to avoid confusion of same satellite account category for different extensions. For example 'Food' in 'pack_use_waste_act' is changed to 'Food (pack_use_waste)' to avoid confusion with 'Food' in 'pack_sup_waste'.
    2. The hybrid version of EXIOBASE, which is part of wider input-output database , is a multi-regional supply and use table. Here the term hybrid indicates that physical flows are accounted in mass units, energy flows in TJ and services in millions of euro (current prices).
    EXIOBASE 3 provides a time series of environmentally extended multi-regional input‐output (EE MRIO) tables ranging from 1995 to a recent year for 44 countries (28 EU member plus 16 major economies) and five rest of the world regions. EXIOBASE 3 builds upon the previous versions of EXIOBASE by using rectangular supply‐use tables (SUT) in a 163 industry by 200 products classification as the main building blocks. The tables are provided in current, basic prices (Million EUR).
    EXIOBASE 3 is the culmination of work in the FP7 DESIRE project and builds upon earlier work on EXIOBASE 2 in the FP7 CREEA project, EXIOBASE 1 of the FP6 EXIOPOL project and FORWAST project.
    A special issue of Journal of Industrial Ecology (Volume 22, Issue 3) describes the build process and some use cases of EXIOBASE 3. ("Merciai, Stefano, & Schmidt, Jannick. (2021). EXIOBASE HYBRID v3 - 2011 (3.3.18) [Data set]. Zenodo.)
    3. The current hybrid parser targets the ``3.3.18`` bundle
    (`Zenodo 7244919 <https://doi.org/10.5281/zenodo.7244919>`_) and does not
    yet include the later consequential developments released separately on
    `Zenodo 15421526 <https://zenodo.org/records/15421526>`_.
    """

    validate_named_selection(
        extensions,
        valid_options=HMRSUT_EXTENSIONS,
        option_name="extensions",
    )

    matrices, indeces, units, layout = parse_exiobase_hybrid_sut(
        path=path,
        extensions=extensions,
    )

    notes = [
        "The name of extensions are changed to avoid confusion of same satellite account category for different extensions. For example 'Food' in 'pack_use_waste_act' is changed to 'Food (pack_use_waste)' to avoid confusion with 'Food' in 'pack_sup_waste'"
    ]

    if "year" in kwargs:
        del kwargs["year"]

    return models[model](
        name=name,
        table="SUT",
        source=layout.source,
        year=layout.year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        notes=notes,
        **kwargs,
    )


def hybrid_iot_exiobase(
    path: str,
    extensions: list | str | None = None,
    model: str = "Database",
    name: str = None,
    calc_all: bool = False,
    **kwargs,
):
    """Parse the hybrid EXIOBASE 3.3.18 HIOT."""
    validate_named_selection(
        extensions,
        valid_options=HMIOT_EXTENSIONS,
        option_name="extensions",
    )

    matrices, indeces, units, layout = parse_exiobase_hybrid_iot(
        path=path,
        extensions=extensions,
    )

    if "year" in kwargs:
        del kwargs["year"]

    return models[model](
        name=name,
        table="IOT",
        source=layout.source,
        year=layout.year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_eurostat(
    country: str,
    year: int,
    table: str = "SUT",
    iot_mode: str = "product",
    unit: str = "MIO_EUR",
    path: str | None = None,
    download: bool = False,
    overwrite_download: bool = False,
    model: str = "Database",
    name: str = None,
    calc_all: bool = False,
    timeout: int = 60,
    **kwargs,
) -> object:
    """Parse Eurostat national tables directly from the official SDMX API.

    This parser targets the official national Eurostat supply-use and
    input-output datasets exposed through the SDMX API, not arbitrary local
    spreadsheets.

    Eurostat availability is year- and country-dependent. In general:

    * ``SUT`` tables are annual and published from reference year ``2010``
      onward;
    * ``IOT`` tables are published from reference year ``2010`` onward, but
      mandatory transmission is only five-yearly for years ending with ``0``
      or ``5``;
    * additional ``IOT`` years depend on voluntary country transmission.

    Parameters
    ----------
    country : str
        Eurostat geo code, for example ``IT`` or ``DE``.
    year : int
        reference year to download.
    table : str, optional
        target table family, either ``SUT`` or ``IOT``.
    iot_mode : str, optional
        Eurostat IOT layout when ``table='IOT'``. Supported values are
        ``product`` for product-by-product and ``industry`` for
        industry-by-industry tables.
    unit : str, optional
        Eurostat SDMX unit code. Supported values are ``MIO_EUR`` and
        ``MIO_NAC``.
    path : str, optional
        optional directory for locally stored raw Eurostat CSV slices.
    download : bool, optional
        when ``True``, download the raw CSV slice into ``path`` and then parse
        it locally.
    overwrite_download : bool, optional
        when ``download=True``, overwrite already downloaded raw files.
    model : str, optional
        currently only ``Database`` is supported.
    name : str, optional
        optional database name stored in metadata.
    calc_all : bool, optional
        if True, calculate missing derived matrices after parsing.
    timeout : int, optional
        request timeout in seconds used for each SDMX call.

    References
    ----------
    Eurostat metadata and dataset context:
    https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_n_esms.htm

    Eurostat API guide:
    https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)

    if unit not in EUROSTAT_SUT_UNITS:
        raise WrongInput(
            f"Eurostat unit should be one of {list(EUROSTAT_SUT_UNITS)}."
        )
    if download and path is None:
        raise WrongInput("Eurostat raw downloads require 'path' to be provided.")

    local_paths = None
    if path is not None:
        local_paths = _eurostat_local_paths(
            path,
            country=country,
            year=year,
            table=table,
            unit=unit,
            iot_mode=iot_mode,
        )
        if download:
            info = download_eurostat(
                path,
                country=country,
                year=year,
                table=table,
                iot_mode=iot_mode,
                unit=unit,
                timeout=timeout,
                overwrite=overwrite_download,
            )
            local_paths = {key: Path(value) for key, value in info["files"].items()}

    if table == "IOT":
        if iot_mode not in EUROSTAT_IOT_MODES:
            raise WrongInput(
                f"Eurostat iot_mode should be one of {list(EUROSTAT_IOT_MODES)}."
            )
        if local_paths is not None:
            if not local_paths["iot"].exists():
                raise WrongInput(
                    f"Eurostat local raw file not found: {local_paths['iot']}. "
                    "Pass download=True to fetch it or omit 'path' for direct online parsing."
                )
            matrices, indeces, units, layout = parse_eurostat_iot_sdmx(
                country=country,
                year=year,
                unit=unit,
                mode=iot_mode,
                iot_path=local_paths["iot"],
                timeout=timeout,
            )
        else:
            matrices, indeces, units, layout = parse_eurostat_iot_sdmx(
                country=country,
                year=year,
                unit=unit,
                mode=iot_mode,
                timeout=timeout,
            )
    else:
        if local_paths is not None:
            missing = [
                item for item in (local_paths["supply"], local_paths["use"]) if not item.exists()
            ]
            if missing:
                raise WrongInput(
                    f"Eurostat local raw files not found: {[str(item) for item in missing]}. "
                    "Pass download=True to fetch them or omit 'path' for direct online parsing."
                )
            matrices, indeces, units, layout = parse_eurostat_sut_sdmx(
                country=country,
                year=year,
                unit=unit,
                supply_path=local_paths["supply"],
                use_path=local_paths["use"],
                timeout=timeout,
            )
        else:
            matrices, indeces, units, layout = parse_eurostat_sut_sdmx(
                country=country,
                year=year,
                unit=unit,
                timeout=timeout,
            )

    return models[model](
        name=name or layout.dataset_name,
        table=table,
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_statcan(
    year: int,
    table: str = "SUT",
    level: str = "summary",
    geo: str = "Canada",
    valuation: str = "basic",
    satellite_account: str | None = None,
    path: str | None = None,
    download: bool = False,
    overwrite_download: bool = False,
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    timeout: int = 60,
    **kwargs,
) -> object:
    """Parse Statistics Canada supply-use or symmetric I-O tables via WDS.

    Parameters
    ----------
    year : int
        reference year to download.
    table : str, optional
        table family, either ``SUT`` or ``IOT``.
    level : str, optional
        StatCan table level. Supported values are:

        * ``summary`` for both ``SUT`` and ``IOT``
        * ``detail`` for both ``SUT`` and ``IOT``
        * ``link1997`` only for ``SUT``

    geo : str, optional
        geography label as published by Statistics Canada. ``Canada`` is the
        default. SUT tables expose provinces and territories as well.
    valuation : str, optional
        price system for ``IOT`` tables. Supported values are ``basic`` and
        ``purchaser``. SUT parsing currently supports only ``basic`` because
        supply rows are published at basic prices.
    satellite_account : str, optional
        optional external satellite-account bundle. The currently supported
        value is ``"openio_canada"``, which uses the OpenIO-Canada emission
        factors published on Zenodo at ``10.5281/zenodo.18304088``. This path
        is currently supported only for ``table="SUT"``, ``level="detail"``,
        reference year ``2022``, and provincial/territorial geographies.
        When ``download=True``, MARIO downloads the same fixed 2022 workbook
        into ``path`` and reuses it on later parses.
    path : str, optional
        optional directory for locally stored StatCan raw CSV files.
    download : bool, optional
        when ``True``, download the raw full-table CSV into ``path`` and then
        parse it locally.
    overwrite_download : bool, optional
        when ``download=True``, overwrite already downloaded raw files.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        optional dataset name stored in metadata.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.
    timeout : int, optional
        request timeout in seconds used for each WDS call.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)
    if download and path is None:
        raise WrongInput("StatCan raw downloads require 'path' to be provided.")
    if satellite_account not in {None, False, STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT}:
        raise WrongInput(
            f"StatCan satellite_account should be None or {STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT!r}."
        )
    if satellite_account == STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT and table != "SUT":
        raise NotImplementable(
            "OpenIO-Canada emission factors are currently supported only with StatCan SUT detail tables."
        )
    if satellite_account == STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT and path is None:
        raise WrongInput(
            "StatCan OpenIO-Canada satellite parsing requires 'path' so MARIO can find or download the local workbook."
        )
    if satellite_account == STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT and level != "detail":
        raise WrongInput(
            "OpenIO-Canada emission factors are currently compatible only with StatCan SUT level='detail'."
        )
    if satellite_account == STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT and int(year) != 2022:
        raise WrongInput(
            "OpenIO-Canada emission factors are currently available only for reference year 2022."
        )

    local_csv = None
    local_satellite = None
    if path is not None:
        local_csv = _statcan_local_csv_path(path, table=table, level=level)
        if satellite_account == STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT:
            local_satellite = _statcan_openio_local_xlsx_path(path)
        if download:
            info = download_statcan(
                path,
                table=table,
                level=level,
                timeout=timeout,
                overwrite=overwrite_download,
            )
            local_csv = Path(info["csv"])
            if satellite_account == STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT:
                sat_info = download_statcan_openio_canada(
                    path,
                    overwrite=overwrite_download,
                )
                local_satellite = Path(sat_info["xlsx"])

    if table == "SUT":
        if level not in STATCAN_TABLES["SUT"]:
            raise WrongInput(
                f"StatCan SUT level should be one of {list(STATCAN_TABLES['SUT'])}."
            )
        if valuation != "basic":
            raise NotImplementable(
                "Statistics Canada SUT parsing currently supports only valuation='basic'."
            )
        if satellite_account == STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT and local_satellite is not None and not local_satellite.exists():
            raise WrongInput(
                f"StatCan local OpenIO-Canada workbook not found: {local_satellite}. "
                "Pass download=True to fetch it or omit 'satellite_account'."
            )
        if local_csv is not None:
            if not local_csv.exists():
                raise WrongInput(
                    f"StatCan local raw file not found: {local_csv}. "
                    "Pass download=True to fetch it or omit 'path' for direct online parsing."
                )
            matrices, indeces, units, layout = parse_statcan_sut_wds(
                year=year,
                level=level,
                geo=geo,
                csv_path=local_csv,
                satellite_account=satellite_account,
                satellite_path=local_satellite,
                timeout=timeout,
            )
        else:
            matrices, indeces, units, layout = parse_statcan_sut_wds(
                year=year,
                level=level,
                geo=geo,
                satellite_account=satellite_account,
                satellite_path=local_satellite,
                timeout=timeout,
            )
    else:
        if level not in STATCAN_TABLES["IOT"]:
            raise WrongInput(
                f"StatCan IOT level should be one of {list(STATCAN_TABLES['IOT'])}."
            )
        if valuation not in STATCAN_VALUATIONS:
            raise WrongInput(
                f"StatCan valuation should be one of {list(STATCAN_VALUATIONS)}."
            )
        if local_csv is not None:
            if not local_csv.exists():
                raise WrongInput(
                    f"StatCan local raw file not found: {local_csv}. "
                    "Pass download=True to fetch it or omit 'path' for direct online parsing."
                )
            matrices, indeces, units, layout = parse_statcan_iot_wds(
                year=year,
                level=level,
                geo=geo,
                valuation=valuation,
                csv_path=local_csv,
                timeout=timeout,
            )
        else:
            matrices, indeces, units, layout = parse_statcan_iot_wds(
                year=year,
                level=level,
                geo=geo,
                valuation=valuation,
                timeout=timeout,
            )

    source = layout.source
    if satellite_account == STATCAN_OPENIO_CANADA_SATELLITE_ACCOUNT:
        source = f"{source}; satellite account: {STATCAN_OPENIO_CANADA_SOURCE}"

    return models[model](
        name=name or layout.dataset_name,
        table=table,
        source=source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_oecd(
    path: str | None = None,
    *,
    dataset: str = "ICIO",
    year: int | None = None,
    country: str | None = None,
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse OECD ICIO, OECD national IOT, or OECD SUT datasets.

    The parser exposes three OECD families behind one entry point:

    * ``dataset="ICIO"``: local OECD ICIO csv bundles from the official OECD
      inter-country input-output tables page. Both ``<year>.csv`` and regular
      ``<year>_SML.csv`` naming conventions are supported.
    * ``dataset="IOT"``: local OECD national Input-Output total tables such as
      ``CZE2014ttl.csv`` from the official OECD IOT release page.
    * ``dataset="SUT"``: annual OECD Supply and Use Tables pulled directly from
      the official OECD SDMX API. This mode does not require ``path`` but does
      require ``country`` and ``year``.

    Parameters
    ----------
    path : str, optional
        local OECD file or directory when ``dataset`` is ``"ICIO"`` or
        ``"IOT"``. Ignored for ``dataset="SUT"``.
    dataset : str, optional
        one of ``"ICIO"``, ``"IOT"``, or ``"SUT"``.
    year : int, optional
        reference year to select when ``path`` points to a directory, or the
        SDMX year when ``dataset="SUT"``.
    country : str, optional
        ISO3 country code used to disambiguate OECD national IOT files and
        required for ``dataset="SUT"``.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        dataset name stored in MARIO metadata. Defaults to the inferred OECD
        dataset label.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.

    Notes
    -----
    MARIO currently parses the economic OECD tables only. The OECD parser does
    not yet attach environmental extensions, so the resulting databases should
    not be interpreted as environmentally extended tables.
    """
    dataset_name = str(dataset).upper()
    add_extensions = kwargs.pop("add_extensions", None)
    if add_extensions is not None:
        raise NotImplementable(
            "OECD tables are currently parsed as economic tables only. "
            "Environmental extensions are not implemented yet."
        )

    if dataset_name == "ICIO":
        validate_parse_request(table="IOT", model=model)
        if path is None:
            raise WrongInput("path is required for OECD dataset='ICIO'.")
        matrices, indeces, units, layout = parse_oecd_icio(path=path, year=year)
        table_kind = "IOT"
    elif dataset_name == "IOT":
        validate_parse_request(table="IOT", model=model)
        if path is None:
            raise WrongInput("path is required for OECD dataset='IOT'.")
        matrices, indeces, units, layout = parse_oecd_iot_total(
            path=path,
            year=year,
            country=country,
        )
        table_kind = "IOT"
    elif dataset_name == "SUT":
        validate_parse_request(table="SUT", model=model)
        if year is None or country is None:
            raise WrongInput("country and year are required for OECD dataset='SUT'.")
        matrices, indeces, units, layout = parse_oecd_sut_sdmx(
            country=country,
            year=year,
        )
        table_kind = "SUT"
    else:
        raise WrongInput("dataset should be one of ['ICIO', 'IOT', 'SUT'].")

    return models[model](
        name=name or layout.dataset_name,
        table=table_kind,
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        notes=list(getattr(layout, "notes", ())),
        calc_all=calc_all,
        **kwargs,
    )


def parse_cepalstat(
    path: str,
    *,
    table: str,
    year: int | None = None,
    country: str | None = None,
    iot_mode: str = "pxp",
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse selected local CEPALSTAT COU/MIP bundles.

    The CEPALSTAT repository is not structurally uniform. MARIO therefore
    resolves a set of supported layout families behind one public entry point.

    Supported ``SUT`` families currently include:

    - integrated offer/use workbooks such as the Colombia bundles;
    - two-sheet workbooks such as the Argentina bundles;
    - split offer/demand workbooks such as the Brazil bundles;
    - multi-cuadro workbooks such as the Chile bundles.

    Supported ``IOT`` families currently include:

    - direct symmetric matrix workbooks such as Dominican Republic and
      Guatemala bundles;
    - ``Cuadro`` workbooks such as the Colombia bundles;
    - symmetric workbooks such as the Argentina bundles;
    - demand-at-basic-prices workbooks such as the Brazil bundles;
    - matrix workbooks such as the Chile bundles.

    Other bundle families are still rejected explicitly until implemented.

    Parameters
    ----------
    path : str
        local CEPALSTAT bundle file, extracted workbook, or directory
        containing one or more local CEPALSTAT files.
    table : str
        choose between ``"SUT"`` and ``"IOT"``.
    year : int, optional
        reference year to select from a multi-year workbook or to disambiguate
        one directory containing more than one CEPALSTAT bundle.
    country : str, optional
        ISO3 country code used to disambiguate one directory containing more
        than one CEPALSTAT bundle.
    iot_mode : str, optional
        only relevant when ``table='IOT'``. Supported values are ``pxp``,
        ``axa`` and ``auto``. The default is ``pxp`` because some CEPALSTAT
        IOT bundles contain both representations.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        optional dataset name stored in metadata.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.

    Notes
    -----
    Official repository:
    https://statistics.cepal.org/repository/cou-mip/index.html?lang=en
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)
    if table == "SUT":
        matrices, indeces, units, layout = parse_cepalstat_sut(
            path=path,
            year=year,
            country=country,
        )
    elif table == "IOT":
        if iot_mode not in CEPALSTAT_IOT_MODES:
            raise WrongInput(
                f"CEPALSTAT iot_mode should be one of {list(CEPALSTAT_IOT_MODES)}."
            )
        matrices, indeces, units, layout = parse_cepalstat_iot(
            path=path,
            year=year,
            country=country,
            iot_mode=iot_mode,
        )
    else:
        raise NotImplementable("CEPALSTAT parsing currently supports only IOT and SUT tables.")

    return models[model](
        name=name or layout.dataset_name,
        table=table,
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        notes=list(layout.notes),
        calc_all=calc_all,
        **kwargs,
    )


def parse_istat(
    path: str,
    *,
    year: int,
    table: str = "IOT",
    iot_mode: str = "product",
    level: str = "63",
    price: str = "current",
    valuation: str = "basic",
    download: bool = False,
    overwrite_download: bool = False,
    edition: str = "latest",
    page_url: str | None = None,
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse official ISTAT input-output workbooks from local files or a downloaded release.

    This parser targets the official ISTAT release bundles published on the
    public release pages for the Italian input-output system. The supported
    source format is the Excel content distributed inside the official release
    zip, not other ad hoc spreadsheets.

    Parameters
    ----------
    path : str
        local workbook, extracted release directory, or release zip. When
        ``download=True``, this should be the destination directory where the
        official ISTAT release zip will be stored and extracted.
    year : int
        reference year to select from the multi-year workbook.
    table : str, optional
        one of ``"IOT"`` or ``"SUT"``.
    iot_mode : str, optional
        ISTAT symmetric table layout when ``table='IOT'``. Supported values are
        ``product`` for product-by-product and ``industry`` for branch-by-branch.
    level : str, optional
        SUT aggregation level when ``table='SUT'``. Supported values are ``"63"``
        and ``"20"``.
    price : str, optional
        SUT price system when ``table='SUT'``. Supported values are ``current``
        and ``pyp``.
    valuation : str, optional
        SUT use-table valuation when ``table='SUT'``. Supported values are
        ``basic`` and ``purchaser``.
    download : bool, optional
        when ``True``, download the official ISTAT release zip into ``path``
        before parsing it locally.
    overwrite_download : bool, optional
        when ``download=True``, overwrite an existing local archive/extraction.
    edition : str, optional
        known ISTAT release page label used by the downloader, for example
        ``"2020-2022"`` or ``"2015-2020"``. Ignored when ``download=False``.
    page_url : str, optional
        explicit ISTAT release page URL for the downloader. Ignored when
        ``download=False``.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)

    effective_path = path
    if download:
        info = download_istat_io(
            path,
            edition=edition,
            page_url=page_url,
            overwrite=overwrite_download,
        )
        effective_path = info["extracted_path"] or info["archive"]

    if table == "IOT":
        if iot_mode not in ISTAT_IOT_MODES:
            raise WrongInput(f"ISTAT iot_mode should be one of {list(ISTAT_IOT_MODES)}.")
        matrices, indeces, units, layout = parse_istat_iot(
            effective_path,
            year=year,
            mode=iot_mode,
        )
    else:
        if level not in ISTAT_SUT_LEVELS:
            raise WrongInput(f"ISTAT SUT level should be one of {list(ISTAT_SUT_LEVELS)}.")
        if price not in ISTAT_SUT_PRICES:
            raise WrongInput(f"ISTAT SUT price should be one of {list(ISTAT_SUT_PRICES)}.")
        if valuation not in ISTAT_SUT_VALUATIONS:
            raise WrongInput(
                f"ISTAT SUT valuation should be one of {list(ISTAT_SUT_VALUATIONS)}."
            )
        matrices, indeces, units, layout = parse_istat_sut(
            effective_path,
            year=year,
            level=level,
            price=price,
            valuation=valuation,
        )

    return models[model](
        name=name or layout.dataset_name,
        table=table,
        source=layout.source,
        year=layout.year,
        price=layout.price_label,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_ceads(
    path: str,
    *,
    format: str = "auto",
    table: str = "IOT",
    year: int | None = None,
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse one local CEADS China provincial MRIO workbook.

    Parameters
    ----------
    path : str
        local workbook path or one directory containing one or more supported
        CEADS workbooks.
    format : str, optional
        workbook layout selector. ``auto`` is the default and currently
        resolves to ``ceads_provincial_workbook`` for the verified 2018/2020
        CEADS workbook family.
    table : str, optional
        currently only ``IOT`` is supported.
    year : int, optional
        workbook year used to disambiguate one directory containing more than
        one supported workbook.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        optional dataset name stored in metadata.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.

    Notes
    -----
    Verified local format:

    * CEADS provincial MRIO workbooks for 2018 and 2020, distributed as
      Excel files through figshare and the CEADS data portal.

    No automatic download is implemented yet. Callers should point the parser
    to one local workbook.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    normalized_format = str(format).strip().lower()
    if normalized_format not in CEADS_FORMATS:
        raise WrongInput(f"CEADS format should be one of {list(CEADS_FORMATS)}.")

    validate_parse_request(table=table, model=model)
    if table != "IOT":
        raise NotImplementable("CEADS parsing currently supports only IOT tables.")

    matrices, indeces, units, layout = parse_ceads_iot(
        path=path,
        format=normalized_format,
        year=year,
    )

    return models[model](
        name=name or layout.dataset_name,
        table="IOT",
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        notes=list(layout.notes),
        calc_all=calc_all,
        **kwargs,
    )


def parse_bea(
    path: str,
    *,
    year: int,
    level: str = "summary",
    table: str = "SUT",
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse one local BEA Supply-Use release bundle.

    Parameters
    ----------
    path : str
        path to one extracted BEA Supply-Use directory, to one workbook inside
        that directory, or directly to the official ``SUPPLY-USE.zip`` bundle.
    year : int
        yearly sheet to parse from the selected BEA release family.
    level : str, optional
        BEA aggregation level. Supported values are ``summary``, ``sector``,
        and ``detail``.
    table : str, optional
        currently only ``SUT`` is supported.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        optional dataset name stored in metadata.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.

    Notes
    -----
    This parser targets only the official BEA ``SUPPLY-USE`` workbook family.
    It does not parse the separate ``MAKE-USE-IMPORTS (BEFORE
    REDEFINITIONS)`` or ``TOTAL AND DOMESTIC REQUIREMENTS`` bundles.

    The verified yearly coverage in the official workbooks is:

    - ``summary`` and ``sector``: 1997 onward in the current bundle;
    - ``detail``: 2007, 2012, and 2017 in the current bundle.

    No automatic download is implemented yet. Callers should point the parser
    to one local bundle or extracted directory.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    normalized_level = str(level).strip().lower()
    if normalized_level not in BEA_LEVELS:
        raise WrongInput(f"BEA level should be one of {list(BEA_LEVELS)}.")

    validate_parse_request(table=table, model=model)
    if table != "SUT":
        raise NotImplementable("BEA parsing currently supports only SUT tables.")

    matrices, indeces, units, layout = parse_bea_sut(
        path=path,
        year=year,
        level=normalized_level,
    )

    return models[model](
        name=name or layout.dataset_name,
        table="SUT",
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        notes=list(layout.notes),
        calc_all=calc_all,
        **kwargs,
    )


def parse_adb(
    path: str,
    table: str = "IOT",
    year: int | None = None,
    economies: int | None = None,
    add_extensions: str | None = None,
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse one locally downloaded ADB MRIO or SRIO Excel workbook.

    This parser targets the Asian Development Bank Excel workbooks
    distributed on the official ADB MRIO page at
    ``https://kidb.adb.org/globalization/current``. MARIO does not implement
    any automatic download here: callers should point the parser to one local
    ``.xlsx`` workbook or to a directory containing one or more of those
    workbooks.

    ``parse_adb`` supports both:

    - ADB MRIO workbooks, typically one workbook per release year;
    - ADB SRIO workbooks, where one workbook contains multiple yearly sheets.

    The MRIO release family also mixes closely related workbook variants
    (for example the 2017 LAC release and the 2024 ``62/72/74 economies``
    releases). ``parse_adb`` auto-detects the header layout used by each
    workbook. When ``path`` points to a directory that contains more than one
    candidate MRIO workbook, use ``year=`` and/or ``economies=`` to
    disambiguate or point directly to one file. For SRIO workbooks, ``year=``
    is required because one workbook contains multiple annual sheets.

    Parameters
    ----------
    path : str
        path to one local ADB ``.xlsx`` workbook or to a directory
        containing one or more ADB workbooks.
    table : str, optional
        ADB parsing currently supports only ``IOT`` tables.
    year : int, optional
        reference year used to select one MRIO workbook when ``path`` points
        to a directory containing multiple yearly releases. For SRIO
        workbooks, this selects the yearly sheet and is mandatory.
    economies : int, optional
        MRIO workbook variant selector used when a directory contains more
        than one release for the same year. This matches the folder/file
        marker values commonly used by the downloaded workbooks, such as
        ``62``, ``71``, ``72`` or ``74``.
    add_extensions : str, optional
        optional path to an ADB air-emissions workbook. When provided, MARIO
        imports the environmental extension matrix ``E`` from that file and
        keeps ``EY`` zero-filled. The same mechanism works for both MRIO and
        SRIO economic tables. The matching air-emissions workbooks are
        distributed on the ADB page at
        ``https://kidb.adb.org/globalization/adb_environmentally_extended_multiregional_inputoutput_tables``.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        optional dataset name stored in metadata.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.

    Notes
    -----
    In normal usage there are four common parse patterns:

    - direct path to one MRIO workbook;
    - path to one directory containing multiple MRIO workbooks, resolved with
      ``year=`` and optionally ``economies=``;
    - direct path to one SRIO workbook, where ``year=`` selects the annual
      sheet;
    - either of the previous two cases plus ``add_extensions=...`` to attach
      the matching air-emissions table.

    When ``add_extensions`` is used, MARIO records parser warnings in the
    database metadata history if:

    - the emissions workbook year does not match the economic table year;
    - the emissions workbook does not cover all regions present in the
      economic table.

    Those warnings do not stop the parse. They can be inspected after parsing
    through ``db.meta_history``.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)
    if table != "IOT":
        raise NotImplementable("ADB parsing currently supports only IOT tables.")

    matrices, indeces, units, layout = parse_adb_iot(
        path=path,
        year=year,
        economies=economies,
        add_extensions=add_extensions,
    )
    return models[model](
        name=name or layout.dataset_name,
        table="IOT",
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        notes=list(layout.notes),
        calc_all=calc_all,
        **kwargs,
    )


def parse_emerging(
    path: str,
    table: str = "IOT",
    year: int | None = None,
    regions=None,
    load_co2: bool = True,
    co2_path: str | None = None,
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse one EMERGING MATLAB bundle from the supported Zenodo releases.

    This parser supports the EMERGING bundles associated with these official
    Zenodo version records:

    * the older record ``https://doi.org/10.5281/zenodo.10956623`` with main
      files like ``global_mrio_2017.mat`` and companion CO2 files like
      ``EMERGING_CO2_2017.mat``;
    * ``https://doi.org/10.5281/zenodo.17557778`` for ``v2.0``;
    * ``https://doi.org/10.5281/zenodo.18518911`` for ``v2.1``;
    * ``https://doi.org/10.5281/zenodo.19461860`` for ``v2.2``.

    In practice, MARIO accepts these local naming conventions:

    * ``global_mrio_<year>.mat`` for ``v1.0`` bundles;
    * ``EMERGING_V2_<year>_m.mat`` for ``v2.x`` bundles;
    * ``EMERGING_V2_<year>.mat`` for older local ``v2.x`` copies when they
      expose the same internal MATLAB structure.

    For local ``v2.x`` files, the parser does not try to infer the exact
    sub-version ``2.0`` versus ``2.1`` versus ``2.2`` from the filename alone,
    because the public naming convention is shared across those releases.

    The associated paper is:

    Huo, J., Chen, P., Hubacek, K., Zheng, H., Meng, J., & Guan, D. (2022).
    Full-scale, near real-time multi-regional input-output table for the
    global emerging economies (EMERGING). *Journal of Industrial Ecology*,
    26, 1218-1232. https://doi.org/10.1111/jiec.13264

    MARIO currently supports only the multiregional IOT bundle, not any future
    alternative table layouts.

    Parameters
    ----------
    path : str
        path to one local EMERGING main ``.mat`` file or to a directory
        containing one or more EMERGING yearly bundles.
    table : str, optional
        EMERGING parsing currently supports only ``IOT`` tables.
    year : int, optional
        reference year to select when ``path`` points to a directory that
        contains more than one EMERGING main MATLAB file.
    regions : sequence[str] or str, optional
        optional ISO3 subset. When omitted, parse all regions in the bundle.
        This is useful because the full EMERGING matrix is very large.
    load_co2 : bool, optional
        when ``True``, auto-detect and parse the companion
        ``EMERGING_CO2_<year>.mat`` or ``EMERGING_CO2_<year>_IEA.mat`` file if
        it is present next to the main bundle. When ``False``, keep satellite
        accounts as placeholders.
    co2_path : str, optional
        explicit path to the companion CO2 MATLAB file. When provided it
        overrides sibling auto-detection.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        optional dataset name stored in metadata.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)
    if table != "IOT":
        raise NotImplementable("EMERGING parsing currently supports only IOT tables.")

    matrices, indeces, units, layout = parse_emerging_iot(
        path=path,
        year=year,
        regions=regions,
        load_co2=load_co2,
        co2_path=co2_path,
    )
    return models[model](
        name=name or layout.dataset_name,
        table="IOT",
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_wiod(
    path: str,
    table: str = "IOT",
    year: int | None = None,
    country: str | None = None,
    add_extensions: str | None = None,
    row_mode: str = "external_account",
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse one WIOD 2016 multiregional Excel workbook from the official release.

    This parser targets the multiregional WIOD 2016 Excel workbooks distributed
    on the official GGDC release page at
    ``https://www.rug.nl/ggdc/valuechain/wiod/wiod-2016-release?lang=en``.
    The direct file links used there are currently:

    - MRIO IOT, current prices: ``https://dataverse.nl/api/access/datafile/199104``
    - MRIO IOT, previous-year prices (``_PYP``): ``https://dataverse.nl/api/access/datafile/199102``
    - MRIO SUT, international: ``https://dataverse.nl/api/access/datafile/199100``
    - national IOT bundle: ``https://dataverse.nl/api/access/datafile/199099``
    - national SUT bundle: ``https://dataverse.nl/api/access/datafile/199096``
    - socio-economic accounts: ``https://dataverse.nl/api/access/datafile/199095``

    MARIO currently supports:

    - multiregional IOT ``.xlsb`` workbooks, including the ``_PYP`` variant;
    - multiregional SUT ``.xlsb`` workbooks;
    - national IOT ``.xlsx`` workbooks such as ``ITA_NIOT_nov16.xlsx``;
    - national SUT ``.xlsx`` workbooks such as ``ITA_SUT_nov16.xlsx``.

    Parameters
    ----------
    path : str
        path to one local WIOD 2016 multiregional ``.xlsb`` workbook or to a
        directory containing one or more WIOD 2016 multiregional workbooks.
    table : str, optional
        choose between ``IOT`` and ``SUT``.
    year : int, optional
        reference year to select when ``path`` points to a directory that
        contains more than one WIOD 2016 workbook. For national WIOD tables,
        this is mandatory because one workbook contains the full time series.
    country : str, optional
        country selector used when ``path`` points to a directory containing
        multiple national WIOD workbooks.
    add_extensions : str, optional
        optional path to ``Socio_Economic_Accounts.xlsx``. When provided,
        MARIO imports the socio-economic accounts as satellite extensions.
        For IOT tables they populate ``E``; for SUT tables they populate
        ``Ea`` while leaving ``Ec`` zero-filled.
    row_mode : str, optional
        only relevant for the international WIOD SUT workbook. Use
        ``"external_account"`` (default) to remove ``ROW`` from the
        endogenous region set and reclassify its intermediate/final-demand
        uses into ``Va`` and ``VY``. Use ``"legacy_region"`` to keep the
        previous parser behavior where ``ROW`` stays on the commodity side
        of the SUT region axis. This part of the WIOD international SUT
        treatment should still be considered investigative because the source
        workbook does not provide a fully endogenous ``ROW`` economy.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        optional dataset name stored in metadata.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)
    if table == "IOT":
        matrices, indeces, units, layout = parse_wiod_iot(
            path=path,
            year=year,
            country=country,
            add_extensions=add_extensions,
        )
    elif table == "SUT":
        matrices, indeces, units, layout = parse_wiod_sut(
            path=path,
            year=year,
            country=country,
            add_extensions=add_extensions,
            row_mode=row_mode,
        )
    else:
        raise NotImplementable("WIOD parsing currently supports only IOT and SUT tables.")
    return models[model](
        name=name or layout.dataset_name,
        table=table,
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        notes=list(layout.notes),
        calc_all=calc_all,
        **kwargs,
    )


def parse_eurostat_sut(
    country: str,
    year: int,
    unit: str = "MIO_EUR",
    model: str = "Database",
    name: str = None,
    calc_all: bool = False,
    timeout: int = 60,
    **kwargs,
) -> object:
    """Compatibility alias for ``parse_eurostat(..., table='SUT')``."""
    return parse_eurostat(
        country=country,
        year=year,
        table="SUT",
        unit=unit,
        model=model,
        name=name,
        calc_all=calc_all,
        timeout=timeout,
        **kwargs,
    )


def parse_from_pymrio(
        io,
        value_added,
        satellite_account,
        include_meta=True
    ):
    """Convert a ``pymrio.IOSystem`` into a ``mario.Database``.

    Parameters
    ------------
    io : pymrio.IOSystem
        the pymrio IOSystem to be converted to mario.Database

    value_added : dict or str
        value-added mapper. Keys are pymrio Extension names and values are row
        selectors. Use ``"all"`` as one dictionary value to assign the full
        Extension to factors. As a top-level shorthand, ``value_added="all"``
        assigns all Extensions not explicitly assigned to ``satellite_account``
        to the factor side.

    satellite_account : dict or str
        satellite-account mapper. Keys are pymrio Extension names and values
        are row selectors. Use ``"all"`` as one dictionary value to assign the
        full Extension to satellites. As a top-level shorthand,
        ``satellite_account="all"`` assigns all Extensions not explicitly
        assigned to ``value_added`` to the satellite side. When both arguments
        are ``"all"``, MARIO looks for exactly one factor-like Extension such
        as ``factor_inputs`` or ``factor_of_production`` and assigns the rest
        to satellites.

    include_meta : bool
        if True, will record the pymrio.meta into mario.meta

    Returns:
       mario.Database
    """

    matrices, units, indeces = parse_pymrio(io, value_added, satellite_account)

    notes = [
        "Database parsed from pymrio",
    ]
    if include_meta:
        notes.extend(["pymrio meta:"] + io.meta.history)

    return models["Database"](
        name=io.name,
        table="IOT",
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        notes=notes,
    )


def parse_figaro(
    path: str,
    table: str = "SUT",
    year: int | None = None,
    iot_mode: str = "auto",
    model: str = "Database",
    name: str = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    f"""Parse FIGARO tables from locally downloaded CIRCABC files.

    As of March 23, 2026, the FIGARO flat files are published in four public
    CIRCABC libraries referenced by ``mario.parsers.specs``:

    * supply files: ``{FIGARO_SUPPLY_URL}``
    * use files: ``{FIGARO_USE_URL}``
    * product-by-product IOT files: ``{FIGARO_IOT_PXP_URL}``
    * industry-by-industry IOT files: ``{FIGARO_IOT_IXI_URL}``

    MARIO does not rely on automatic download here: callers should point this
    parser to a local directory containing the FIGARO flat files, either as
    ``.zip`` bundles or extracted ``.csv`` files.

    Parameters
    ----------
    table : str, optional
        either ``SUT`` or ``IOT``.
    iot_mode : str, optional
        FIGARO IOT variant. Supported values are ``auto``, ``product`` and
        ``industry``. When both IOT variants are present and ``auto`` is used,
        MARIO defaults to the product-by-product file.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)
    if table == "IOT":
        if iot_mode not in FIGARO_IOT_MODES:
            raise WrongInput(
                f"FIGARO iot_mode should be one of {list(FIGARO_IOT_MODES)}."
            )
        matrices, indeces, units, layout = parse_figaro_iot(
            path=path,
            year=year,
            mode=iot_mode,
        )
    else:
        matrices, indeces, units, layout = parse_figaro_sut(path=path, year=year)
    return models[model](
        name=name or layout.dataset_name,
        table=table,
        source=layout.source,
        year=layout.year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_gtap(
    path: str,
    table: str = "IOT",
    variant: str = "power",
    layout: str = "MRIO",
    input_format: str = "auto",
    model: str = "Database",
    name: str | None = None,
    year: int | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse a locally downloaded GTAP bundle.

    The current backend supports the GTAP Power multi-regional input-output
    bundle used in the Horizon collaboration. The parser is structured with
    explicit ``variant`` and ``layout`` arguments so more GTAP branches can be
    added later without changing the public API.

    Parameters
    ----------
    path : str
        directory containing the GTAP bundle, or one file inside that
        directory.
    table : str, optional
        currently only ``IOT`` is supported.
    variant : str, optional
        GTAP family. The only supported value today is ``power``.
    layout : str, optional
        GTAP layout. The only supported value today is ``MRIO``.
    input_format : str, optional
        one of ``auto``, ``csv`` or ``gdx``. ``auto`` prefers the CSV bundle
        when both bundles are present in the same directory.

    Notes
    -----
    The GDX path requires the GAMS Python API in the active environment
    because MARIO relies on ``gams.transfer`` to read the GDX containers.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)
    normalized_variant = str(variant).strip().lower()
    normalized_layout = str(layout).strip().upper()
    normalized_input_format = str(input_format).strip().lower()

    if normalized_variant not in {item.lower() for item in GTAP_VARIANTS}:
        raise WrongInput(f"GTAP variant should be one of {list(GTAP_VARIANTS)}.")
    if normalized_layout not in {item.upper() for item in GTAP_LAYOUTS}:
        raise WrongInput(f"GTAP layout should be one of {list(GTAP_LAYOUTS)}.")
    if normalized_input_format not in {item.lower() for item in GTAP_INPUT_FORMATS}:
        raise WrongInput(f"GTAP input_format should be one of {list(GTAP_INPUT_FORMATS)}.")
    if table != "IOT":
        raise NotImplementable("GTAP parsing currently supports only IOT tables.")

    if normalized_layout != "MRIO" or normalized_variant != "power":
        raise NotImplementable("Only GTAP Power MRIO is currently implemented.")

    if normalized_input_format == "gdx":
        matrices, indeces, units, parsed_layout = parse_gtap_mrio_gdx(path)
    else:
        try:
            matrices, indeces, units, parsed_layout = parse_gtap_mrio_csv(path)
        except WrongInput:
            if normalized_input_format != "auto":
                raise
            matrices, indeces, units, parsed_layout = parse_gtap_mrio_gdx(path)

    return models[model](
        name=name or parsed_layout.dataset_name,
        table="IOT",
        source=parsed_layout.source,
        year=year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_useeio(
    path: str,
    *,
    format: str = "auto",
    table: str = "SUT",
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse one local USEEIO workbook export.

    Parameters
    ----------
    path : str
        path to one local ``USEEIO*.xlsx`` workbook or to a directory
        containing a single workbook.
    format : str, optional
        workbook layout selector. This is a parser-side file-format selector,
        not a USEEIO model alias. ``auto`` is the default and currently
        resolves to ``v2.5_workbook`` when the workbook matches the known
        USEEIO v2.5 export structure.
    table : str, optional
        currently only ``SUT`` is supported.
    model : str, optional
        public MARIO model class to instantiate. ``Database`` is the default
        and the only supported value.
    name : str, optional
        optional dataset name stored in metadata.
    calc_all : bool, optional
        whether to materialize derived blocks immediately after parsing.

    Notes
    -----
    In ``USEEIO`` naming, aliases such as ``yellowthroat``, ``kingbird``,
    ``oriole``, or ``waxwing`` identify different model families and contents.
    MARIO's ``format=`` argument instead identifies the workbook structure that
    the parser knows how to read. Different aliases can therefore share the
    same parser format.

    The currently relevant published national v2.5 aliases include:

    - ``yellowthroat`` and ``waxwing``: GLORIA-backed models, respectively at
      BEA Summary and BEA Detail level, with GHG and material-footprint
      extensions;
    - ``kingbird`` and ``kinglet``: EXIOBASE-backed models, respectively at
      BEA Summary and BEA Detail level, with GHG extensions;
    - ``oriole`` and ``catbird``: CEDA-backed models, respectively at BEA
      Summary and BEA Detail level, with GHG extensions.

    The supported v2.5 workbook layout is parsed as a split-native SUT:

    - ``S`` from workbook ``V``;
    - ``U``, ``Yc`` and ``Va`` from the extended workbook ``U`` block;
    - ``Ec`` from ``B * q`` because the verified v2.5 workbook stores the
      direct environmental coefficient matrix on the commodity axis.

    No automatic download is implemented yet. Callers should point the parser
    to one local workbook.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    normalized_format = str(format).strip().lower()
    if normalized_format not in USEEIO_FORMATS:
        raise WrongInput(f"USEEIO format should be one of {list(USEEIO_FORMATS)}.")

    validate_parse_request(table=table, model=model)
    if table != "SUT":
        raise NotImplementable("USEEIO parsing currently supports only SUT tables.")

    matrices, indeces, units, layout = parse_useeio_sut(path=path, format=normalized_format)

    return models[model](
        name=name or layout.dataset_name,
        table="SUT",
        source=layout.source,
        year=layout.io_year,
        price=layout.price,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        notes=list(layout.notes),
        calc_all=calc_all,
        **kwargs,
    )


def parse_gloria(
    path: str,
    table: str = "SUT",
    valuation: str | int = "basic",
    year: int | None = None,
    regions: str | list[str] | tuple[str, ...] | None = None,
    satellites: str | list[str] | tuple[str, ...] | None = "all",
    dtype: str = "float32",
    cache: bool | str | Path = False,
    model: str = "Database",
    name: str | None = None,
    calc_all: bool = False,
    **kwargs,
) -> object:
    """Parse a locally downloaded GLORIA release.

    The current GLORIA backend targets the monetary multi-regional SUT bundles
    shipped as raw ``T``, ``Y`` and ``V`` csv files together with the GLORIA
    ReadMe workbook. GLORIA IOT parsing is intentionally left for a later step.

    Parameters
    ----------
    path : str
        path to the GLORIA release root or directly to the ``GLORIA_MRIOs_*``
        directory containing the raw csv files.
    table : str, optional
        currently only ``SUT`` is supported.
    valuation : str or int, optional
        one of ``basic``, ``trade``, ``transport``, ``taxes`` or
        ``subsidies`` (or the corresponding markup number ``1``-``5``).
    year : int, optional
        reference year when the selected folder contains more than one yearly
        GLORIA bundle.
    regions : sequence of str, optional
        optional subset of GLORIA region acronyms to keep.
    satellites : str or sequence of str, optional
        satellite filter. Use ``\"all\"`` for the full satellite account
        payload, pass one full label such as ``\"Emissions | CO2\"``, or one
        group name from the GLORIA ReadMe such as ``\"Emissions\"``.
    dtype : str, optional
        numeric dtype used for dense GLORIA blocks. ``float32`` is the default
        because GLORIA use matrices are large.
    cache : bool or path-like, optional
        if ``True``, cache the parsed result as parquet under the GLORIA root
        and reuse it on subsequent calls when the raw file signature matches.
        A custom directory can also be provided.
    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    validate_parse_request(table=table, model=model)
    if table != "SUT":
        raise NotImplementable("GLORIA parsing currently supports only SUT tables.")

    layout, metadata = detect_gloria_layout(
        path=path,
        valuation=valuation,
        year=year,
    )
    _select_gloria_satellites(metadata, satellites)
    cache_dir = None
    cache_signature = None
    cache_info_path = None
    if cache:
        cache_dir = (
            _default_gloria_cache_dir(layout, regions=regions, satellites=satellites, dtype=dtype)
            if cache is True
            else Path(cache)
        )
        cache_signature = _gloria_cache_signature(
            layout,
            regions=regions,
            satellites=satellites,
            dtype=dtype,
        )
        cache_info_path = cache_dir / "gloria_cache.json"
        flows_dir = cache_dir / "flows"

        if cache_info_path.exists() and flows_dir.exists():
            cache_info = _read_json_file(cache_info_path)
            if cache_info.get("signature") == cache_signature:
                log_time(logger, f"Parser: loading GLORIA parquet cache from {cache_dir}.", "info")
                state = parse_state_from_parquet(
                    path=str(flows_dir),
                    table="SUT",
                    mode="flows",
                    flat=True,
                    name=name or cache_info.get("name") or layout.dataset_name,
                    source=cache_info.get("source") or layout.source,
                    year=cache_info.get("year", layout.year),
                    price=cache_info.get("price", layout.price),
                )
                return build_database_from_state(
                    state,
                    model=model,
                    calc_all=calc_all,
                    name=name or cache_info.get("name") or layout.dataset_name,
                    source=cache_info.get("source") or layout.source,
                    year=cache_info.get("year", layout.year),
                    price=cache_info.get("price", layout.price),
                    **kwargs,
                )

    matrices, indeces, units, layout = parse_gloria_sut(
        path=path,
        valuation=valuation,
        year=year,
        regions=regions,
        satellites=satellites,
        dtype=dtype,
        layout=layout,
        metadata=metadata,
    )
    database = _build_gloria_database(
        matrices=matrices,
        indeces=indeces,
        units=units,
        layout=layout,
        model=model,
        name=name,
        calc_all=False,
        notes=layout.notes,
        kwargs=kwargs,
    )

    if cache_dir is not None:
        log_time(logger, f"Parser: writing GLORIA parquet cache to {cache_dir}.", "info")
        database.to_parquet(path=str(cache_dir), flows=True, coefficients=False, flat=True, include_meta=True)
        _write_json_file(
            cache_info_path,
            {
                "signature": cache_signature,
                "name": database.meta.name,
                "source": database.meta.source,
                "year": database.meta.year,
                "price": database.meta.price,
                "notes": list(layout.notes),
            },
        )

    if calc_all:
        database.calc_all()
    return database
