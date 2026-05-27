# -*- coding: utf-8 -*-
"""Aggregation helpers used by the public ``Database.aggregate`` API."""

from __future__ import annotations

import copy
import logging

import numpy as np
import pandas as pd
from scipy import sparse

from mario.compute.primitives import calc_E, calc_V, calc_X, calc_Z
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.sut_formulas import (
    build_sut_Ea_from_ea_Xa,
    build_sut_Ec_from_ec_Xc,
    build_sut_S_from_s_Xc,
    build_sut_U_from_u_Xa,
    build_sut_Va_from_va_Xa,
    build_sut_Vc_from_vc_Xc,
    build_sut_Xa_from_S_Ya,
    build_sut_Xc_from_U_Yc,
)
from mario.compute.views import (
    extract_Ea_from_E,
    extract_Ec_from_E,
    extract_S_from_Z,
    extract_U_from_Z,
    extract_Va_from_V,
    extract_Vc_from_V,
    extract_Xa_from_X,
    extract_Xc_from_X,
    extract_Ya_from_Y,
    extract_Yc_from_Y,
    extract_ea_from_e,
    extract_ec_from_e,
    extract_s_from_z,
    extract_u_from_z,
    extract_va_from_v,
    extract_vc_from_v,
)
from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _ENUM, _MASTER_INDEX
from mario.utils import delete_duplicates

logger = logging.getLogger(__name__)

_LEGACY_AXIS_NAMES = (_MASTER_INDEX["r"], "Level", "Item")
_SUT_SPLIT_FLOW_BLOCKS = ("U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", _ENUM.EY, _ENUM.VY)
_SUT_EXTENSION_BLOCKS = {"Ea", "Ec", _ENUM.EY}
_SUT_SPLIT_FROM_UNIFIED = {
    "U": (_ENUM.Z, extract_U_from_Z),
    "S": (_ENUM.Z, extract_S_from_Z),
    "Ya": (_ENUM.Y, extract_Ya_from_Y),
    "Yc": (_ENUM.Y, extract_Yc_from_Y),
    "Va": (_ENUM.V, extract_Va_from_V),
    "Vc": (_ENUM.V, extract_Vc_from_V),
    "Ea": (_ENUM.E, extract_Ea_from_E),
    "Ec": (_ENUM.E, extract_Ec_from_E),
    "Xa": (_ENUM.X, extract_Xa_from_X),
    "Xc": (_ENUM.X, extract_Xc_from_X),
    "u": (_ENUM.z, extract_u_from_z),
    "s": (_ENUM.z, extract_s_from_z),
    "va": (_ENUM.v, extract_va_from_v),
    "vc": (_ENUM.v, extract_vc_from_v),
    "ea": (_ENUM.e, extract_ea_from_e),
    "ec": (_ENUM.e, extract_ec_from_e),
}


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


def _factorize_aggregated_labels(labels):
    """Return integer aggregation codes and unique labels preserving first-seen order."""
    codes, uniques = labels.factorize(sort=False)
    if isinstance(uniques, pd.MultiIndex):
        return codes.astype(np.intp, copy=False), uniques.set_names(labels.names)
    return codes.astype(np.intp, copy=False), uniques.rename(labels.name)


def _build_axis_aggregator(codes: np.ndarray, source_size: int, *, axis: int):
    """Build a sparse aggregation matrix for one block axis."""
    data = np.ones(len(codes), dtype=np.int8)
    positions = np.arange(source_size, dtype=np.intp)
    target_size = int(codes.max()) + 1 if len(codes) else 0
    if axis == 0:
        return sparse.csr_matrix(
            (data, (codes, positions)),
            shape=(target_size, source_size),
        )
    return sparse.csr_matrix(
        (data, (positions, codes)),
        shape=(source_size, target_size),
    )


def _is_zero_fill_sparse_frame(frame: pd.DataFrame) -> bool:
    """Return ``True`` when every column uses a zero-fill SparseDtype."""
    if frame.shape[1] == 0:
        return False
    return all(
        isinstance(dtype, pd.SparseDtype) and dtype.fill_value == 0
        for dtype in frame.dtypes
    )


