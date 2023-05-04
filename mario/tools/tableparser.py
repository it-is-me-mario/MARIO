# -*- coding: utf-8 -*-
"""
this module contains the main functions behind parsing differnet type of
databases
"""
from mario.log_exc.exceptions import WrongInput, WrongExcelFormat, WrongFormat

from mario.log_exc.logger import log_time

from mario.tools.utilities import (
    delete_duplicates,
    all_file_reader,
    return_index,
    rename_index,
    sort_frames,
    to_single_index,
    extract_metadata_from_eurostat,
)

from mario.tools.constants import (
    _ACCEPTABLES,
    _UNITS,
    _EXIO_FACTORS,
    _MASTER_INDEX,
    _EXIO_INDEX,
    _PYMRIO_INDEXING,
)

from mario.tools.parsers_id import (
    exiobase_version_3,
    exiobase_mrsut,
    txt_parser_id,
    eora,
    eora_parser_id,
    hybrid_sut_exiobase_parser_id,
    eurostat_id
)

from mario.tools.iomath import (
    calc_X,
    calc_X_from_w,
    calc_w,
    calc_X_from_z,
)

import pandas as pd
import logging
import copy
import numpy as np
import math
import pymrio

# reading the constants

logger = logging.getLogger(__name__)


def get_index_txt(Z, V, Y, E, table):

    if table == "SUT":
        regions_main = delete_duplicates(Z.columns.get_level_values(0))
        satellite_main = delete_duplicates(E.index)
        factors_main = delete_duplicates(V.index)

        try:
            activities_main = delete_duplicates(
                Z.loc[(slice(None), _MASTER_INDEX["a"]), :].index.get_level_values(2)
            )
            dummy = Z.loc[(slice(None), _MASTER_INDEX["a"]), :]
        except KeyError:
            raise WrongFormat(
                "{} can not be found in rows or columns in the database.".format(
                    _MASTER_INDEX["a"]
                )
            )

        try:
            commodities_main = delete_duplicates(
                Z.loc[(slice(None), _MASTER_INDEX["c"]), :].index.get_level_values(2)
            )
            dummy = Z.loc[(slice(None), _MASTER_INDEX["c"]), :]
        except KeyError:
            raise WrongFormat(
                "{} can not be found in rows or columns in the database.".format(
                    _MASTER_INDEX["c"]
                )
            )

        try:
            finaluser_main = delete_duplicates(
                Y.T.loc[(slice(None), _MASTER_INDEX["n"]), :].index.get_level_values(2)
            )
        except KeyError:
            raise WrongFormat(
                "{} can not be found in the database.".format(_MASTER_INDEX["n"])
            )

        indeces = {
            "r": {"main": regions_main},
            "n": {"main": finaluser_main},
            "k": {"main": satellite_main},
            "f": {"main": factors_main},
            "a": {"main": activities_main},
            "c": {"main": commodities_main},
            "s": {"main": activities_main + commodities_main},
        }

    else:
        regions_main = delete_duplicates(Z.columns.get_level_values(0))
        satellite_main = delete_duplicates(E.index)
        factors_main = delete_duplicates(V.index)

        try:
            sectors_main = delete_duplicates(
                Z.loc[(slice(None), _MASTER_INDEX["s"]), :].index.get_level_values(2)
            )
            dummy = Z.loc[(slice(None), _MASTER_INDEX["s"]), :]
        except KeyError:
            raise WrongFormat(
                "{} can not be found in rows or columns in the database.".format(
                    _MASTER_INDEX["s"]
                )
            )

        try:
            finaluser_main = delete_duplicates(
                Y.T.loc[(slice(None), _MASTER_INDEX["n"]), :].index.get_level_values(2)
            )
        except KeyError:
            raise WrongFormat(
                "{} can not be found in the database.".format(_MASTER_INDEX["n"])
            )

        indeces = {
            "r": {"main": regions_main},
            "n": {"main": finaluser_main},
            "k": {"main": satellite_main},
            "f": {"main": factors_main},
            "s": {"main": sectors_main},
        }

    return indeces


def get_index_excel(data, table, mode):

    if table == "SUT":
        # first level of the columns should represent the regions
        regions_main = delete_duplicates(data.columns.get_level_values(0))

        try:
            satellite_main = delete_duplicates(
                data.loc[(slice(None), _MASTER_INDEX["k"]), :].index.get_level_values(2)
            )
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in the database.".format(_MASTER_INDEX["k"])
            )

        try:
            factors_main = delete_duplicates(
                data.loc[(slice(None), _MASTER_INDEX["f"]), :].index.get_level_values(2)
            )
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in the database.".format(_MASTER_INDEX["f"])
            )

        try:
            activities_main = delete_duplicates(
                data.loc[(slice(None), _MASTER_INDEX["a"]), :].index.get_level_values(2)
            )
            dummy = data.loc[(slice(None), _MASTER_INDEX["a"]), :]
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in rows or columns in the database.".format(
                    _MASTER_INDEX["a"]
                )
            )

        try:
            commodities_main = delete_duplicates(
                data.loc[(slice(None), _MASTER_INDEX["c"]), :].index.get_level_values(2)
            )
            dummy = data.loc[(slice(None), _MASTER_INDEX["c"]), :]
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in rows or columns in the database.".format(
                    _MASTER_INDEX["c"]
                )
            )

        try:
            finaluser_main = delete_duplicates(
                data.T.loc[(slice(None), _MASTER_INDEX["n"]), :].index.get_level_values(
                    2
                )
            )
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in the database.".format(_MASTER_INDEX["n"])
            )

        indeces = {
            "r": {"main": regions_main},
            "n": {"main": finaluser_main},
            "k": {"main": satellite_main},
            "f": {"main": factors_main},
            "a": {"main": activities_main},
            "c": {"main": commodities_main},
            "s": {"main": activities_main + commodities_main},
        }

    else:

        # first level of the columns should represent the regions
        regions_main = delete_duplicates(data.columns.get_level_values(0))

        try:
            satellite_main = delete_duplicates(
                data.loc[(slice(None), _MASTER_INDEX["k"]), :].index.get_level_values(2)
            )
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in the database.".format(_MASTER_INDEX["k"])
            )

        try:
            factors_main = delete_duplicates(
                data.loc[(slice(None), _MASTER_INDEX["f"]), :].index.get_level_values(2)
            )
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in the database.".format(_MASTER_INDEX["f"])
            )

        try:
            sectors_main = delete_duplicates(
                data.loc[(slice(None), _MASTER_INDEX["s"]), :].index.get_level_values(2)
            )
            dummy = data.loc[(slice(None), _MASTER_INDEX["s"]), :]
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in rows or columns in the database.".format(
                    _MASTER_INDEX["s"]
                )
            )

        try:
            finaluser_main = delete_duplicates(
                data.T.loc[(slice(None), _MASTER_INDEX["n"]), :].index.get_level_values(
                    2
                )
            )
        except KeyError:
            raise WrongExcelFormat(
                "{} can not be found in the database.".format(_MASTER_INDEX["n"])
            )

        indeces = {
            "r": {"main": regions_main},
            "n": {"main": finaluser_main},
            "k": {"main": satellite_main},
            "f": {"main": factors_main},
            "s": {"main": sectors_main},
        }

    return indeces


