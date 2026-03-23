"""Export operations extracted from the ``Database`` class."""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
import pymrio

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.ops.export_specs import PYMRIO_EXPORT_LAYOUTS
from mario.model.conventions import _ENUM, _MASTER_INDEX
from mario.ops.excel import database_excel, database_txt
from mario.utils import pymrio_styling

logger = logging.getLogger(__name__)


def export_database_to_excel(
    database,
    *,
    path=None,
    flows: bool = True,
    coefficients: bool = False,
    scenario: str = "baseline",
    include_meta: bool = False,
):
    """Export a database to the historical MARIO Excel format."""

    if scenario not in database.scenarios:
        raise WrongInput(
            "{} is not a valid scenario. Existing scenarios are {}".format(
                scenario, [*database.matrices]
            )
        )

    if flows is False and coefficients is False:
        raise WrongInput("At least one of the flows or coefficients should be True")

    log_time(logger, f"Export: writing Excel database for {scenario}.", "info")
    database_excel(
        database,
        flows,
        coefficients,
        database._getdir(path, "Database", "New_Database.xlsx"),
        scenario,
    )

    if include_meta:
        meta = database.meta._to_dict()
        meta_path = database._getdir(path, "Database", "")
        meta_path = meta_path.split("/")[:-1]
        meta_path = ("/").join(meta_path) + "/metadata.json"

        with open(meta_path, "w") as fp:
            json.dump(meta, fp)
    log_time(logger, "Export: Excel database written.", "info")


def export_database_to_txt(
    database,
    *,
    path=None,
    flows: bool = True,
    coefficients: bool = False,
    scenario: str = "baseline",
    _format: str = "txt",
    include_meta: bool = False,
    sep: str = ",",
):
    """Export a database as multiple txt/csv files."""

    if scenario not in database.scenarios:
        raise WrongInput(
            "{} is not a valid scenario. Existing scenarios are {}".format(
                scenario, [*database.matrices]
            )
        )

    if flows is False and coefficients is False:
        raise WrongInput("At least one of the flows or coefficients should be True")

    log_time(logger, f"Export: writing {_format} database for {scenario}.", "info")
    database_txt(
        database,
        flows,
        coefficients,
        database._getdir(path, "Database", ""),
        scenario,
        _format,
        sep,
    )

    if include_meta:
        meta = database.meta._to_dict()
        with open(database._getdir(path, "Database", "") + "/metadata.json", "w") as fp:
            json.dump(meta, fp)
    log_time(logger, f"Export: {_format} database written.", "info")


def export_database_to_pymrio(
    database,
    *,
    satellite_account: str = "satellite_account",
    factor_of_production: str = "factor_of_production",
    include_meta: bool = True,
    scenario: str = "baseline",
    **kwargs,
):
    """Convert an IOT database into a pymrio.IOSystem."""

    if database.table_type != "IOT":
        raise NotImplementable("pymrio supports only IO tables.")

    if any([" " in item for item in [satellite_account, factor_of_production]]):
        raise WrongInput(
            "satellte_account and factor_of_production does not accept values containing space."
        )

    log_time(logger, f"Export: building pymrio IOSystem for {scenario}.", "info")
    matrices = database.query(
        matrices=[_ENUM.V, _ENUM.Z, _ENUM.Y, _ENUM.E, _ENUM.EY],
        scenarios=[scenario],
    )

    factor_input = pymrio.Extension(
        name=factor_of_production,
        F=pymrio_styling(df=matrices[_ENUM.V], **PYMRIO_EXPORT_LAYOUTS["V"]),
        unit=database.units[_MASTER_INDEX["f"]],
    )

    satellite = pymrio.Extension(
        name=satellite_account,
        F=pymrio_styling(df=matrices[_ENUM.E], **PYMRIO_EXPORT_LAYOUTS["E"]),
        F_Y=pymrio_styling(df=matrices[_ENUM.EY], **PYMRIO_EXPORT_LAYOUTS["EY"]),
        unit=database.units[_MASTER_INDEX["k"]],
    )

    units = pd.DataFrame(
        data=np.tile(
            database.units[_MASTER_INDEX["s"]].values,
            (len(database.get_index(_MASTER_INDEX["r"])), 1),
        ),
        index=matrices[_ENUM.Z].index,
        columns=["unit"],
    )

    io = pymrio.IOSystem(
        Z=pymrio_styling(df=matrices[_ENUM.Z], **PYMRIO_EXPORT_LAYOUTS["Z"]),
        Y=pymrio_styling(df=matrices[_ENUM.Y], **PYMRIO_EXPORT_LAYOUTS["Y"]),
        unit=units,
        **kwargs,
    )

    setattr(io, satellite_account, satellite)
    setattr(io, factor_of_production, factor_input)

    io.meta.note("IOSystem and Extension initliazied by mario")

    if include_meta:
        for note in database.meta._history:
            io.meta.note(f"mario HISTORY - {note}")

    log_time(logger, "Export: pymrio IOSystem ready.", "info")
    return io
