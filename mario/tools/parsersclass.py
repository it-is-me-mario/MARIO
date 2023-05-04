# -*- coding: utf-8 -*-
"""
This module contains all the mario parsers API
"""

from mario import Database
from mario.tools.tableparser import (
    eora_single_region,
    txt_praser,
    excel_parser,
    exio3,
    monetary_sut_exiobase,
    eora_multi_region,
    eurostat_sut,
    parse_pymrio,
    hybrid_sut_exiobase_reader
)

from mario.log_exc.exceptions import WrongInput, LackOfInput

models = {"Database": Database}


def parse_from_txt(
    path,
    table,
    mode,
    calc_all=False,
    year=None,
    name=None,
    source=None,
    model="Database",
    sep = ',',
    **kwargs,
):

    """Parsing database from text files

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
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    matrices, indeces, units = txt_praser(path, table, mode,sep)

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
    path,
    table,
    mode,
    data_sheet=0,
    unit_sheet="units",
    calc_all=False,
    year=None,
    name=None,
    source=None,
    model="Database",
    **kwargs,
):

    """Parsing database from excel file

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

    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

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
    path, calc_all=False, name=None, year=None, model="Database", **kwargs,
):

    """Parsing exiobase mrsut

    .. note::

        mario v.0.1.0, supports only Monetary Exiobase MRSUT database.

    Parameters
    ----------
    path : str
        defined the zip file containing data

    calc_all : boolean
        if True, by default will calculate z,v,e after parsing

    year : int, Optional
        optional to the Database (just for recoding the metadata)

    name : str, Optional
        optional but suggested. is useful for visualization and metadata.

    Returns
    -------
    mario.Database
    """

    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    matrices, indeces, units = monetary_sut_exiobase(path,)

    return models[model](
        name=name,
        table="SUT",
        source="Exiobase Monetary Multi Regional Supply and Use Table (https://www.exiobase.eu/)",
        year=year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_exiobase_3(
    path,
    calc_all=False,
    year=None,
    name=None,
    model="Database",
    version="3.8.2",
    **kwargs,
):

    """Parsing exiobase3

    .. note::

        pxp & ixi does not make any difference for the parser.

    Parameters
    ----------

    path : str
        defined the zip file containing data

    calc_all : boolean
        if True, by default will calculate z,v,e after parsing

    year : int, Optional
        optional to the Database (just for recoding the metadata)

    name : str, Optional
        optional but suggested. is useful for visualization and metadata.

    version : str
        accpetable versions are:

            * 3.8.2: F_Y for the final demand satellite account
            * 3.8.1: F_hh for the final demand satellite account

    Returns
    -------
    mario.Database

    """
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))

    if version not in ["3.8.2", "3.8.1"]:
        raise WrongInput("Acceptable versions are {}".format(["3.8.2", "3.8.1"]))
    matrices, indeces, units = exio3(path, version)

    return models[model](
        name=name,
        table="IOT",
        source="Exiobase3",
        year=year,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_eora(
    path,
    multi_region,
    table,
    indeces=None,
    name_convention="full_name",
    aggregate_trade=True,
    year=None,
    name=None,
    calc_all=False,
    model="Database",
    **kwargs,
) -> object:
    """Parsing eora databases

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

        if table == 'SUT':
            raise NotImplemented("No handling of multiregional SUT from EORA is implemented yet")

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
            path=path, table=table, name_convention=name_convention, aggregate_trade=aggregate_trade
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
    table,
    unit,
    path,
    model = "Database",
    name = None,
    year = None,
    calc_all = False,
    **kwargs 
):
    """A unique function for parsing all exiobase databases

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
    
    if table not in ["IOT","SUT"]:
        raise WrongInput("table only accpets 'IOT' or 'SUT'.")
    
    if unit not in ["Hybrid","Monetary"]:
        raise WrongInput("unit only accpets 'Hybrid' or 'Monetary.'")
    
    if table == "IOT":
        if unit == "Monetary":
            parser = parse_exiobase_3

        else: 
            raise WrongInput("Hybrid IOT exiobase is not supported by mario.")
        
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
    path,
    extensions = [],
    model = "Database",
    name=None,
    calc_all=False,
    **kwargs
):
    """reads hybrid supply and use exiobase

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
    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))   

    matrices,indeces,units = hybrid_sut_exiobase_reader(
        path = path,
        extensions = extensions,
    )

    notes = ["The name of extensions are changed to avoid confusion of same satellite account category for different extensions. For example 'Food' in 'pack_use_waste_act' is changed to 'Food (pack_use_waste)' to avoid confusion with 'Food' in 'pack_sup_waste'"]

    return models[model](
        name=name,
        table="SUT",
        source="Merciai, Stefano, & Schmidt, Jannick. (2021). EXIOBASE HYBRID v3 - 2011 (3.3.18) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.7244919",
        year=2011,
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        notes = notes,
        **kwargs,
    )

def parse_eurostat_sut(
    supply_path,
    use_path,
    model="Database",
    name=None,
    calc_all=False,
    **kwargs,
) -> object:

    """Parsing Eurostat databases

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

    if model not in models:
        raise WrongInput("Available models are {}".format([*models]))


    matrices, indeces, units,meta = eurostat_sut(
            supply_path,
            use_path,
        )

    return models[model](
        name=name,
        table="SUT",
        source="eurostat",
        year=meta["year"],
        init_by_parsers={"matrices": matrices, "_indeces": indeces, "units": units},
        calc_all=calc_all,
        **kwargs,
    )


def parse_from_pymrio(
    io,
    value_added,
    satellite_account,
    include_meta=True
    ):
    """Parsing a pymrio database

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

