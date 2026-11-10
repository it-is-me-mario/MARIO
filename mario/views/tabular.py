"""Tabular views extracted from the ``Database`` class."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mario.model.conventions import _ENUM, _MASTER_INDEX


def _axis_records(axis, terminal):
    """Describe display coordinates without encoding dimensions in labels."""
    if not isinstance(axis, pd.MultiIndex):
        return [{terminal: item} for item in axis]
    records = []
    for item in axis:
        if tuple(axis.names) == ("Region", "Level", "Item"):
            records.append({"Region": item[0], item[1]: item[2]})
        else:
            record = dict(zip(axis.names, item))
            if "Level" in record and "Item" in record:
                record[record.pop("Level")] = record.pop("Item")
            elif "Item" in record:
                record[terminal] = record.pop("Item")
            records.append(record)
    return records


def _semantic_database_frame(data):
    """Keep all declared row dimensions, including inapplicable empty levels."""
    Z, Y, V, E, EY, VY = (data[name] for name in (_ENUM.Z, _ENUM.Y, _ENUM.V, _ENUM.E, _ENUM.EY, _ENUM.VY))
    row_blocks = [(Z, "Sector"), (V, "Factor of production"), (E, "Satellite account")]
    column_blocks = [(Z, "Sector"), (Y, "Consumption category")]
    row_records = [_axis_records(frame.index, terminal) for frame, terminal in row_blocks]
    col_records = [_axis_records(frame.columns, terminal) for frame, terminal in column_blocks]
    order = ("Region", "Sector", "Activity", "Commodity", "Factor of production", "Satellite account", "Consumption category")
    row_names = [name for name in order if any(name in row for records in row_records for row in records)]
    col_names = [name for name in order if any(name in row for records in col_records for row in records)]
    index = pd.MultiIndex.from_tuples(
        [tuple(record.get(name) for name in row_names) for records in row_records for record in records],
        names=row_names,
    )
    columns = pd.MultiIndex.from_tuples(
        [tuple(record.get(name) for name in col_names) for records in col_records for record in records],
        names=col_names,
    )
    output = pd.DataFrame(0.0, index=index, columns=columns)
    def values(frame):
        if len(frame.columns) and all(isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes):
            frame = frame.sparse.to_dense()
        return frame.to_numpy()

    for frame, row_terminal, col_terminal in (
        (Z, "Sector", "Sector"), (Y, "Sector", "Consumption category"),
        (V, "Factor of production", "Sector"),
        (VY, "Factor of production", "Consumption category"),
        (E, "Satellite account", "Sector"),
        (EY, "Satellite account", "Consumption category"),
    ):
        source_rows = pd.MultiIndex.from_tuples(
            [tuple(record.get(name) for name in row_names) for record in _axis_records(frame.index, row_terminal)],
            names=row_names,
        )
        source_cols = pd.MultiIndex.from_tuples(
            [tuple(record.get(name) for name in col_names) for record in _axis_records(frame.columns, col_terminal)],
            names=col_names,
        )
        rows, cols = index.get_indexer(source_rows), columns.get_indexer(source_cols)
        if (rows < 0).any() or (cols < 0).any():
            raise ValueError("Database display blocks have inconsistent axis labels.")
        output.iloc[rows, cols] = values(frame)
    return output


def build_database_frame(database, scenario: str = "baseline") -> pd.DataFrame:
    """Return the historical single-sheet dataframe view of the database."""

    data = database.query(
        matrices=[_ENUM.Z, _ENUM.Y, _ENUM.V, _ENUM.E, _ENUM.EY, _ENUM.VY],
        scenarios=scenario,
    )

    if (any(isinstance(data[name].index, pd.MultiIndex) for name in (_ENUM.V, _ENUM.E))
            or data[_ENUM.Z].index.nlevels != 3 or data[_ENUM.Y].columns.nlevels != 3):
        return _semantic_database_frame(data)

    # A display operation must not replace the model's live matrix indexes.
    data = {name: frame.copy() for name, frame in data.items()}
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
