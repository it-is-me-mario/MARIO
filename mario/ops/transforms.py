"""Operational transforms extracted from the ``Database`` class."""

from __future__ import annotations

import logging

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _ENUM
from mario.ops.transform_engine import ISARD_TO_CHENERY_MOSES, SUT_to_IOT
from mario.utils import sort_frames

logger = logging.getLogger(__name__)


def _capture_custom_transform_block_specs(database):
    """Capture custom SUT extension/factor block specs before SUT->IOT transforms."""
    captured = {}
    for name in ("V", "v", "VY", "E", "e", "EY"):
        if name in database.list_custom_block_specs():
            captured[name] = database.get_block_spec(name)
    return captured


def _restore_iot_transform_block_specs(database, captured_specs):
    """Re-register custom block specs after SUT->IOT using IOT output columns."""
    productive_cols = (("Region", "Region"), ("Sector", "Sector"))
    final_demand_cols = (("Region", "Region"), ("Consumption category", "Consumption category"))

    for name, spec in captured_specs.items():
        row_axes = tuple((axis.id, axis.base) for axis in spec.row_axes)
        col_axes = final_demand_cols if name in {"EY", "VY"} else productive_cols
        database.register_block_spec(
            name=name,
            row_axes=row_axes,
            col_axes=col_axes,
            replace=True,
        )


def build_new_instance_from_scenario(database, scenario):
    """Return a new database whose baseline is the requested scenario."""

    database._validate_scenario(scenario)

    data = database.query(
        matrices=[_ENUM.Y, _ENUM.E, _ENUM.V, _ENUM.Z, _ENUM.EY, _ENUM.VY],
        scenarios=scenario,
    )

    new = database.__class__(
        name=getattr(database.meta, "name", None),
        Y=data[_ENUM.Y],
        E=data[_ENUM.E],
        V=data[_ENUM.V],
        Z=data[_ENUM.Z],
        EY=data[_ENUM.EY],
        VY=data[_ENUM.VY],
        units=database.units,
        table=database.meta.table,
        price=getattr(database.meta, "price", None),
        source=getattr(database.meta, "source", None),
        year=getattr(database.meta, "year", None),
        tech_assumption=getattr(database.meta, "tech_assumption", None),
    )
    if hasattr(database, "clusters") and hasattr(new, "set_clusters"):
        new.set_clusters(clusters=database.clusters)
    if hasattr(database, "baseline_scenario_name") and hasattr(new, "rename_baseline_scenario"):
        new.rename_baseline_scenario(database.baseline_scenario_name)
    return new


def transform_sut_to_iot(database, method, inplace: bool = True):
    """Transform a SUT database into an IOT database."""

    if not inplace:
        new = database.copy()
        transform_sut_to_iot(new, method, inplace=True)
        return new

    if database.meta.table == "IOT":
        raise NotImplementable("IOT table cannot be transformed to IOT.")

    log_time(
        logger,
        "Database: Transforming the database from SUT to IOT via method {}".format(
            method
        ),
    )
    captured_specs = _capture_custom_transform_block_specs(database)
    matrices, indeces, units = SUT_to_IOT(database, method)

    for scenario in database.scenarios:
        log_time(logger, f"{scenario} deleted from the database", "warning")
        database.meta._add_history(f"{scenario} deleted from the database")

    database.matrices = matrices
    database._indeces = indeces
    database.units = units

    database.meta.table = "IOT"
    database.meta._add_attribute(tech_assumption=None)
    if captured_specs:
        _restore_iot_transform_block_specs(database, captured_specs)
    database.meta._add_history(
        "Transformation of the database from SUT to IOT via method {}".format(
            method
        )
    )
    log_time(
        logger,
        "Transformation of the database from SUT to IOT via method {}".format(
            method
        ),
    )
    return None


