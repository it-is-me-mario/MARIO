# -*- coding: utf-8 -*-
"""
this module contains the main functions behind parsing differnet type of
databases
"""
from copy import deepcopy
from pathlib import Path

from mario.log_exc.exceptions import WrongInput, WrongExcelFormat, WrongFormat

from mario.log_exc.logger import log_time

from mario.utils import (
    delete_duplicates,
    all_file_reader,
    return_index,
    rename_index,
    sort_frames,
    to_single_index,
)

from mario.model.conventions import TABLE_UNIT_LEVELS
from mario.parsers.specs import (
    EXIO_FACTOR_ROWS,
    EXIO_INDEX_LAYOUT,
    INPUT_OPTIONS,
    PYMRIO_IMPORT_LAYOUTS,
)
from mario.model.conventions import _MASTER_INDEX

from mario.parsers.identifiers import (
    txt_parser_id,
)

import pandas as pd
import logging
import numpy as np
import math
import pymrio

# reading the constants

logger = logging.getLogger(__name__)
import os
import re
from zipfile import ZipFile


TEXT_BUNDLE_FORMATS = ("txt", "csv")


def normalize_text_bundle_format(_format: str | None) -> str | None:
    """Normalize one public text-bundle format selector."""
    if _format is None:
        return None
    normalized = str(_format).strip().lower()
    if normalized not in TEXT_BUNDLE_FORMATS:
        raise WrongInput(
            f"_format should be one of {list(TEXT_BUNDLE_FORMATS)} or None for autodetection, got {_format!r}."
        )
    return normalized


def _guide_with_text_format(guide, suffix: str):
    """Return one parser guide rewritten to use the requested text suffix."""
    updated = deepcopy(guide)
    for section in updated.values():
        for spec in section.values():
            spec["file_name"] = str(Path(spec["file_name"]).with_suffix(f".{suffix}"))
    return updated


def _available_text_basenames(path: str) -> set[str]:
    """Return the visible file basenames inside one text bundle directory or zip."""
    if str(path).lower().endswith(".zip"):
        with ZipFile(path) as archive:
            return {Path(name).name for name in archive.namelist() if Path(name).name}
    root = Path(path)
    return {item.name for item in root.iterdir() if item.is_file()}


def detect_text_bundle_format(path: str, guide, _format: str | None = None) -> str:
    """Detect the text bundle suffix to parse, or validate the requested one."""
    requested = normalize_text_bundle_format(_format)
    if requested is not None:
        return requested

    available = _available_text_basenames(path)
    stems = [
        Path(spec["file_name"]).stem
        for section in guide.values()
        for spec in section.values()
    ]
    scores = {
        suffix: sum(1 for stem in stems if f"{stem}.{suffix}" in available)
        for suffix in TEXT_BUNDLE_FORMATS
    }
    best_suffix = max(scores, key=scores.get)
    if scores[best_suffix] == 0:
        raise FileNotFoundError(
            f"Unable to detect whether the text bundle uses txt or csv files in {path!r}."
        )
    return best_suffix


def get_index_txt(Z, V, Y, E, table):
    """Infer canonical MARIO indexes from text-parsed matrix blocks."""
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
    """Infer canonical MARIO indexes from the standard Excel workbook layout."""
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
    """Normalize the units sheet into per-level MARIO unit dataframes."""
    if set(units.index.get_level_values(0)) != set([*TABLE_UNIT_LEVELS[table]]):
        raise WrongFormat(
            "the units should contain {} levels for {}.".format([*TABLE_UNIT_LEVELS[table]], table)
        )

    _ = {}
    for matrix in [*TABLE_UNIT_LEVELS[table]]:
        # take all the items that should be there (in units)
        index_check = indeces[TABLE_UNIT_LEVELS[table][matrix]]["main"]
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
                _units[item] = units.loc[(matrix, item)].iloc[0]

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

