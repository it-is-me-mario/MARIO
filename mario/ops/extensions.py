"""Select satellite accounts without resolving or copying economic blocks."""

from collections.abc import Mapping
import copy

import pandas as pd

from mario.compute.operators import get_registered_operator
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.settings.settings import canonical_matrix_name


SATELLITE = _MASTER_INDEX["k"]


def _satellite_positions(instance, name, labels, side):
    """Locate satellite levels in native, structured or custom block axes."""
    named = [i for i, label in enumerate(labels.names) if label == SATELLITE]
    if named:
        return named
    try:
        spec = instance.get_block_spec(name)
    except WrongInput:
        return []
    axes = spec.row_axes if side == "index" else spec.col_axes
    positions = [i for i, axis in enumerate(axes) if axis.base in {"k", SATELLITE}]
    if positions and len(axes) != labels.nlevels:
        raise WrongInput(f"Cannot locate the Satellite account level in {name!r} {side}.")
    return positions


def _filter_axis(frame, positions, selected, *, side):
    labels = frame.index if side == "index" else frame.columns
    mask = pd.Series(True, index=range(len(labels))).to_numpy()
    for position in positions:
        mask &= labels.get_level_values(position).isin(selected)
    return frame.loc[mask, :] if side == "index" else frame.loc[:, mask]


def _filter_members(members, selected):
    if isinstance(members, Mapping):
        return {key: _filter_members(values, selected) for key, values in members.items()}
    return [label for label in members if label in selected]


def keep_extensions(instance, extensions, *, inplace):
    """Apply a satellite whitelist atomically across all stored scenarios."""
    if not isinstance(inplace, bool):
        raise WrongInput("inplace must be True or False.")
    if isinstance(extensions, str):
        extensions = [extensions]
    if isinstance(extensions, Mapping):
        raise WrongInput("extensions must be a label or an iterable of satellite labels.")
    try:
        requested = list(extensions)
        requested_set = set(requested)
    except TypeError as exc:
        raise WrongInput("extensions must be a label or an iterable of satellite labels.") from exc
    if len(requested) != len(requested_set):
        raise WrongInput("Repeated satellite accounts are not allowed.")
    available = instance.get_index(SATELLITE)
    missing = [label for label in requested if label not in available]
    if missing:
        raise WrongInput(f"Unknown Satellite account labels: {missing!r}.")
    selected = [label for label in available if label in requested_set]

    target = instance if inplace else instance.copy()
    if len(selected) == len(available):
        return None if inplace else target

    matrices = {}
    for scenario, blocks in target.matrices.items():
        updated = dict(blocks)
        affected = set()
        for name, frame in blocks.items():
            if not isinstance(frame, pd.DataFrame):
                # Never silently leave a known extension block unfiltered.
                try:
                    spec = target.get_block_spec(name)
                except WrongInput:
                    continue
                if any(axis.base in {"k", SATELLITE} for axis in spec.row_axes + spec.col_axes):
                    raise WrongInput(f"Satellite block {name!r} must be a pandas DataFrame.")
                continue
            rows = _satellite_positions(target, name, frame.index, "index")
            cols = _satellite_positions(target, name, frame.columns, "columns")
            if rows or cols:
                filtered = (
                    _filter_axis(frame, rows, requested_set, side="index") if rows else frame
                )
                if cols:
                    filtered = _filter_axis(filtered, cols, requested_set, side="columns")
                updated[name] = filtered.copy()
                affected.add(canonical_matrix_name(name))

        # A custom result may have summed over the satellite axis. Slicing it
        # would retain a stale total, so invalidate dependent operators instead.
        pending = set(target.list_custom_operators())
        while pending:
            invalid = {
                name
                for name in pending
                if name in affected
                or any(
                    canonical_matrix_name(source) in affected
                    for source in get_registered_operator(target, name).inputs
                )
            }
            if not invalid:
                break
            for name in invalid:
                updated.pop(name, None)
                affected.add(canonical_matrix_name(name))
            pending -= invalid
        matrices[scenario] = updated

    # Prepare metadata before replacing any part of an in-place database.
    indexes = copy.deepcopy(target._indeces["k"])
    indexes["main"] = selected
    for variant, values in list(indexes.items()):
        if variant == "main":
            continue
        if isinstance(values, (pd.DataFrame, pd.Series)):
            indexes[variant] = values.loc[values.index.isin(requested_set)].copy()
        elif isinstance(values, pd.Index):
            indexes[variant] = values[values.isin(requested_set)]
        elif isinstance(values, Mapping):
            indexes[variant] = {
                label: value for label, value in values.items() if label in requested_set
            }
        else:
            indexes[variant] = _filter_members(values, requested_set)
    units = target.units[SATELLITE]
    units = units.loc[units.index.isin(requested_set)].copy()
    clusters = copy.deepcopy(target._clusters)
    if SATELLITE in clusters:
        clusters[SATELLITE] = _filter_members(clusters[SATELLITE], requested_set)

    target.matrices = matrices
    target._indeces["k"] = indexes
    target.units[SATELLITE] = units
    target._clusters = clusters
    target.meta._add_history(f"Satellite accounts retained: {selected!r}.")
    return None if inplace else target
