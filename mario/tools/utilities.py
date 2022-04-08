# -*- coding: utf-8 -*-
"""
contains the utils functions in mario
"""
import pandas as pd
import numpy as np
import logging
import math
import os


from mario.tools.constants import (
    _MASTER_INDEX,
    _LEVELS,
    _ALL_MATRICES,
    _INDEX_NAMES,
)

from mario.log_exc.logger import log_time

from mario.log_exc.exceptions import (
    WrongInput,
    WrongExcelFormat,
)
from zipfile import ZipFile


logger = logging.getLogger(__name__)

from IPython import get_ipython


def slicer(matrix, axis, **levels):
    """Helps to slice the matrices

    Parameters
    ----------
    matrix : str
        the matrix to be sliced

    axis : int
        0 for rows and 1 for columns

    levels : Dict['list']
        defines the level to be sliced (according to index and columns names).
        for 3 level data [Region,Level,Item] and for 1 level data only [Item].

    Returns
    -------
    tuple, list

    Example
    --------
    For slicing a the final demand matrix for reg1 and sec1 on the rows and
    reg1 on the columns (local final demand of sec1 of reg1):

    .. code-block:: python

        Y_rows = slicer(matrix= 'Y', axis= 0, Region= ['reg1'], Item= ['sec1'])
        Y_cols = slicer(matrix= 'Y', axis= 1, Region= ['reg1'])

        # To use the slicer
        data.Y.loc[Y_rows,Y_cols]
    """

    if matrix.upper() in ["V", "E"] and axis == 0:
        acceptable_levels = ["Item"]
    else:
        acceptable_levels = ["Region", "Level", "Item"]

    difference = set(levels.keys()).difference(set(acceptable_levels))
    if difference:
        raise ValueError(f"for {matrix}, acceptable levels are {acceptable_levels}")

    _slicer = [levels.get(level, slice(None)) for level in acceptable_levels]

    if len(_slicer) == 1:
        return _slicer[0]

    return tuple(_slicer)


def run_from_jupyter():
    if get_ipython() is not None:
        ipy_str = str(type(get_ipython()))
        if "zmqshell" in ipy_str:
            return True
        return False


def sort_frames(_dict):

    for key, value in _dict.items():

        if key.upper() in ["E", "V", "EY"]:
            _dict[key] = value.sort_index(axis=1, level=1)

        else:
            _dict[key] = value.sort_index(axis=1, level=1).sort_index(axis=0, level=1)


def validate_path(path: [str, list]):

    if isinstance(path, str):
        path = [path]

    for item in path:
        if not os.path.exists(item):
            raise FileNotFoundError(f"{item} does not exist.")


def unique_frmaes(
    frame: pd.DataFrame,
) -> list:

    all_items = []
    for col, values in frame.iteritems():
        given_values = delete_duplicates(values.values)
        all_items.extend(given_values)

    return delete_duplicates(all_items)


def delete_duplicates(_list: [list, tuple]) -> list:
    return list(dict.fromkeys(_list))


def index_col_equlity(
    original: pd.DataFrame, given: pd.DataFrame, levels: list = ["index", "columns"]
):

    for level in levels:
        if not getattr(original, level).equals(getattr(given, level)):
            raise WrongExcelFormat(f"{level} does not have the correct format.")


def _meta_parse_history(instance, function, old_index=None, new_index=None):

    if function == "parse":
        instance.meta._add_history("Database successfully imported.")
        for index in instance._indeces.keys():
            instance.meta._add_history(
                "Number of {} = {}".format(
                    _MASTER_INDEX[index], len(instance._indeces[index]["main"])
                )
            )

    elif function == "aggregation":
        for index, value in instance._indeces.items():
            instance.meta._add_history(
                "{} aggregated from {} levels to {} levels".format(
                    _MASTER_INDEX[index],
                    len(old_index[index]["main"]),
                    len(new_index[index]["main"]),
                )
            )


