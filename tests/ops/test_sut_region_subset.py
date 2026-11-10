"""Independent boundary accounting for native SUT region extraction."""

from copy import deepcopy
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from tests.api.test_regional_indexes import regional_database


def dense(frame):
    return frame.sparse.to_dense() if all(
        isinstance(dtype, pd.SparseDtype) for dtype in frame.dtypes
    ) else frame.copy()


@pytest.fixture(params=[False, True], ids=["dense", "sparse"])
def database(request):
    db = regional_database(
        {"IT": ["manufacturing", "wind"], "DE": ["coal", "wind", "services"],
         "FR": ["coal"]},
        {r: ["goods", "electricity"] for r in ("IT", "DE", "FR")},
        {"IT": ["HH", "GOV"], "DE": ["HH", "GOV"], "FR": ["HH"]},
    )
    for level in ("Activity", "Commodity"):
        db.units[level].loc[:, "unit"] = "EUR"
    source = {name: dense(frame) for name, frame in db.matrices["baseline"].items()}
    s, u, yc, ya = (source[name] for name in ("S", "U", "Yc", "Ya"))
    for row, col, amount in (
        (0, 0, 100), (0, 1, 10), (1, 1, 40),
        (2, 2, 15), (2, 3, 30), (3, 3, 10), (4, 2, 40),
        (5, 4, 30), (5, 5, 20),
    ):
        s.iloc[row, col] = amount
    for row, col, amount in (
        (3, 0, 8), (2, 1, 3), (5, 0, 2), (0, 2, 4), (1, 3, 5),
        (2, 0, 1), (1, 5, 2), (4, 4, 6), (3, 5, 2), (0, 0, 5), (1, 0, 4),
    ):
        u.iloc[row, col] = amount
    for row, col, amount in ((3, 0, 6), (3, 1, 2), (4, 0, 4), (0, 3, 3)):
        yc.iloc[row, col] = amount
    for i, node in enumerate(yc.index):
        own_hh = yc.columns.get_loc((node[0], "Consumption category", "HH"))
        yc.iloc[i, own_hh] += s.iloc[:, i].sum() - u.iloc[i].sum() - yc.iloc[i].sum()
    ya.iloc[2, 0] = 2.0
    ya.iloc[0, 4] = 1.0
    source["Va"].iloc[0, :] = s.sum(axis=1).to_numpy() + ya.sum(axis=1).to_numpy() - u.sum(axis=0).to_numpy()
    source["Ea"].iloc[0, :] = np.arange(1, len(s) + 1)
    source["Ec"].iloc[0, :] = np.arange(1, s.shape[1] + 1) / 10
    source["EY"].iloc[0, :] = [1, 2, 3, 4, 5]
    source["VY"] = pd.DataFrame(0.25, index=source["Va"].index, columns=yc.columns)
    db.matrices["baseline"] = {
        name: frame.astype(pd.SparseDtype(float, 0.0)) if request.param else frame
        for name, frame in source.items()
    }
    return db


def expected_imports(source, selected, by, partners):
    """Scalar source-cell oracle, including observed cross-border supply."""
    s, u, ya, yc = (dense(source[name]) for name in ("S", "U", "Ya", "Yc"))
    expected = {name: {} for name in ("Va", "Vc", "VY")}

    def add(block, origin, item, buyer, value):
        if value == 0:
            return
        label = (origin, item, "imports") if partners else (item, "imports")
        key = (label, buyer)
        expected[block][key] = expected[block].get(key, 0.0) + value

    for block, frame in (("Va", u), ("VY", yc)):
        for commodity in frame.index:
            if commodity[0] in selected:
                continue
            for buyer in frame.columns:
                if buyer[0] not in selected:
                    continue
                amount = frame.loc[commodity, buyer]
                if by == "commodity":
                    add(block, commodity[0], commodity[2], buyer, amount)
                elif amount:
                    for producer in s.index:
                        weight = s.loc[producer, commodity] / s[commodity].sum()
                        add(block, producer[0], producer[2], buyer, weight * amount)
    for producer in s.index:
        if producer[0] in selected:
            continue
        for commodity in s.columns:
            if commodity[0] in selected:
                item = commodity[2] if by == "commodity" else producer[2]
                add("Vc", producer[0], item, commodity, s.loc[producer, commodity])
        for buyer in ya.columns:
            if buyer[0] not in selected:
                continue
            amount = ya.loc[producer, buyer]
            if by == "activity":
                add("VY", producer[0], producer[2], buyer, amount)
            elif amount:
                for commodity in s.columns:
                    weight = s.loc[producer, commodity] / s.loc[producer].sum()
                    add("VY", producer[0], commodity[2], buyer, weight * amount)
    return expected


