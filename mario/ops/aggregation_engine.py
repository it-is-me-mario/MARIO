# -*- coding: utf-8 -*-
"""Aggregation helpers used by the public ``Database.aggregate`` API."""

from __future__ import annotations

import copy
import logging
from copy import deepcopy

import pandas as pd

from mario.compute.primitives import calc_E, calc_V, calc_X, calc_Z
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
    aggregated = _aggregate_semantic_axis(labels, semantic_names, agg_indeces)
    if not isinstance(labels, pd.MultiIndex) and getattr(labels, "name", None) in {None, "Item"}:
        aggregated = aggregated.rename(labels.name)
    return aggregated


def _group_axis(frame: pd.DataFrame, *, axis: int) -> pd.DataFrame:
    """Group one dataframe axis after relabeling aggregation targets."""
    labels = frame.index if axis == 0 else frame.columns
    levels = list(range(labels.nlevels)) if isinstance(labels, pd.MultiIndex) else [0]
    if isinstance(labels, pd.MultiIndex):
        levels = list(range(labels.nlevels))
    if axis == 0:
        return frame.groupby(level=levels, sort=False).sum()
    return frame.T.groupby(level=levels, sort=False).sum().T


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


def _scenario_block(instance, values, scenario: str, matrix_name: str) -> pd.DataFrame:
    """Return one scenario block either from the iterator payload or by resolving it."""
    if matrix_name in values:
        return deepcopy(values[matrix_name])
    return deepcopy(instance.query([matrix_name], scenarios=[scenario]))


def _single_output_series(block: pd.DataFrame | pd.Series) -> pd.Series:
    """Return the scalar production vector behind one ``X``-like block."""
    if isinstance(block, pd.Series):
        return block.astype(float).copy()

    if isinstance(block, pd.DataFrame):
        if block.shape[1] != 1:
            raise ValueError("Expected a single-column output block.")
        return block.iloc[:, 0].astype(float).copy()

    raise TypeError("Expected a pandas Series or single-column DataFrame.")


def _zero_output_labels(X: pd.DataFrame | pd.Series) -> pd.Index:
    """Return labels whose output is exactly zero."""
    series = _single_output_series(X)
    return series.index[series == 0]


def _nonzero_coefficient_columns(block: pd.DataFrame, labels: pd.Index) -> pd.Index:
    """Return zero-output labels that still expose non-zero stored coefficients."""
    if len(labels) == 0:
        return labels

    columns = block.columns.intersection(labels)
    if len(columns) == 0:
        return columns

    mask = (block.loc[:, columns].to_numpy(dtype=float) != 0).any(axis=0)
    return columns[mask]


def _build_zero_output_flow_overrides(instance, values, scenario: str, epsilon: float | None):
    """Re-materialize tiny flow columns for zero-output items that still carry coefficients."""
    if epsilon is None:
        return {}, pd.Index([])

    if epsilon <= 0:
        raise WrongInput("zero_output_epsilon must be greater than zero.")

    X = _scenario_block(instance, values, scenario, _ENUM.X)
    zero_outputs = _zero_output_labels(X)
    if len(zero_outputs) == 0:
        return {}, pd.Index([])

    coefficient_blocks = {}
    preserved_labels = pd.Index([])
    for coefficient in (_ENUM.z, _ENUM.v, _ENUM.e):
        try:
            block = _scenario_block(instance, values, scenario, coefficient)
        except Exception:
            continue
        coefficient_blocks[coefficient] = block
        preserved_labels = preserved_labels.union(
            _nonzero_coefficient_columns(block, zero_outputs)
        )

    if len(preserved_labels) == 0:
        return {}, pd.Index([])

    adjusted_X = X.copy()
    adjusted_X.loc[preserved_labels, :] = float(epsilon)

    overrides = {}
    for flow_name, coefficient_name, calculator in (
        (_ENUM.Z, _ENUM.z, calc_Z),
        (_ENUM.V, _ENUM.v, calc_V),
        (_ENUM.E, _ENUM.e, calc_E),
    ):
        coefficient_block = coefficient_blocks.get(coefficient_name)
        if coefficient_block is None:
            continue

        flow_block = _scenario_block(instance, values, scenario, flow_name)
        rebuilt = calculator(coefficient_block, adjusted_X)
        columns = flow_block.columns.intersection(preserved_labels)
        if len(columns):
            flow_block.loc[:, columns] = rebuilt.loc[:, columns]
        overrides[flow_name] = flow_block

    return overrides, preserved_labels


def _clear_zero_output_flow_overrides(matrices: dict[str, pd.DataFrame]) -> pd.Index:
    """Clear reconstructed flow columns that still aggregate to zero output."""
    X = matrices.get(_ENUM.X)
    if X is None:
        return pd.Index([])

    zero_outputs = _zero_output_labels(X)
    if len(zero_outputs) == 0:
        return zero_outputs

    cleared = pd.Index([])
    for matrix_name in (_ENUM.Z, _ENUM.V, _ENUM.E):
        block = matrices.get(matrix_name)
        if block is None:
            continue

        columns = block.columns.intersection(zero_outputs)
        if len(columns) == 0:
            continue

        mask = (block.loc[:, columns].to_numpy(dtype=float) != 0).any(axis=0)
        impacted = columns[mask]
        if len(impacted) == 0:
            continue

        block = block.copy()
        block.loc[:, impacted] = 0.0
        matrices[matrix_name] = block
        cleared = cleared.union(impacted)

    if len(cleared) == 0:
        return cleared

    X = X.copy()
    X.loc[cleared, :] = 0.0
    matrices[_ENUM.X] = X
    return cleared


def _aggregator(instance, drop, *, zero_output_epsilon: float | None = None):
    """Aggregate all scenarios of a database using prepared mapping tables."""
    instance.query(matrices=[_ENUM.Y, _ENUM.V, _ENUM.E])
    units = unit_aggregation_check(instance, drop)
    agg_indeces = instance.get_index("all", "aggregated")

    matrices = {}

    for scenario, values in instance:
        matrices[scenario] = {}
        flow_overrides, preserved_labels = _build_zero_output_flow_overrides(
            instance,
            values,
            scenario,
            zero_output_epsilon,
        )

        for matrix in [_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.EY, _ENUM.VY, _ENUM.Y]:
            item = deepcopy(
                flow_overrides[matrix]
                if matrix in flow_overrides
                else _scenario_block(instance, values, scenario, matrix)
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
        cleared_outputs = pd.Index([])
        if zero_output_epsilon is not None:
            cleared_outputs = _clear_zero_output_flow_overrides(matrices[scenario])

        if len(preserved_labels):
            log_time(
                logger,
                (
                    f"Aggregation: scenario `{scenario}` preserved coefficients for "
                    f"{len(preserved_labels)} zero-output item(s) using "
                    f"zero_output_epsilon={zero_output_epsilon}."
                ),
                "warning",
            )
        if len(cleared_outputs):
            log_time(
                logger,
                (
                    f"Aggregation: scenario `{scenario}` cleared reconstructed flow "
                    f"columns for {len(cleared_outputs)} zero-output item(s) after "
                    f"aggregation using zero_output_epsilon={zero_output_epsilon}."
                ),
                "warning",
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

                match = list(aggregation.loc[index, :].to_numpy().flatten())

                take_units = delete_duplicates(
                    units[item].loc[match, "unit"].to_numpy().flatten()
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