def replace_nan_indices(matrix):
    """Replace NaN labels in matrix axes with string sentinels before parsing."""
    for axis in [0,1]:
        if axis == 0:
            n_levels = matrix.index.nlevels
        else:
             n_levels = matrix.columns.nlevels
        new_levels = [[] for i in range(n_levels)]
        
        for level in range(n_levels):
            if axis == 0:
                new_levels[level] = ["None" if pd.isna(x) else x for x in matrix.index.get_level_values(level)]
            else:
                new_levels[level] = ["None" if pd.isna(x) else x for x in matrix.columns.get_level_values(level)]

        if axis == 0:
            if n_levels == 1:
                matrix.index = pd.Index(new_levels[0])
            else:
                matrix.index = pd.MultiIndex.from_arrays(new_levels)
        else:
            if n_levels == 1:
                matrix.columns = pd.Index(new_levels[0])
            else:
                matrix.columns = pd.MultiIndex.from_arrays(new_levels)
    
    return matrix

def replace_nan_units_indices(units):
    """Replace NaN labels in the units index with stable string sentinels."""

    new_levels = [[],[]]
    for level in range(len(units.index.names)):
        for i in units.index.get_level_values(level):
            if pd.isna(i):
                i = "None"
            new_levels[level].append(i)
    units.index = pd.MultiIndex.from_arrays(new_levels)
    units.fillna("None", inplace=True)
    return units


def _collapse_duplicate_index_rows(frame):
    """Collapse duplicate row labels produced by merged placeholder rows in Excel."""
    if not frame.index.has_duplicates:
        return frame

    levels = list(range(frame.index.nlevels)) if isinstance(frame.index, pd.MultiIndex) else 0
    collapsed = frame.groupby(level=levels, sort=False).sum(min_count=1)
    return collapsed.fillna(0)


def coerce_excel_numeric_block(frame, matrix_name):
    """Coerce one Excel matrix block to floats with explicit empty-block semantics."""
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    missing = numeric.isna()
    if not missing.any().any():
        return numeric.astype(float)
    if missing.all().all():
        return numeric.fillna(0.0)
    raise WrongExcelFormat(
        f"Matrix {matrix_name} contains partially empty or non-numeric cells. "
        "Leave the whole matrix blank to resolve zeros, or provide all numeric values."
    )

def txt_parser(path, table, mode, sep, _format=None):
    """Parse a database stored as delimited text files in MARIO layout."""
    if mode == "coefficients":
        v, e, z = list("vez")
    else:
        v, e, z = list("VEZ")

    bundle_format = detect_text_bundle_format(path, txt_parser_id[mode], _format)
    log_time(logger, f"Parser: Reading {mode} from txt files.")
    read = all_file_reader(
        path=path,
        guide=_guide_with_text_format(txt_parser_id[mode], bundle_format),
        sub_folder=False,
        sep=sep,
        exceptions=("EY", "VY"),
    )

    log_time(logger, "Parser: Reading files finished.")
    _units = read["units"]["all"]
    _units = replace_nan_units_indices(_units)

    log_time(logger, "Parser: Investigating possible identifiable errors.")

    for matrix in read["matrices"].keys():
        read["matrices"][matrix] = replace_nan_indices(read["matrices"][matrix])

    indeces = get_index_txt(
        Z=read["matrices"][z],
        V=read["matrices"][v],
        Y=read["matrices"]["Y"],
        E=read["matrices"][e],
        table=table,
    )

    # sorting the matrices
    sort_frames(read["matrices"])
    log_time(logger, "Parser: parsing database finished.", "info")

    if "EY" not in read["matrices"]:
        log_time(
            logger,
            "Parser: EY matrix is not present in the database. An EY matrix with 0 values created",
            "warning",
        )
        read["matrices"]["EY"] = pd.DataFrame(
            0, index=read["matrices"][e].index, columns=read["matrices"]["Y"].columns
        )
    if "VY" not in read["matrices"]:
        log_time(
            logger,
            "Parser: VY matrix is not present in the database. A VY matrix with 0 values will be resolved on demand",
            "debug",
        )

    units = get_units(_units, table, indeces)
    rename_index(read["matrices"])

    matrices = {"baseline": {**read["matrices"]}}


    return matrices, indeces, units


