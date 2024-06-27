# -*- coding: utf-8 -*-
"""
The module containing functionalities for adding a sector
"""
import pandas as pd
from typing import Dict
from mario.tools.database_builder import MatrixBuilder

# constants
from mario.tools.constants import (
    _ENUM,
    _MASTER_INDEX,
    _ADD_SECTOR_SHEETS,
)
from mario.log_exc.exceptions import (
    LackOfInput,
    WrongExcelFormat,
)

from mario.tools.utilities import multiindex_contain


# TODO It does seem that improving the speed will be very limited


def add_new_sector(
    instance,  # TODO add the typing
    io: str,
    new_sectors: list,
    item: str,
    regions: list,
) -> tuple:
    table = instance.table_type

    # get the original baseline data
    data = instance.query(
        matrices=[_ENUM.e, _ENUM.v, _ENUM.z, _ENUM.Y],
        scenarios=["baseline"],
    )

    # get the essentail keys to read the data, and the counter_item
    keys, counter_item = get_corresponding_keys(item)

    add_sector_dfs = {
        key: parse_add_sector_excels(
            io, key, new_sectors, instance, item, counter_item, regions
        )
        for key in keys
    }

    # check if the units are passed or not
    check_unit_consistency(add_sector_dfs["un"], new_sectors)

    # build new sets of matrices to be filled for the new sectors
    new_matrices = build_additional_matrix(table, instance, new_sectors, item)

    empty_matrices = dict(
        z=new_matrices.Z,
        Y=new_matrices.Y,
        e=new_matrices.E,
        v=new_matrices.V,
    )
    # how each new level of information is added to the table?
    matrix_mapping = {
        "z": ["if", "it", "sf", "of"],
        "Y": ["fd"],
        "e": ["sa"],
        "v": ["fp"],
    }

    matrix_concat(data, empty_matrices, new_sectors)

    for m, ks in matrix_mapping.items():
        df_to_fill = data[m]
        for k in ks:
            if k not in keys:
                continue

            df_filled = fill_matrix(df_to_fill, add_sector_dfs[k])

        data[m] = df_filled

    return data, add_sector_dfs["un"]


def check_unit_consistency(units_df: pd.DataFrame, new_sectors: list) -> list:
    """Checks the consistency of units

    Parameters
    ----------
    units_df : pd.DataFrame
        _description_
    new_sectors : list
        _description_

    Returns
    -------
    list
        _description_

    Raises
    ------
    LackOfInput
        _description_
    """
    unit_errors = []

    nan_indices = units_df[units_df["unit"].isna()].index.tolist()
    for new_sector in new_sectors:
        if new_sector in nan_indices:
            unit_errors.append(new_sector)

    if unit_errors:
        msg = "The unit of measure of following items are not identified. Please fill the info in '{}' sheet of excel file. \n".format(
            _ADD_SECTOR_SHEETS["un"]["sheet"]
        )
        raise LackOfInput(msg + "\n".join(unit_errors))


def get_corresponding_keys(item):
    keys = [*_ADD_SECTOR_SHEETS]

    # if sector, output from not needed
    if item == _MASTER_INDEX["s"]:
        keys.remove("of")
        counter_item = item  # TODO why is needed?

    # if activity, self consumption & input_to not needed
    elif item == _MASTER_INDEX["a"]:
        keys.remove("sf")
        keys.remove("it")
        counter_item = _MASTER_INDEX["c"]

    # if commodity, self consumption & input_from not needed
    elif item == _MASTER_INDEX["c"]:
        keys.remove("sf")
        keys.remove("if")
        counter_item = _MASTER_INDEX["a"]

    return keys, counter_item


