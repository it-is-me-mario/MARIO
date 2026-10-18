"""Aggregation operations extracted from the ``Database`` class."""

from __future__ import annotations

from mario.ops.aggregation_engine import _aggregator
from mario.model.conventions import TABLE_LEVELS, _ENUM, _MASTER_INDEX
from mario.utils import _manage_indeces


def _build_region_aggregation_map(database) -> dict[str, list[str]] | None:
    """Compose the current Region aggregation against any previously stored base map."""
    region_level = TABLE_LEVELS[database.meta.table][_MASTER_INDEX["r"]]
    region_index = database._indeces.get(region_level, {}).get("aggregated")
    if region_index is None:
        return None

    previous = getattr(database.meta, "region_aggregation_map", None)
    mapping: dict[str, list[str]] = {}
    for source_region, target_region in region_index["Aggregation"].items():
        target_key = str(target_region)
        source_key = str(source_region)
        members = previous.get(source_key, [source_key]) if isinstance(previous, dict) else [source_key]
        mapping.setdefault(target_key, [])
        for member in members:
            if member not in mapping[target_key]:
                mapping[target_key].append(member)

    return mapping


def _store_region_aggregation_map(database) -> None:
    """Persist one structured Region aggregation map on public metadata."""
    mapping = _build_region_aggregation_map(database)
    if mapping is None:
        return

    previous = getattr(database.meta, "region_aggregation_map", None)
    database.meta.region_aggregation_map = mapping
    if previous != mapping:
        database.meta._add_history(
            f"Metadata: saved region aggregation map for {len(mapping)} aggregated regions."
        )


def aggregate_database(
    database,
    io,
    *,
    drop=("unused",),
    levels="all",
    calc_all: bool = True,
    ignore_nan: bool = False,
    zero_output_epsilon: float | None = 1e-30,
    inplace: bool = True,
):
    """Aggregate a database while keeping the public Database API stable."""

    if database.table_type == "IOT":
        for scenario in database.scenarios:
            database.calc_all([_ENUM.E, _ENUM.V, _ENUM.Z], scenario=scenario)

    if not inplace:
        new = database.copy()
        aggregate_database(
            new,
            io=io,
            drop=drop,
            levels=levels,
            calc_all=calc_all,
            ignore_nan=ignore_nan,
            zero_output_epsilon=zero_output_epsilon,
            inplace=True,
        )
        return new

    if isinstance(drop, str):
        drop = [drop]
    else:
        drop = list(drop)

    if io is None:
        new_matrices, units = _aggregator(
            database,
            drop,
            zero_output_epsilon=zero_output_epsilon,
        )
    else:
        database.read_aggregated_index(
            levels=levels,
            io=io,
            ignore_nan=ignore_nan,
        )
        _store_region_aggregation_map(database)
        new_matrices, units = _aggregator(
            database,
            drop,
            zero_output_epsilon=zero_output_epsilon,
        )

    for scenario in database._storage_scenarios():
        database.matrices[scenario] = new_matrices[scenario]

    database.meta._add_history(
        "original matrices changed to the aggregated level based on the inputs from {}".format(
            io
        )
    )
    database.units = units
    _manage_indeces(database, "aggregation")

    if calc_all:
        for scenario in database.scenarios:
            database.calc_all(scenario=scenario)

    return None
