# -*- coding: utf-8 -*-
"""
module contains the shock functions
"""

import copy
import pandas as pd
import logging
from mario.log_exc.logger import log_time
from mario.log_exc.exceptions import WrongInput
from mario.tools.constants import _MASTER_INDEX, _SHOCKS, _ENUM

logger = logging.getLogger(__name__)


def check_replace_clusters(userValue, dataValues, clusters):
    if userValue in dataValues:
        return userValue

    else:
        if clusters is not None and clusters.get(userValue) is not None:
            return clusters.get(userValue)

        else:
            raise WrongInput(f"{userValue} not in the database neither in clusters.")


def get_value(given):
    if isinstance(given, (pd.DataFrame, pd.Series)):
        return given.values
    return given


def nan_check(dataframe, row, shock_type):
    dataframe = copy.deepcopy(dataframe)

    if shock_type != "Switch":
        try:
            dataframe = dataframe.drop(_SHOCKS["s_sec"], axis=1)
        except:
            pass
    return dataframe.loc[row].isnull().values.any()


def Y_shock(instance, path, boolean, clusters, to_baseline):
    Y = instance.query(_ENUM.Y)
    notes = []

    if boolean:
        if isinstance(path, str):
            info = pd.read_excel(path, _ENUM.Y, header=[0])
        else:
            info = path[_ENUM.Y]

        row_region = list(info[_SHOCKS["r_reg"]].values)
        row_level = list(info[_SHOCKS["r_lev"]].values)
        row_sector = list(info[_SHOCKS["r_sec"]].values)
        column_region = list(info[_SHOCKS["c_reg"]].values)
        demand_category = list(info[_SHOCKS["d_cat"]].values)
        _type = list(info[_SHOCKS["type"]].values)
        value = list(info[_SHOCKS["value"]].values)

        if info.isnull().values.any():
            raise WrongInput(
                f"nans(empty cells) found in the shock file for '{_ENUM.Y}'."
            )

        for shock in range(len(info)):
            if nan_check(info, shock, _type[shock]):
                log_time(
                    logger,
                    "nan values found on row {} of {} shock sheet. No more shock is imported after row {}".format(
                        shock, _ENUM.Y, shock
                    ),
                    "warning",
                )
                break

            # Performing a full shock on the inputs
            row_region_ = check_replace_clusters(
                userValue=row_region[shock],
                dataValues=instance.get_index(_MASTER_INDEX["r"]),
                clusters=clusters.get(_MASTER_INDEX["r"]),
            )

            row_level_ = check_replace_clusters(
                userValue=row_level[shock],
                dataValues=[_MASTER_INDEX["s"]]
                if instance.meta.table == "IOT"
                else [_MASTER_INDEX["a"], _MASTER_INDEX["c"]],
                clusters=None,
            )

            row_sector_ = check_replace_clusters(
                userValue=row_sector[shock],
                dataValues=instance.get_index(row_level[shock]),
                clusters=clusters.get(row_level[shock]),
            )

            column_region_ = check_replace_clusters(
                userValue=column_region[shock],
                dataValues=instance.get_index(_MASTER_INDEX["r"]),
                clusters=clusters.get(_MASTER_INDEX["r"]),
            )

            demand_category_ = check_replace_clusters(
                userValue=demand_category[shock],
                dataValues=instance.get_index(_MASTER_INDEX["n"]),
                clusters=clusters.get(_MASTER_INDEX["n"]),
            )

            if _type[shock] == "Absolute":
                Y.loc[
                    (row_region_, row_level_, row_sector_),
                    (column_region_, _MASTER_INDEX["n"], demand_category_),
                ] = (
                    Y.loc[
                        (row_region_, row_level_, row_sector_),
                        (column_region_, _MASTER_INDEX["n"], demand_category_),
                    ]
                    + value[shock]
                )

            elif _type[shock] == "Percentage":
                Y.loc[
                    (row_region_, row_level_, row_sector_),
                    (column_region_, _MASTER_INDEX["n"], demand_category_),
                ] = Y.loc[
                    (row_region_, row_level_, row_sector_),
                    (column_region_, _MASTER_INDEX["n"], demand_category_),
                ] * (
                    1 + value[shock]
                )

            elif _type[shock] == "Update":
                Y.loc[
                    (row_region_, row_level_, row_sector_),
                    (column_region_, _MASTER_INDEX["n"], demand_category_),
                ] = value[shock]

            else:
                raise WrongInput(
                    "Acceptable values for type are Absolute, Percentage, and Update."
                )

            notes.append(
                "Shock on Y implemented: row_region:{}, row_level:{}, "
                "row_sector:{}, column_region:{}, demand_category: {}, "
                "type: {}, value: {}.".format(
                    row_region_,
                    row_level_,
                    row_sector_,
                    column_region_,
                    demand_category_,
                    _type[shock],
                    value[shock],
                )
            )

    return Y, notes