def _matrices(instance, function, scenario="baseline"):
    """
    This function is in charge of deleting or adding the matrices as a callable
    attribute to the instance
    """
    # acceptable_matrices=_ALL_MATRICES+_SUT_MATRICES

    if function == "del":

        for attribute in _ALL_MATRICES[instance.table_type]:
            if scenario != "baseline":
                attribute = "{}_c".format(attribute)
            try:
                delattr(instance, attribute)
            except AttributeError:
                pass

    if function == "add":
        pass
        # --TODO-- check if it is necessary to have it
        # for attribute,value in instance.matrices[scenario].items():
        #     if scenario != 'baseline':
        #         attribute = '{}_c'.format(attribute)

        #     setattr(instance, attribute,value)


def _manage_indeces(instance, case, **kwargs):

    if case == "aggregation":
        for index in instance._indeces.keys():
            if "aggregated" in instance._indeces[index]:
                main = {
                    instance._indeces[index]["aggregated"].values[i][0]
                    for i in range(instance._indeces[index]["aggregated"].shape[0])
                    if instance._indeces[index]["aggregated"].values[i][0] != "unused"
                }
                instance._indeces[index] = {"main": list(main)}

    elif case == "single_region":
        for key, value in kwargs.items():
            instance._indeces[key] = {"main": value}


def subplot_grid(subplot_number, orientation="v"):

    if orientation == "v":
        j = 0
        n_cols = []
        for i in reversed(range(subplot_number + 1)):
            if int(math.sqrt(i) + 0.5) ** 2 == i:
                n_cols += [int(math.sqrt(i))]
            j += 1
        n_cols = n_cols[0]

        if int(math.sqrt(subplot_number) + 0.5) ** 2 == subplot_number:
            n_rows = n_cols
        else:
            n_rows = n_cols + int(math.ceil((subplot_number - n_cols ** 2) / n_cols))

    elif orientation == "h":
        j = 0
        n_rows = []
        for i in reversed(range(subplot_number + 1)):
            if int(math.sqrt(i) + 0.5) ** 2 == i:
                n_rows += [int(math.sqrt(i))]
            j += 1
        n_rows = n_rows[0]

        if int(math.sqrt(subplot_number) + 0.5) ** 2 == subplot_number:
            n_cols = n_rows
        else:
            n_cols = n_rows + int(math.ceil((subplot_number - n_rows ** 2) / n_rows))

    grid = [(row + 1, col + 1) for row in range(n_rows) for col in range(n_cols)]

    return (n_rows, n_cols, grid)


def str_2_list(*args):

    "this fucntion returns a list in case that the user pass a string"

    output = []
    for arg in args:
        if isinstance(arg, str):
            output.append([arg])
        else:
            output.append(arg)

    return output


def master_exist(instance, **kwargs):
    """
    'this function checks if a specific item (any of the items from the MASTER_INDEX are valid or not'
    instance = self
    for kwargs:
        key   = the key of the MASTER_INDEX
        value = a list of the items that the user is giving
    """

    for key, values in kwargs.items():
        for value in values:
            if value not in instance.get_index(_MASTER_INDEX[key]):
                raise WrongInput(f"{value} is not a valid {_MASTER_INDEX[key]}.")


def check_clusters(instance, clusters):

    for level, level_cluster in clusters.items():
        if level not in _LEVELS[instance.meta.table]:
            raise WrongInput(
                "{} is not a valid level. Valid items are {}".format(
                    level, [*_LEVELS[instance.meta.table]]
                )
            )
        for cluster, values in level_cluster.items():
            for value in values:
                if value not in instance.get_index(level):
                    raise WrongInput(
                        "{} in cluster {} for level {} is not a valid item.".format(
                            value, cluster, level
                        )
                    )