def _aggregate_frame_values(frame: pd.DataFrame, row_labels, col_labels) -> pd.DataFrame:
    """Aggregate one numeric block with sparse mapping matrices instead of pandas groupby."""
    row_codes, unique_rows = _factorize_aggregated_labels(row_labels)
    col_codes, unique_cols = _factorize_aggregated_labels(col_labels)

    if frame.shape[0] == 0 or frame.shape[1] == 0:
        return pd.DataFrame(index=unique_rows, columns=unique_cols, dtype=float)

    row_aggregator = _build_axis_aggregator(row_codes, frame.shape[0], axis=0)
    col_aggregator = _build_axis_aggregator(col_codes, frame.shape[1], axis=1)

    if _is_zero_fill_sparse_frame(frame):
        values = frame.sparse.to_coo().tocsr()
        aggregated = (row_aggregator @ values @ col_aggregator).tocsr()
        return pd.DataFrame.sparse.from_spmatrix(
            aggregated,
            index=unique_rows,
            columns=unique_cols,
        )

    values = frame.to_numpy(copy=False)
    if values.dtype == object:
        values = frame.to_numpy(dtype=float, copy=True)
    aggregated = row_aggregator @ values
    aggregated = aggregated @ col_aggregator
    return pd.DataFrame(aggregated, index=unique_rows, columns=unique_cols)


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


def _scenario_block(
    instance,
    values,
    scenario: str,
    matrix_name: str,
    *,
    copy_block: bool = False,
) -> pd.DataFrame:
    """Return one scenario block either from the iterator payload or by resolving it."""
    block = None
    if matrix_name in values:
        block = values[matrix_name]
    else:
        block = instance.query([matrix_name], scenarios=[scenario])
    return copy.deepcopy(block) if copy_block else block


def _extract_sut_split_from_unified(matrix_name: str, source_name: str, source_block: pd.DataFrame):
    """Extract one split SUT block from a materialized unified source block."""
    _, extractor = _SUT_SPLIT_FROM_UNIFIED[matrix_name]
    ordering = SUTUnifiedOrderingPolicy.from_blocks(**{source_name: source_block})
    return extractor(source_block, ordering)


def _scenario_sut_block(
    instance,
    values,
    scenario: str,
    matrix_name: str,
    *,
    copy_block: bool = False,
) -> pd.DataFrame:
    """Return one SUT block, preferring extraction from unified sources when present."""
    source = _SUT_SPLIT_FROM_UNIFIED.get(matrix_name)
    if source is not None:
        source_name, _ = source
        if source_name in values:
            log_time(
                logger,
                (
                    f"Aggregation: scenario `{scenario}` extracting split block "
                    f"`{matrix_name}` from materialized unified `{source_name}`."
                ),
                "debug",
            )
            block = _extract_sut_split_from_unified(
                matrix_name,
                source_name,
                values[source_name],
            )
            return copy.deepcopy(block) if copy_block else block

    return _scenario_block(
        instance,
        values,
        scenario,
        matrix_name,
        copy_block=copy_block,
    )


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

        flow_block = _scenario_block(
            instance,
            values,
            scenario,
            flow_name,
            copy_block=True,
        )
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


def _aggregate_block(instance, matrix_name: str, frame: pd.DataFrame, agg_indeces: dict, drop) -> pd.DataFrame:
    """Aggregate one block by relabeling both axes and summing duplicates."""
    row_labels = _aggregate_axis(
        instance,
        matrix_name,
        frame.index,
        side="index",
        agg_indeces=agg_indeces,
    )
    col_labels = _aggregate_axis(
        instance,
        matrix_name,
        frame.columns,
        side="columns",
        agg_indeces=agg_indeces,
    )
    aggregated = _aggregate_frame_values(frame, row_labels, col_labels)

    if matrix_name in _SUT_EXTENSION_BLOCKS or matrix_name in {_ENUM.E, _ENUM.EY}:
        before = aggregated.shape[0]
        aggregated = _drop_extension_rows(instance, aggregated, matrix_name, drop)
        if aggregated.shape[0] != before:
            log_time(
                logger,
                "{} removed from {}.".format(drop, _MASTER_INDEX["k"]),
                "info",
            )

    return aggregated


def _aggregate_labels(instance, matrix_name: str, labels, *, side: str, agg_indeces: dict):
    """Aggregate one index-like label set and drop duplicates while preserving order."""
    if len(labels) == 0:
        return labels

    aggregated = _aggregate_axis(
        instance,
        matrix_name,
        labels,
        side=side,
        agg_indeces=agg_indeces,
    )
    return aggregated.unique() if hasattr(aggregated, "unique") else aggregated