def transform_to_chenery_moses(
    database,
    *,
    inplace: bool = True,
    scenarios: list | None = None,
):
    """Transform an Isard SUT into a Chenery-Moses SUT."""

    if not inplace:
        new = database.copy()
        transform_to_chenery_moses(new, inplace=True, scenarios=scenarios)
        return new

    if scenarios is None:
        scenarios = database.scenarios

    for scenario in scenarios:
        if database.is_chenerymoses(scenario=scenario):
            raise NotImplementable(
                f"scenario {scenario} is already in Chenery-Moses format"
            )

    log_time(
        logger,
        "Database: Transforming the database into Chenery-Moses",
    )

    for scenario in scenarios:
        Z_chenery, Y_chenery = ISARD_TO_CHENERY_MOSES(database, scenario)
        to_update = {_ENUM.Z: Z_chenery, _ENUM.Y: Y_chenery}
        sort_frames(to_update)
        database.update_scenarios(scenario, **to_update)
        database.calc_all(
            matrices=[_ENUM.U, _ENUM.S, "Ya", "Yc"],
            scenario=scenario,
            force_rewrite=True,
        )
        database.reset_to_flows(scenario=scenario)

        database.meta._add_history(
            f"Transformation of the database from into Chenery-Moses for scenario {scenario}"
        )

    log_time(logger, "Transformation of the database from into Chenery-Moses")
    return None