def get_units(units, table, indeces):

    if set(units.index.get_level_values(0)) != set([*_UNITS[table]]):
        raise WrongFormat(
            "the units should contain {} levels for {}.".format([*_UNITS[table]], table)
        )

    _ = {}
    for matrix in [*_UNITS[table]]:

        # take all the items that should be there (in units)
        index_check = indeces[_UNITS[table][matrix]]["main"]
        # take the items that are there
        index_unit = units.index.get_level_values(1).to_list()

        warning = []
        _units = {}

        # check if all the items are represented in the data or not
        for item in index_check:
            # if it is not there, append it to the warnign list
            if item not in index_unit:
                warning.append(item)
            else:
                # otherwise add it to the _unit dict
                _units[item] = units.loc[(matrix, item)][0]

        # if some items are missed, raise an error and show them
        if warning:
            raise WrongExcelFormat(
                "unit is not represented for the following items: \n{} for '{}' level.".format(
                    warning, matrix
                )
            )

        _[matrix] = pd.DataFrame.from_dict(_units, orient="index", columns=["unit"])

    # if everything is ok, build a dataframe from the units.
    return _


def txt_praser(path, table, mode,sep):

    if mode == "coefficients":
        v, e, z = list("vez")
    else:
        v, e, z = list("VEZ")

    log_time(logger, f"Parser: Reading {mode} from txt files.")
    read = all_file_reader(
        path=path,
        guide=txt_parser_id[mode],
        sub_folder=False,
        sep=sep,
        exceptions=("EY"),
    )

    log_time(logger, "Parser: Reading files finished.")
    _units = read["units"]["all"]

    log_time(logger, "Parser: Investigating possible identifiable errors.")

    indeces = get_index_txt(
        Z=read["matrices"][z],
        V=read["matrices"][v],
        Y=read["matrices"]["Y"],
        E=read["matrices"][e],
        table=table,
    )

    # sorting the matrices
    sort_frames(read["matrices"])
    log_time(
        logger, "Parser: Parsing database finished. Calculating missing matrices.."
    )
    print(read["matrices"])
    if mode == "flows":
        read["matrices"]["X"] = calc_X(read["matrices"]["Z"], read["matrices"]["Y"])

    else:
        read["matrices"]["X"] = calc_X_from_w(calc_w(read["matrices"]["z"]), read["matrices"]["Y"])

    
    log_time(logger, "Parser: Production matrix calculated and added.")

    if "EY" not in read["matrices"]:
        log_time(
            logger,
            "Parser: EY matrix is not present in the database. An EY matrix with 0 values created",
            "warn",
        )
        read["matrices"]["EY"] = pd.DataFrame(
            0, index=read["matrices"][e].index, columns=read["matrices"]["Y"].columns
        )

    units = get_units(_units, table, indeces)
    rename_index(read["matrices"])

    matrices = {"baseline": {**read["matrices"]}}

    return matrices, indeces, units


