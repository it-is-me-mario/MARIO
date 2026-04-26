# -*- coding: utf-8 -*-
"""Small packaged fixtures used by MARIO tests and examples."""

from mario.parsers.entrypoints import parse_from_excel
from mario.model.conventions import _ENUM
from mario.log_exc.exceptions import WrongInput


import os

path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
    )
)


_LOAD_TEST_VARIANTS = {
    ("IOT", "legacy"): {
        "path": "new/test_IOT_standard.xlsx",
        "matrix_layouts": None,
    },
    ("IOT", "standard"): {
        "path": "new/test_IOT_standard.xlsx",
        "matrix_layouts": None,
    },
    ("IOT", "special"): {
        "path": "new/test_IOT_special.xlsx",
        "matrix_layouts": {
            "V": ("Region", "Sector"),
            "E": "Region",
        },
    },
    ("SUT", "legacy"): {
        "path": "new/test_SUT_standard.xlsx",
        "matrix_layouts": None,
    },
    ("SUT", "standard"): {
        "path": "new/test_SUT_standard.xlsx",
        "matrix_layouts": None,
    },
    ("SUT", "special"): {
        "path": "new/test_SUT_special.xlsx",
        "matrix_layouts": {
            "E": ("Region", "Commodity"),
        },
    },
}


def load_test(table, tech_assumption=None, layout="standard"):
    """Load one of the packaged test databases.

    Parameters
    ----------
    table : str
        Table kind to load. Accepted values are ``"IOT"`` and ``"SUT"``.
    tech_assumption : str, optional
        Optional SUT technology assumption forwarded to the parser. Accepted
        values are ``"industry-based"``, ``"product-based"``, ``"IT"`` and
        ``"PT"``.
    layout : str, optional
        Fixture layout to load. Accepted values are:

        * ``"legacy"``: retained as an alias for ``"standard"``;
        * ``"standard"``: the new standard-layout workbook in ``mario/test/new``;
        * ``"special"``: the new workbook variant that needs explicit
          ``matrix_layouts``.

    Returns
    -------
    mario.Database
        Parsed test database ready for examples or tests.
    """
    normalized_table = str(table).upper()
    normalized_layout = str(layout).strip().lower()
    spec = _LOAD_TEST_VARIANTS.get((normalized_table, normalized_layout))
    if spec is None:
        raise WrongInput(
            f"Unsupported load_test combination {(normalized_table, normalized_layout)!r}. "
            "Accepted layouts are 'legacy', 'standard', and 'special' for tables 'IOT' and 'SUT'."
        )

    return parse_from_excel(
        path=os.path.join(path, spec["path"]),
        table=normalized_table,
        matrix_layouts=spec["matrix_layouts"],
        name=f"{normalized_table} test ({normalized_layout})",
        mode="flows",
        tech_assumption=tech_assumption,
    )


def load_dummy(test="IOT"):
    """Build a raw IOT fixture mapping from the packaged standard workbook."""
    if str(test).strip().upper() not in {"IOT", "IOT_DUMMY"}:
        raise WrongInput("load_dummy currently supports only the packaged IOT fixture.")

    from mario.compute.primitives import calc_y

    database = load_test("IOT", layout="standard")
    database.calc_all([_ENUM.X], force_rewrite=True)
    database.calc_all(
        [
            _ENUM.z,
            _ENUM.v,
            _ENUM.e,
            _ENUM.w,
            _ENUM.b,
            _ENUM.g,
            _ENUM.f,
            _ENUM.F,
            _ENUM.m,
            _ENUM.M,
            _ENUM.p,
        ],
        force_rewrite=True,
    )

    matrices = {
        matrix: database["baseline"][matrix]
        for matrix in [
            _ENUM.X,
            _ENUM.Y,
            _ENUM.E,
            _ENUM.e,
            _ENUM.V,
            _ENUM.v,
            _ENUM.Z,
            _ENUM.z,
            _ENUM.b,
            _ENUM.g,
            _ENUM.w,
            _ENUM.f,
            _ENUM.F,
            _ENUM.m,
            _ENUM.M,
            _ENUM.p,
        ]
    }
    matrices[_ENUM.y] = calc_y(matrices[_ENUM.Y])
    return matrices


# %%
