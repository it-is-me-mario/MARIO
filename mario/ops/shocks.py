# -*- coding: utf-8 -*-
"""
module contains the shock functions
"""

import copy
import pandas as pd
import logging
from mario.log_exc.logger import log_time
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX, _ENUM
from mario.ops.workbook_specs import SHOCK_COLUMNS, SHOCK_FLAT_COLUMNS

logger = logging.getLogger(__name__)


def _sheet_candidates(*sheet_names):
    """Return de-duplicated candidate worksheet names preserving order."""
    seen = set()
    ordered = []
    for name in sheet_names:
        if name is None:
            continue
        token = str(name)
        if token not in seen:
            ordered.append(token)
            seen.add(token)
    return ordered


def has_shock_sheet(path, *sheet_names):
    """Return whether a workbook-like source exposes one of the requested sheets."""
    candidates = _sheet_candidates(*sheet_names)
    if isinstance(path, str):
        with pd.ExcelFile(path) as workbook:
            return any(name in workbook.sheet_names for name in candidates)

    if hasattr(path, "keys"):
        available = {str(key) for key in path.keys()}
        return any(name in available for name in candidates)

    return False


def _read_shock_sheet(path, *sheet_names):
    """Read the first available worksheet among the provided candidate names."""
    candidates = _sheet_candidates(*sheet_names)
    if isinstance(path, str):
        with pd.ExcelFile(path) as workbook:
            for name in candidates:
                if name in workbook.sheet_names:
                    return pd.read_excel(workbook, name, header=[0])
        return None

    if hasattr(path, "keys"):
        for name in candidates:
            if name in path:
                return path[name]
        return None

    raise WrongInput("Shock source should be an Excel path or a workbook-like mapping.")


def _shock_column(info, *candidates, required=True, default=None):
    """Return one shock workbook column trying multiple legacy/new labels."""
    for candidate in candidates:
        if candidate in info.columns:
            return list(info[candidate].values)

    if required:
        raise WrongInput(
            f"Shock file is missing required column. Expected one of: {candidates}"
        )

    return [default] * len(info)


def check_replace_clusters(userValue, dataValues, clusters):
    """Resolve a user value directly or through the optional cluster mapping."""
    if userValue in dataValues:
        return userValue

    else:
        if clusters is not None and clusters.get(userValue) is not None:
            return clusters.get(userValue)

        else:
            raise WrongInput(f"{userValue} not in the database neither in clusters.")


def get_value(given):
    """Return a scalar/array view for either pandas or plain Python inputs."""
    if isinstance(given, (pd.DataFrame, pd.Series)):
        return given.values
    return given


def nan_check(dataframe, row, shock_type):
    """Detect whether a shock row is effectively incomplete."""
    dataframe = copy.deepcopy(dataframe)

    if shock_type != "Switch":
        try:
            dataframe = dataframe.drop(SHOCK_COLUMNS["s_sec"], axis=1)
        except:
            pass
    return dataframe.loc[row].isnull().values.any()


