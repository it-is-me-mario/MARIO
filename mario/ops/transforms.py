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

    if scenario not in database.scenarios:
        raise WrongInput(
            "{} is not a valid scenario. Valid scenarios are {}".format(
                scenario, database.scenarios
            )
        )

    data = database.query(
        matrices=[_ENUM.Y, _ENUM.E, _ENUM.V, _ENUM.Z, _ENUM.EY, _ENUM.VY],
        scenarios=scenario,
    )

    return database.__class__(
        Y=data[_ENUM.Y],
        E=data[_ENUM.E],
        V=data[_ENUM.V],
        Z=data[_ENUM.Z],
        EY=data[_ENUM.EY],
        VY=data[_ENUM.VY],
        units=database.units,
        table=database.meta.table,
    )


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
        database.reset_to_flows(scenario=scenario)

        database.meta._add_history(
            f"Transformation of the database from into Chenery-Moses for scenario {scenario}"
        )

    log_time(logger, "Transformation of the database from into Chenery-Moses")
    return None
