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
)

from mario.tools.constants import (
    _ACCEPTABLES,
    _UNITS,
    _EXIO_FACTORS,
    _MASTER_INDEX,
    _EXIO_INDEX,
)

from mario.tools.parsers_id import (
    exiobase_version_3,
    exiobase_mrsut,
    txt_parser_id,
    eora,
    eora_parser_id,
)

from mario.tools.iomath import (
    calc_X,
    calc_X_from_w,
    calc_w,
    calc_X_from_z,
)

from mario.tools.constants import _acceptable_extensions

import pandas as pd
import logging
import copy
import numpy as np
import math
from zipfile import ZipFile

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


def txt_praser(path, table, mode):

    if mode == "coefficients":
        v, e, z = list("vez")
    else:
        v, e, z = list("VEZ")

    log_time(logger, f"Parser: Reading {mode} from txt files.")
    read = all_file_reader(
        path=path,
        guide=txt_parser_id[mode],
        sub_folder=False,
        sep=",",
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

    if mode == "flows":
        read["matrices"]["X"] = calc_X(read["matrices"]["Z"], read["matrices"]["Y"])

    else:
        read["matrices"]["X"] = calc_X_from_w(calc_w(z), read["matrices"]["Y"])

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
            "baseline": {
                "Z": Z,
                "V": V,
                "E": E,
                "Y": Y,
                "X": calc_X(Z, Y),
                "EY": EY,
            }
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

    matrices = {
        "baseline": {
            "Z": Z,
            "Y": Y,
            "V": V,
            "E": E,
            "X": X,
            "EY": EY,
        }
    }

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

    # Commodities index
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


#%%%
def hybrid_sut_exiobase(path,extensions):
    
    if extensions == 'all':
        extensions = list(_acceptable_extensions.keys())
    
    if path.split(".")[-1] == "zip":
        
        zf = ZipFile(r"{}".format(path), "a")
        units = {}
        
        S = pd.read_csv(zf.open([i for i in zf.namelist() if "MR_HSUP_2011_v3_3_18" in i][0]), sep=",", index_col=[0,1,2,3,4], header=[0,1,2,3])
        U = pd.read_csv(zf.open([i for i in zf.namelist() if "MR_HUSE_2011_v3_3_18" in i][0]), sep=",", index_col=[0,1,2,3,4], header=[0,1,2,3])
        Y = pd.read_csv(zf.open([i for i in zf.namelist() if "MR_HSUTs_2011_v3_3_18_FD" in i][0]), sep=",", index_col=[0,1,2,3,4], header=[0,1,2,3])
        E = pd.DataFrame()
        EY = pd.DataFrame()

        # Commodities index
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
        
        if extensions != None:
            E_dict = {}
            for ext in extensions:
                E_dict[ext+"_act"] =  pd.read_excel(zf.open([i for i in zf.namelist() if "MR_HSUTs_2011_v3_3_18_extensions" in i][0]), 
                                                    sheet_name=ext+"_act", 
                                                    index_col=_acceptable_extensions[ext]["index_col"], 
                                                    header=_acceptable_extensions[ext]["header"])
                try:
                    E_dict[ext+"_FD"] =  pd.read_excel(zf.open([i for i in zf.namelist() if "MR_HSUTs_2011_v3_3_18_extensions" in i][0]), 
                                                        sheet_name=ext+"_FD", 
                                                        index_col=_acceptable_extensions[ext]["index_col"], 
                                                        header=_acceptable_extensions[ext]["header"])
                except:
                    E_dict[ext+"_FD"] =  pd.read_excel(zf.open([i for i in zf.namelist() if "MR_HSUTs_2011_v3_3_18_extensions" in i][0]), 
                                                        sheet_name=ext+"_fd", 
                                                        index_col=_acceptable_extensions[ext]["index_col"], 
                                                        header=_acceptable_extensions[ext]["header"])
                    
                                
                if len(E_dict[ext+"_act"].index.names) == 2:
                    E = pd.concat([E, E_dict[ext+"_act"]], axis=0)
                    EY = pd.concat([EY, E_dict[ext+"_FD"]], axis=0)
                else:
                    df_act = copy.deepcopy(E_dict[ext+"_act"])
                    df_FD  = copy.deepcopy(E_dict[ext+"_FD"])
                    
                    df_act = df_act.droplevel(-1)
                    df_FD = df_FD.droplevel(-1)
                    
                    E = pd.concat([E, df_act], axis=0)
                    EY = pd.concat([EY, df_FD], axis=0)
                    
        else:
            E = pd.DataFrame(index=pd.MultiIndex.from_arrays([["None"],["None"]]),columns=a_index).fillna(0)
            EY =pd.DataFrame(index=pd.MultiIndex.from_arrays([["None"],["None"]]),columns=n_index).fillna(0)
                           
    else:
        raise WrongInput("Path must direct to a zip folder")
        
        
    # Satellite accounts index
    k_index = [
        E.index.get_level_values(0),
    ]


    # Units 
    commodities_unit = pd.DataFrame(
        S.iloc[0:len(set(c_index[2])),:].index.get_level_values(-1),
        S.iloc[0:len(set(c_index[2])),:].index.get_level_values(1),
        columns=["unit"],
    )
    activities_unit = pd.DataFrame(
        U.iloc[0:len(set(a_index[2])),:].index.get_level_values(-1),
        index=U.iloc[0:len(set(a_index[2])),:].index.get_level_values(1),
        columns=["unit"],
    )
    factors_unit = pd.DataFrame(
        ["EUR"],
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
    
    V = pd.concat([pd.DataFrame(index=["None"],columns=c_index).fillna(0),
                   pd.DataFrame(index=["None"],columns=a_index).fillna(0)], axis=1)

    Y.index = c_index
    Y.columns = n_index
    
    E.index = k_index[0]
    E.columns = U.columns
    E = pd.concat([pd.DataFrame(np.zeros((E.shape[0],S.shape[1])),index=E.index,columns=S.columns),
                   E], axis=1)
    
    EY.index = k_index[0]
    EY.columns = n_index
    
    
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
    
    # adding the lower part to Y
    y_lower = pd.DataFrame(
        np.zeros((len(a_index[0]), len(n_index[0]))), index=a_index, columns=n_index
    )
    Y = Y.append(y_lower)
    
    X = calc_X(Z, Y)

    indeces = {
        "r": {"main": delete_duplicates(c_index[0].to_list())},
        "n": {"main": delete_duplicates(n_index[2].to_list())},
        "k": {"main": k_index[0]},
        "f": {"main": ["None"]},
        "s": {
            "main": delete_duplicates(a_index[2].to_list())
            + delete_duplicates(c_index[2].to_list()),
        },
        "a": {"main": delete_duplicates(a_index[2].to_list())},
        "c": {"main": delete_duplicates(c_index[2].to_list())},
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

#%%%




def eora_single_region(path, name_convention="full_name", aggregate_trade=True):
    """
    Eora single region parser
    """

    region_level = 1 if name_convention == "full_name" else 2

    data = pd.read_csv(path, sep="\t", index_col=[2, 0, 1, 3], header=[2, 0, 1, 3])

    Z = data.loc[eora[_MASTER_INDEX["s"]], eora[_MASTER_INDEX["s"]]]
    Y = data.loc[eora[_MASTER_INDEX["s"]], eora[_MASTER_INDEX["n"]]]
    V = data.loc[eora[_MASTER_INDEX["f"]], eora[_MASTER_INDEX["s"]]]

    take_E = data.drop(eora[_MASTER_INDEX["s"]] + eora[_MASTER_INDEX["f"]])

    E = take_E[eora[_MASTER_INDEX["s"]]]
    EY = take_E[eora[_MASTER_INDEX["n"]]].fillna(0)

    # taking the indeces

    regions = delete_duplicates(Z.index.get_level_values(region_level).tolist())
    satellite = [
        E.index.get_level_values(3).tolist()[index] + " (" + value + ")"
        for index, value in enumerate(E.index.get_level_values(2).tolist())
    ]
    sectors = Z.index.get_level_values(-1).tolist()

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
    sectors_unit = pd.DataFrame("USD", index=sectors, columns=["unit"])
    factor_unit = pd.DataFrame("USD", index=factors, columns=["unit"])

    satellite_unit = pd.DataFrame(
        E.index.get_level_values(0).tolist(), index=satellite, columns=["unit"]
    )

    Z_index = pd.MultiIndex.from_product([regions, [_MASTER_INDEX["s"]], sectors])
    Y_index = pd.MultiIndex.from_product(
        [regions, [_MASTER_INDEX["s"]], final_consumptions]
    )

    indeces = {
        "Y": {"columns": Y_index, "index": Z_index},
        "Z": {"columns": Z_index, "index": Z_index},
        "E": {"columns": Z_index, "index": satellite},
        "V": {"columns": Z_index, "index": factors},
        "EY": {"columns": Y_index, "index": satellite},
    }

    for matrix, value in indeces.items():
        for level, ind in value.items():
            exec(f"{matrix}.{level} = ind")

    matrices = {
        "baseline": {
            "Z": Z,
            "V": V,
            "E": E,
            "EY": EY,
            "Y": Y,
            "X": calc_X(Z, Y),
        }
    }

    rename_index(matrices["baseline"])

    indeces = {
        "r": {"main": regions},
        "n": {"main": final_consumptions},
        "k": {"main": satellite},
        "f": {"main": factors},
        "s": {"main": sectors},
    }

    units = {
        _MASTER_INDEX["s"]: sectors_unit,
        _MASTER_INDEX["f"]: factor_unit,
        _MASTER_INDEX["k"]: satellite_unit,
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
    region,
    selected_year,
    consumption_categories,
    factors_of_production,
    imports,
):

    supply = pd.read_excel(supply_path, header=None, index_col=0)
    use = pd.read_excel(use_path, header=None, index_col=0)

    "Warning on years correspondance"
    try:
        supply_years = supply.loc["TIME", 1].to_list()
    except:
        supply_years = [supply.loc["TIME", 1]]
    try:
        use_years = use.loc["TIME", 1].to_list()
    except:
        use_years = [use.loc["TIME", 1]]

    if supply_years == use_years:
        years = supply_years    
    else:
        raise WrongInput("No correspondance between years of use and supply tables")

    "Warning on supply in IxP format, Use in PxI format"
    if "INDUSE/PROD_NA" not in supply.index or "PROD_NA/INDUSE" not in use.index:
        raise WrongExcelFormat("Tables not in the correct format")

    "Warning on number of regions"
    try:
        supply_regions = supply.loc["GEO", 1].to_list()
    except:
        supply_regions = [supply.loc["GEO", 1]]
    try:
        use_regions = use.loc["GEO", 1].to_list()
    except:
        use_regions = [use.loc["GEO", 1]]

    if len(set(supply_regions)) > 1:
        raise WrongExcelFormat(
            "The supply tables contains accounts of multiple regions"
        )
    if len(set(use_regions)) > 1:
        raise WrongExcelFormat("The use tables contains accounts of multiple regions")

    "Warning on presence of selected region"
    if region not in supply_regions or region.capitalize() not in supply_regions:
        raise WrongInput("Input region not present in the tables")

    "Warning on region correspondance"
    if supply_regions != use_regions:
        raise WrongExcelFormat(
            "Supply and use tables contains information about different regions"
        )

    "Preparing data (ready for dynamic version)"
    data = {}
    for y in years:
        data[y] = {}

        start_sup = supply.loc[:, 1].to_list().index(str(y)) + 2
        end_sup = copy.deepcopy(start_sup)

        for i in list(supply.index)[start_sup:]:
            if isinstance(i, float) and math.isnan(i):
                break
            else:
                end_sup += 1

        data[y]["S"] = pd.DataFrame(
            supply.iloc[start_sup + 1 : end_sup, :].values,
            index=supply.iloc[start_sup + 1 : end_sup, :].index,
            columns=supply.iloc[start_sup, :].to_list(),
        )

        start_use = use.loc[:, 1].to_list().index(str(y)) + 4
        end_use = copy.deepcopy(start_use)

        for i in list(use.index)[start_use:]:
            if isinstance(i, float) and math.isnan(i):
                break
            else:
                end_use += 1

        data[y]["U"] = pd.DataFrame(
            use.iloc[start_use + 1 : end_use, :].values,
            index=use.iloc[start_use + 1 : end_use, :].index,
            columns=use.iloc[start_use, :].to_list(),
        )

        activities = []
        commodities = []
        for activity in data[y]["U"].columns:
            if activity == "Total":
                break
            else:
                activities += [activity]
        for commodity in data[y]["U"].index:
            if commodity == "Total":
                break
            else:
                commodities += [commodity]

        data[y]["Y"] = data[y]["U"].loc[commodities, consumption_categories]
        data[y]["IMP"] = data[y]["S"].loc[imports, commodities]
        data[y]["V"] = data[y]["U"].loc[factors_of_production, activities]
        data[y]["U"] = data[y]["U"].loc[commodities, activities]
        data[y]["S"] = data[y]["S"].loc[activities, commodities]

    for y in years:
        for key in data[y].keys():
            data[y][key].replace({":": 0}, regex=True, inplace=True)

    "Preparing indeces"
    commodities_multiindex = pd.MultiIndex.from_arrays(
        [
            [region.capitalize() for i in range(len(commodities))],
            [_MASTER_INDEX["c"] for i in range(len(commodities))],
            commodities,
        ]
    )
    activities_multiindex = pd.MultiIndex.from_arrays(
        [
            [region.capitalize() for i in range(len(activities))],
            [_MASTER_INDEX["a"] for i in range(len(activities))],
            activities,
        ]
    )
    sectors_multiindex = commodities_multiindex.append(activities_multiindex)
    factors_index = factors_of_production + imports
    final_demand_multiindex = pd.MultiIndex.from_arrays(
        [
            [region.capitalize() for i in range(len(consumption_categories))],
            [_MASTER_INDEX["n"] for i in range(len(consumption_categories))],
            consumption_categories,
        ]
    )

    "Providing shapes of new matrices"
    V = pd.DataFrame(
        np.zeros(
            (
                data[y]["V"].shape[0] + data[y]["IMP"].shape[0],
                data[y]["V"].shape[1] + data[y]["IMP"].shape[1],
            )
        ),
        index=factors_index,
        columns=sectors_multiindex,
    )
    Z = pd.DataFrame(
        np.zeros(
            (
                data[y]["S"].shape[0] + data[y]["U"].shape[0],
                data[y]["S"].shape[1] + data[y]["U"].shape[1],
            )
        ),
        index=sectors_multiindex,
        columns=sectors_multiindex,
    )
    Y = pd.DataFrame(
        np.zeros(
            (data[y]["S"].shape[0] + data[y]["U"].shape[0], data[y]["Y"].shape[1])
        ),
        index=sectors_multiindex,
        columns=final_demand_multiindex,
    )

    "Changing old indices with new ones"
    for y in years:

        data[y]["S"].index = activities_multiindex
        data[y]["S"].columns = commodities_multiindex

        data[y]["U"].index = commodities_multiindex
        data[y]["U"].columns = activities_multiindex

        data[y]["Y"].index = commodities_multiindex
        data[y]["Y"].columns = final_demand_multiindex

        data[y]["V"].columns = activities_multiindex
        data[y]["IMP"].columns = commodities_multiindex

    Z.loc[activities_multiindex, commodities_multiindex] = data[str(selected_year)]["S"]
    Z.loc[commodities_multiindex, activities_multiindex] = data[str(selected_year)]["U"]
    Y.loc[commodities_multiindex, final_demand_multiindex] = data[str(selected_year)][
        "Y"
    ]
    V.loc[factors_of_production, activities_multiindex] = data[str(selected_year)]["V"]
    V.loc[imports, commodities_multiindex] = data[str(selected_year)]["IMP"]
    E = pd.DataFrame(data=0, index=["None"], columns=sectors_multiindex)
    EY = pd.DataFrame(data=0, index=["None"], columns=final_demand_multiindex)

    indeces = {
        "r": {"main": [region]},
        "n": {"main": consumption_categories},
        "k": {"main": delete_duplicates(E.index.get_level_values(0))},
        "f": {"main": factors_index},
        "c": {"main": commodities},
        "a": {"main": activities},
    }

    units = {
        _MASTER_INDEX["a"]: pd.DataFrame(
            "M EUR", index=indeces["a"]["main"], columns=["unit"]
        ),
        _MASTER_INDEX["c"]: pd.DataFrame(
            "M EUR", index=indeces["c"]["main"], columns=["unit"]
        ),
        _MASTER_INDEX["f"]: pd.DataFrame(
            "M EUR", index=indeces["f"]["main"], columns=["unit"]
        ),
        _MASTER_INDEX["k"]: pd.DataFrame(
            "None", index=indeces["k"]["main"], columns=["unit"]
        ),
    }

    matrices = {
        "baseline": {
            "Z": Z,
            "V": V,
            "E": E,
            "EY": EY,
            "Y": Y,
            "X": calc_X(Z, Y),
        }
    }

    rename_index(matrices["baseline"])

    return matrices, indeces, units