@pytest.mark.parametrize("by", ["commodity", "activity"])
@pytest.mark.parametrize("partners", [False, True])
@pytest.mark.parametrize("selected", [["IT"], ["IT", "FR"]])
def test_import_cells_and_balances_match_independent_source(database, by, partners, selected):
    source = {name: frame.copy() for name, frame in database.matrices["baseline"].items()}
    original_x = {name: dense(database.query(name)) for name in ("Xa", "Xc")}
    result = database.to_region_subset(
        selected, imports_by=by, trade_mode="by_region" if partners else "aggregate",
        inplace=False,
    )
    expected = expected_imports(source, selected, by, partners)
    for name, values in expected.items():
        frame = dense(result.query(name))
        actual = frame.loc[frame.index.get_level_values("Factor of production") == "imports"]
        for row in actual.index:
            for col in actual.columns:
                assert actual.loc[row, col] == pytest.approx(values.get((row, col), 0))
        for (row, col), value in values.items():
            assert frame.loc[row, col] == pytest.approx(value)
    for name in ("S", "U", "Ea", "Ec"):
        original = dense(source[name])
        result_frame = dense(result.query(name))
        pd.testing.assert_frame_equal(result_frame, original.loc[result_frame.index, result_frame.columns])
    for name, original in original_x.items():
        actual = dense(result.query(name))
        np.testing.assert_allclose(actual, original.loc[actual.index], atol=1e-12)
    # No expenditure disappears when foreign final uses are moved into VY.
    original_budget = sum(dense(source[name]).sum(axis=0) for name in ("Ya", "Yc", "VY"))
    local_fd = original_budget.index.get_level_values(0).isin(selected)
    result_budget = sum(dense(result.query(name)).sum(axis=0) for name in ("Ya", "Yc", "VY"))
    np.testing.assert_allclose(result_budget.loc[original_budget.index[local_fd]], original_budget[local_fd])
    cols = source["EY"].columns[local_fd]
    pd.testing.assert_frame_equal(dense(result.query("EY")).loc[:, cols], dense(source["EY"]).loc[:, cols])
    actual_vy = dense(result.query("VY"))
    for factor in source["VY"].index:
        actual = actual_vy.xs(factor, level="Factor of production").loc[:, cols].sum(axis=0)
        np.testing.assert_allclose(actual, dense(source["VY"]).loc[factor, cols])
    prefix = "Commodity" if by == "commodity" else "Activity"
    ordinary = result.query("Va").index.get_level_values("Factor of production") != "imports"
    assert result.query("Va").index.get_level_values(prefix)[ordinary].isna().all()
    assert result.get_index("Activity", region="IT") == ["manufacturing", "wind"]
    assert result.get_index("Commodity", region="IT") == ["goods", "electricity"]
    assert result.get_index("Consumption category", region="IT")[:2] == ["HH", "GOV"]
    for name, original in source.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], original)


@pytest.mark.parametrize("by", ["commodity", "activity"])
def test_chenery_moses_supply_imports_enter_vc_and_exports_enter_ya(database, by):
    database.to_chenery_moses()
    source = {name: frame.copy() for name, frame in database.matrices["baseline"].items()}
    result = database.to_single_region("IT", imports_by=by, inplace=False)
    expected = expected_imports(source, ["IT"], by, False)
    for name, values in expected.items():
        frame = dense(result.query(name))
        for (row, col), value in values.items():
            assert frame.loc[row, col] == pytest.approx(value)
    vc = dense(result.query("Vc"))
    assert vc.loc[vc.index.get_level_values("Factor of production") == "imports"].sum().sum() > 0
    assert dense(result.query("Ya")).iloc[:, -1].sum() > 0
    # Both sides of the native monetary accounting remain balanced.
    s, u = (dense(result.query(name)) for name in ("S", "U"))
    np.testing.assert_allclose(s.sum(axis=1) + dense(result.query("Ya")).sum(axis=1),
                               u.sum(axis=0) + dense(result.query("Va")).sum(axis=0))
    np.testing.assert_allclose(s.sum(axis=0) + vc.sum(axis=0),
                               u.sum(axis=1) + dense(result.query("Yc")).sum(axis=1))


