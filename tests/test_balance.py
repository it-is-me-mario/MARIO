import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.test.mario_test import load_test


def test_ras_balances_dataframe_and_aligns_labeled_targets():
    matrix = pd.DataFrame(
        [[5.0, 1.0], [2.0, 4.0]],
        index=pd.Index(["row_b", "row_a"], name="row"),
        columns=pd.Index(["col_y", "col_x"], name="col"),
    )
    target_rows = pd.Series({"row_a": 8.0, "row_b": 10.0})
    target_cols = pd.Series({"col_x": 7.0, "col_y": 11.0})

    balanced = mario.ras(matrix, target_rows=target_rows, target_cols=target_cols)

    assert isinstance(balanced, pd.DataFrame)
    assert balanced.index.equals(matrix.index)
    assert balanced.columns.equals(matrix.columns)
    assert np.allclose(
        balanced.sum(axis=1).to_numpy(),
        target_rows.reindex(matrix.index).to_numpy(),
    )
    assert np.allclose(
        balanced.sum(axis=0).to_numpy(),
        target_cols.reindex(matrix.columns).to_numpy(),
    )


def test_ras_rejects_inconsistent_target_totals():
    with pytest.raises(WrongInput, match="same total"):
        mario.ras(np.array([[1.0, 2.0], [3.0, 4.0]]), [5.0, 5.0], [4.0, 7.0])


def test_database_ras_returns_balanced_copy_and_leaves_original_untouched():
    database = load_test("IOT")
    target_rows = database.Z.sum(axis=1)
    target_cols = database.Z.sum(axis=0)

    unbalanced = database.copy()
    perturbed_Z = unbalanced.Z.copy()
    perturbed_Z.iloc[0, 0] += 7.0
    perturbed_Z.iloc[1, 2] += 3.0
    unbalanced.set_block("Z", perturbed_Z)

    balanced = unbalanced.ras(
        target_rows=target_rows,
        target_cols=target_cols,
        inplace=False,
    )

    assert balanced is not unbalanced
    assert np.max(
        np.abs(unbalanced.Z.sum(axis=1).to_numpy() - target_rows.to_numpy())
    ) > 0
    assert np.allclose(balanced.Z.sum(axis=1).to_numpy(), target_rows.to_numpy())
    assert np.allclose(balanced.Z.sum(axis=0).to_numpy(), target_cols.to_numpy())
    assert balanced.has_matrix("z")
    assert np.allclose(
        balanced.query("X").to_numpy().reshape(-1),
        (balanced.Z.sum(axis=1) + balanced.Y.sum(axis=1)).to_numpy(),
    )


def test_database_ras_requires_iot():
    with pytest.raises(WrongInput, match="only available for IOT"):
        load_test("SUT").ras(target_rows=[1.0], target_cols=[1.0])