def excel_parser(path, table, mode, sheet_name, unit_sheet):

    if table not in _ACCEPTABLES["table"]:
        raise WrongInput(
            "{} is not an acceptable value for table. Acceptable valuse are \n{}".format(
                table, _ACCEPTABLES["table"]
            )
        )
    if mode not in ["flows", "coefficients"]:
        raise WrongInput("Acceptable modes are `coefficients` and `flows`.")

    data = pd.read_excel(
        path, header=[0, 1, 2], index_col=[0, 1, 2], sheet_name=sheet_name
    )
    indeces = get_index_excel(data, table, mode)

    if table == "SUT":

        Z = data.loc[
            (slice(None), [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]),
            (slice(None), [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]),
        ]
        Y = data.loc[
            (slice(None), [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]),
            (slice(None), _MASTER_INDEX["n"]),
        ]
        E = data.loc[
            (slice(None), _MASTER_INDEX["k"]),
            (slice(None), [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]),
        ]
        V = data.loc[
            (slice(None), _MASTER_INDEX["f"]),
            (slice(None), [_MASTER_INDEX["a"], _MASTER_INDEX["c"]]),
        ]
        EY = data.loc[
            (slice(None), _MASTER_INDEX["k"]), (slice(None), _MASTER_INDEX["n"])
        ]

    else:
        Z = data.loc[
            (slice(None), [_MASTER_INDEX["s"], _MASTER_INDEX["s"]]),
            (slice(None), [_MASTER_INDEX["s"], _MASTER_INDEX["s"]]),
        ]
        Y = data.loc[
            (slice(None), [_MASTER_INDEX["s"], _MASTER_INDEX["s"]]),
            (slice(None), _MASTER_INDEX["n"]),
        ]
        E = data.loc[
            (slice(None), _MASTER_INDEX["k"]),
            (slice(None), [_MASTER_INDEX["s"], _MASTER_INDEX["s"]]),
        ]
        V = data.loc[
            (slice(None), _MASTER_INDEX["f"]),
            (slice(None), [_MASTER_INDEX["s"], _MASTER_INDEX["s"]]),
        ]
        EY = data.loc[
            (slice(None), _MASTER_INDEX["k"]), (slice(None), _MASTER_INDEX["n"])
        ]

    V.index = V.index.get_level_values(-1)
    E.index = E.index.get_level_values(-1)
    EY.index = EY.index.get_level_values(-1)

    if mode == "coefficients":

        matrices = {
            "baseline": {
                "z": Z,
                "v": V,
                "e": E,
                "Y": Y,
                "X": calc_X_from_z(Z, Y),
                "EY": EY,
            }
        }
    else:
        matrices = {
            "baseline": {"Z": Z, "V": V, "E": E, "Y": Y, "X": calc_X(Z, Y), "EY": EY,}
        }

    # read the unit sheet from the excel file
    units = get_units(
        pd.read_excel(path, sheet_name=unit_sheet, index_col=[0, 1]), table, indeces
    )
    rename_index(matrices["baseline"])
    sort_frames(matrices["baseline"])

    return matrices, indeces, units


def exio3(path, version):

    log_time(logger, "Parser: Parsing exiobase database from {}".format(path))
    read = all_file_reader(path, exiobase_version_3[version], sub_folder=True)

    log_time(logger, "Parser: Parsing finished. Reshaping the datbase to MARIO format.")
    # we need to reshape the V and E matrix from F
    read["matrices"]["V"] = read["matrices"]["F"].loc[_EXIO_FACTORS, :]
    read["matrices"]["E"] = read["matrices"]["F"].drop(_EXIO_FACTORS)
    read["matrices"]["EY"] = read["matrices"]["EY"].drop(_EXIO_FACTORS)

    del read["matrices"]["F"]

    indeces = {}
    for key, value in _EXIO_INDEX.items():
        indeces[key] = return_index(
            df=read["matrices"][value["matrix"]],
            item=value["item"],
            level=value["level"],
            multi_index=value["multi_index"],
            del_duplicate=value["del_duplicate"],
            reindex=value.get("reindex"),
        )

    z_index = read["matrices"]["Z"].index
    z_index = [
        z_index.get_level_values(0),
        [_MASTER_INDEX["s"]] * len(z_index.get_level_values(0)),
        z_index.get_level_values(1),
    ]

    y_index = read["matrices"]["Y"].columns
    y_index = [
        y_index.get_level_values(0),
        [_MASTER_INDEX["n"]] * len(y_index.get_level_values(0)),
        y_index.get_level_values(1),
    ]

    REINDEX = {
        "Z": {"columns": z_index, "index": z_index},
        "V": {"columns": z_index, "index": indeces[_MASTER_INDEX["f"]]},
        "E": {"columns": z_index, "index": indeces[_MASTER_INDEX["k"]]},
        "EY": {"columns": y_index, "index": indeces[_MASTER_INDEX["k"]]},
        "Y": {"columns": y_index, "index": z_index},
    }

    for matrix, value in REINDEX.items():
        for level, newindex in value.items():
            exec("read['matrices']['{}'].{} = newindex".format(matrix, level))

    read["matrices"]["X"] = calc_X(read["matrices"]["Z"], read["matrices"]["Y"])

    # adding the missing units
    for item in ["f", "s"]:
        read["units"][_MASTER_INDEX[item]] = pd.DataFrame(
            data="M EUR", index=indeces[_MASTER_INDEX[item]], columns=["unit"]
        )

    matrices = {"baseline": read["matrices"]}
    _indeces = {}

    for key, value in _MASTER_INDEX.items():
        try:
            _indeces[key] = {"main": indeces[value]}
        except KeyError:
            pass

    rename_index(read["matrices"])

    return matrices, _indeces, read["units"]


def dataframe_parser(Z, Y, E, V, EY, units, table):

    if isinstance(units, dict):
        units = pd.concat(units.values(), keys=units.keys())

    indeces = get_index_txt(Z, V, Y, E, table)
    units = get_units(units, table, indeces)

    if not EY.index.equals(E.index) or not EY.columns.equals(Y.columns):
        raise WrongInput("EY has not the correct format.")

    X = calc_X(Z, Y)

    matrices = {"baseline": {"Z": Z, "Y": Y, "V": V, "E": E, "X": X, "EY": EY,}}

    rename_index(matrices["baseline"])
    sort_frames(matrices["baseline"])

    return matrices, indeces, units