def test_sparse_extraction_avoids_unified_queries_densification_and_inverse(database, monkeypatch):
    if not isinstance(database.query("S").dtypes.iloc[0], pd.SparseDtype):
        pytest.skip("Sparse-path guard")
    query = database.query

    def native_query(matrices=None, *args, **kwargs):
        names = [matrices] if isinstance(matrices, str) else matrices
        assert not set(names or []) & {"Z", "Y", "X", "V", "E", "s", "u"}
        return query(matrices, *args, **kwargs)

    monkeypatch.setattr(database, "query", native_query)
    with patch.object(pd.DataFrame, "to_numpy", side_effect=AssertionError("dense frame")), \
         patch.object(np.linalg, "inv", side_effect=AssertionError("inverse")):
        database.to_single_region("IT", imports_by="activity")
    assert all(isinstance(t, pd.SparseDtype) for t in database.matrices["baseline"]["Va"].dtypes)


def test_undefined_producer_allocation_leaves_source_unchanged(database):
    s = dense(database.query("S"))
    s.iloc[:, 3] = 0
    database.matrices["baseline"]["S"] = s
    source = {name: frame.copy() for name, frame in database.matrices["baseline"].items()}
    history = deepcopy(database.meta._history)
    with pytest.raises(WrongInput, match="zero net supply.*DE.*electricity"):
        database.to_single_region("IT", imports_by="activity")
    for name, frame in source.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], frame)
    assert database.meta._history == history
    # Product imports do not require a producer-allocation assumption.
    database.to_single_region("IT", imports_by="commodity")


def test_alias_and_wrapper_keep_scenarios_and_account_units_consistent(database):
    database.clone_scenario("baseline", "policy")
    database.rename_baseline_scenario("reference")
    result = database.to_single_region("IT", imports_by="commodity", trade_mode="by_sector", inplace=False)
    equivalent = database.to_region_subset(["IT"], imports_by="commodity", externalized_trade_layout="sectorized", inplace=False)
    assert result.scenarios == ["reference"]
    assert database.scenarios == ["reference", "policy"]
    for name, frame in result.matrices["baseline"].items():
        pd.testing.assert_frame_equal(frame, equivalent.matrices["baseline"][name])
    assert result.units["Factor of production"].loc["imports", "unit"] == "EUR"
    result.keep_extensions(["CO2"])
    assert result.query("EY").shape[0] == 1
    assert result.query("VY").index.equals(result.query("Va").index)


@pytest.mark.parametrize("bad", ["sector", "producer", 1, []])
def test_invalid_import_classification_is_rejected(database, bad):
    with pytest.raises(WrongInput, match="imports_by"):
        database.to_single_region("IT", imports_by=bad, inplace=False)


def test_default_extraction_retains_imported_final_demand(database):
    original = dense(database.query("Yc"))
    imported = original.loc[original.index.get_level_values(0) != "IT",
                            original.columns.get_level_values(0) == "IT"].sum(axis=0)
    ya = dense(database.query("Ya"))
    imported += ya.loc[ya.index.get_level_values(0) != "IT", imported.index].sum(axis=0)
    database.to_single_region("IT")
    np.testing.assert_allclose(database.query("VY").loc["imports", imported.index], imported)


def test_missing_direct_accounts_are_zero_and_existing_ones_are_not_overwritten(database):
    for name in ("EY", "VY"):
        database.matrices["baseline"].pop(name)
    database.to_single_region("IT", imports_by="commodity")
    assert dense(database.query("EY")).eq(0).all().all()
    assert dense(database.query("VY")).xs("VA", level="Factor of production").eq(0).all().all()
    assert dense(database.query("VY")).loc[("electricity", "imports")].sum() > 0


