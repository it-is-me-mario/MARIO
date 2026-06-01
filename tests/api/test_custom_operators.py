import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from mario.compute import (
    block_spec,
    matrix_product_operator,
    ratio_operator,
    sum_operator,
    zeros_like_operator,
)
from mario.log_exc.exceptions import WrongInput
from mario.test.mario_test import load_test


IOT_ENTITY_AXES = (
    ("region_output", "r"),
    ("sector_output", "s"),
    ("item_output", "item"),
)


def _regionalized_extension(database):
    extension = database.E.copy()
    extension.index = pd.MultiIndex.from_tuples(
        [("Italy", str(label)) for label in extension.index],
        names=["Extension region", "Satellite account"],
    )
    return extension


def test_custom_ratio_operator_supports_richer_row_axes():
    database = load_test("IOT")
    regional_extension = _regionalized_extension(database)
    database.matrices["baseline"]["E_regional"] = regional_extension
    database.register_block_spec(
        name="E_regional",
        row_axes=(("extension_region", "r"), ("satellite", "k")),
        col_axes=IOT_ENTITY_AXES,
    )

    database.register_operator(
        ratio_operator(
            name="e_regional",
            numerator="E_regional",
            denominator="X",
            align="columns",
            output_spec=block_spec(
                name="e_regional",
                row_axes=(("extension_region", "r"), ("satellite", "k")),
                col_axes=IOT_ENTITY_AXES,
            ),
        )
    )

    resolved = database.resolve("e_regional")
    expected = regional_extension.divide(database.X.iloc[:, 0], axis="columns")

    pdt.assert_frame_equal(resolved, expected)
    pdt.assert_frame_equal(database.e_regional, expected)
    assert "e_regional" in database.list_custom_operators()
    assert "e_regional" in database.available_matrices()

    spec = database.get_block_spec("e_regional")
    assert tuple(axis.id for axis in spec.row_axes) == ("extension_region", "satellite")
    assert tuple(axis.base for axis in spec.row_axes) == ("r", "k")


def test_custom_matrix_product_operator_chains_with_other_custom_blocks():
    database = load_test("IOT")
    regional_extension = _regionalized_extension(database)
    database.matrices["baseline"]["E_regional"] = regional_extension
    database.register_block_spec(
        name="E_regional",
        row_axes=(("extension_region", "r"), ("satellite", "k")),
        col_axes=IOT_ENTITY_AXES,
    )
    database.register_operator(
        ratio_operator(
            name="e_regional",
            numerator="E_regional",
            denominator="X",
            output_spec=block_spec(
                name="e_regional",
                row_axes=(("extension_region", "r"), ("satellite", "k")),
                col_axes=IOT_ENTITY_AXES,
            ),
        )
    )
    database.register_operator(
        matrix_product_operator(
            name="f_regional",
            left="e_regional",
            right="w",
            output_spec=block_spec(
                name="f_regional",
                row_axes=(("extension_region", "r"), ("satellite", "k")),
                col_axes=IOT_ENTITY_AXES,
            ),
        )
    )

    resolved = database.resolve("f_regional")
    expected = database.e_regional.dot(database.w)

    pdt.assert_frame_equal(resolved, expected)


def test_custom_sum_and_zero_like_builders_are_available():
    database = load_test("IOT")
    database.register_operator(
        sum_operator(
            name="Y_total_custom",
            source="Y",
            over="columns",
            label="Total final demand",
            output_spec=block_spec(
                name="Y_total_custom",
                row_axes=IOT_ENTITY_AXES,
                col_axes=(("total_final_demand", "n"),),
            ),
        )
    )
    database.register_operator(
        zeros_like_operator(
            name="VY_zero_custom",
            rows_from="V",
            cols_from="Y",
            output_spec=block_spec(
                name="VY_zero_custom",
                row_axes=(("factor", "f"),),
                col_axes=(("region_final_use", "r"), ("final_use", "n"), ("item_final_use", "item")),
            ),
        )
    )

    y_total = database.resolve("Y_total_custom")
    expected_total = pd.DataFrame(
        database.Y.sum(axis=1).to_numpy(dtype=float),
        index=database.Y.index,
        columns=["Total final demand"],
    )
    pdt.assert_frame_equal(y_total, expected_total)

    vy_zero = database.resolve("VY_zero_custom")
    assert vy_zero.shape == (database.V.shape[0], database.Y.shape[1])
    assert np.count_nonzero(vy_zero.to_numpy()) == 0


def test_custom_operator_cannot_shadow_built_in_block_by_default():
    database = load_test("IOT")

    with pytest.raises(WrongInput):
        database.register_operator(
            ratio_operator(
                name="e",
                numerator="E",
                denominator="X",
            )
        )