def monetary_sut_exiobase(path):

    # reading the files
    read = all_file_reader(path, exiobase_mrsut, sub_folder=True)

    V = read["matrices"]["V"]
    U = read["matrices"]["U"]
    Y = read["matrices"]["Y"]
    S = read["matrices"]["S"]

    # Cpmmodities index
    c_index = [
        S.index.get_level_values(0),
        [_MASTER_INDEX["c"]] * S.shape[0],
        S.index.get_level_values(1),
    ]
    # Activities index
    a_index = [
        S.columns.get_level_values(0),
        [_MASTER_INDEX["a"]] * S.shape[1],
        S.columns.get_level_values(1),
    ]
    # Demand index
    n_index = [
        Y.columns.get_level_values(0),
        [_MASTER_INDEX["n"]] * Y.shape[1],
        Y.columns.get_level_values(1),
    ]

    # reshape the indeces
    S.index = c_index
    S.columns = a_index
    S = S.T

    U.index = c_index
    U.columns = a_index

    V.columns = a_index

    Y.index = c_index
    Y.columns = n_index

    # adding the lower part to Y
    y_lower = pd.DataFrame(
        np.zeros((len(a_index[0]), len(n_index[0]))), index=a_index, columns=n_index
    )
    Y = Y.append(y_lower)

    # Creating the missing parts of the z matrix
    z_upper = pd.DataFrame(
        np.zeros((len(c_index[0]), len(c_index[0]))), index=c_index, columns=c_index
    )
    z_upper = z_upper.append(S)

    z_lower = pd.DataFrame(
        np.zeros((len(a_index[0]), len(a_index[0]))), index=a_index, columns=a_index
    )
    z_lower = U.append(z_lower)

    Z = z_upper.join(z_lower)

    # adding the left part of V
    v_left = pd.DataFrame(
        np.zeros((len(V.index), len(c_index[0]))), index=V.index, columns=c_index
    )
    V = v_left.join(V)

    # creating fake E and EY
    E = pd.DataFrame(0, index=["None"], columns=V.columns)
    EY = pd.DataFrame(0, index=["None"], columns=Y.columns)

    X = calc_X(Z, Y)

    indeces = {
        "r": {"main": delete_duplicates(c_index[0].to_list())},
        "n": {"main": delete_duplicates(n_index[2].to_list())},
        "k": {"main": ["None"]},
        "f": {"main": delete_duplicates(V.index.to_list())},
        "s": {
            "main": delete_duplicates(a_index[2].to_list())
            + delete_duplicates(c_index[2].to_list()),
        },
        "a": {"main": delete_duplicates(a_index[2].to_list())},
        "c": {"main": delete_duplicates(c_index[2].to_list())},
    }

    # creating units
    activities_unit = pd.DataFrame(
        ["EUR"] * len(indeces["a"]["main"]),
        index=indeces["a"]["main"],
        columns=["unit"],
    )
    commodities_unit = pd.DataFrame(
        ["EUR"] * len(indeces["c"]["main"]),
        index=indeces["c"]["main"],
        columns=["unit"],
    )
    factors_unit = pd.DataFrame(
        ["EUR"] * len(indeces["f"]["main"]),
        index=indeces["f"]["main"],
        columns=["unit"],
    )
    extensions_unit = pd.DataFrame(
        ["None"] * len(indeces["k"]["main"]),
        index=indeces["k"]["main"],
        columns=["unit"],
    )

    matrices = {"baseline": {"Z": Z, "V": V, "E": E, "EY": EY, "Y": Y, "X": X,}}

    units = {
        _MASTER_INDEX["a"]: activities_unit,
        _MASTER_INDEX["c"]: commodities_unit,
        _MASTER_INDEX["f"]: factors_unit,
        _MASTER_INDEX["k"]: extensions_unit,
    }

    rename_index(matrices["baseline"])

    return matrices, indeces, units

def eora_single_region(path, table, name_convention="full_name", aggregate_trade=True):
    """
    Eora single region parser
    """

    region_level = 1 if name_convention == "full_name" else 2

    data = pd.read_csv(path, sep="\t", index_col=[2, 0, 1, 3], header=[2, 0, 1, 3])

    if table == 'IOT': 
        Z_index = eora[_MASTER_INDEX["s"]]

    elif table == 'SUT':
        Z_index = eora[_MASTER_INDEX["a"]] + eora[_MASTER_INDEX["c"]]

    Z = data.loc[Z_index, Z_index]
    Y = data.loc[Z_index, eora[_MASTER_INDEX["n"]]]
    V = data.loc[eora[_MASTER_INDEX["f"]], Z_index]

    take_E = data.drop(Z_index + eora[_MASTER_INDEX["f"]])

    E = take_E[Z_index]
    EY = take_E[eora[_MASTER_INDEX["n"]]].fillna(0)

    # taking the indeces

    regions = delete_duplicates(Z.index.get_level_values(region_level).tolist())
    satellite = [
        E.index.get_level_values(3).tolist()[index] + " (" + value + ")"
        for index, value in enumerate(E.index.get_level_values(2).tolist())
    ]
    
    if table == 'IOT':
        sectors = Z.index.get_level_values(-1).tolist()
    else:
        activities = Z.loc[eora[_MASTER_INDEX["a"]]].index.get_level_values(-1).tolist()
        commodities = Z.loc[eora[_MASTER_INDEX["c"]]].index.get_level_values(-1).tolist()

    if aggregate_trade:

        V = V.groupby(level=[0, 3], axis=0, sort=False).sum()
        Y = Y.groupby(level=[0, 3], axis=1, sort=False).sum()
        EY = EY.groupby(level=[0, 3], axis=1, sort=False).sum()

        final_consumptions = Y.columns.get_level_values(-1).tolist()
        final_consumptions.remove("Total")
        final_consumptions.append("Exports")

        factors = V.index.get_level_values(-1).tolist()
        factors.remove("Total")
        factors.append("Imports")

    else:
        imports_from = [
            "Import From " + index[0] for index in V.loc["ImportsFrom"].index
        ]
        factors = V.loc["Primary Inputs"].index.get_level_values(-1).tolist()

        factors.extend(imports_from)

        exports_to = ["Export To " + index[0] for index in Y["ExportsTo"].columns]
        final_consumptions = Y["Final Demand"].columns.get_level_values(-1).tolist()

        final_consumptions.extend(exports_to)

    # Taking the units

    if table == 'IOT':
        sectors_unit = pd.DataFrame("USD", index=sectors, columns=["unit"])
        Z_index = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["s"]], sectors])

    else:
        activities_unit = pd.DataFrame("USD", index=activities, columns=["unit"])
        commodities_unit = pd.DataFrame("USD", index=commodities, columns=["unit"])
        Z_index_a = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["a"]], activities])
        Z_index_c = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["c"]], commodities])
        Z_index = Z_index_a.append(Z_index_c)

   
    factor_unit = pd.DataFrame("USD", index=factors, columns=["unit"])

    satellite_unit = pd.DataFrame(
        E.index.get_level_values(0).tolist(), index=satellite, columns=["unit"]
    )

    
    Y_index = pd.MultiIndex.from_product([regions, [_MASTER_INDEX['n']], final_consumptions])

    indeces = {
        "Y": {"columns": Y_index, "index": Z_index},
        "Z": {"columns": Z_index, "index": Z_index},
        "E": {"columns": Z_index, "index": satellite},
        "V": {"columns": Z_index, "index": factors},
        "EY": {"columns": Y_index, "index": satellite},
    }

    for matrix, value in indeces.items():
        print(matrix)
        for level, ind in value.items():
            exec(f"{matrix}.{level} = ind")

    matrices = {
        "baseline": {"Z": Z, "V": V, "E": E, "EY": EY, "Y": Y, "X": calc_X(Z, Y),}
    }

    rename_index(matrices["baseline"])



    if table =='IOT':
        units = {
            _MASTER_INDEX["s"]: sectors_unit,
            _MASTER_INDEX["f"]: factor_unit,
            _MASTER_INDEX["k"]: satellite_unit,
        }    
        indeces = {
        "r": {"main": regions},
        "n": {"main": final_consumptions},
        "k": {"main": satellite},
        "f": {"main": factors},
        "s": {"main": sectors},
    }
    else:
        
        units = {
        _MASTER_INDEX["a"]: activities_unit,
        _MASTER_INDEX["c"]: commodities_unit,
        _MASTER_INDEX["f"]: factor_unit,
        _MASTER_INDEX["k"]: satellite_unit,
    }
        indeces = {
        "r": {"main": regions},
        "n": {"main": final_consumptions},
        "k": {"main": satellite},
        "f": {"main": factors},
        "a": {"main": activities},
        "c": {"main": commodities},
    }

    return matrices, indeces, units


