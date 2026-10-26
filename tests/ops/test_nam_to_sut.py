"""National FIGARO projection and composition with the existing IO models."""

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

import mario
from mario.log_exc.exceptions import DataMissing, NotImplementable, WrongInput
from tests.parsers.test_nam import dense, write_bulk_source, write_figaro_source


@pytest.fixture
def nam(tmp_path):
    source = tmp_path / "FIGARO_NAM_IT_2023.xlsx"
    # Two active activities make A/C's supply-inverse assumptions testable.
    def second_activity(codes, flows):
        for row, column, amount in [("C10", "CPA_C10", 50), ("CPA_C10", "C10", 10),
                                    ("D11", "C10", 40), ("CPA_C10", "P3_S14", 40)]:
            flows[codes.index(row), codes.index(column)] = amount
        for row, column in [("S14", "D11"), ("P3_S14", "S14")]:
            flows[codes.index(row), codes.index(column)] += 40
    write_figaro_source(source, change=second_activity)
    return mario.parse_figaro(source, table="NAM")


def flat(frame):
    frame = dense(frame).copy()
    if isinstance(frame.index, pd.MultiIndex):
        frame.index = frame.index.get_level_values("Item")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values("Item")
    return frame


def edit(nam, block, row, column, amount, scenario="baseline"):
    frame = dense(nam.get_block(block, scenario))
    frame.iloc[frame.index.get_level_values("Item").get_loc(row),
               frame.columns.get_level_values("Item").get_loc(column)] += amount
    nam.set_block(block, frame, scenario)


def test_projection_conserves_production_trade_and_final_demand(nam):
    before = {name: nam.get_block(name) for name in nam.list_matrices()}
    sut = nam.to_sut()
    assert sut.table_type == "SUT" and nam.table_type == "NAM"
    for name in ("S", "U"):
        pdt.assert_frame_equal(flat(sut.query(name)), flat(nam.get_block(name)), check_names=False)
    va, vy, y = (flat(sut.query(name)) for name in ("Va", "VY", "Yc"))
    assert va.loc["D11", "A01"] == 50
    assert va.loc["Imports P7", "A01"] == 10
    assert vy.loc["D21X31", "P51G"] == 2
    assert vy.loc["Imports P7", "P51G"] == 2
    assert vy.loc["Purchases abroad P33", "P3_S14"] == 1
    assert vy.loc["External settlement P7", "P6"] == 2
    assert y.loc["CPA_A01", "P51G"] == 10  # not the asset acquisition/routing total 14
    assert y.loc["CPA_A01", "P6"] == 10  # not exports plus non-product settlement
    assert y.loc["CPA_C10", "P3_S14"] == 40
    assert set(sut.get_index("Factor of production")).isdisjoint({"F41", "D9", "B9FX9"})
    for value in sut.info["nam_to_sut"]["checks"]["baseline"].values():
        assert value == pytest.approx(0, abs=1e-12)
    Xa = sut.resolve("Xa").iloc[:, 0]
    np.testing.assert_allclose(sut.resolve("u").to_numpy() * Xa.to_numpy(), sut.query("U"))
    assert sut.units["Activity"].iloc[0, 0] == "EUR x 1e+06"
    assert tuple(before) == nam.list_matrices()
    for name, frame in before.items():
        pdt.assert_frame_equal(nam.get_block(name), frame)
    assert sut.info["nam_to_sut"]["source_audit"] == nam.info["figaro_nam"]
    sut.info["nam_to_sut"]["source_audit"]["source_reconciled"] = False
    assert nam.info["figaro_nam"]["source_reconciled"]