def Y_shock(instance, path, boolean, clusters, to_baseline):
    """Apply final-demand shocks and return the updated block plus notes."""
    Y = instance.query(_ENUM.Y)
    notes = []

    if boolean:
        info = _read_shock_sheet(path, _ENUM.Y, _ENUM.Y.lower(), _ENUM.Y.upper())
        if info is None:
            return Y, notes

        row_region = _shock_column(
            info,
            SHOCK_FLAT_COLUMNS["region_from"],
            SHOCK_COLUMNS["r_reg"],
        )
        if instance.meta.table == "IOT":
            row_level = [_MASTER_INDEX["s"]] * len(info)
            row_sector = _shock_column(
                info,
                SHOCK_FLAT_COLUMNS["sector_from"],
                SHOCK_COLUMNS["r_sec"],
            )
        else:
            row_level = _shock_column(info, SHOCK_COLUMNS["r_lev"])
            row_sector = _shock_column(info, SHOCK_COLUMNS["r_sec"])

        column_region = _shock_column(
            info,
            SHOCK_FLAT_COLUMNS["region_to"],
            SHOCK_COLUMNS["c_reg"],
        )
        demand_category = _shock_column(
            info,
            SHOCK_FLAT_COLUMNS["category_to"],
            SHOCK_COLUMNS["d_cat"],
        )
        _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
        value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

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
                dataValues=instance.get_index(row_level_),
                clusters=clusters.get(row_level_),
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
    """Apply value-added or extension shocks in coefficient space."""
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
        info = _read_shock_sheet(path, matrix, matrix.lower(), matrix.upper())
        if info is None:
            return v, notes

        if info.isnull().values.any():
            raise WrongInput(
                f"nans(empty cells) found in the shock file for '{matrix}'."
            )

        from_column = (
            SHOCK_FLAT_COLUMNS["factor_from"]
            if matrix == _ENUM.v
            else SHOCK_FLAT_COLUMNS["satellite_from"]
        )
        row_sector = _shock_column(info, from_column, SHOCK_COLUMNS["r_sec"])
        column_region = _shock_column(
            info,
            SHOCK_FLAT_COLUMNS["region_to"],
            SHOCK_COLUMNS["c_reg"],
        )
        if instance.meta.table == "IOT":
            column_level = [_MASTER_INDEX["s"]] * len(info)
            column_sector = _shock_column(
                info,
                SHOCK_FLAT_COLUMNS["sector_to"],
                SHOCK_COLUMNS["c_sec"],
            )
        else:
            column_level = _shock_column(info, SHOCK_COLUMNS["c_lev"])
            column_sector = _shock_column(info, SHOCK_COLUMNS["c_sec"])
        _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
        value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

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
                dataValues=instance.get_index(column_level_),
                clusters=clusters.get(column_level_),
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