def eora_multi_region(data_path, index_path, year, price):
    """
    Eora 26 multi-region parser
    """

    parser_ids = copy.deepcopy(eora_parser_id)

    for main_key in parser_ids.keys():
        for values in parser_ids[main_key].values():
            values["file_name"] = values["file_name"].format(year=year, price=price)

    labels = all_file_reader(
        index_path, dict(labels=parser_ids["labels"]), sub_folder=False
    )

    # reading the files
    read = all_file_reader(
        data_path, dict(matrices=parser_ids["matrices"]), sub_folder=False
    )

    Z = copy.deepcopy(read["matrices"]["Z"])
    V = copy.deepcopy(read["matrices"]["V"])
    E = copy.deepcopy(read["matrices"]["E"])
    Y = copy.deepcopy(read["matrices"]["Y"])
    EY = copy.deepcopy(read["matrices"]["EY"])

    z_index = copy.deepcopy(labels["labels"]["Z_i"].index)
    z_index = [
        z_index.get_level_values(0),
        [_MASTER_INDEX["s"]] * len(z_index),
        z_index.get_level_values(-1),
    ]

    v_index = copy.deepcopy(labels["labels"]["V_i"].index)
    e_index = copy.deepcopy(labels["labels"]["E_i"].index)
    e_index = [e_index[i][0] + " - " + e_index[i][1] for i in range(len(e_index))]

    y_correct = [
        "Household final consumption P.3h",
        "Non-profit institutions serving households P.3n",
        "Government final consumption P.3g",
        "Gross fixed capital formation P.51",
        "Changes in inventories P.52",
        "Acquisitions less disposals of valuables P.53",
        "Export to ROW",
    ]

    y_index = copy.deepcopy(labels["labels"]["Y_c"].index)

    y_index = [
        y_index.get_level_values(0),
        [_MASTER_INDEX["n"]] * len(y_index),
        y_index.get_level_values(-1),
    ]

    REINDEX = {
        "Z": {"columns": z_index, "index": z_index},
        "V": {"columns": z_index, "index": v_index},
        "E": {"columns": z_index, "index": e_index},
        "EY": {"columns": y_index, "index": e_index},
        "Y": {"columns": y_index, "index": z_index},
    }

    for matrix, value in REINDEX.items():
        for level, newindex in value.items():
            exec("{}.{} = newindex".format(matrix, level))

    log_time(
        logger,
        "Parser; Deleting `ROW` from database due to inconsistency"
        " in the datbase and will be added to Z and Y matrix.",
        "critical",
    )

    row_import = Z.loc[("ROW", "Sector", "TOTAL")]
    row_import.drop("ROW", axis=0, inplace=True)

    row_export = Z[("ROW", "Sector", "TOTAL")]
    row_export.drop("ROW", axis=0, inplace=True)
    row_export = row_export.to_frame()

    for matrix in [Z, V, E, EY, Y]:
        for axis in [0, 1]:
            try:
                matrix.drop("ROW", axis=axis, inplace=True)
            except KeyError:
                pass

    # adding row_import to V matrix
    V.loc["Import from ROW", V.columns] = row_import.values

    indeces = {
        "r": {"main": Z.index.unique(level=0).tolist()},
        "n": {"main": Y.columns.unique(level=-1).tolist()},
        "k": {"main": E.index.tolist()},
        "f": {"main": V.index.tolist()},
        "s": {"main": Z.index.unique(level=-1).tolist()},
    }

    # adding export to row in Y matrix and EY matrix
    new_Y_index = Y.index
    new_Y_columns = pd.MultiIndex.from_product(
        [
            indeces["r"]["main"],
            [_MASTER_INDEX["n"]],
            indeces["n"]["main"] + ["Export to ROW"],
        ]
    )
    new_Y = pd.DataFrame(0, index=new_Y_index, columns=new_Y_columns)
    new_Y.loc[Y.index, Y.columns] = Y.loc[Y.index, Y.columns].values

    # filling matrices
    for names, value in row_export.iterrows():
        new_Y.loc[names, (names[0], _MASTER_INDEX["n"], "Export to ROW")] = value.values

    # filling the EY
    new_EY = pd.DataFrame(0, index=EY.index, columns=new_Y_columns)
    new_EY.loc[EY.index, EY.columns] = EY.loc[EY.index, EY.columns].values

    # reindexing the final demand due to errors in the database
    y_columns = [
        new_Y.columns.get_level_values(0),
        new_Y.columns.get_level_values(1),
        y_correct * int(new_Y.shape[1] / len(y_correct)),
    ]

    new_Y.columns = y_columns
    new_EY.columns = y_columns

    units = {
        _MASTER_INDEX["s"]: pd.DataFrame(
            "M EUR", index=indeces["s"]["main"], columns=["unit"]
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            "M EUR", index=indeces["f"]["main"], columns=["unit"]
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            list(labels["labels"]["E_i"].index.get_level_values(0)),
            index=indeces["k"]["main"],
            columns=["unit"],
        ),
    }

    # updating the indeces
    indeces["n"]["main"] = new_Y.columns.unique(level=-1).tolist()

    matrices = {
        "baseline": {
            "Z": Z,
            "V": V,
            "E": E,
            "EY": new_EY,
            "Y": new_Y,
            "X": calc_X(Z, Y),
        }
    }

    rename_index(matrices["baseline"])

    return matrices, indeces, units