def V_shock(instance, path, matrix, boolean, clusters, to_baseline):
    notes = []
    if matrix == "V":
        v = instance.query(_ENUM.v)
        V = instance.query(_ENUM.V)
        X = instance.query(_ENUM.X)
        _id = "f"

    else:
        v = instance.query(_ENUM.e)
        V = instance.query(_ENUM.E)
        X = instance.query(_ENUM.X)
        _id = "k"

    matrix = _ENUM[matrix]

    if boolean:
        if isinstance(path, str):
            info = pd.read_excel(path, matrix.lower(), header=[0])
        else:
            info = path[matrix]

        if info.isnull().values.any():
            raise WrongInput(
                f"nans(empty cells) found in the shock file for '{matrix}'."
            )

        row_sector = list(info[_SHOCKS["r_sec"]].values)
        column_region = list(info[_SHOCKS["c_reg"]].values)
        column_level = list(info[_SHOCKS["c_lev"]].values)
        column_sector = list(info[_SHOCKS["c_sec"]].values)
        _type = list(info[_SHOCKS["type"]].values)
        value = list(info[_SHOCKS["value"]].values)

        for shock in range(len(info)):
            if nan_check(info, shock, _type[shock]):
                log_time(
                    logger,
                    "nan values found on row {} of {} shock sheet. No more shock is imported after row {}".format(
                        shock, matrix, shock
                    ),
                    "warning",
                )
                break

            row_sector_ = check_replace_clusters(
                userValue=row_sector[shock],
                dataValues=instance.get_index(_MASTER_INDEX[_id]),
                clusters=clusters.get(_MASTER_INDEX[_id]),
            )

            column_region_ = check_replace_clusters(
                userValue=column_region[shock],
                dataValues=instance.get_index(_MASTER_INDEX["r"]),
                clusters=clusters.get(_MASTER_INDEX["r"]),
            )

            column_level_ = check_replace_clusters(
                userValue=column_level[shock],
                dataValues=[_MASTER_INDEX["s"]]
                if instance.meta.table == "IOT"
                else [_MASTER_INDEX["a"], _MASTER_INDEX["c"]],
                clusters=None,
            )

            column_sector_ = check_replace_clusters(
                userValue=column_sector[shock],
                dataValues=instance.get_index(column_level[shock]),
                clusters=clusters.get(column_level[shock]),
            )

            if _type[shock] == "Percentage":
                v.loc[
                    row_sector_, (column_region_, column_level_, column_sector_)
                ] = get_value(
                    v.loc[row_sector_, (column_region_, column_level_, column_sector_)]
                ) * (
                    1 + value[shock]
                )

            elif _type[shock] == "Absolute":
                v.loc[row_sector_, (column_region_, column_level_, column_sector_)] = (
                    get_value(
                        V.loc[
                            row_sector_, (column_region_, column_level_, column_sector_)
                        ]
                    )
                    + value[shock]
                ) / get_value(
                    X.loc[(column_region_, column_level_, column_sector_), "production"]
                )

            elif _type[shock] == "Update":
                v.loc[
                    row_sector_, (column_region_, column_level_, column_sector_)
                ] = value[shock]

            else:
                raise WrongInput(
                    "Acceptable values for type are Absolute, Percentage and Update"
                )

            notes.append(
                "Shock on {} implemented: row_sector:{}, column_region:{}, "
                "column_level:{}, column_sector:{}, "
                "type: {}, value: {}.".format(
                    matrix.lower(),
                    row_sector_,
                    column_region,
                    column_level,
                    column_sector,
                    _type[shock],
                    value[shock],
                )
            )

    return v, notes


