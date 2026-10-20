"""Isard detection sums native use by region, including irregular domains."""

from unittest.mock import patch

import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from tests.api.test_regional_indexes import regional_database


@pytest.fixture(params=[False, True], ids=["dense", "sparse"])
def database(request):
    db = regional_database(
        {"DE": ["A"], "IT": ["B"], "Global": []},
        {"IT": ["X"], "DE": [], "Global": ["Y", "Z"]},
    )
    U = db.query("U").sparse.to_dense()
    U.iloc[0, 1] = 3  # domestic, despite different row/column region ordering
    if request.param:
        U = U.astype(pd.SparseDtype(float, 0.0))
    db.matrices["baseline"]["U"] = U
    return db


def set_use(db, entries):
    U = db.query("U")
    sparse = all(isinstance(t, pd.SparseDtype) for t in U.dtypes)
    U = U.sparse.to_dense() if sparse else U.copy()
    for row, col, value in entries:
        U.iloc[row, col] = value
    db.matrices["baseline"]["U"] = U.astype(pd.SparseDtype(float, 0.0)) if sparse else U


def test_actual_region_labels_domestic_trade_and_negative_net_flows(database):
    assert database.is_isard() is False
    set_use(database, [(1, 0, -2)])
    assert database.is_isard() is True


def test_regional_net_cancellation_retains_existing_semantics(database):
    set_use(database, [(1, 0, 2), (2, 0, -2)])
    assert database.is_isard() is False


def test_native_path_never_materializes_unified_views(database):
    get_matrix = database._get_matrix

    def native(name, *args, **kwargs):
        assert name == "U"
        return get_matrix(name, *args, **kwargs)

    with patch.object(database, "_get_matrix", side_effect=native):
        assert database.is_isard() is False
    assert "Z" not in database.matrices["baseline"]
    assert "z" not in database.matrices["baseline"]


def test_selected_scenario_and_renamed_baseline(database):
    database.clone_scenario("baseline", "policy")
    database.rename_baseline_scenario("reference")
    frame = database.matrices["policy"]["U"].copy()
    sparse = all(isinstance(t, pd.SparseDtype) for t in frame.dtypes)
    frame = frame.sparse.to_dense() if sparse else frame
    frame.iloc[1, 0] = 4
    database.matrices["policy"]["U"] = frame
    assert not database.is_isard("baseline")
    assert not database.is_isard("reference")
    assert database.is_isard("policy")
    with pytest.raises(WrongInput, match="Acceptable data_sets"):
        database.is_isard("missing")