def eurostat_sut(
        supply_path,
        use_path,
):
    supply_file = pd.ExcelFile(supply_path)
    use_file = pd.ExcelFile(use_path)

    supply_meta = extract_metadata_from_eurostat(supply_file)
    use_meta = extract_metadata_from_eurostat(use_file)

    if "Supply table at basic prices" not in supply_meta["table"]:
        raise WrongInput("specified supply table dataset is {}. Acceptable dataset is 'Supply table at basic prices'."
                         "Please refer to the documents for proper download of the dataset".format(supply_meta["table"]))

    if "Use table at basic prices " not in use_meta["table"]:
        raise WrongInput("specified use table dataset is {}. Acceptable dataset is 'Use table at basic prices '."
                         "Please refer to the documents for proper download of the dataset".format(use_meta["table"]))
    
    if supply_meta["country"]!=use_meta["country"] or supply_meta["year"]!=use_meta["year"]:
        raise WrongInput("there are mismatched between the country/year of supply and use datasets.\nSupply Dataset: {}\nUse Dataset:{}".format(
            supply_meta,
            use_meta
        ))
    

    supply_data = supply_file.parse(
        sheet_name=eurostat_id["supply"]["sheet_name"],
        index_col=eurostat_id["supply"]["index_col"],
        header=eurostat_id["supply"]["header"],
    )

    use_data = use_file.parse(
        sheet_name=eurostat_id["use"]["sheet_name"],
        index_col=eurostat_id["use"]["index_col"],
        header=eurostat_id["use"]["header"],
    )

    # build Z_matrix
    z_index_c = pd.MultiIndex.from_product(
        [
            [supply_meta["country"]],
            [_MASTER_INDEX["c"]],
            eurostat_id["c"]
        ]
    )

    z_index_a = pd.MultiIndex.from_product(
        [
            [supply_meta["country"]],
            [_MASTER_INDEX["a"]],
            eurostat_id["a"]
        ]
    )

    z_index = z_index_c.append(z_index_a)

    Z = pd.DataFrame(
        data = 0,
        index = z_index,
        columns=z_index
        )

    # fill supply side
    Z.loc[
        (supply_meta["country"],_MASTER_INDEX["a"],eurostat_id["a"]),
        (supply_meta["country"],_MASTER_INDEX["c"],eurostat_id["c"])
    ] = supply_data.loc[eurostat_id["a"],eurostat_id["c"]].values

    # fill use side
    Z.loc[
        (supply_meta["country"],_MASTER_INDEX["c"],eurostat_id["c"]),
        (supply_meta["country"],_MASTER_INDEX["a"],eurostat_id["a"])
    ] = use_data.loc[eurostat_id["c"],eurostat_id["a"]].values  


    # build V_matrix
    V = pd.DataFrame(
        data = 0,
        index = eurostat_id['f'] + eurostat_id["c_import"],
        columns = z_index
    )

    # Activity VA
    V.loc[
        eurostat_id['f'],
        (supply_meta["country"],_MASTER_INDEX["a"],eurostat_id["a"])
    ] = use_data.loc[eurostat_id['f'],eurostat_id['a']].values

    # Commodity VA
    V.loc[
        eurostat_id["c_import"],
        (supply_meta["country"],_MASTER_INDEX["c"],eurostat_id["c"])
    ] = supply_data.loc[eurostat_id["c_import"],eurostat_id["c"]].values

    # Building Y matrix
    Y_columns = pd.MultiIndex.from_product(
        [
            [supply_meta["country"]],
            [_MASTER_INDEX["n"]],
            eurostat_id["n"]
        ]      
    )
    Y = pd.DataFrame(
        data = 0 ,
        index = z_index,
        columns = Y_columns
    )

    Y.loc[
        (supply_meta["country"],_MASTER_INDEX["c"],eurostat_id["c"]),
        (supply_meta["country"],_MASTER_INDEX["n"],eurostat_id["n"])       
    ] = use_data.loc[eurostat_id["c"],eurostat_id["n"]].values

    # Building E and EY
    E = pd.DataFrame(data=0,index=["None"],columns=z_index)
    EY = pd.DataFrame(data=0,index=["None"],columns=Y_columns)

    # Units
    units = {
        _MASTER_INDEX["a"]: pd.DataFrame(
            use_meta["unit"], index=eurostat_id["a"], columns=["unit"]
        ),
        _MASTER_INDEX["c"]: pd.DataFrame(
            use_meta["unit"], index=eurostat_id["c"], columns=["unit"]
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            use_meta["unit"], index=eurostat_id["c_import"] + eurostat_id["f"], columns=["unit"]
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            "None",
            index=E.index,
            columns=["unit"],
        ),
    }

    X = calc_X(Z, Y)

    for matrix in [Z,V,E,EY,Y,X]:
        matrix.replace(":",0,inplace=True)
        
    matrices = {
        "baseline": {
            "Z": Z,
            "V": V,
            "E": E,
            "EY": EY,
            "Y": Y,
            "X": X,
        }
    }
    sort_frames(matrices["baseline"])
    indeces = {
        "r": {"main": Z.index.unique(0).tolist()},
        "n": {"main": Y.columns.unique(-1).tolist()},
        "k": {"main": E.index.tolist()},
        "f": {"main": V.index.tolist()},
        "a": {"main": eurostat_id["a"]},
        "c": {"main": eurostat_id["c"]},
    }
    rename_index(matrices["baseline"])

    return matrices, indeces, units,use_meta


