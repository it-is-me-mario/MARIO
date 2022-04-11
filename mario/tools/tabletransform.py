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
from mario.tools.constants import _MASTER_INDEX
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

    data = instance.get_data(
        matrices=["Z", "V", "E", "X", "Y", "S", "U", "EY"],
        units=False,
        indeces=False,
        auto_calc=True,
        format="dict",
    )["baseline"]

    data["V"] = data["V"].loc[:, (slice(None), _MASTER_INDEX["a"], slice(None))]
    data["E"] = data["E"].loc[:, (slice(None), _MASTER_INDEX["a"], slice(None))]

    q = data["X"].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :].values
    g = data["X"].loc[(slice(None), _MASTER_INDEX["a"], slice(None)), :].values

    if method == "A":

        "Check number of commodities and industries"
        if data["S"].shape[0] != data["S"].shape[1]:
            raise NotImplementable(
                "Method "
                + str(method)
                + " is not an acceptable for this table: commodities number must match activities number"
            )

        "Transformation matrix"
        try:
            T = np.linalg.inv(data["S"].T) @ np.diagflat(q)
        except np.linalg.LinAlgError:
            log_time(
                logger,
                "Singular matrix issue. The (Moore-Penrose) "
                "pseudo-inverse of a matrix will be used. This "
                "may raise some inconsistency in the data",
                "critical",
            )
            T = np.linalg.pinv(data["S"].T) @ np.diagflat(q)

        "Product by Product IOT"
        Z_index = [
            data["U"].index.get_level_values(0),
            [_MASTER_INDEX["s"]] * data["U"].shape[0],
            data["U"].index.get_level_values(2),
        ]

        Z = pd.DataFrame(data["U"].values @ T, index=Z_index, columns=Z_index)
        V = pd.DataFrame(data["V"].values @ T, index=data["V"].index, columns=Z_index)
        E = pd.DataFrame(data["E"].values @ T, index=data["E"].index, columns=Z_index)

        Y = data["Y"].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :]
        Y.index = Z_index

        "Fixing units"
        units = copy.deepcopy(instance.units)
        units[_MASTER_INDEX["s"]] = units[_MASTER_INDEX["c"]]

        _indeces = copy.deepcopy(instance._indeces)
        _indeces["s"] = _indeces["c"]

    if method == "B":

        "Transformation matrix"
        try:
            T = np.linalg.inv(np.diagflat(g)) @ data["S"].values
        except np.linalg.LinAlgError:
            log_time(
                logger,
                "Singular matrix issue. The (Moore-Penrose) "
                "pseudo-inverse of a matrix will be used. This "
                "may raise some inconsistency in the data",
                "critical",
            )
            T = np.linalg.pinv(np.diagflat(g)) @ data["S"].values

        "Product by Product IOT"
        Z_index = [
            data["U"].index.get_level_values(0),
            [_MASTER_INDEX["s"]] * data["U"].shape[0],
            data["U"].index.get_level_values(2),
        ]

        Z = pd.DataFrame(data["U"].values @ T, index=Z_index, columns=Z_index)
        V = pd.DataFrame(data["V"].values @ T, index=data["V"].index, columns=Z_index)
        E = pd.DataFrame(data["E"].values @ T, index=data["E"].index, columns=Z_index)

        Y = data["Y"].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :]
        Y.index = Z_index

        "Fixing units"
        units = copy.deepcopy(instance.units)
        units[_MASTER_INDEX["s"]] = units[_MASTER_INDEX["c"]]

        _indeces = copy.deepcopy(instance._indeces)
        _indeces["s"] = _indeces["c"]

    if method == "C":

        "Check number of commodities and industries"
        if data["S"].shape[0] != data["S"].shape[1]:
            raise NotImplementable(
                "Method "
                + str(method)
                + " is not an acceptable for this table: commodities number must match activities number"
            )

        "Transformation matrix"
        try:
            T = np.diagflat(g) @ np.linalg.inv(data["S"].T)
        except np.linalg.LinAlgError:
            log_time(
                logger,
                "Singular matrix issue. The (Moore-Penrose) "
                "pseudo-inverse of a matrix will be used. This "
                "may raise some inconsistency in the data",
                "critical",
            )
            T = np.diagflat(g) @ np.linalg.pinv(data["S"].T)

        "Industry by Industry IOT"
        Z_index = [
            data["S"].index.get_level_values(0),
            [_MASTER_INDEX["s"]] * data["S"].shape[0],
            data["S"].index.get_level_values(2),
        ]

        Z = pd.DataFrame(T @ data["U"].values, index=Z_index, columns=Z_index)
        V = pd.DataFrame(data["V"].values, index=data["V"].index, columns=Z_index)
        E = pd.DataFrame(data["E"].values, index=data["E"].index, columns=Z_index)
        Y = pd.DataFrame(
            T @ data["Y"].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :].values,
            index=Z_index,
            columns=data["Y"].columns,
        )

        "Fixing units"
        units = copy.deepcopy(instance.units)
        units[_MASTER_INDEX["s"]] = units[_MASTER_INDEX["a"]]

        _indeces = copy.deepcopy(instance._indeces)
        _indeces["s"] = _indeces["a"]

    if method == "D":

        "Transformation matrix"
        try:
            T = data["S"].values @ np.linalg.inv(np.diagflat(q))
        except np.linalg.LinAlgError:
            log_time(
                logger,
                "Singular matrix issue. The (Moore-Penrose) "
                "pseudo-inverse of a matrix will be used. This "
                "may raise some inconsistency in the data",
                "critical",
            )
            T = data["S"].values @ np.linalg.pinv(np.diagflat(q))

        "Industry by Industry IOT"
        Z_index = [
            data["S"].index.get_level_values(0),
            [_MASTER_INDEX["s"]] * data["S"].shape[0],
            data["S"].index.get_level_values(2),
        ]

        Z = pd.DataFrame(T @ data["U"].values, index=Z_index, columns=Z_index)
        V = pd.DataFrame(data["V"].values, index=data["V"].index, columns=Z_index)
        E = pd.DataFrame(data["E"].values, index=data["E"].index, columns=Z_index)
        Y = pd.DataFrame(
            T @ data["Y"].loc[(slice(None), _MASTER_INDEX["c"], slice(None)), :].values,
            index=Z_index,
            columns=data["Y"].columns,
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

    matrices = {"baseline": {"Z": Z, "V": V, "E": E, "X": X, "Y": Y, "EY": data["EY"]}}
    indeces = {item: value for item, value in _indeces.items()}
    rename_index(matrices["baseline"])

    return matrices, indeces, units