def test_structured_factor_rows_preserve_receiving_region(database):
    for name in ("Va", "Vc", "VY"):
        frame = database.matrices["baseline"][name]
        frame.index = pd.MultiIndex.from_tuples(
            [("IT", value) for value in frame.index],
            names=["Region", "Factor of production"],
        )
    database.to_region_subset(["IT", "FR"], imports_by="commodity")
    va = dense(database.query("Va"))
    assert va.loc[(None, "electricity", "imports"), ("IT", "Activity", "manufacturing")] == pytest.approx(8)
    assert va.loc[("IT", None, "VA"), ("IT", "Activity", "manufacturing")] > 0
    assert va.loc[(None, "electricity", "imports"), ("FR", "Activity", "coal")] == pytest.approx(2)
    assert database.query("VY").index.equals(database.query("Vc").index)


def test_signed_imports_and_reordered_axes_keep_source_values(database):
    frame = dense(database.query("Yc"))
    frame.loc[("DE", "Commodity", "electricity"), ("IT", "Consumption category", "GOV")] = -2
    database.matrices["baseline"]["Yc"] = frame
    expected = database.to_single_region("IT", imports_by="activity", inplace=False)
    for name in ("U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"):
        database.matrices["baseline"][name] = database.matrices["baseline"][name].iloc[::-1, ::-1]
    actual = database.to_single_region("IT", imports_by="activity", inplace=False)
    for name, frame in expected.matrices["baseline"].items():
        aligned = actual.query(name).reindex(index=frame.index, columns=frame.columns)
        pd.testing.assert_frame_equal(dense(aligned), dense(frame))
    assert actual.query("VY").loc[("coal", "imports"), ("IT", "Consumption category", "GOV")] == pytest.approx(-1.5)


def test_nonfinite_imports_fail_without_repair(database):
    frame = dense(database.query("U"))
    frame.iloc[3, 0] = np.nan
    database.matrices["baseline"]["U"] = frame
    with pytest.raises(WrongInput, match="finite flow"):
        database.to_single_region("IT", imports_by="commodity")
    assert np.isnan(database.query("U").iloc[3, 0])
    assert len(database.regions) == 3


def test_import_classification_is_sut_only():
    from mario import load_test

    with pytest.raises(WrongInput, match="imports_by for IOT"):
        load_test("IOT").to_single_region("Reg1", imports_by="commodity", inplace=False)


@pytest.mark.parametrize("by,label", [("commodity", ("goods", "imports")),
                                      ("activity", ("services", "imports"))])
def test_zero_import_rows_keep_the_external_classification(database, by, label):
    for name in ("U", "Ya", "Yc"):
        frame = dense(database.query(name))
        frame.loc[frame.index.get_level_values(0) != "IT",
                  frame.columns.get_level_values(0) == "IT"] = 0
        database.matrices["baseline"][name] = frame
    database.to_single_region("IT", imports_by=by)
    for name in ("Va", "Vc", "VY"):
        assert dense(database.query(name)).loc[label].eq(0).all()


def test_imported_final_demand_survives_excel_roundtrip(database, tmp_path):
    from mario import parse_from_excel

    result = database.to_single_region("IT", imports_by="commodity", inplace=False)
    path = tmp_path / "national_sut.xlsx"
    result.to_excel(path=str(path), flows=True, coefficients=False)
    loaded = parse_from_excel(str(path), table="SUT", mode="flows", matrix_layouts={"V": "Commodity"})
    for name in ("S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "VY", "EY"):
        expected = dense(result.query(name))
        actual = dense(loaded.query(name)).reindex(index=expected.index, columns=expected.columns)
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("partners", [False, True])
def test_import_only_activity_labels_can_be_aggregated_without_adding_nodes(database, partners):
    database.to_single_region("IT", imports_by="activity", trade_mode="by_region" if partners else "aggregate")
    assert "services" not in database.get_index("Activity")
    before = dense(database.query("VY"))
    database.aggregate(
        {"Activity": pd.DataFrame({"Aggregation": ["foreign services"]}, index=["services"])},
        levels=["Activity"], zero_output_epsilon=None,
    )
    assert database.get_index("Activity") == ["manufacturing", "wind"]
    assert "foreign services" in database.query("VY").index.get_level_values("Activity")
    assert "services" not in database.query("VY").index.get_level_values("Activity")
    np.testing.assert_allclose(dense(database.query("VY")).sum(axis=0), before.sum(axis=0))