def excel_parser(path, table, mode, sheet_name, unit_sheet):
    """Parse a database stored in the standard MARIO Excel workbook layout."""
    if table not in INPUT_OPTIONS["table"]:
        raise WrongInput(
            "{} is not an acceptable value for table. Acceptable valuse are \n{}".format(
                table, INPUT_OPTIONS["table"]
            )
        )
    if mode not in ["flows", "coefficients"]:
        raise WrongInput("Acceptable modes are `coefficients` and `flows`.")

    data = pd.read_excel(
        path, header=[0, 1, 2], index_col=[0, 1, 2], sheet_name=sheet_name
    )
    
    data = replace_nan_indices(data)
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
        VY = data.loc[
            (slice(None), _MASTER_INDEX["f"]), (slice(None), _MASTER_INDEX["n"])
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
        VY = data.loc[
            (slice(None), _MASTER_INDEX["f"]), (slice(None), _MASTER_INDEX["n"])
        ]

    V.index = indeces['f']['main']
    E = _collapse_duplicate_index_rows(E)
    EY = _collapse_duplicate_index_rows(EY)
    VY = _collapse_duplicate_index_rows(VY)
    E.index = indeces['k']['main']
    EY.index = indeces['k']['main']
    VY.index = indeces['f']['main']
    Z = coerce_excel_numeric_block(Z, "Z")
    Y = coerce_excel_numeric_block(Y, "Y")
    V = coerce_excel_numeric_block(V, "V")
    E = coerce_excel_numeric_block(E, "E")
    EY = coerce_excel_numeric_block(EY, "EY")
    VY = coerce_excel_numeric_block(VY, "VY")

    if mode == "coefficients":
        matrices = {
            "baseline": {
                "z": Z,
                "v": V,
                "e": E,
                "Y": Y,
                "EY": EY,
                "VY": VY,
            }
        }
    else:
        matrices = {
            "baseline": {
                "Z": Z,
                "V": V,
                "E": E,
                "Y": Y,
                "EY": EY,
                "VY": VY,
            }
        }

    # read the unit sheet from the excel file
    _units = pd.read_excel(path, sheet_name=unit_sheet, index_col=[0, 1])
    _units = replace_nan_units_indices(_units)

    units = get_units(
        _units, table, indeces
    )

    rename_index(matrices["baseline"])
    sort_frames(matrices["baseline"])

    return matrices, indeces, units


def dataframe_parser(Z, Y, E, V, EY, units, table, VY=None):
    """Normalize explicit dataframe inputs into canonical parser output objects."""
    if isinstance(units, dict):
        units = pd.concat(units.values(), keys=units.keys())

    indeces = get_index_txt(Z, V, Y, E, table)
    units = get_units(units, table, indeces)

    if not EY.index.equals(E.index) or not EY.columns.equals(Y.columns):
        raise WrongInput("EY has not the correct format.")
    if VY is not None and (not VY.index.equals(V.index) or not VY.columns.equals(Y.columns)):
        raise WrongInput("VY has not the correct format.")

    matrices = {
        "baseline": {
            "Z": Z,
            "Y": Y,
            "V": V,
            "E": E,
            "EY": EY,
        }
    }
    if VY is not None:
        matrices["baseline"]["VY"] = VY

    rename_index(matrices["baseline"])
    sort_frames(matrices["baseline"])

    return matrices, indeces, units

def parse_pymrio(io, value_added, satellite_account):
    """Extracts the data from pymrio in mario format"""

    # be sure that system is calculated
    io = io.calc_all()

    extensions = {}
    for value in dir(io):
        obj = getattr(io, value)
        if isinstance(obj, pymrio.Extension):
            extensions[value] = obj

    value_added, satellite_account = _normalize_pymrio_extension_assignment(
        extensions=extensions,
        value_added=value_added,
        satellite_account=satellite_account,
    )

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
            v = pd.concat([v, to_single_index(target.F)])
            v_unit = pd.concat([v_unit, to_single_index(target.unit)])
        else:
            try:
                to_append_mat = to_single_index(target.F.loc[value, :])
                to_append_unit = to_single_index(target.unit.loc[value, :])

                counter_mat = to_single_index(target.F.drop(value))
                counter_unit = to_single_index(target.unit.drop(value))

                v = pd.concat([v, to_append_mat])
                v_unit = pd.concat([v_unit, to_append_unit])

                e = pd.concat([e, counter_mat])
                e_unit = pd.concat([e_unit, counter_unit])

                EY = pd.concat([EY, to_single_index(target.F_Y.drop(value))])

            except KeyError:
                raise WrongInput(
                    f"{value} is not a correct slicer for the specific Extension."
                )

    for key, value in satellite_account.items():
        target = extensions[key]

        if value == "all":
            e = pd.concat([e, to_single_index(target.F)])
            e_unit = pd.concat([e_unit, to_single_index(target.unit)])
            EY = pd.concat([EY, to_single_index(target.F_Y)])
        else:
            try:
                to_append_e = to_single_index(target.F.loc[value, :])
                to_append_e_unit = to_single_index(target.unit.loc[value, :])

                to_append_v = to_single_index(target.F.drop(value))
                to_append_v_unit = to_single_index(target.unit.drop(value))

                v = pd.concat([v, to_append_v])
                v_unit = pd.concat([v_unit, to_append_v_unit])

                e = pd.concat([e, to_append_e])
                e_unit = pd.concat([e_unit, to_append_e_unit])

                EY = pd.concat([EY, to_single_index(target.F_Y.loc[value, :])])

            except KeyError:
                raise WrongInput(
                    f"{value} is not a correct slicer for the specific Extension."
                )

    if not len(v):
        v.loc["-", io.Z.columns] = 0
        v_unit.loc["-", "unit"] = "None"

    if not len(e):
        e.loc["-", io.Z.columns] = 0
        EY.loc["-", io.Y.columns] = 0
        e_unit.loc["-", "unit"] = "None"

    Y = io.Y
    z = io.A
    sector_unit = io.unit.loc[io.get_regions()[0]]

    for matrix, info in PYMRIO_IMPORT_LAYOUTS.items():
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

    matrices = {
        "baseline": {
            "z": z,
            "E": e,
            "V": v,
            "Y": Y,
            "EY": EY,
        }
    }

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


def _normalize_pymrio_extension_assignment(extensions, value_added, satellite_account):
    """Normalize public pymrio assignment shorthands into explicit mappings."""
    extension_names = list(extensions)

    def _normalize_side(argument, label):
        if isinstance(argument, str):
            normalized = argument.strip().lower()
            if normalized != "all":
                raise WrongInput(
                    f"{label} should be a dict or the string 'all', got {argument!r}."
                )
            return "all"
        if not isinstance(argument, dict):
            raise WrongInput(
                f"{label} should be a dict or the string 'all', got {type(argument).__name__}."
            )
        missing = set(argument).difference(extension_names)
        if missing:
            raise WrongInput(
                f"{label} contains unknown pymrio Extensions: {sorted(missing)}."
            )
        return argument

    def _looks_like_factor_extension(name):
        normalized = re.sub(r"[^a-z0-9]+", "", str(name).lower())
        factor_like = {
            "factorinputs",
            "factorinput",
            "factorofproduction",
            "factorsofproduction",
            "valueadded",
            "primaryinputs",
        }
        return normalized in factor_like

    value_added = _normalize_side(value_added, "value_added")
    satellite_account = _normalize_side(satellite_account, "satellite_account")

    if value_added == "all" and satellite_account == "all":
        factor_extensions = [
            name for name in extension_names if _looks_like_factor_extension(name)
        ]
        if len(factor_extensions) != 1:
            raise WrongInput(
                "parse_from_pymrio(value_added='all', satellite_account='all') "
                "requires exactly one factor-like Extension such as 'factor_inputs' "
                "or 'factor_of_production'. Use explicit dictionaries otherwise."
            )
        factor_name = factor_extensions[0]
        return (
            {factor_name: "all"},
            {name: "all" for name in extension_names if name != factor_name},
        )

    if value_added == "all":
        return (
            {
                name: "all"
                for name in extension_names
                if name not in satellite_account
            },
            satellite_account,
        )

    if satellite_account == "all":
        return (
            value_added,
            {
                name: "all"
                for name in extension_names
                if name not in value_added
            },
        )

    return value_added, satellite_account


    return matrices, indeces, units
