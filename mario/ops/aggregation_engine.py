# -*- coding: utf-8 -*-
"""Aggregation helpers used by the public ``Database.aggregate`` API."""

from __future__ import annotations

import copy
import logging
from copy import deepcopy

import pandas as pd

from mario.compute.primitives import calc_X
from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _ENUM, _MASTER_INDEX
from mario.utils import delete_duplicates

logger = logging.getLogger(__name__)

_LEGACY_AXIS_NAMES = (_MASTER_INDEX["r"], "Level", "Item")


def _aggregation_mapping(mapping):
    """Normalize one stored aggregation table to a plain source->target dict."""
    if mapping is None:
        return None
    if isinstance(mapping, pd.DataFrame):
        if mapping.shape[1] > 1:
            mapping = mapping.iloc[:, [0]]
        series = mapping.iloc[:, 0]
    else:
        series = mapping
    return series.to_dict()


def _map_values(values, mapping):
    """Apply an optional aggregation mapping while preserving original labels."""
    if mapping is None:
        return list(values)
    return [mapping.get(value, value) for value in values]


def _axis_semantic_names(instance, matrix_name: str, labels, side: str):
    """Return semantic names for one matrix axis or ``None`` for legacy 3-level axes."""
    if isinstance(labels, pd.MultiIndex):
        names = tuple(labels.names)
        if names == _LEGACY_AXIS_NAMES or "Level" in names or "Item" in names:
            return None
        return names

    if getattr(labels, "name", None) not in {None, "Item"}:
        return (labels.name,)

    spec = instance.get_block_spec(matrix_name)
    axes = spec.row_axes if side == "index" else spec.col_axes
    return tuple(axis.id for axis in axes)


def _aggregate_legacy_axis(labels: pd.MultiIndex, agg_indeces: dict) -> pd.MultiIndex:
    """Aggregate one historical ``Region/Level/Item`` axis."""
    regions = _map_values(
        labels.get_level_values(0),
        _aggregation_mapping(agg_indeces.get(_MASTER_INDEX["r"])),
    )
    levels = list(labels.get_level_values(1))

    items = []
    for level_label, value in zip(levels, labels.get_level_values(2)):
        level_mapping = _aggregation_mapping(agg_indeces.get(level_label))
        items.append(level_mapping.get(value, value) if level_mapping else value)

    return pd.MultiIndex.from_arrays(
        [regions, levels, items],
        names=list(labels.names),
    )


def _aggregate_semantic_axis(labels, semantic_names: tuple[str, ...], agg_indeces: dict):
    """Aggregate one axis already expressed with semantic MARIO set names."""
    if isinstance(labels, pd.MultiIndex):
        arrays = []
        for position, level_name in enumerate(semantic_names):
            arrays.append(
                _map_values(
                    labels.get_level_values(position),
                    _aggregation_mapping(agg_indeces.get(level_name)),
                )
            )
        return pd.MultiIndex.from_arrays(arrays, names=list(semantic_names))

    return pd.Index(
        _map_values(
            labels.tolist(),
            _aggregation_mapping(agg_indeces.get(semantic_names[0])),
        ),
        name=semantic_names[0],
    )


def _aggregate_axis(instance, matrix_name: str, labels, *, side: str, agg_indeces: dict):
    """Return one aggregated axis for one matrix block."""
    semantic_names = _axis_semantic_names(instance, matrix_name, labels, side)
    if semantic_names is None:
        return _aggregate_legacy_axis(labels, agg_indeces)
    return _aggregate_semantic_axis(labels, semantic_names, agg_indeces)


def _group_axis(frame: pd.DataFrame, *, axis: int) -> pd.DataFrame:
    """Group one dataframe axis after relabeling aggregation targets."""
    labels = frame.index if axis == 0 else frame.columns
    if isinstance(labels, pd.MultiIndex):
        return frame.groupby(axis=axis, level=list(range(labels.nlevels)), sort=False).sum()
    return frame.groupby(axis=axis, level=[0], sort=False).sum()


def _drop_extension_rows(instance, frame: pd.DataFrame, matrix_name: str, drop):
    """Drop selected satellite-account labels from ``E``-family rows."""
    if not drop:
        return frame

    semantic_names = _axis_semantic_names(instance, matrix_name, frame.index, "index")
    if semantic_names is None:
        return frame.drop(drop, axis=0, errors="ignore")

    if _MASTER_INDEX["k"] not in semantic_names:
        return frame

    position = semantic_names.index(_MASTER_INDEX["k"])
    if isinstance(frame.index, pd.MultiIndex):
        mask = ~frame.index.get_level_values(position).isin(drop)
        return frame.loc[mask, :]
    return frame.drop(drop, axis=0, errors="ignore")


def _aggregator(instance, drop):
    """Aggregate all scenarios of a database using prepared mapping tables."""
    instance.query(matrices=[_ENUM.Y, _ENUM.V, _ENUM.E])
    units = unit_aggregation_check(instance, drop)
    agg_indeces = instance.get_index("all", "aggregated")

    matrices = {}

    for scenario, values in instance:
        matrices[scenario] = {}

        for matrix in [_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.EY, _ENUM.VY, _ENUM.Y]:
            item = deepcopy(
                values[matrix]
                if matrix in values
                else instance.query([matrix], scenarios=[scenario])
            )

            item.index = _aggregate_axis(
                instance,
                matrix,
                item.index,
                side="index",
                agg_indeces=agg_indeces,
            )
            item = _group_axis(item, axis=0)

            if matrix in [_ENUM.E, _ENUM.EY] and drop is not None:
                before = item.shape[0]
                item = _drop_extension_rows(instance, item, matrix, drop)
                if item.shape[0] != before:
                    log_time(
                        logger,
                        "{} removed from {}.".format(drop, _MASTER_INDEX["k"]),
                        "info",
                    )

            item.columns = _aggregate_axis(
                instance,
                matrix,
                item.columns,
                side="columns",
                agg_indeces=agg_indeces,
            )
            item = _group_axis(item, axis=1)

            matrices[scenario][matrix] = item

        matrices[scenario][_ENUM.X] = calc_X(
            matrices[scenario][_ENUM.Z], matrices[scenario][_ENUM.Y]
        )

        log_time(logger, f"Aggregation: scenario: `{scenario}` aggregated.")

    return matrices, units


def unit_aggregation_check(instance, drop):
    """
    This function checks if two items with diffrerent units are not being aggregated
    """

    if isinstance(drop, str):
        drop = [drop]

    units = copy.deepcopy(instance.units)
    new_units = {}

    indeces = copy.deepcopy(instance.get_index("all", "aggregated"))
    for item in [*units]:
        aggregation = indeces.get(item)
        if aggregation is not None:
            aggregation.reset_index(level=0, inplace=True)
            aggregation = aggregation.set_index("Aggregation")

            aggregation.columns = ["values"]

            aggregated = aggregation.index.unique()

            _new_units = {}

            for index in aggregated:
                if index in drop:
                    continue

                match = list(aggregation.loc[index, :].values.flatten())

                take_units = delete_duplicates(
                    units[item].loc[match, "unit"].values.flatten()
                )

                if len(take_units) > 1:
                    raise WrongInput(
                        "Aggregation of items with different units are not allowed for {}.(check aggregation of {})".format(
                            item, index
                        )
                    )
                _new_units[index] = take_units[0]

            _new_units = pd.DataFrame.from_dict(
                _new_units, orient="index", columns=["unit"]
            )

            new_units[item] = _new_units

        else:
            new_units[item] = units[item]

    return new_units