def _split_intermediate_shock(
    instance,
    path,
    *,
    boolean,
    clusters,
    coefficient_matrix,
    flow_matrix,
    output_matrix,
    row_level,
    column_level,
    sheet_name,
    note_label,
):
    """Apply shocks to one split SUT coefficient block such as ``u`` or ``s``."""
    notes = []
    coeff = instance.query(coefficient_matrix)

    if not boolean:
        return coeff, notes

    info = _read_shock_sheet(path, sheet_name, coefficient_matrix, str(coefficient_matrix).lower())
    if info is None:
        return coeff, notes

    flow = instance.query(flow_matrix)
    output = instance.query(output_matrix)

    if info.isnull().values.any():
        raise WrongInput(
            f"nans(empty cells) found in the shock file for '{sheet_name}'."
        )

    row_from = (
        SHOCK_FLAT_COLUMNS["commodity_from"]
        if row_level == _MASTER_INDEX["c"]
        else SHOCK_FLAT_COLUMNS["activity_from"]
    )
    column_to = (
        SHOCK_FLAT_COLUMNS["activity_to"]
        if column_level == _MASTER_INDEX["a"]
        else SHOCK_FLAT_COLUMNS["commodity_to"]
    )
    row_region = _shock_column(
        info,
        SHOCK_FLAT_COLUMNS["region_from"],
        SHOCK_COLUMNS["r_reg"],
    )
    row_sector = _shock_column(info, row_from, SHOCK_COLUMNS["r_sec"])
    column_region = _shock_column(
        info,
        SHOCK_FLAT_COLUMNS["region_to"],
        SHOCK_COLUMNS["c_reg"],
    )
    column_sector = _shock_column(info, column_to, SHOCK_COLUMNS["c_sec"])
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    for shock in range(len(info)):
        if nan_check(info, shock, _type[shock]):
            log_time(
                logger,
                "nan values found on row {} of {} shock sheet. No more shock is imported after row {}".format(
                    shock, sheet_name, shock
                ),
                "warning",
            )
            break

        row_region_ = check_replace_clusters(
            userValue=row_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(row_level),
            clusters=clusters.get(row_level),
        )
        column_region_ = check_replace_clusters(
            userValue=column_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        column_sector_ = check_replace_clusters(
            userValue=column_sector[shock],
            dataValues=instance.get_index(column_level),
            clusters=clusters.get(column_level),
        )

        row_key = (row_region_, row_level, row_sector_)
        col_key = (column_region_, column_level, column_sector_)

        if _type[shock] == "Percentage":
            coeff.loc[row_key, col_key] = get_value(coeff.loc[row_key, col_key]) * (
                1 + value[shock]
            )
        elif _type[shock] == "Absolute":
            coeff.loc[row_key, col_key] = (
                get_value(flow.loc[row_key, col_key]) + value[shock]
            ) / get_value(output.loc[col_key, "production"])
        elif _type[shock] == "Update":
            coeff.loc[row_key, col_key] = value[shock]
        else:
            raise WrongInput(
                "Acceptable values for type are Absolute, Percentage and Update"
            )

        notes.append(
            "Shock on {} implemented: row_region:{}, row_level:{}, "
            "row_sector:{}, column_region:{}, column_level:{}, "
            "column_sector:{}, type: {}, value: {}.".format(
                note_label,
                row_region_,
                row_level,
                row_sector_,
                column_region_,
                column_level,
                column_sector_,
                _type[shock],
                value[shock],
            )
        )

    return coeff, notes


def U_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT use coefficients ``u``."""
    return _split_intermediate_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix=_ENUM.u,
        flow_matrix=_ENUM.U,
        output_matrix="Xa",
        row_level=_MASTER_INDEX["c"],
        column_level=_MASTER_INDEX["a"],
        sheet_name=_ENUM.u,
        note_label="u",
    )


def S_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT supply coefficients ``s``."""
    return _split_intermediate_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix=_ENUM.s,
        flow_matrix=_ENUM.S,
        output_matrix="Xc",
        row_level=_MASTER_INDEX["a"],
        column_level=_MASTER_INDEX["c"],
        sheet_name=_ENUM.s,
        note_label="s",
    )


def _split_final_demand_shock(
    instance,
    path,
    *,
    boolean,
    clusters,
    flow_matrix,
    row_level,
    sheet_name,
    note_label,
):
    """Apply shocks to one split SUT final-demand block such as ``Ya`` or ``Yc``."""
    notes = []
    flow = instance.query(flow_matrix)

    if not boolean:
        return flow, notes

    info = _read_shock_sheet(path, sheet_name, flow_matrix, str(flow_matrix))
    if info is None:
        return flow, notes

    if info.isnull().values.any():
        raise WrongInput(
            f"nans(empty cells) found in the shock file for '{sheet_name}'."
        )

    row_from = (
        SHOCK_FLAT_COLUMNS["activity_from"]
        if row_level == _MASTER_INDEX["a"]
        else SHOCK_FLAT_COLUMNS["commodity_from"]
    )
    row_region = _shock_column(info, SHOCK_FLAT_COLUMNS["region_from"])
    row_sector = _shock_column(info, row_from)
    column_region = _shock_column(info, SHOCK_FLAT_COLUMNS["region_to"])
    demand_category = _shock_column(info, SHOCK_FLAT_COLUMNS["category_to"])
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    for shock in range(len(info)):
        row_region_ = check_replace_clusters(
            userValue=row_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(row_level),
            clusters=clusters.get(row_level),
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

        row_key = (row_region_, row_level, row_sector_)
        col_key = (column_region_, _MASTER_INDEX["n"], demand_category_)

        if _type[shock] == "Absolute":
            flow.loc[row_key, col_key] = get_value(flow.loc[row_key, col_key]) + value[shock]
        elif _type[shock] == "Percentage":
            flow.loc[row_key, col_key] = get_value(flow.loc[row_key, col_key]) * (1 + value[shock])
        elif _type[shock] == "Update":
            flow.loc[row_key, col_key] = value[shock]
        else:
            raise WrongInput(
                "Acceptable values for type are Absolute, Percentage, and Update."
            )

        notes.append(
            "Shock on {} implemented: row_region:{}, row_level:{}, row_sector:{}, "
            "column_region:{}, demand_category:{}, type:{}, value:{}.".format(
                note_label,
                row_region_,
                row_level,
                row_sector_,
                column_region_,
                demand_category_,
                _type[shock],
                value[shock],
            )
        )

    return flow, notes


def Ya_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT final-demand block ``Ya``."""
    return _split_final_demand_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        flow_matrix="Ya",
        row_level=_MASTER_INDEX["a"],
        sheet_name="Ya",
        note_label="Ya",
    )


def Yc_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT final-demand block ``Yc``."""
    return _split_final_demand_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        flow_matrix="Yc",
        row_level=_MASTER_INDEX["c"],
        sheet_name="Yc",
        note_label="Yc",
    )


