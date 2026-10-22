"""Opt-in verification of the locally synchronized, native BONSAI b2 model.

Set MARIO_BONSAI_HIOT_DIR to the directory containing the native b2 export.
The complete matrix is checked; no full inverse or footprint is materialized.
"""

import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

import mario


@pytest.mark.usefixtures("bonsai_without_umfpack")
@pytest.mark.skipif(
    not os.environ.get("MARIO_BONSAI_HIOT_DIR"),
    reason="Set MARIO_BONSAI_HIOT_DIR to a local native BONSAI b2 export.",
)
def test_native_hiot_full_matrix_and_source_axes_are_preserved():
    path = Path(os.environ["MARIO_BONSAI_HIOT_DIR"])
    source = pd.read_pickle(path / "extended_size_hiot.b2.pkl")
    with warnings.catch_warnings(record=True):
        db = mario.parse_bonsai(path, table="IOT")
    blocks = db.matrices["baseline"]
    x = blocks["X"].iloc[:, 0].to_numpy()
    restored = sparse.diags(x) - blocks["Z"].sparse.to_coo().tocsr()
    difference = restored - source.sparse.to_coo().tocsr()
    difference.eliminate_zeros()
    assert difference.nnz == 0
    assert list(blocks["Z"].index.get_level_values(0)) == [
        label.split(";")[0] for label in source.index
    ]
    assert list(blocks["Z"].index.get_level_values(2)) == [
        label.split(";")[1] for label in source.index
    ]
    np.testing.assert_array_equal(x, source.sparse.to_coo().diagonal())
    assert blocks["E"].shape[1] == source.shape[1]
    assert "w" not in blocks and "f" not in blocks
    assert len(db.info["bonsai"]["reference_products"]) == source.shape[1]
    assert blocks["Y"].shape[0] == source.shape[0]
    assert db.info["bonsai"]["variant"] == "b2"