def parse_pymrio(io, value_added, satellite_account):
    """Extracts the data from pymrio in mario format
    """
    
    # be sure that system is calculated
    io = io.calc_all()
    
    extensions = {}
    for value in dir(io):
        obj = getattr(io, value)
        if isinstance(obj, pymrio.Extension):
            extensions[value] = obj

    difference = set(extensions).difference([*value_added] + [*satellite_account])

    if difference:
        raise WrongInput(
            f"Extensions: {difference} are not explicitely characterized."
            "All pymrio Extensions should characterized to define the factor of productions "
            "and stallite accounts in mario."
        )

    v = pd.DataFrame()
    e = pd.DataFrame()
    EY = pd.DataFrame()
    v_unit = pd.DataFrame()
    e_unit = pd.DataFrame()

    for key, value in value_added.items():
        target = extensions[key]

        if value == "all":
            v = v.append(to_single_index(target.F))
            v_unit = v_unit.append(to_single_index(target.unit))
        else:
            try:

                to_append_mat = to_single_index(target.F.loc[value, :])
                to_append_unit = to_single_index(target.unit.loc[value, :])

                counter_mat = to_single_index(target.F.drop(value))
                counter_unit = to_single_index(target.unit.drop(value))

                v = v.append(to_append_mat)
                v_unit = v_unit.append(to_append_unit)

                e = e.append(counter_mat)
                e_unit = e_unit.append(counter_unit)

                EY = EY.append(to_single_index(target.F_Y.drop(value)))

            except KeyError:
                raise WrongInput(
                    f"{value} is not a correct slicer for the specific Extension."
                )

    for key, value in satellite_account.items():
        target = extensions[key]

        if value == "all":
            e = e.append(to_single_index(target.F))
            e_unit = e_unit.append(to_single_index(target.unit))
            EY = EY.append(to_single_index(target.F_Y))
        else:
            try:

                to_append_e = to_single_index(target.F.loc[value, :])
                to_append_e_unit = to_single_index(target.unit.loc[value, :])

                to_append_v = to_single_index(target.F.drop(value))
                to_append_v_unit = to_single_index(target.unit.drop(value))

                v = v.append(to_append_v)
                v_unit = v_unit.append(to_append_v_unit)

                e = e.append(to_append_e)
                e_unit = e_unit.append(to_append_e_unit)

                EY = EY.append(to_single_index(target.F_Y.loc[value, :]))

            except KeyError:
                raise WrongInput(
                    f"{value} is not a correct slicer for the specific Extension."
                )

    if not len(v):
        v.loc["None", io.Z.columns] = 0
        v_unit.loc["None", "unit"] = "None"

    if not len(e):
        e.loc["None", io.Z.columns] = 0
        EY.loc["None", io.Y.columns] = 0
        e_unit.loc["None", "unit"] = "None"

    Y = io.Y
    z = io.A
    sector_unit = io.unit.loc[io.get_regions()[0]]

    for matrix, info in _PYMRIO_INDEXING.items():
        if info["index"] == 3:
            eval(matrix).index = pd.MultiIndex.from_arrays(
                [
                    eval(matrix).index.get_level_values(0),
                    info["add_i"] * len(eval(matrix)),
                    eval(matrix).index.get_level_values(-1),
                ]
            )
        if info["columns"] == 3:
            eval(matrix).columns = pd.MultiIndex.from_arrays(
                [
                    eval(matrix).columns.get_level_values(0),
                    info["add_c"] * eval(matrix).shape[1],
                    eval(matrix).columns.get_level_values(-1),
                ]
            )

    matrices = {"baseline": {"z": z, "E": e, "V": v, "Y": Y, "EY": EY,}}

    units = {
        _MASTER_INDEX["s"]: sector_unit,
        _MASTER_INDEX["k"]: e_unit,
        _MASTER_INDEX["f"]: v_unit,
    }

    indeces = {
        "r": {"main": list(z.index.unique(0))},
        "n": {"main": list(Y.columns.unique(-1))},
        "k": {"main": list(e.index)},
        "f": {"main": list(v.index)},
        "s": {"main": list(z.index.unique(-1))},
    }

    rename_index(matrices["baseline"])
    return matrices, units, indeces



