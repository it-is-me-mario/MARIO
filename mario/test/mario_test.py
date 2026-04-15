# -*- coding: utf-8 -*-
"""Small packaged fixtures used by MARIO tests and examples."""

from numpy import dtype, float64
from mario.parsers.entrypoints import parse_from_excel
from mario.model.conventions import _ENUM


import os
import pandas as pd

_DATA_MAP = {
    _ENUM.X: dict(sheet_name="X", index_col=[0, 1, 2], header=0),
    _ENUM.Y: dict(sheet_name="Y", index_col=[0, 1, 2], header=[0, 1, 2]),
    _ENUM.y: dict(sheet_name="_y", index_col=[0, 1, 2], header=[0, 1, 2]),
    _ENUM.E: dict(sheet_name="E", index_col=[0], header=[0, 1, 2]),
    _ENUM.e: dict(sheet_name="_e", index_col=[0], header=[0, 1, 2]),
    _ENUM.V: dict(sheet_name="V", index_col=[0], header=[0, 1, 2]),
    _ENUM.v: dict(sheet_name="_v", index_col=[0], header=[0, 1, 2]),
    _ENUM.Z: dict(sheet_name="Z", index_col=[0, 1, 2], header=[0, 1, 2]),
    _ENUM.z: dict(sheet_name="_z", index_col=[0, 1, 2], header=[0, 1, 2]),
    _ENUM.b: dict(sheet_name="b", index_col=[0, 1, 2], header=[0, 1, 2]),
    _ENUM.g: dict(sheet_name="g", index_col=[0, 1, 2], header=[0, 1, 2]),
    _ENUM.w: dict(sheet_name="w", index_col=[0, 1, 2], header=[0, 1, 2]),
    _ENUM.f: dict(sheet_name="_f", index_col=[0], header=[0, 1, 2]),
    _ENUM.F: dict(sheet_name="F", index_col=[0], header=[0, 1, 2]),
    _ENUM.m: dict(sheet_name="_m", index_col=[0], header=[0, 1, 2]),
    _ENUM.M: dict(sheet_name="M", index_col=[0], header=[0, 1, 2]),
    _ENUM.p: dict(sheet_name="p", index_col=[0, 1, 2], header=[0]),
}

path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
    )
)


def load_test(table, tech_assumption=None):
    """Load one of the packaged test databases.

    Parameters
    ----------
    table : str
        Table kind to load. Accepted values are ``"IOT"`` and ``"SUT"``.
    tech_assumption : str, optional
        Optional SUT technology assumption forwarded to the parser. Accepted
        values are ``"industry-based"``, ``"product-based"``, ``"IT"`` and
        ``"PT"``.

    Returns
    -------
    mario.Database
        Parsed test database ready for examples or tests.
    """

    return parse_from_excel(
        path=f"{path}/{table}.xlsx",
        table=table,
        name=f"{table} test",
        mode="flows",
        tech_assumption=tech_assumption,
    )


def load_dummy(test):
    """Load a raw workbook fixture as a mapping of matrix names to dataframes."""
    file = pd.ExcelFile(f"{path}/{test}.xlsx")

    return {
        matrix: file.parse(
            **info,
        ).astype(float)
        for matrix, info in _DATA_MAP.items()
    }


# %%
