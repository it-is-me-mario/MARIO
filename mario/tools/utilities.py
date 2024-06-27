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
    _ENUM,
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

    if matrix.upper() in [_ENUM.V, _ENUM.E] and axis == 0:
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
        if key.upper() in [_ENUM.E, _ENUM.V, _ENUM.EY]:
            _dict[key] = value.sort_index(axis=1, level=1)

        else:
            _dict[key] = value.sort_index(axis=1, level=1).sort_index(axis=0, level=1)


def delete_duplicates(_list: [list, tuple]) -> list:
    return list(dict.fromkeys(_list))


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


def check_clusters(index_dict, table, clusters):
    differences = set(clusters).difference(set(_LEVELS[table]))

    if differences:
        raise WrongInput(
            "{} is/are not valid level/s. Valid items are {}".format(
                differences, [*_LEVELS[table]]
            )
        )

    for level, level_cluster in clusters.items():
        for cluster, values in level_cluster.items():
            differences = set(values).difference(set(index_dict[level]))
            if differences:
                raise WrongInput(
                    "{} in cluster {} for level {} is/are not a valid item/s.".format(
                        differences, cluster, level
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


def return_index(df, item, multi_index, del_duplicate, reindex=None, level=None):
    if multi_index:
        index = list(getattr(df, item).get_level_values(level))

    else:
        index = list(getattr(df, item))

    if del_duplicate:
        index = delete_duplicates(index)

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
            levels = list(
                range(inner_index.nlevels)
            )  # [i for i in range(inner_index.nlevels)]
        else:
            levels = check_levels

        differences = {}
        passed = True
        for level in levels:
            diff = (
                outer_index.levels[level].difference(inner_index.levels[level]).tolist()
            )

            differences[level] = diff
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
            if isinstance(getattr(value, item), pd.MultiIndex):
                getattr(value, item).names = _INDEX_NAMES["3levels"]
            else:
                getattr(value, item).name = _INDEX_NAMES["1level"]


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


def pymrio_styling(df, keep_index, keep_columns, index_name, columns_name):
    index = [df.index.get_level_values(i) for i in keep_index]
    columns = [df.columns.get_level_values(i) for i in keep_columns]

    if len(index) - 1:
        index = pd.MultiIndex.from_arrays(index, names=index_name)
    else:
        index = pd.Index(index[0], name=index_name)

    if len(columns) - 1:
        columns = pd.MultiIndex.from_arrays(columns, names=columns_name)
    else:
        columns = pd.Index(columns[0], name=columns_name)

    return pd.DataFrame(data=df.values, index=index, columns=columns)


def to_single_index(df):
    """Retuns joined pd.Index from pd.MultiIndex"""

    if isinstance(df.index, pd.MultiIndex):
        df.index = [", ".join(ii) for ii in df.index]

    return df


def extract_metadata_from_eurostat(file):
    """extracts some info such as country,table_info, and the year of the data from an xlsx

    Parameters
    ----------
    file : pd.ExcelFile
        contains the Sheet 1 information

    Return
    -------
    dict
        metadata with country,table_type, and year info
    """
    meta_info = {
        "year": (7, 2, int),
        "country": (6, 2, str),
        "table": (0, 1, str),
        "unit": (4, 2, str),
    }

    initial_data = file.parse(sheet_name="Sheet 1")
    metadata = {}
    for item, info in meta_info.items():
        metadata[item] = info[2](initial_data.iloc[info[0], info[1]])

    return metadata
