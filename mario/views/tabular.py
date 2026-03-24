"""Tabular views extracted from the ``Database`` class."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mario.model.conventions import _ENUM, _MASTER_INDEX


def build_database_frame(database, scenario: str = "baseline") -> pd.DataFrame:
    """Return the historical single-sheet dataframe view of the database."""

    data = database.query(
        matrices=[_ENUM.Z, _ENUM.Y, _ENUM.V, _ENUM.E, _ENUM.EY, _ENUM.VY],
        scenarios=scenario,
    )

    Z = data[_ENUM.Z]
    Y = data[_ENUM.Y]
    V = data[_ENUM.V]
    E = data[_ENUM.E]
    EY = data[_ENUM.EY]
    VY = data[_ENUM.VY]

    V.index = [[""] * len(V), [_MASTER_INDEX["f"]] * len(V), V.index]
    E.index = [[""] * len(E), [_MASTER_INDEX["k"]] * len(E), E.index]
    EY.index = [[""] * len(EY), [_MASTER_INDEX["k"]] * len(EY), EY.index]
    VY.index = [[""] * len(VY), [_MASTER_INDEX["f"]] * len(VY), VY.index]

    index = []
    columns = []

    for level in range(3):
        index.append(
            Z.index.get_level_values(level).to_list()
            + E.index.get_level_values(level).to_list()
            + V.index.get_level_values(level).to_list()
        )
        columns.append(
            Z.columns.get_level_values(level).to_list()
            + Y.columns.get_level_values(level).to_list()
        )

    dataframe = pd.DataFrame(
        np.zeros((len(index[0]), len(columns[0]))), index=index, columns=columns
    )

    for item in [Z, Y, V, E, EY, VY]:
        dataframe.loc[item.index, item.columns] = item.loc[item.index, item.columns]

    return dataframe