# TODO --> This is messy. Can we avoid it?
def parse_add_sector_excels(
    io: str,
    key: str,
    new_sectors: list,
    instance,
    item: str,
    counter_item: str,
    regions,
):
    _ACCEPTABLE_EMPTY_SHEETS = ["fd", "it", "of"]
    # only accept str for io

    sheet = _ADD_SECTOR_SHEETS[key]["sheet"]
    index_col = list(range(_ADD_SECTOR_SHEETS[key]["rows"]))
    header = list(range(_ADD_SECTOR_SHEETS[key]["cols"]))

    try:
        df = pd.read_excel(io, sheet, index_col=index_col, header=header)

    except (
        IndexError
    ) as e:  # catch the error raised when empty file passed pandas v1.3.5
        # in some specific cases it is ok to have empty sheets
        if (e.args[0] == "list index out of range") and (
            key in _ACCEPTABLE_EMPTY_SHEETS
        ):
            df = get_empty_frame(
                key, new_sectors, instance, item, counter_item, regions
            )

        else:
            raise Exception(e)

    except (
        ValueError
    ) as e:  # catch the error raised when empty file passed pandas v2.0.3
        if ("Length of new names must be 1, got 3" in e.args[0]) and (
            key in _ACCEPTABLE_EMPTY_SHEETS
        ):
            df = get_empty_frame(
                key, new_sectors, instance, item, counter_item, regions
            )

        else:
            raise Exception(e)

    return df


def get_empty_frame(key, new_sectors, instance, item, counter_item, regions):
    if key in ["it", "of"]:
        return pd.DataFrame(
            0,
            index=pd.MultiIndex.from_product([regions, [item], new_sectors]),
            columns=pd.MultiIndex.from_product(
                [[regions[0]], [counter_item], [instance.get_index(counter_item)[0]]]
            ),
        )

    elif key == "fd":
        return pd.DataFrame(
            0,
            index=pd.MultiIndex.from_product([regions, [item], new_sectors]),
            columns=pd.MultiIndex.from_product(
                [
                    [regions[0]],
                    [_MASTER_INDEX["n"]],
                    [instance.get_index(_MASTER_INDEX["n"])[0]],
                ]
            ),
        )


def build_additional_matrix(table, instance, new_sectors, item):
    levels = {k: instance.get_index(k) for k in instance.sets}

    # update the new set of info
    levels[item] = levels[item] + new_sectors

    return MatrixBuilder(
        table=table,
        levels=levels,
    )


def fill_matrix(empty_df, user_df):
    # if there is no user value passed, just skip any operation
    if (user_df == 0).all().all():
        return empty_df

    # otherwise fille the data
    empty_df.loc[user_df.index, user_df.columns] = user_df.values
    return empty_df


def matrix_concat(data: Dict, empty_matrices: Dict, new_sectors: list) -> None:
    """concat the original data to the newly create one and sort the index"""
    for k, v in empty_matrices.items():
        if k in ["v", "e", "EY"]:
            data[k] = (
                pd.concat(
                    [data[k], v.loc[:, (slice(None), slice(None), new_sectors)]], axis=1
                )
                .sort_index(axis=1)
                .fillna(0)
            )

        elif k in ["z"]:
            data[k] = (
                pd.concat([data[k], v.loc[(slice(None), slice(None), new_sectors)]])
                .sort_index(axis=0)
                .sort_index(axis=1)
                .fillna(0)
            )

        elif k in ["Y"]:
            data[k] = (
                pd.concat([data[k], v.loc[(slice(None), slice(None), new_sectors)]])
                .sort_index()
                .fillna(0)
            )

        else:
            raise ValueError(f"invalid key {k}.")


# def adding_new_sector(instance, data, new_sectors, item, regions):

#     keys = list(_ADD_SECTOR_SHEETS.keys())
#     # Taking the right keys based on the database type: SUT or IOT
#     if item == _MASTER_INDEX["s"]:
#         keys.remove("of")
#         counter_item = item
#     else:
#         keys.remove("sf")
#         if item == _MASTER_INDEX["a"]:
#             keys.remove("it")
#             counter_item = _MASTER_INDEX["c"]
#         else:
#             keys.remove("if")
#             counter_item = _MASTER_INDEX["a"]

#     _data = instance.query(
#         matrices=[_ENUM.e, _ENUM.v, _ENUM.z, _ENUM.Y],
#         scenarios=["baseline"],
#     )