def _split_factor_extension_shock(
    instance,
    path,
    *,
    boolean,
    clusters,
    coefficient_matrix,
    flow_matrix,
    output_matrix,
    row_code,
    column_level,
    sheet_name,
    note_label,
):
    """Apply shocks to one split SUT coefficient block such as ``va`` or ``ec``."""
    notes = []
    coeff = instance.query(coefficient_matrix)

    if not boolean:
        return coeff, notes

    info = _read_shock_sheet(path, sheet_name, coefficient_matrix, str(coefficient_matrix))
    if info is None:
        return coeff, notes

    flow = instance.query(flow_matrix)
    output = instance.query(output_matrix)

    if info.isnull().values.any():
        raise WrongInput(
            f"nans(empty cells) found in the shock file for '{sheet_name}'."
        )

    row_column = (
        SHOCK_FLAT_COLUMNS["factor_from"]
        if row_code == _MASTER_INDEX["f"]
        else SHOCK_FLAT_COLUMNS["satellite_from"]
    )
    column_to = (
        SHOCK_FLAT_COLUMNS["activity_to"]
        if column_level == _MASTER_INDEX["a"]
        else SHOCK_FLAT_COLUMNS["commodity_to"]
    )
    row_sector = _shock_column(info, row_column, SHOCK_COLUMNS["r_sec"])
    column_region = _shock_column(info, SHOCK_FLAT_COLUMNS["region_to"], SHOCK_COLUMNS["c_reg"])
    column_sector = _shock_column(info, column_to, SHOCK_COLUMNS["c_sec"])
    _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
    value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

    for shock in range(len(info)):
        row_sector_ = check_replace_clusters(
            userValue=row_sector[shock],
            dataValues=instance.get_index(row_code),
            clusters=clusters.get(row_code),
        )
        column_region_ = check_replace_clusters(
            userValue=column_region[shock],
            dataValues=instance.get_index(_MASTER_INDEX["r"]),
            clusters=clusters.get(_MASTER_INDEX["r"]),
        )
        column_sector_ = check_replace_clusters(
            userValue=column_sector[shock],
            dataValues=instance.get_index(column_level),
            clusters=clusters.get(column_level),
        )

        col_key = (column_region_, column_level, column_sector_)

        if _type[shock] == "Percentage":
            coeff.loc[row_sector_, col_key] = get_value(coeff.loc[row_sector_, col_key]) * (1 + value[shock])
        elif _type[shock] == "Absolute":
            coeff.loc[row_sector_, col_key] = (
                get_value(flow.loc[row_sector_, col_key]) + value[shock]
            ) / get_value(output.loc[col_key, "production"])
        elif _type[shock] == "Update":
            coeff.loc[row_sector_, col_key] = value[shock]
        else:
            raise WrongInput(
                "Acceptable values for type are Absolute, Percentage and Update"
            )

        notes.append(
            "Shock on {} implemented: row_sector:{}, column_region:{}, "
            "column_level:{}, column_sector:{}, type:{}, value:{}.".format(
                note_label,
                row_sector_,
                column_region_,
                column_level,
                column_sector_,
                _type[shock],
                value[shock],
            )
        )

    return coeff, notes