def all_file_reader(
    path, guide, sub_folder=False, sep="\t", exceptions=[], engine=None
):
    read = {}

    def readers(file_to_read, file):
        try:
            if file_to_read.split(".")[-1] in ["txt", "csv"]:

                read[key][inner_key] = pd.read_csv(
                    file,
                    index_col=inner_value["index_col"],
                    header=inner_value["header"],
                    sep=sep,
                )
            else:
                read[key][inner_key] = pd.read_excel(
                    file,
                    index_col=inner_value["index_col"],
                    header=inner_value["header"],
                    engine=engine,
                    sheet_name=0
                    if "sheet_name" not in inner_value
                    else inner_value["sheet_name"],
                )

        except FileNotFoundError:
            if inner_key not in exceptions:
                raise FileNotFoundError(f"No such file or directory: {file}")

    if path.split(".")[-1] == "zip":
        with ZipFile(r"{}".format(path), "a") as folder:

            try:
                new_path = folder.namelist()[0].split("/")[0] if sub_folder else ""
            except IndexError:
                raise FileNotFoundError

            for key, value in guide.items():

                read[key] = {}

                for inner_key, inner_value in value.items():
                    path = (
                        r"{}/{}".format(new_path, inner_value["file_name"])
                        if new_path
                        else r"{}".format(inner_value["file_name"])
                    )
                    with folder.open(path) as file:
                        readers(inner_value["file_name"], file)

    else:
        for key, value in guide.items():
            read[key] = {}

            for inner_key, inner_value in value.items():

                file = r"{}/{}".format(path, inner_value["file_name"])
                readers(file, file)

    return read


def return_index(df, item, multi_index, del_duplicate, reindex, level=None):

    if multi_index:
        index = eval("df.{}.get_level_values({})".format(item, level))
    else:
        index = eval("df.{}".format(item))

    if del_duplicate:
        index = delete_duplicates(list(index))

    return index


def multiindex_contain(inner_index, outer_index, file, check_levels=None):

    if type(inner_index) != type(outer_index):
        raise WrongInput(
            f"Incorrect indexing for {file}. the indexing should be with a {type(outer_index)} format."
        )

    if isinstance(inner_index, pd.MultiIndex):
        if check_levels is None:
            if inner_index.nlevels != outer_index.nlevels:
                raise WrongInput(f"number levels for {file} are not valid.")
            levels = [(i, i) for i in range(inner_index.nlevels)]
        else:
            levels = check_levels

        differences = {}
        passed = True
        for level in levels:

            diff = (
                outer_index.levels[level[1]]
                .difference(inner_index.levels[level[0]])
                .tolist()
            )

            differences[level[1]] = diff
            if len(diff):
                passed = False

        return {"passed": passed, "differences": differences}

    elif isinstance(inner_index, pd.Index):
        differences = outer_index.difference(inner_index).tolist()
        passed = False if len(differences) else True

        return {"passed": passed, "differences": differences}


def rename_index(_dict):

    for key, value in _dict.items():
        for item in ["index", "columns"]:
            if isinstance(eval(f"value.{item}"), pd.MultiIndex):
                exec(f"value.{item}.names = _INDEX_NAMES['3levels']")
            else:
                exec(f"value.{item}.name = _INDEX_NAMES['1level']")