#     matrix_mapper = {
#         "it": {
#             "columns": pd.MultiIndex.from_product(
#                 [[regions[0]], [counter_item], [instance.get_index(counter_item)[0]]]
#             ),
#             "index": pd.MultiIndex.from_product([regions, [item], new_sectors]),
#         },
#         "of": {
#             "columns": pd.MultiIndex.from_product(
#                 [[regions[0]], [counter_item], [instance.get_index(counter_item)[0]]]
#             ),
#             "index": pd.MultiIndex.from_product([regions, [item], new_sectors]),
#         },
#         "fd": {
#             "columns": pd.MultiIndex.from_product(
#                 [
#                     [regions[0]],
#                     [_MASTER_INDEX["n"]],
#                     [instance.get_index(_MASTER_INDEX["n"])[0]],
#                 ]
#             ),
#             "index": pd.MultiIndex.from_product([regions, [item], new_sectors]),
#         },
#     }

#     dataframes = {}
#     if isinstance(data, str):

#         for key in keys:
#             try:
#                 dataframes[key] = pd.read_excel(
#                     data,
#                     _ADD_SECTOR_SHEETS[key]["sheet"],
#                     index_col=list(range(_ADD_SECTOR_SHEETS[key]["rows"])),
#                     header=list(range(_ADD_SECTOR_SHEETS[key]["cols"])),
#                 ).fillna(0)

#             except IndexError as e:

#                 if e.args[0] == "list index out of range" and key in ["fd", "it", "of"]:

#                     df = pd.DataFrame(
#                         0,
#                         index=matrix_mapper[key]["index"],
#                         columns=matrix_mapper[key]["columns"],
#                     )
#                     dataframes[key] = df
#                 else:
#                     raise Exception(e)

#     data = instance.query(
#         matrices=[_ENUM.e, _ENUM.v, _ENUM.z, _ENUM.Y],
#         scenarios=["baseline"],
#     )
#     e = data[_ENUM.e]
#     v = data[_ENUM.v]
#     z = data[_ENUM.z]
#     Y = data[_ENUM.Y]
#     ## IDEA
#     # 1. --> Creat a new matrix from scratch and populate it?
#     # 2. --> add find the new matrix and append it the existing matrix?


#     # check if the units are passed or not
#     for sec in new_sectors:
#         if str(dataframes["un"].loc[sec, "unit"]) == "nan":
#             raise LackOfInput("The unit of measure of {} is unfilled.".format(sec))

#     # Creating a new data frame with new items added
#     Y_index0 = pd.MultiIndex.from_product(
#         [instance.get_index(_MASTER_INDEX["r"]), [item], new_sectors]
#     )

#     Y_extra = pd.DataFrame(0, index=Y_index0, columns=Y.columns)

#     Y_index1 = pd.MultiIndex.from_product([regions, [item], new_sectors])

#     Y_check = pd.DataFrame(0, index=Y_index1, columns=Y.columns)

#     Y = create_new_matrix(
#         orginal_matrix=Y,
#         extra_matrix=Y_extra,
#         given_matrix=dataframes["fd"],
#         to_check_matrix=Y_check,
#         key="fd",
#     )

#     # Creating a new data frame with new items added
#     e_extra = pd.DataFrame(0, index=e.index, columns=Y_index0)
#     e_check = pd.DataFrame(0, index=e.index, columns=Y_index1)

#     e = create_new_matrix(
#         orginal_matrix=e,
#         extra_matrix=e_extra,
#         given_matrix=dataframes["sa"],
#         to_check_matrix=e_check,
#         key="sa",
#     )

#     # Creating a new data frame with new items added
#     v_extra = pd.DataFrame(0, index=v.index, columns=Y_index0)
#     v_check = pd.DataFrame(0, index=v.index, columns=Y_index1)

#     v = create_new_matrix(
#         orginal_matrix=v,
#         extra_matrix=v_extra,
#         given_matrix=dataframes["fp"],
#         to_check_matrix=v_check,
#         key="fp",
#     )
#     # input from matrix
#     z_index0 = pd.MultiIndex.from_product(
#         [
#             instance.get_index(_MASTER_INDEX["r"]),
#             [counter_item],
#             instance.get_index(counter_item),
#         ]
#     )

#     z_columns0 = pd.MultiIndex.from_product(
#         [instance.get_index(_MASTER_INDEX["r"]), [item], new_sectors]
#     )

#     z_columns1 = pd.MultiIndex.from_product([regions, [item], new_sectors])

#     """
#     if: works for IOT
#     """
#     z_extra = pd.DataFrame(0, index=z_columns0, columns=z_columns0)
#     z = z.append(z_extra)
#     if item != _MASTER_INDEX["c"]:
#         # we have the input from to be checked

#         z_check = pd.DataFrame(0, index=z_index0, columns=z_columns1)
#         z = create_new_matrix(
#             orginal_matrix=None,
#             extra_matrix=z,
#             given_matrix=dataframes["if"],
#             to_check_matrix=z_check,
#             key="if",
#         )

#     if item != _MASTER_INDEX["a"]:
#         # we have the input to to be checked

#         z_check = pd.DataFrame(0, columns=z_index0, index=z_columns1)
#         z = create_new_matrix(
#             orginal_matrix=None,
#             extra_matrix=z,
#             given_matrix=dataframes["it"],
#             to_check_matrix=z_check,
#             key="it",
#         )

#     if item == _MASTER_INDEX["a"]:
#         z_check = pd.DataFrame(0, index=z_columns1, columns=z_index0)
#         z = create_new_matrix(
#             orginal_matrix=None,
#             extra_matrix=z,
#             given_matrix=dataframes["of"],
#             to_check_matrix=z_check,
#             key="of",
#         )

#     if item == _MASTER_INDEX["c"]:
#         z_check = pd.DataFrame(0, index=z_index0, columns=z_columns1)
#         z = create_new_matrix(
#             orginal_matrix=None,
#             extra_matrix=z,
#             given_matrix=dataframes["of"],
#             to_check_matrix=z_check,
#             key="of",
#         )

#     if item == _MASTER_INDEX["s"]:

#         z_index0 = pd.MultiIndex.from_product([regions, [item], new_sectors])
#         # self consumption

#         z_check = pd.DataFrame(0, columns=z_index0, index=z_index0)
#         z = create_new_matrix(
#             orginal_matrix=None,
#             extra_matrix=z,
#             given_matrix=dataframes["sf"],
#             to_check_matrix=z_check,
#             key="sf",
#         )

#     v = v.sort_index(axis=1, level=1)
#     e = e.sort_index(axis=1, level=1)
#     Y = Y.sort_index(axis=1, level=1).sort_index(axis=0, level=1)
#     z = z.sort_index(axis=1, level=1).sort_index(axis=0, level=1)

#     return z.fillna(0), v.fillna(0), e.fillna(0), Y.fillna(0), dataframes["un"]


# def create_new_matrix(orginal_matrix, extra_matrix, given_matrix, to_check_matrix, key):

#     """
#     original_matrix: from database
#     extra_matrix: matrix to be added
#     given_matrix: the one passed by user
#     matrix: name of the matrix
#     key: the key of _ADD_SECTOR_SHEET
#     """
#     for item in ["index", "columns"]:

#         check = multiindex_contain(
#             inner_index=getattr(to_check_matrix, item),
#             outer_index=getattr(given_matrix, item),
#             file=_ADD_SECTOR_SHEETS[key]["sheet"],
#         )
#         if not check["passed"]:
#             raise WrongExcelFormat(
#                 "Data structure is not correct for {}."
#                 " Following non acceptable items found in different levels"
#                 " of {} {}".format(
#                     _ADD_SECTOR_SHEETS[key]["sheet"], item, check["differences"]
#                 )
#             )

#     extra_matrix.loc[given_matrix.index, given_matrix.columns] = given_matrix.loc[
#         given_matrix.index, given_matrix.columns
#     ].values

#     if key == "fd":
#         result = orginal_matrix.append(extra_matrix)

#     elif key in ["sa", "fp"]:
#         result = pd.concat([orginal_matrix, extra_matrix], axis=1)

#     elif key in ["if", "it", "sf", "of"]:
#         return extra_matrix

#     return result