def Z_shock(instance, path, boolean, clusters, to_baseline):
    z = instance.query(_ENUM.z)

    notes = []
    if boolean:
        Z = instance.query(_ENUM.Z)
        X = instance.query(_ENUM.X)
        if isinstance(path, str):
            info = pd.read_excel(path, _ENUM.z, header=[0])
        else:
            info = path[_ENUM.Z]

        row_region = list(info[_SHOCKS["r_reg"]].values)
        row_level = list(info[_SHOCKS["r_lev"]].values)
        row_sector = list(info[_SHOCKS["r_sec"]].values)
        column_region = list(info[_SHOCKS["c_reg"]].values)
        column_level = list(info[_SHOCKS["c_lev"]].values)
        column_sector = list(info[_SHOCKS["c_sec"]].values)
        _type = list(info[_SHOCKS["type"]].values)
        value = list(info[_SHOCKS["value"]].values)

        if info.isnull().values.any():
            raise WrongInput(
                f"nans(empty cells) found in the shock file for '{_ENUM.Z}'."
            )

        for shock in range(len(info)):
            if nan_check(info, shock, _type[shock]):
                log_time(
                    logger,
                    "nan values found on row {} of {} shock sheet. No more shock is imported after row {}".format(
                        shock, _ENUM.Z, shock
                    ),
                    "warning",
                )
                break

            # Performing a full shock on the inputs
            row_region_ = check_replace_clusters(
                userValue=row_region[shock],
                dataValues=instance.get_index(_MASTER_INDEX["r"]),
                clusters=clusters.get(_MASTER_INDEX["r"]),
            )

            row_level_ = check_replace_clusters(
                userValue=row_level[shock],
                dataValues=[_MASTER_INDEX["s"]]
                if instance.meta.table == "IOT"
                else [_MASTER_INDEX["a"], _MASTER_INDEX["c"]],
                clusters=None,
            )

            row_sector_ = check_replace_clusters(
                userValue=row_sector[shock],
                dataValues=instance.get_index(row_level[shock]),
                clusters=clusters.get(row_level[shock]),
            )

            column_region_ = check_replace_clusters(
                userValue=column_region[shock],
                dataValues=instance.get_index(_MASTER_INDEX["r"]),
                clusters=clusters.get(_MASTER_INDEX["r"]),
            )

            column_level_ = check_replace_clusters(
                userValue=column_level[shock],
                dataValues=[_MASTER_INDEX["s"]]
                if instance.meta.table == "IOT"
                else [_MASTER_INDEX["a"], _MASTER_INDEX["c"]],
                clusters=None,
            )

            column_sector_ = check_replace_clusters(
                userValue=column_sector[shock],
                dataValues=instance.get_index(column_level[shock]),
                clusters=clusters.get(column_level[shock]),
            )

            if _type[shock] == "Percentage":
                z.loc[
                    (row_region_, row_level_, row_sector_),
                    (column_region_, column_level_, column_sector_),
                ] = z.loc[
                    (row_region_, row_level_, row_sector_),
                    (column_region_, column_level_, column_sector_),
                ] * (
                    1 + value[shock]
                )

            elif _type[shock] == "Absolute":
                z.loc[
                    (row_region_, row_level_, row_sector_),
                    (column_region_, column_level_, column_sector_),
                ] = (
                    get_value(
                        Z.loc[
                            (row_region_, row_level_, row_sector_),
                            (column_region_, column_level_, column_sector_),
                        ]
                    )
                    + value[shock]
                ) / get_value(
                    X.loc[(column_region_, column_level_, column_sector_), "production"]
                )

            elif _type[shock] == "Update":
                z.loc[
                    (row_region_, row_level_, row_sector_),
                    (column_region_, column_level_, column_sector_),
                ] = value[shock]

            else:
                raise WrongInput(
                    "Acceptable values for type are Absolute, Percentage, and Update."
                )

            notes.append(
                "Shock on z implemented: row_region_:{}, row_level_:{}, "
                "row_sector_:{}, column_region_:{}, column_level_:{} "
                "column_sector_:{}, type: {}, value: {}.".format(
                    row_region_,
                    row_level_,
                    row_sector_,
                    column_region_,
                    column_level_,
                    column_sector_,
                    _type[shock],
                    value[shock],
                )
            )

    return z, notes