def hybrid_sut_exiobase_reader(path,extensions):
    
    _ACCEPTABLE_EXIOBASE_EXTENSIONS = [*hybrid_sut_exiobase_parser_id]
    
    _ACCEPTABLE_EXIOBASE_EXTENSIONS.remove("matrices")


    if extensions:
        if extensions == "all":
            extensions = _ACCEPTABLE_EXIOBASE_EXTENSIONS

        else:
            differnce = set(extensions).difference(_ACCEPTABLE_EXIOBASE_EXTENSIONS)

            if differnce:
                raise WrongInput(f"Following items are not valid for extensions: \n {differnce}.\n Valid items are: \n {_ACCEPTABLE_EXIOBASE_EXTENSIONS}")


    main_files = dict(
        matrices = hybrid_sut_exiobase_parser_id["matrices"],
        )
    
    extensions_files = {extension: hybrid_sut_exiobase_parser_id[extension] for extension in extensions}
    main_files = {**main_files, **extensions_files}


    # reading the files
    read = all_file_reader(path, main_files, sub_folder=False,sep=',')

    S = read["matrices"]["S"]
    U = read["matrices"]["U"]
    Y = read["matrices"]["Y"]


    # Commodity index
    c_index= pd.MultiIndex.from_product(
        [
            S.index.unique(0),
            [_MASTER_INDEX["c"]],
            S.index.unique(1)
        ]
    )

    # Activity index
    a_index = pd.MultiIndex.from_product(
        [
            S.columns.unique(0),
            [_MASTER_INDEX['a']],
            S.columns.unique(1)
        ]        
    )

    # # Demand index
    n_index = pd.MultiIndex.from_product(
        [
            Y.columns.unique(0),
            [_MASTER_INDEX["n"]],
            Y.columns.unique(1)
        ]
    )

    
    
    if extensions:               
        E = []
        EY = []
        for extension in extensions:   
            dfs = read[extension]
            e  = dfs["activity"]
            ey = dfs["final_demand"]

            if e.index.nlevels == 3:
                
                idx = pd.MultiIndex.from_arrays(
                    [
                        e.index.get_level_values(0) + " (" + e.index.get_level_values(-1) + f" - {extension})",
                        e.index.get_level_values(1)
                    ]
                )

            else:
                idx = pd.MultiIndex.from_arrays(
                    [
                        e.index.get_level_values(0) + f" ({extension})",
                        e.index.get_level_values(1)
                    ]
                )

            e.index = idx
            ey.index= idx

            E.append(e)
            EY.append(ey)

        E  = pd.concat(E,axis=0)
        EY = pd.concat(EY,axis=0)
                
    else:
        E = pd.DataFrame(data = 0,index=[["None"],["None"]],columns=a_index)
        EY =pd.DataFrame(data = 0,index=[["None"],["None"]],columns=n_index)
                           
        
        
    # # Satellite accounts index
    k_index = E.index.get_level_values(0)


    # units
    commodities_unit = pd.DataFrame(
        data  = S.index.get_level_values(-1)[0:len(c_index.unique(2))],
        index = c_index.unique(2),
        columns = ["unit"]
    )

    activities_unit = pd.DataFrame(
        data  = ["None"] * len(a_index.unique(2)),
        index = a_index.unique(2),
        columns = ["unit"]
    )

    factors_unit = pd.DataFrame(
        ["None"],
        index=["None"],
        columns=["unit"],
    )

    extensions_unit = pd.DataFrame(
        E.index.get_level_values(1),
        index=E.index.get_level_values(0),
        columns=["unit"],
    )

    
    # reshape the indeces
    S.index = c_index
    S.columns = a_index
    S = S.T

    U.index = c_index
    U.columns = a_index
    
    V = pd.DataFrame(data=0,index=["None"],columns=c_index.append(a_index))

    Y.index = c_index
    Y.columns = n_index
    
    E.index = k_index
    E.columns = U.columns
    E = pd.concat([pd.DataFrame(np.zeros((E.shape[0],S.shape[1])),index=E.index,columns=S.columns),
                   E], axis=1)
    
    EY.index = k_index
    EY.columns = n_index
    
    
    # Creating the missing parts of the z matrix
    z_upper = pd.DataFrame(
        np.zeros((len(c_index), len(c_index))), index=c_index, columns=c_index
    )
    z_upper = z_upper.append(S)
    z_lower = pd.DataFrame(
        np.zeros((len(a_index), len(a_index))), index=a_index, columns=a_index
    )
    z_lower = U.append(z_lower)
    Z = z_upper.join(z_lower)
    
    # adding the lower part to Y
    y_lower = pd.DataFrame(
        np.zeros((len(a_index), len(n_index))), index=a_index, columns=n_index
    )
    Y = Y.append(y_lower)
    
    X = calc_X(Z, Y)

    indeces = {
        "r": {"main": a_index.unique(0).tolist()},
        "n": {"main": n_index.unique(-1).tolist()},
        "k": {"main": k_index.tolist()},
        "f": {"main": ["None"]},
        "s": {"main": (a_index.unique(-1).append(c_index.unique(-1)).tolist())},
        "a": {"main": a_index.unique(-1).tolist()},
        "c": {"main": c_index.unique(-1).tolist()},
    }

    matrices = {
        "baseline": {
            "Z": Z,
            "V": V,
            "E": E,
            "EY": EY,
            "Y": Y,
            "X": X,
        }
    }

    units = {
        _MASTER_INDEX["a"]: activities_unit,
        _MASTER_INDEX["c"]: commodities_unit,
        _MASTER_INDEX["f"]: factors_unit,
        _MASTER_INDEX["k"]: extensions_unit,
    }

    rename_index(matrices["baseline"])

    return matrices, indeces, units

