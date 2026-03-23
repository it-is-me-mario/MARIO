# -*- coding: utf-8 -*-
"""Parser entry points that return ``mario.Database`` objects."""

from mario.api import Database
from mario.log_exc.exceptions import WrongInput, LackOfInput
from mario.parsers.exiobase_hybrid import (
    parse_exiobase_hybrid_iot,
    parse_exiobase_hybrid_sut,
)
from mario.parsers.exiobase_iot import parse_exiobase_iot_monetary
from mario.parsers.exiobase_sut import parse_exiobase_sut_monetary
from mario.parsers.tabular import (
    eora_single_region,
    txt_parser,
    excel_parser,
    eora_multi_region,
    parse_pymrio,
    parser_figaro_sut,
)
from mario.parsers.handshake import (
    parse_exiobase_3_9_4,
    parse_oecd
    )

from mario.parsers.specs import HMRSUT_EXTENSIONS, HMIOT_EXTENSIONS, INPUT_OPTIONS
import pandas as pd

models = {"Database": Database}

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
    **kwargs,
):
    """Parse a database from a folder of text files.

    .. note::

        This function works with different files to parse the io data. So every matrix & units should be placed in different txt files.


    Parameters
    ----------
    path : str
        defined the folder that contains data files.

    table : str
        acceptable options are 'IOT' & 'SUT'

    mode : str
        defined the base matrices to parse. The options are:

            * `flows`: needs [Z.txt, Y.txt, EY.txt, V.txt, E.txt, units.txt] in the path
            * `coefficients`: needs [z.txt, Y.txt, EY.txt, v.txt, e.txt, units.txt] in the path

    calc_all : boolean
        if True, by default will calculate z,v,e,V,E,Z after parsing

    year : int, Optional
        optional to the Database (just for recoding the metadata)

    source : str, Optional
        optional to the Database (just for recoding the metadata)

    name : str, Optional
        optional but suggested. is useful for visualization and metadata.

    sep : str, Optional
        txt file separator

    Returns
    -------
    mario.Database
    """

    # check key inputs to be correct
    errmsg = []
    if table not in INPUT_OPTIONS["table"]:
        errmsg.append(f"Table should be in {INPUT_OPTIONS['table']}")
    if mode not in INPUT_OPTIONS["mode"]:
        errmsg.append(f"Mode should be in {INPUT_OPTIONS['mode']}")
    if errmsg:
        raise WrongInput(errmsg)

    matrices, indeces, units = txt_parser(path, table, mode, sep)

    return models[model](
        name=name,
        table=table,
        source=source,
        year=year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_from_excel(
    path: str,
    table: str,
    mode: str,
    data_sheet: str = 0,
    unit_sheet: str = "units",
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
        * Please look at the tutorials to understand the format/shape of the data

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

    # check key inputs to be correct
    errmsg = []
    if table not in INPUT_OPTIONS["table"]:
        errmsg.append(f"Table should be in {INPUT_OPTIONS['table']}")
    if mode not in INPUT_OPTIONS["mode"]:
        errmsg.append(f"Mode should be in {INPUT_OPTIONS['mode']}")
    if errmsg:
        raise WrongInput(errmsg)
    
    matrices, indeces, units = excel_parser(path, table, mode, data_sheet, unit_sheet)

    return models[model](
        name=name,
        table=table,
        source=source,
        year=year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_exiobase_sut(
    path: str,
    calc_all: bool =False,
    name: str = None,
    year: int = None,
    add_extensions: str | None = None,
    model: str = "Database",
    **kwargs,
):
    """Parse the monetary EXIOBASE SUT into a ``Database`` instance.

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
    **kwargs,
):
    """Parse a monetary EXIOBASE IOT folder into a ``Database`` instance.

    .. note::

        The parser auto-detects the EXIOBASE layout from the folder contents and
        ``metadata.json``. The ``version`` argument is kept only as an optional
        compatibility check.

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
    table: str,
    indeces: str = None,
    name_convention: str = "full_name",
    aggregate_trade: bool = True,
    year: int = None,
    name: str = None,
    calc_all: bool = False,
    model: str = "Database",
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
        path to the zip file containing the database

    multi_region : bool
        True for eora26 else False

    indeces : str
        in case of multi_region database, the indeces.zip file path should be
        given

    name_convension : str
        will take the full names of countries if `full_name` otherwise, takes
        the abbreviations

    aggregate_trade : boolean
        if True, will aggregated all the trades into total imports and exports
        in single region database

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
        if year is None or indeces is None:
            raise LackOfInput(
                "For multi region Eora, the year and indeces path should be defined"
            )

        if table == "SUT":
            raise NotImplemented(
                "No handling of multiregional SUT from EORA is implemented yet"
            )

        matrices, indeces, units = eora_multi_region(
            data_path=path, index_path=indeces, year=year, price="bp"
        )

        kwargs["notes"] = [
            "ROW deleted from database due to inconsistency.",
            "Intermediate imports from ROW added to VA matrix",
            "Intermediate exports to ROW added to Y matrix",
        ]

    else:
        matrices, indeces, units = eora_single_region(
            path=path,
            table=table,
            name_convention=name_convention,
            aggregate_trade=aggregate_trade,
        )

    return models[model](
        name=name,
        table=table,
        year=year,
        source="Eora website @ https://www.worldmrio.com/",
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_exiobase(
    table:str,
    unit:str,
    path:str,
    model:str = "Database",
    name:str = None, 
    year:int = None, 
    calc_all: bool = False, 
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
    calc_all : boolean
        if True, by default will calculate z,v,e after parsing
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

    kwargs["path"] = path
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

    For more informatio refer to https://zenodo.org/record/7244919#.Y6hEfi8w2L1
    """

    if extensions not in (None, "all"):
        differnce = sorted(set(extensions).difference(set(HMRSUT_EXTENSIONS)))
        if differnce:
            raise WrongInput(
                "Following items are not valid for extensions: \n {}.\n Valid items are: \n {}".format(
                    differnce,
                    HMRSUT_EXTENSIONS,
                )
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
    if extensions not in (None, "all"):
        differnce = sorted(set(extensions).difference(set(HMIOT_EXTENSIONS)))
        if differnce:
            raise WrongInput(
                "Following items are not valid for extensions: \n {}.\n Valid items are: \n {}".format(
                    differnce,
                    HMIOT_EXTENSIONS,
                )
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


def parse_eurostat_sut(
    supply_path:str,
    use_path:str,
    model:str="Database",
    name:str=None,
    calc_all:bool=False,
    **kwargs,
) -> object:
    """Parse a Eurostat SUT pair.

    .. note::

        * this function is not generally applicable to any Eurostat table: it works only for specific table formats. Please refer to the example on the website
        * first rule: it is not possible to parse file different from .xls format
        * second rule: in each .xsl file, be sure data are referring to only one region
        * third rule: use only "total" as stock/flow parameter, and only one unit of measure
        * forth rule: supply must be provided in activity by commodity, use must be provided in commodity by activitiy formats

    Parameters
    ----------
    supply_path : str
        path to the .xls file containing the supply table
    use_path : str
        path to the .xls file containing the use table
    name : str, Optional
        for recording on the metadata

    calc_all : bool, Optional
        if True, will calculate the main missing matrices

    Returns
    -------
    mario.Database
    """

    raise NotImplemented("This function was deprecated since the parser was too dependent on Eurostat web interface. Downgrade to mariopy==v.3.3.3 in case you need it")


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

    value_added : dict
        the value_added mapper. keys will be the io Extensions and the values will be the slicers if exist. in case that all the rows of the
        specific Extension should be assigned, 'all' should be passed.

    satellite_account : dict
        the satellite_account mapper. keys will be the io Extensions and the values will be the slicers if exist. in case that all the rows of the
        specific Extension should be assigned, 'all' should be passed.

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


def parse_FIGARO_SUT(
        path:str, 
        name:str = None, 
        calc_all:bool = False, 
        **kwargs
    ):
    """Parse a FIGARO SUT folder into a ``Database`` instance.

    Parameters
    ----------
    path : str
        the folder where the files are downloaded
    name : str, optional
        a name for the database, by default None
    calc_all : bool, optional
        calacualtes all the missing matrices, by default False

    Returns
    -------
    mario.Database
        mario database object
    """

    matrices, indeces, units, year = parser_figaro_sut(path)

    return models["Database"](
        name=name,
        table="SUT",
        source="eurostat (https://ec.europa.eu/eurostat/web/esa-supply-use-input-tables/database)",
        year=year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )
