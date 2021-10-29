# -*- coding: utf-8 -*-
"""
The module containing functionalities for adding a sector
"""
import pandas as pd

# constants
from mario.tools.constants import (
    _MASTER_INDEX,
    _ADD_SECTOR_SHEETS,
)
from mario.log_exc.exceptions import (
    LackOfInput,
    WrongExcelFormat,
)

from mario.tools.utilities import multiindex_contain


def adding_new_sector(instance, data, new_sectors, item, regions):

    keys = list(_ADD_SECTOR_SHEETS.keys())
    # Taking the right keys based on the database type: SUT or IOT
    if item == _MASTER_INDEX["s"]:
        keys.remove("of")
        counter_item = item
    else:
        keys.remove("sf")
        if item == _MASTER_INDEX["a"]:
            keys.remove("it")
            counter_item = _MASTER_INDEX["c"]
        else:
            keys.remove("if")
            counter_item = _MASTER_INDEX["a"]

    _data = instance.get_data(
        matrices=["e", "v", "z", "Y"],
        scenarios=["baseline"],
        units=False,
        indeces=False,
    )["baseline"]

    matrix_mapper = {
        "it": {
            "columns": pd.MultiIndex.from_product(
                [[regions[0]], [counter_item], [instance.get_index(counter_item)[0]]]
            ),
            "index": pd.MultiIndex.from_product([regions, [item], new_sectors]),
        },
        "of": {
            "columns": pd.MultiIndex.from_product(
                [[regions[0]], [counter_item], [instance.get_index(counter_item)[0]]]
            ),
            "index": pd.MultiIndex.from_product([regions, [item], new_sectors]),
        },
        "fd": {
            "columns": pd.MultiIndex.from_product(
                [
                    [regions[0]],
                    [_MASTER_INDEX["n"]],
                    [instance.get_index(_MASTER_INDEX["n"])[0]],
                ]
            ),
            "index": pd.MultiIndex.from_product([regions, [item], new_sectors]),
        },
    }

    dataframes = {}
    if isinstance(data, str):

        for key in keys:
            try:
                dataframes[key] = pd.read_excel(
                    data,
                    _ADD_SECTOR_SHEETS[key]["sheet"],
                    index_col=list(range(_ADD_SECTOR_SHEETS[key]["rows"])),
                    header=list(range(_ADD_SECTOR_SHEETS[key]["cols"])),
                ).fillna(0)

            except IndexError as e:

                if e.args[0] == "list index out of range" and key in ["fd", "it", "of"]:

                    df = pd.DataFrame(
                        0,
                        index=matrix_mapper[key]["index"],
                        columns=matrix_mapper[key]["columns"],
                    )
                    dataframes[key] = df
                else:
                    raise Exception(e)

    data = instance.get_data(
        matrices=["e", "v", "z", "Y"],
        scenarios=["baseline"],
        units=False,
        indeces=False,
    )["baseline"]
    e = data.e
    v = data.v
    z = data.z
    Y = data.Y

    # check if the units are passed or not
    for sec in new_sectors:
        if str(dataframes["un"].loc[sec, "unit"]) == "nan":
            raise LackOfInput("The unit of measure of {} is unfilled.".format(sec))

    # Creating a new data frame with new items added
    Y_index0 = pd.MultiIndex.from_product(
        [instance.get_index(_MASTER_INDEX["r"]), [item], new_sectors]
    )

    Y_extra = pd.DataFrame(0, index=Y_index0, columns=Y.columns)

    Y_index1 = pd.MultiIndex.from_product([regions, [item], new_sectors])

    Y_check = pd.DataFrame(0, index=Y_index1, columns=Y.columns)

    Y = create_new_matrix(
        orginal_matrix=Y,
        extra_matrix=Y_extra,
        given_matrix=dataframes["fd"],
        to_check_matrix=Y_check,
        key="fd",
    )

    # Creating a new data frame with new items added
    e_extra = pd.DataFrame(0, index=e.index, columns=Y_index0)
    e_check = pd.DataFrame(0, index=e.index, columns=Y_index1)

    e = create_new_matrix(
        orginal_matrix=e,
        extra_matrix=e_extra,
        given_matrix=dataframes["sa"],
        to_check_matrix=e_check,
        key="sa",
    )

    # Creating a new data frame with new items added
    v_extra = pd.DataFrame(0, index=v.index, columns=Y_index0)
    v_check = pd.DataFrame(0, index=v.index, columns=Y_index1)

    v = create_new_matrix(
        orginal_matrix=v,
        extra_matrix=v_extra,
        given_matrix=dataframes["fp"],
        to_check_matrix=v_check,
        key="fp",
    )
    # input from matrix
    z_index0 = pd.MultiIndex.from_product(
        [
            instance.get_index(_MASTER_INDEX["r"]),
            [counter_item],
            instance.get_index(counter_item),
        ]
    )

    z_columns0 = pd.MultiIndex.from_product(
        [instance.get_index(_MASTER_INDEX["r"]), [item], new_sectors]
    )

    z_columns1 = pd.MultiIndex.from_product([regions, [item], new_sectors])

    """
    if: works for IOT
    """
    z_extra = pd.DataFrame(0, index=z_columns0, columns=z_columns0)
    z = z.append(z_extra)
    if item != _MASTER_INDEX["c"]:
        # we have the input from to be checked

        z_check = pd.DataFrame(0, index=z_index0, columns=z_columns1)
        z = create_new_matrix(
            orginal_matrix=None,
            extra_matrix=z,
            given_matrix=dataframes["if"],
            to_check_matrix=z_check,
            key="if",
        )

    if item != _MASTER_INDEX["a"]:
        # we have the input to to be checked

        z_check = pd.DataFrame(0, columns=z_index0, index=z_columns1)
        z = create_new_matrix(
            orginal_matrix=None,
            extra_matrix=z,
            given_matrix=dataframes["it"],
            to_check_matrix=z_check,
            key="it",
        )

    if item == _MASTER_INDEX["a"]:
        z_check = pd.DataFrame(0, index=z_columns1, columns=z_index0)
        z = create_new_matrix(
            orginal_matrix=None,
            extra_matrix=z,
            given_matrix=dataframes["of"],
            to_check_matrix=z_check,
            key="of",
        )

    if item == _MASTER_INDEX["c"]:
        z_check = pd.DataFrame(0, index=z_index0, columns=z_columns1)
        z = create_new_matrix(
            orginal_matrix=None,
            extra_matrix=z,
            given_matrix=dataframes["of"],
            to_check_matrix=z_check,
            key="of",
        )

    if item == _MASTER_INDEX["s"]:

        z_index0 = pd.MultiIndex.from_product([regions, [item], new_sectors])
        # self consumption

        z_check = pd.DataFrame(0, columns=z_index0, index=z_index0)
        z = create_new_matrix(
            orginal_matrix=None,
            extra_matrix=z,
            given_matrix=dataframes["sf"],
            to_check_matrix=z_check,
            key="sf",
        )

    v = v.sort_index(axis=1, level=1)
    e = e.sort_index(axis=1, level=1)
    Y = Y.sort_index(axis=1, level=1).sort_index(axis=0, level=1)
    z = z.sort_index(axis=1, level=1).sort_index(axis=0, level=1)

    return z.fillna(0), v.fillna(0), e.fillna(0), Y.fillna(0), dataframes["un"]


def create_new_matrix(orginal_matrix, extra_matrix, given_matrix, to_check_matrix, key):

    """
    original_matrix: from database
    extra_matrix: matrix to be added
    given_matrix: the one passed by user
    matrix: name of the matrix
    key: the key of _ADD_SECTOR_SHEET
    """
    for item in ["index", "columns"]:

        check = multiindex_contain(
            inner_index=getattr(to_check_matrix, item),
            outer_index=getattr(given_matrix, item),
            file=_ADD_SECTOR_SHEETS[key]["sheet"],
        )
        if not check["passed"]:
            raise WrongExcelFormat(
                "Data structure is not correct for {}."
                " Following non acceptable items found in different levels"
                " of {} {}".format(
                    _ADD_SECTOR_SHEETS[key]["sheet"], item, check["differences"]
                )
            )

    extra_matrix.loc[given_matrix.index, given_matrix.columns] = given_matrix.loc[
        given_matrix.index, given_matrix.columns
    ].values

    if key == "fd":
        result = orginal_matrix.append(extra_matrix)

    elif key in ["sa", "fp"]:
        result = pd.concat([orginal_matrix, extra_matrix], axis=1)

    elif key in ["if", "it", "sf", "of"]:
        return extra_matrix

    return result