def test_all_scenarios_are_independent_and_unbalanced_edits_are_preserved(nam):
    nam.clone_scenario("baseline", "policy")
    edit(nam, "U", "CPA_A01", "A01", 3, "policy")
    sut = nam.to_sut(tech_assumption="PT")
    assert sut.scenarios == ["baseline", "policy"]
    assert sut.meta.tech_assumption == "product-based"
    assert flat(sut.query("U", scenarios="policy")).loc["CPA_A01", "A01"] == 43
    assert sut.info["nam_to_sut"]["checks"]["policy"]["max_activity_imbalance"] == 3
    assert sut.info["nam_to_sut"]["checks"]["baseline"]["max_activity_imbalance"] == 0
    assert flat(sut.query("U")).loc["CPA_A01", "A01"] == 40


def test_reordered_native_axes_are_aligned_by_account_identity(nam):
    expected = nam.to_sut()
    for name in ("S", "U", "Va_f", "Yc_c"):
        frame = nam.get_block(name).iloc[::-1, ::-1]
        nam.set_block(name, frame)
    actual = nam.to_sut()
    for name in ("S", "U", "Va", "Yc"):
        pdt.assert_frame_equal(actual.query(name), expected.query(name))


@pytest.mark.parametrize("method", ["A", "B", "C", "D"])
def test_nam_to_iot_matches_explicit_composition_for_every_scenario(nam, method):
    nam.clone_scenario("baseline", "policy")
    edit(nam, "U", "CPA_A01", "A01", 3, "policy")
    output = nam.to_iot(method)
    assert output.table_type == "IOT"
    assert output.scenarios == nam.scenarios == ["baseline", "policy"]
    assert output.info["nam_to_iot"]["method"] == method
    for scenario in nam.scenarios:
        sut = nam.to_sut()
        sut.matrices = {"baseline": dict(sut.matrices[scenario])}
        expected = sut.to_iot(method, inplace=False)
        for name in ("Z", "Y", "V", "VY", "E", "EY"):
            pdt.assert_frame_equal(output.query(name, scenarios=scenario), expected.query(name))
    assert nam.table_type == "NAM"
    assert flat(nam.get_block("U", "policy")).loc["CPA_A01", "A01"] == 43


def test_iot_composition_calls_public_to_sut(nam, monkeypatch):
    from mario.api.nam import NAMDatabase
    actual = NAMDatabase.to_sut
    called = []
    def recorded(self, **kwargs):
        called.append(kwargs)
        return actual(self, **kwargs)
    monkeypatch.setattr(NAMDatabase, "to_sut", recorded)
    nam.to_iot("B", region="IT")
    assert called == [{"region": "IT"}]


def test_activity_demand_preserves_existing_iot_assumption_guards(nam):
    edit(nam, "Ya_c", "A01", "P3_S14", 5)
    assert flat(nam.to_sut().query("Ya")).loc["A01", "P3_S14"] == 5
    for method in ("A", "C"):
        with pytest.raises(NotImplementable, match="Ya"):
            nam.to_iot(method)
    for method in ("B", "D"):
        assert nam.to_iot(method).table_type == "IOT"
    with pytest.raises(WrongInput, match="method"):
        nam.to_iot("bad")


def test_only_required_production_flows_need_be_available(nam):
    nam.set_block("AF_d", None, metadata={"presence": "unavailable"})
    assert nam.to_sut().table_type == "SUT"
    nam.set_block("U", None, metadata={"presence": "unavailable"})
    with pytest.raises(DataMissing, match="U.*baseline"):
        nam.to_sut()


@pytest.mark.parametrize(("block", "row", "column"), [
    ("C_o", "CPA_A01", "B8_S1"), ("Yc_inv", "CPA_A01", "NP"),
    ("O_a", "B9FX9", "A01"),
])
def test_unknown_nonzero_routes_are_not_dropped(nam, block, row, column):
    edit(nam, block, row, column, 1)
    with pytest.raises(NotImplementable, match=block):
        nam.to_sut()