def va_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT value-added coefficients ``va``."""
    return _split_factor_extension_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix="va",
        flow_matrix="Va",
        output_matrix="Xa",
        row_code=_MASTER_INDEX["f"],
        column_level=_MASTER_INDEX["a"],
        sheet_name="va",
        note_label="va",
    )


def vc_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT value-added coefficients ``vc``."""
    return _split_factor_extension_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix="vc",
        flow_matrix="Vc",
        output_matrix="Xc",
        row_code=_MASTER_INDEX["f"],
        column_level=_MASTER_INDEX["c"],
        sheet_name="vc",
        note_label="vc",
    )


def ea_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT extension coefficients ``ea``."""
    return _split_factor_extension_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix="ea",
        flow_matrix="Ea",
        output_matrix="Xa",
        row_code=_MASTER_INDEX["k"],
        column_level=_MASTER_INDEX["a"],
        sheet_name="ea",
        note_label="ea",
    )


def ec_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the split SUT extension coefficients ``ec``."""
    return _split_factor_extension_shock(
        instance,
        path,
        boolean=boolean,
        clusters=clusters,
        coefficient_matrix="ec",
        flow_matrix="Ec",
        output_matrix="Xc",
        row_code=_MASTER_INDEX["k"],
        column_level=_MASTER_INDEX["c"],
        sheet_name="ec",
        note_label="ec",
    )


def Z_shock(instance, path, boolean, clusters, to_baseline):
    """Apply shocks to the inter-industry coefficient matrix ``z``."""
    z = instance.query(_ENUM.z)

    notes = []
    if boolean:
        Z = instance.query(_ENUM.Z)
        X = instance.query(_ENUM.X)
        info = _read_shock_sheet(path, _ENUM.z, _ENUM.Z, str(_ENUM.z).lower(), str(_ENUM.Z).upper())
        if info is None:
            return z, notes

        row_region = _shock_column(info, SHOCK_FLAT_COLUMNS["region_from"], SHOCK_COLUMNS["r_reg"])
        if instance.meta.table == "IOT":
            row_level = [_MASTER_INDEX["s"]] * len(info)
            row_sector = _shock_column(info, SHOCK_FLAT_COLUMNS["sector_from"], SHOCK_COLUMNS["r_sec"])
            column_level = [_MASTER_INDEX["s"]] * len(info)
            column_sector = _shock_column(info, SHOCK_FLAT_COLUMNS["sector_to"], SHOCK_COLUMNS["c_sec"])
        else:
            row_level = _shock_column(info, SHOCK_COLUMNS["r_lev"])
            row_sector = _shock_column(info, SHOCK_COLUMNS["r_sec"])
            column_level = _shock_column(info, SHOCK_COLUMNS["c_lev"])
            column_sector = _shock_column(info, SHOCK_COLUMNS["c_sec"])
        column_region = _shock_column(info, SHOCK_FLAT_COLUMNS["region_to"], SHOCK_COLUMNS["c_reg"])
        _type = _shock_column(info, SHOCK_FLAT_COLUMNS["type"], SHOCK_COLUMNS["type"])
        value = _shock_column(info, SHOCK_FLAT_COLUMNS["value"], SHOCK_COLUMNS["value"])

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
                dataValues=instance.get_index(row_level_),
                clusters=clusters.get(row_level_),
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
                dataValues=instance.get_index(column_level_),
                clusters=clusters.get(column_level_),
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
