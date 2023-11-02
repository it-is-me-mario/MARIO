# -*- coding: utf-8 -*-
"""
This module will contain a set of functions useful for tables transformation
such as SUT-to-IOT transformation

Methods A,B,C,D refer to the Eurostat manual of nomenclature for SUT-to-IOT 
transformation models.
For further information check 
'Eurostat Manual of Supply, Use and Input-Output Tables, 2008'
"""

from mario.log_exc.exceptions import (
    WrongInput,
    NotImplementable,
)
from mario.log_exc.logger import log_time
import pandas as pd
import numpy as np
import copy
from mario.tools.constants import _ENUM, _MASTER_INDEX
from mario.tools.iomath import calc_X
from mario.tools.utilities import rename_index


import logging

logger = logging.getLogger(__name__)


_ACCEPTABLES = ["A", "B", "C", "D"]


def SUT_to_IOT(instance, method):

    if method not in _ACCEPTABLES:
        raise WrongInput(
            "'{}' is not an accpetable input for 'method'. "
            "Acceptable values are \n{}".format(method, _ACCEPTABLES)
        )
    # Making a deep copy of the matrices to avoid changing the baseline

    data = instance.query(
        matrices=[_ENUM.Z, _ENUM.V, _ENUM.E, _ENUM.X, _ENUM.Y, _ENUM.S, _ENUM.U, _ENUM.EY],
    )

    data[_ENUM.V] = data[_ENUM.V].loc[:, (slice(None), _MASTER_INDEX["a"], slice(None))]
    data[_ENUM.E] = data[_ENUM.E].loc[:, (slice(None), _MASTER_INDEX["a"], slice(None))]

    q = data[_ENUM.X].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :].values
    g = data[_ENUM.X].loc[(slice(None), _MASTER_INDEX["a"], slice(None)), :].values

    if method == "A":

        "Check number of commodities and industries"
        if data[_ENUM.S].shape[0] != data[_ENUM.S].shape[1]:
            raise NotImplementable(
                "Method "
                + str(method)
                + " is not an acceptable for this table: commodities number must match activities number"
            )

        "Transformation matrix"
        try:
            T = np.linalg.inv(data[_ENUM.S].T) @ np.diagflat(q)
        except np.linalg.LinAlgError:
            log_time(
                logger,
                "Singular matrix issue. The (Moore-Penrose) "
                "pseudo-inverse of a matrix will be used. This "
                "may raise some inconsistency in the data",
                "critical",
            )
            T = np.linalg.pinv(data[_ENUM.S].T) @ np.diagflat(q)

        "Product by Product IOT"
        Z_index = [
            data[_ENUM.U].index.get_level_values(0),
            [_MASTER_INDEX["s"]] * data[_ENUM.U].shape[0],
            data[_ENUM.U].index.get_level_values(2),
        ]

        Z = pd.DataFrame(data[_ENUM.U].values @ T, index=Z_index, columns=Z_index)
        V = pd.DataFrame(data[_ENUM.V].values @ T, index=data[_ENUM.V].index, columns=Z_index)
        E = pd.DataFrame(data[_ENUM.E].values @ T, index=data[_ENUM.E].index, columns=Z_index)

        Y = data[_ENUM.Y].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :]
        Y.index = Z_index

        "Fixing units"
        units = copy.deepcopy(instance.units)
        units[_MASTER_INDEX["s"]] = units[_MASTER_INDEX["c"]]

        _indeces = copy.deepcopy(instance._indeces)
        _indeces["s"] = _indeces["c"]

    if method == "B":

        "Transformation matrix"
        try:
            T = np.linalg.inv(np.diagflat(g)) @ data[_ENUM.S].values
        except np.linalg.LinAlgError:
            log_time(
                logger,
                "Singular matrix issue. The (Moore-Penrose) "
                "pseudo-inverse of a matrix will be used. This "
                "may raise some inconsistency in the data",
                "critical",
            )
            T = np.linalg.pinv(np.diagflat(g)) @ data[_ENUM.S].values

        "Product by Product IOT"
        Z_index = [
            data[_ENUM.U].index.get_level_values(0),
            [_MASTER_INDEX["s"]] * data[_ENUM.U].shape[0],
            data[_ENUM.U].index.get_level_values(2),
        ]

        Z = pd.DataFrame(data[_ENUM.U].values @ T, index=Z_index, columns=Z_index)
        V = pd.DataFrame(data[_ENUM.V].values @ T, index=data[_ENUM.V].index, columns=Z_index)
        E = pd.DataFrame(data[_ENUM.E].values @ T, index=data[_ENUM.E].index, columns=Z_index)

        Y = data[_ENUM.Y].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :]
        Y.index = Z_index

        "Fixing units"
        units = copy.deepcopy(instance.units)
        units[_MASTER_INDEX["s"]] = units[_MASTER_INDEX["c"]]

        _indeces = copy.deepcopy(instance._indeces)
        _indeces["s"] = _indeces["c"]

    if method == "C":

        "Check number of commodities and industries"
        if data[_ENUM.S].shape[0] != data[_ENUM.S].shape[1]:
            raise NotImplementable(
                "Method "
                + str(method)
                + " is not an acceptable for this table: commodities number must match activities number"
            )

        "Transformation matrix"
        try:
            T = np.diagflat(g) @ np.linalg.inv(data[_ENUM.S].T)
        except np.linalg.LinAlgError:
            log_time(
                logger,
                "Singular matrix issue. The (Moore-Penrose) "
                "pseudo-inverse of a matrix will be used. This "
                "may raise some inconsistency in the data",
                "critical",
            )
            T = np.diagflat(g) @ np.linalg.pinv(data[_ENUM.S].T)

        "Industry by Industry IOT"
        Z_index = [
            data[_ENUM.S].index.get_level_values(0),
            [_MASTER_INDEX["s"]] * data[_ENUM.S].shape[0],
            data[_ENUM.S].index.get_level_values(2),
        ]

        Z = pd.DataFrame(T @ data[_ENUM.U].values, index=Z_index, columns=Z_index)
        V = pd.DataFrame(data[_ENUM.V].values, index=data[_ENUM.V].index, columns=Z_index)
        E = pd.DataFrame(data[_ENUM.E].values, index=data[_ENUM.E].index, columns=Z_index)
        Y = pd.DataFrame(
            T @ data[_ENUM.Y].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :].values,
            index=Z_index,
            columns=data[_ENUM.Y].columns,
        )

        "Fixing units"
        units = copy.deepcopy(instance.units)
        units[_MASTER_INDEX["s"]] = units[_MASTER_INDEX["a"]]

        _indeces = copy.deepcopy(instance._indeces)
        _indeces["s"] = _indeces["a"]

    if method == "D":

        "Transformation matrix"
        try:
            T = data[_ENUM.S].values @ np.linalg.inv(np.diagflat(q))
        except np.linalg.LinAlgError:
            log_time(
                logger,
                "Singular matrix issue. The (Moore-Penrose) "
                "pseudo-inverse of a matrix will be used. This "
                "may raise some inconsistency in the data",
                "critical",
            )
            T = data[_ENUM.S].values @ np.linalg.pinv(np.diagflat(q))

        "Industry by Industry IOT"
        Z_index = [
            data[_ENUM.S].index.get_level_values(0),
            [_MASTER_INDEX["s"]] * data[_ENUM.S].shape[0],
            data[_ENUM.S].index.get_level_values(2),
        ]

        Z = pd.DataFrame(T @ data[_ENUM.U].values, index=Z_index, columns=Z_index)
        V = pd.DataFrame(data[_ENUM.V].values, index=data[_ENUM.V].index, columns=Z_index)
        E = pd.DataFrame(data[_ENUM.E].values, index=data[_ENUM.E].index, columns=Z_index)
        Y = pd.DataFrame(
            T @ data[_ENUM.Y].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :].values,
            index=Z_index,
            columns=data[_ENUM.Y].columns,
        )

        "Fixing units"
        units = copy.deepcopy(instance.units)
        units[_MASTER_INDEX["s"]] = units[_MASTER_INDEX["a"]]
        _indeces = copy.deepcopy(instance._indeces)
        _indeces["s"] = _indeces["a"]

    del units[_MASTER_INDEX["c"]]
    del units[_MASTER_INDEX["a"]]

    del _indeces["c"]
    del _indeces["a"]

    X = calc_X(Z, Y)

    matrices = {"baseline": {
        _ENUM.Z: Z, 
        _ENUM.V: V, 
        _ENUM.E: E, 
        _ENUM.X: X, 
        _ENUM.Y: Y, 
        _ENUM.EY: data[_ENUM.EY]}}
    
    indeces = {item: value for item, value in _indeces.items()}
    rename_index(matrices["baseline"])

    return matrices, indeces, units