def test_typed_direct_asset_purchases_and_direct_factors_are_projected(nam):
    edit(nam, "Yc_inv", "CPA_A01", "N111G", 8)
    edit(nam, "F_o", "D11", "P51G", 3)
    output = nam.to_sut()
    assert flat(output.Yc).loc["CPA_A01", "P51G"] == 18
    assert flat(output.VY).loc["D11", "P51G"] == 3


def test_bulk_memberships_and_native_reload_keep_projection_recipe(tmp_path):
    path = tmp_path / "FIGARO_NAM_2023.csv"
    write_bulk_source(path)
    nam = mario.parse_figaro(path, table="NAM", countries="IT")
    edit(nam, "Yc_cap_d", "CPA_A01", "S11", 7)
    expected = nam.to_sut()
    assert expected.get_index("Activity") == nam.get_index("a")
    assert "C10-C12" in expected.get_index("Activity")  # source codes unchanged
    assert flat(expected.Yc).loc["CPA_A01", "P5M"] == 7
    native = tmp_path / "native.xlsx"
    nam.to_excel(native)
    restored = mario.parse_from_excel(native, table="NAM", mode="flows").to_sut()
    for name in ("S", "U", "Yc", "Ya", "Va", "Vc", "VY"):
        pdt.assert_frame_equal(restored.query(name), expected.query(name))


def test_multi_country_selection_and_cross_border_payments(tmp_path):
    paths = [tmp_path / f"FIGARO_NAM_{region}_2023.xlsx" for region in ("IT", "FR")]
    for path, region in zip(paths, ("IT", "FR")):
        write_figaro_source(path, region=region)
    nam = mario.parse_figaro(paths, table="NAM")
    with pytest.raises(WrongInput, match="region="):
        nam.to_sut()
    with pytest.raises(WrongInput, match="Unknown"):
        nam.to_sut(region="XX")
    selected = nam.to_sut(region="FR")
    assert selected.get_index("Region") == ["FR"]
    assert selected.info["nam_to_sut"]["source_audit"]["reference_economies"] == ["FR"]
    frame = dense(nam.U)
    frame.loc[("FR", "Commodity", "CPA_A01"), ("IT", "Activity", "A01")] = 1
    with pytest.raises(ValueError, match="cannot mix reference economies"):
        nam.set_block("U", frame)


@pytest.mark.parametrize("representation", ["use_imports", "supply_imports"])
def test_other_sources_and_import_authorities_need_explicit_recipes(tmp_path, representation):
    path = tmp_path / "template.xlsx"
    mario.write_parse_template(path, table="NAM", sets={"IT": {"a": ["A"], "c": ["C"]}},
        units={"currency": "EUR", "scale": 1e6, "period": 2023}, representation=representation)
    nam = mario.parse_from_excel(path, table="NAM", mode="flows")
    if representation == "supply_imports":
        nam.info["figaro_nam"] = {}
    with pytest.raises(NotImplementable, match="FIGARO-NAM.*use_imports"):
        nam.to_sut()


@pytest.mark.parametrize("companion", [False, True], ids=["web-guide", "notebook"])
def test_published_conversion_examples_execute(tmp_path, monkeypatch, companion):
    from tests.docs.test_workflow_examples import ROOT, nam_notebook_cell, python_blocks
    source = tmp_path / "FIGARO_NAM_2023.csv"
    write_bulk_source(source)
    monkeypatch.chdir(tmp_path)
    if companion:
        scope = {"nam": mario.parse_figaro(source, table="NAM", countries="IT")}
        code = nam_notebook_cell("notebooks/parsers/figaro/walkthrough_figaro.ipynb", "nam-sut-iot")
        exec(code, scope)
    else:
        scope = {}
        blocks = python_blocks(ROOT / "transformations/nam_to_sut.rst")
        exec(blocks[0], scope)
        exec(blocks[1], scope)
    assert scope["sut"].table_type == "SUT"
    assert scope["iot"].table_type == "IOT"
    assert scope["nam"].table_type == "NAM"