def _resolve_sut_output_blocks(instance, values, scenario: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return split activity and commodity outputs without building unified SUT views."""
    try:
        Xa = _scenario_sut_block(instance, values, scenario, "Xa")
    except Exception:
        Xa = build_sut_Xa_from_S_Ya(
            _scenario_sut_block(instance, values, scenario, "S"),
            _scenario_sut_block(instance, values, scenario, "Ya"),
        )

    try:
        Xc = _scenario_sut_block(instance, values, scenario, "Xc")
    except Exception:
        Xc = build_sut_Xc_from_U_Yc(
            _scenario_sut_block(instance, values, scenario, "U"),
            _scenario_sut_block(instance, values, scenario, "Yc"),
        )

    return Xa, Xc


def _build_zero_output_sut_flow_overrides(instance, values, scenario: str, epsilon: float | None):
    """Preserve SUT split-flow columns for zero-output items using split coefficients."""
    if epsilon is None:
        return {}, pd.Index([]), pd.Index([])

    if epsilon <= 0:
        raise WrongInput("zero_output_epsilon must be greater than zero.")

    Xa, Xc = _resolve_sut_output_blocks(instance, values, scenario)
    zero_activities = _zero_output_labels(Xa)
    zero_commodities = _zero_output_labels(Xc)
    if len(zero_activities) == 0 and len(zero_commodities) == 0:
        return {}, pd.Index([]), pd.Index([])

    coefficient_blocks = {}
    preserved_activities = pd.Index([])
    preserved_commodities = pd.Index([])
    for coefficient in ("u", "va", "ea"):
        try:
            block = _scenario_sut_block(instance, values, scenario, coefficient)
        except Exception:
            continue
        coefficient_blocks[coefficient] = block
        preserved_activities = preserved_activities.union(
            _nonzero_coefficient_columns(block, zero_activities)
        )

    for coefficient in ("s", "vc", "ec"):
        try:
            block = _scenario_sut_block(instance, values, scenario, coefficient)
        except Exception:
            continue
        coefficient_blocks[coefficient] = block
        preserved_commodities = preserved_commodities.union(
            _nonzero_coefficient_columns(block, zero_commodities)
        )

    if isinstance(preserved_activities, pd.MultiIndex):
        preserved_activities = preserved_activities.set_names(Xa.index.names)
    if isinstance(preserved_commodities, pd.MultiIndex):
        preserved_commodities = preserved_commodities.set_names(Xc.index.names)

    if len(preserved_activities) == 0 and len(preserved_commodities) == 0:
        return {}, pd.Index([]), pd.Index([])

    adjusted_Xa = Xa.copy()
    adjusted_Xc = Xc.copy()
    if len(preserved_activities):
        adjusted_Xa.loc[preserved_activities, :] = float(epsilon)
    if len(preserved_commodities):
        adjusted_Xc.loc[preserved_commodities, :] = float(epsilon)

    overrides = {}
    activity_rebuilders = (
        ("U", "u", build_sut_U_from_u_Xa, adjusted_Xa),
        ("Va", "va", build_sut_Va_from_va_Xa, adjusted_Xa),
        ("Ea", "ea", build_sut_Ea_from_ea_Xa, adjusted_Xa),
    )
    for flow_name, coefficient_name, builder, output_block in activity_rebuilders:
        coefficient_block = coefficient_blocks.get(coefficient_name)
        if coefficient_block is None:
            continue

        flow_block = _scenario_sut_block(
            instance,
            values,
            scenario,
            flow_name,
            copy_block=True,
        )
        rebuilt = builder(coefficient_block, output_block)
        columns = flow_block.columns.intersection(preserved_activities)
        if len(columns):
            flow_block.loc[:, columns] = rebuilt.loc[:, columns]
        overrides[flow_name] = flow_block

    tech_assumption = getattr(instance, "tech_assumption", None)
    commodity_rebuilders = (
        (
            "S",
            "s",
            lambda coefficient_block, output_block: build_sut_S_from_s_Xc(
                coefficient_block,
                output_block,
                Xa=adjusted_Xa,
                tech_assumption=tech_assumption,
            ),
        ),
        ("Vc", "vc", build_sut_Vc_from_vc_Xc),
        ("Ec", "ec", build_sut_Ec_from_ec_Xc),
    )
    for flow_name, coefficient_name, builder in commodity_rebuilders:
        coefficient_block = coefficient_blocks.get(coefficient_name)
        if coefficient_block is None:
            continue

        flow_block = _scenario_sut_block(
            instance,
            values,
            scenario,
            flow_name,
            copy_block=True,
        )
        rebuilt = builder(coefficient_block, adjusted_Xc)
        columns = flow_block.columns.intersection(preserved_commodities)
        if len(columns):
            flow_block.loc[:, columns] = rebuilt.loc[:, columns]
        overrides[flow_name] = flow_block

    return overrides, preserved_activities, preserved_commodities


def _clear_zero_output_sut_flow_overrides(matrices: dict[str, pd.DataFrame]) -> pd.Index:
    """Clear split-flow columns that still aggregate to zero output in SUT scenarios."""
    Xa = matrices.get("Xa")
    Xc = matrices.get("Xc")
    zero_activities = _zero_output_labels(Xa) if Xa is not None else pd.Index([])
    zero_commodities = _zero_output_labels(Xc) if Xc is not None else pd.Index([])

    cleared = pd.Index([])
    activity_blocks = ("U", "Va", "Ea")
    for matrix_name in activity_blocks:
        block = matrices.get(matrix_name)
        if block is None:
            continue

        columns = block.columns.intersection(zero_activities)
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

    commodity_blocks = ("S", "Vc", "Ec")
    for matrix_name in commodity_blocks:
        block = matrices.get(matrix_name)
        if block is None:
            continue

        columns = block.columns.intersection(zero_commodities)
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

    if Xa is not None and len(zero_activities):
        Xa = Xa.copy()
        Xa.loc[cleared.intersection(zero_activities), :] = 0.0
        matrices["Xa"] = Xa

    if Xc is not None and len(zero_commodities):
        Xc = Xc.copy()
        Xc.loc[cleared.intersection(zero_commodities), :] = 0.0
        matrices["Xc"] = Xc

    return cleared


def _aggregate_sut_split_flows(instance, drop, agg_indeces: dict, *, zero_output_epsilon: float | None = None):
    """Aggregate SUT scenarios directly on split-native flow blocks."""
    matrices = {}

    for scenario, values in instance:
        matrices[scenario] = {}
        available_unified_sources = sorted(
            {
                source_name
                for source_name, _ in _SUT_SPLIT_FROM_UNIFIED.values()
                if source_name in values
            }
        )
        if available_unified_sources:
            log_time(
                logger,
                (
                    f"Aggregation: scenario `{scenario}` reusing materialized unified "
                    f"SUT sources {available_unified_sources} to extract split blocks when needed."
                ),
                "debug",
            )
        flow_overrides, preserved_activities, preserved_commodities = _build_zero_output_sut_flow_overrides(
            instance,
            values,
            scenario,
            zero_output_epsilon,
        )

        for matrix_name in _SUT_SPLIT_FLOW_BLOCKS:
            block = flow_overrides.get(matrix_name)
            if block is None:
                block = _scenario_sut_block(instance, values, scenario, matrix_name)
            matrices[scenario][matrix_name] = _aggregate_block(
                instance,
                matrix_name,
                block,
                agg_indeces,
                drop,
            )

        matrices[scenario]["Xa"] = build_sut_Xa_from_S_Ya(
            matrices[scenario]["S"],
            matrices[scenario]["Ya"],
        )
        matrices[scenario]["Xc"] = build_sut_Xc_from_U_Yc(
            matrices[scenario]["U"],
            matrices[scenario]["Yc"],
        )
        if zero_output_epsilon is not None:
            aggregated_preserved_activities = _aggregate_labels(
                instance,
                "Xa",
                preserved_activities,
                side="index",
                agg_indeces=agg_indeces,
            )
            aggregated_preserved_commodities = _aggregate_labels(
                instance,
                "Xc",
                preserved_commodities,
                side="index",
                agg_indeces=agg_indeces,
            )
            if len(aggregated_preserved_activities):
                matrices[scenario]["Xa"] = matrices[scenario]["Xa"].copy()
                matrices[scenario]["Xa"].loc[aggregated_preserved_activities, :] = float(
                    zero_output_epsilon
                )
            if len(aggregated_preserved_commodities):
                matrices[scenario]["Xc"] = matrices[scenario]["Xc"].copy()
                matrices[scenario]["Xc"].loc[aggregated_preserved_commodities, :] = float(
                    zero_output_epsilon
                )

        cleared_outputs = pd.Index([])
        if zero_output_epsilon is not None:
            cleared_outputs = _clear_zero_output_sut_flow_overrides(matrices[scenario])

        preserved_labels = preserved_activities.union(preserved_commodities)
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

        log_time(
            logger,
            (
                f"Aggregation: scenario `{scenario}` aggregated "
                f"{len(_SUT_SPLIT_FLOW_BLOCKS)} split SUT flow block(s) directly."
            ),
            "info",
        )
        log_time(logger, f"Aggregation: scenario: `{scenario}` aggregated.")

    return matrices


def _aggregator(instance, drop, *, zero_output_epsilon: float | None = None):
    """Aggregate all scenarios of a database using prepared mapping tables."""
    agg_indeces = instance.get_index("all", "aggregated")
    if instance.table_type == "SUT":
        log_time(logger, "Aggregation: using split-native SUT aggregation path.", "info")
        units = unit_aggregation_check(instance, drop)
        return (
            _aggregate_sut_split_flows(
                instance,
                drop,
                agg_indeces,
                zero_output_epsilon=zero_output_epsilon,
            ),
            units,
        )

    instance.query(matrices=[_ENUM.Y, _ENUM.V, _ENUM.E])
    units = unit_aggregation_check(instance, drop)

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
            item = (
                flow_overrides[matrix]
                if matrix in flow_overrides
                else _scenario_block(instance, values, scenario, matrix)
            )

            matrices[scenario][matrix] = _aggregate_block(
                instance,
                matrix,
                item,
                agg_indeces,
                drop,
            )

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