def linkages_calculation(instance, cut_diag, matrices, multi_mode, normalized):
    """calculates the linkages"""
    if cut_diag:
        for key, value in matrices.items():
            np.fill_diagonal(value.values, 0)

    if multi_mode:

        link_types = [
            "Total Forward",
            "Total Backward",
            "Direct Forward",
            "Direct Backward",
        ]
        geo_types = ["Local", "Foreign"]
        links = pd.DataFrame(
            0,
            index=matrices["g"].index,
            columns=pd.MultiIndex.from_product([link_types, geo_types]),
        )

        for index, values in links.iterrows():
            links.loc[index, ("Total Forward", "Local")] = (
                matrices["g"].loc[index, index[0]].sum().sum()
            )
            links.loc[index, ("Total Forward", "Foreign")] = (
                matrices["g"].loc[index].sum().sum()
                - matrices["g"].loc[index, index[0]].sum().sum()
            )

            links.loc[index, ("Total Backward", "Local")] = (
                matrices["w"].loc[index, index[0]].sum().sum()
            )
            links.loc[index, ("Total Backward", "Foreign")] = (
                matrices["w"].loc[index].sum().sum()
                - matrices["w"].loc[index, index[0]].sum().sum()
            )

            links.loc[index, ("Direct Forward", "Local")] = (
                matrices["b"].loc[index, index[0]].sum().sum()
            )
            links.loc[index, ("Direct Forward", "Foreign")] = (
                matrices["b"].loc[index].sum().sum()
                - matrices["b"].loc[index, index[0]].sum().sum()
            )

            links.loc[index, ("Direct Backward", "Local")] = (
                matrices["z"].loc[index, index[0]].sum().sum()
            )
            links.loc[index, ("Direct Backward", "Foreign")] = (
                matrices["z"].loc[index].sum().sum()
                - matrices["z"].loc[index, index[0]].sum().sum()
            )

        if normalized:
            log_time(
                logger, "Normalization not available for multi-regional mode.", "warn"
            )

    # Computing linkages as if there were only one unique region
    else:
        _forward_t = matrices["g"].sum(axis=1).to_frame()
        _backward_t = matrices["w"].sum(axis=0).to_frame()
        _forward_d = matrices["b"].sum(axis=1).to_frame()
        _backward_d = matrices["z"].sum(axis=0).to_frame()

        _forward_t.columns = ["Total Forward"]
        _backward_t.columns = ["Total Backward"]
        _forward_d.columns = ["Direct Forward"]
        _backward_d.columns = ["Direct Backward"]

        if normalized:

            _forward_t.iloc[:, 0] = _forward_t.iloc[:, 0] / np.average(
                _forward_t.values
            )
            _backward_t.iloc[:, 0] = _backward_t.iloc[:, 0] / np.average(
                _backward_t.values
            )
            _forward_d.iloc[:, 0] = _forward_d.iloc[:, 0] / np.average(
                _forward_d.values
            )
            _backward_d.iloc[:, 0] = _backward_d.iloc[:, 0] / np.average(
                _backward_d.values
            )

        links = pd.concat([_forward_t, _backward_t, _forward_d, _backward_d], axis=1)

    return links


def unit_check(instance, sets, slicer=None):

    if sets == _MASTER_INDEX["r"]:
        raise WrongInput(f"Set '{sets}' do not have any unit")
    units = instance.units[sets]
    if slicer is not None:
        units = units.loc[slicer, :]
    uniques = {}

    unique_units = units["unit"].unique()

    for unit in unique_units:
        uniques[unit] = units.index[units["unit"] == unit].tolist()

    return uniques


def filtering(instance, filters):

    for item, value in filters.items():

        splitter = item.split("_")
        if item == "filter_{}".format(_MASTER_INDEX["n"].replace(" ", "_")):
            assign = _MASTER_INDEX["n"]
        elif item == "filter_{}".format(_MASTER_INDEX["k"].replace(" ", "_")):
            assign = _MASTER_INDEX["k"]
        elif item == "filter_{}".format(_MASTER_INDEX["f"].replace(" ", "_")):
            assign = _MASTER_INDEX["f"]
        else:
            assign = splitter[-1] if len(splitter) == 2 else splitter[1]

        if isinstance(value, str):
            value = [value]

        if value == ["all"]:
            if assign in instance.sets:
                filters[item] = instance.get_index(assign)

        else:
            if assign in instance.sets:
                original = instance.get_index(assign)
                difference = set(value).difference(set(original))
                if difference:
                    raise WrongInput(
                        f"Following items are not acceptables for {item}: {difference}"
                    )

    return filters


        
        
    
    
    
    
    