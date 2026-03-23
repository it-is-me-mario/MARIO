"""Aggregation operations extracted from the ``Database`` class."""

from __future__ import annotations

from mario.ops.aggregation_engine import _aggregator
from mario.model.conventions import _ENUM
from mario.utils import _manage_indeces


def aggregate_database(
    database,
    io,
    *,
    drop=("unused",),
    levels="all",
    calc_all: bool = True,
    ignore_nan: bool = False,
    inplace: bool = True,
):
    """Aggregate a database while keeping the public Database API stable."""

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
            inplace=True,
        )
        return new

    if isinstance(drop, str):
        drop = [drop]
    else:
        drop = list(drop)

    if io is None:
        new_matrices, units = _aggregator(database, drop)
    else:
        database.read_aggregated_index(
            levels=levels,
            io=io,
            ignore_nan=ignore_nan,
        )
        new_matrices, units = _aggregator(database, drop)

    for scenario in database.scenarios:
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