def transform_pool_trade(
    database,
    commodities,
    *,
    supply_suffix: str = " - supply",
    need_suffix: str = " - need",
    inplace: bool = True,
):
    """Pool the trade of selected commodities behind one pass-through layer.

    For each selected commodity ``c`` the transformation adds, per region, one
    ``"{c}{supply_suffix}"`` activity and one ``"{c}{need_suffix}"`` commodity:
    the pass-through activity consumes the whole domestic output of ``c``,
    every buyer is rewired to the domestic need commodity, and the supply
    block routes the need markets to the origin pass-through activities with
    the bilateral trade flows observed in the Isard use side. The rest of the
    table keeps its Isard layout.

    The pooled table is a representation change, not a data change: bilateral
    trade totals per destination are preserved exactly, and the initial market
    shares written in ``s`` equal the observed origin shares of each
    destination's total use. Buyer-specific sourcing heterogeneity inside one
    destination region is averaged away (the Chenery-Moses hypothesis),
    applied only to the selected commodities.
    """
    import pandas as pd

    from mario.compute.primitives import calc_X
    from mario.model.conventions import _MASTER_INDEX
    from mario.utils import _manage_indeces

    if not inplace:
        new = database.copy()
        transform_pool_trade(
            new,
            commodities,
            supply_suffix=supply_suffix,
            need_suffix=need_suffix,
            inplace=True,
        )
        return new

    if database.table_type != "SUT":
        raise NotImplementable("pool_trade is implemented only for SUT databases.")

    A, C, N, R = (
        _MASTER_INDEX["a"],
        _MASTER_INDEX["c"],
        _MASTER_INDEX["n"],
        _MASTER_INDEX["r"],
    )

    commodities = (
        [commodities] if isinstance(commodities, str) else list(dict.fromkeys(commodities))
    )
    if not commodities:
        raise WrongInput("commodities must be one non-empty commodity label or iterable.")

    current_activities = list(database.get_index(A))
    current_commodities = list(database.get_index(C))
    missing = [c for c in commodities if c not in current_commodities]
    if missing:
        raise WrongInput(f"pool_trade references unknown commodities: {missing}")

    supply_labels = {c: f"{c}{supply_suffix}" for c in commodities}
    need_labels = {c: f"{c}{need_suffix}" for c in commodities}

    colliding_activities = [
        label for label in supply_labels.values() if label in current_activities
    ]
    colliding_commodities = [
        label for label in need_labels.values() if label in current_commodities
    ]
    if colliding_activities or colliding_commodities:
        raise WrongInput(
            "pool_trade would create labels that already exist (commodity already pooled "
            f"or naming collision): {sorted(colliding_activities + colliding_commodities)}. "
            "Pass different supply_suffix/need_suffix values or drop the colliding items."
        )

    dropped_scenarios = [s for s in database.scenarios if s != "baseline"]
    if dropped_scenarios:
        log_time(
            logger,
            "pool_trade: all non-baseline scenarios will be deleted to build the new baseline.",
            "warning",
        )

    data = database.query(
        matrices=[_ENUM.Z, _ENUM.Y, _ENUM.V, _ENUM.E, _ENUM.EY, _ENUM.VY],
    )
    Z_old = data[_ENUM.Z]
    Y_old = data[_ENUM.Y]

    regions = list(database.get_index(R))
    sN = slice(None)

    new_activities = current_activities + list(supply_labels.values())
    new_commodities = current_commodities + list(need_labels.values())
    activity_axis = pd.MultiIndex.from_product(
        [regions, [A], new_activities], names=Z_old.index.names
    )
    commodity_axis = pd.MultiIndex.from_product(
        [regions, [C], new_commodities], names=Z_old.index.names
    )
    rows_new = activity_axis.append(commodity_axis)

    Z = Z_old.reindex(index=rows_new, columns=rows_new, fill_value=0.0)
    Y = Y_old.reindex(index=rows_new, fill_value=0.0)
    V = data[_ENUM.V].reindex(columns=rows_new, fill_value=0.0)
    E = data[_ENUM.E].reindex(columns=rows_new, fill_value=0.0)
    EY = data[_ENUM.EY]
    VY = data[_ENUM.VY]

    for c in commodities:
        supply_c = supply_labels[c]
        need_c = need_labels[c]
        c_rows = [(region, C, c) for region in regions]

        # Bilateral trade flows observed on the Isard use side:
        # origin region -> destination region, summed over the destination's
        # buyers (intermediate use and final demand).
        intermediate_use = Z_old.loc[c_rows, (sN, A, sN)].T.groupby(level=R, sort=False).sum().T
        final_use = Y_old.loc[c_rows, :].T.groupby(level=R, sort=False).sum().T
        trade_flows = (intermediate_use + final_use).reindex(columns=regions, fill_value=0.0)
        trade_flows.index = regions

        for destination in regions:
            # The destination's buyers move onto the domestic need commodity,
            # keeping their buyer-level totals (summed over origins).
            need_row = (destination, C, need_c)
            buyer_cols = Z.columns[
                (Z.columns.get_level_values(0) == destination)
                & (Z.columns.get_level_values(1) == A)
                & ~Z.columns.get_level_values(2).isin(supply_labels.values())
            ]
            Z.loc[need_row, buyer_cols] = (
                Z_old.loc[c_rows, buyer_cols.intersection(Z_old.columns)]
                .sum(axis=0)
                .reindex(buyer_cols, fill_value=0.0)
                .to_numpy()
            )
            fd_cols = Y.columns[Y.columns.get_level_values(0) == destination]
            Y.loc[need_row, fd_cols] = Y_old.loc[c_rows, fd_cols].sum(axis=0).to_numpy()

            # The original commodity rows stop serving the destination's
            # buyers directly.
            Z.loc[c_rows, buyer_cols] = 0.0
            Y.loc[c_rows, fd_cols] = 0.0

            # The supply block routes the destination market to the origin
            # pass-through activities with the observed bilateral flows.
            supply_rows = [(origin, A, supply_c) for origin in regions]
            Z.loc[supply_rows, (destination, C, need_c)] = (
                trade_flows.loc[:, destination].to_numpy()
            )

        # Each pass-through activity consumes the whole domestic output of the
        # original commodity (its shipments to every destination).
        for origin in regions:
            Z.loc[(origin, C, c), (origin, A, supply_c)] = float(
                trade_flows.loc[origin, :].sum()
            )

    X = calc_X(Z=Z, Y=Y)

    all_indeces = database.get_index("all")
    _manage_indeces(
        database,
        "single_region",
        a=new_activities,
        c=new_commodities,
        r=all_indeces[R],
        f=all_indeces[_MASTER_INDEX["f"]],
        k=all_indeces[_MASTER_INDEX["k"]],
        n=all_indeces[N],
    )

    database.matrices = {"baseline": {}}
    for name, frame in {
        _ENUM.Z: Z,
        _ENUM.Y: Y,
        _ENUM.V: V,
        _ENUM.E: E,
        _ENUM.EY: EY,
        _ENUM.VY: VY,
        _ENUM.X: X,
    }.items():
        database.matrices["baseline"][name] = frame

    for c in commodities:
        commodity_unit = database.units[C].loc[c, "unit"]
        database.units[A].loc[supply_labels[c], "unit"] = commodity_unit
        database.units[C].loc[need_labels[c], "unit"] = commodity_unit

    pooled_map = dict(getattr(database.meta, "pooled_trade_map", {}) or {})
    pooled_map.update(
        {c: {"supply": supply_labels[c], "need": need_labels[c]} for c in commodities}
    )
    database.meta.pooled_trade_map = pooled_map

    for scenario in dropped_scenarios:
        log_time(logger, f"pool_trade: {scenario} deleted from the database.")

    database.meta._add_history(
        "Transformation: pooled the trade of commodities "
        f"{commodities} behind pass-through '{supply_suffix.strip()}'/'{need_suffix.strip()}' "
        "layers; trade mixes now live in the supply block market shares."
    )
    log_time(logger, f"pool_trade: pooled trade layer added for {commodities}.")
    return None
