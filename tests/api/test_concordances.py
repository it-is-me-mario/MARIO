"""Concordances follow parser identity, current sets and qualified source routes."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from mario.log_exc.exceptions import WrongInput
from mario.model.concordances import _bundle, _project
from tests.api.test_regional_indexes import regional_database


def sut(source="GLORIA (release 060)", activities=None, commodities=None):
    activities = activities or {"IT": ["Growing wheat", "Growing rice"], "DE": ["Growing wheat"]}
    commodities = commodities or {"IT": ["Growing wheat"], "DE": ["Growing wheat"]}
    db = regional_database(activities, commodities)
    db.meta._add_attribute(source=source)
    return db


def test_gloria_returns_native_item_keys_codes_and_requested_order_without_computing(monkeypatch):
    db = sut()
    history = deepcopy(db.meta._history)
    monkeypatch.setattr(db, "query", lambda *a, **k: pytest.fail("A metadata lookup must not compute matrices"))
    assert db.get_concordances(item="Growing wheat") == {"Growing wheat": ["01.11"]}
    result = db.get_concordances(set="activity", classification="NACE rev2.1",
                                 item=["Growing rice", "Growing wheat", "Growing rice"])
    assert list(result) == ["Growing rice", "Growing wheat"]
    assert result["Growing rice"] == ["01.12"]
    assert db.meta._history == history


def test_region_restricts_actual_membership_and_default_is_the_distinct_union():
    db = sut()
    assert list(db.get_concordances(region="DE")) == ["Growing wheat"]
    assert list(db.get_concordances()) == ["Growing wheat", "Growing rice"]
    with pytest.raises(WrongInput, match="Unknown items"):
        db.get_concordances(region="DE", item="Growing rice")
    with pytest.raises(WrongInput, match="Unknown region"):
        db.get_concordances(region="missing")


def test_details_retain_sources_qualifications_and_are_independent_results():
    db = sut()
    result = db.get_concordances(item="Growing wheat", details=True)["Growing wheat"]
    assert result["codes"] == ["01.11"]
    assert result["matches"]["01.11"]["name"] == "Growing of cereals, other than rice, leguminous crops and oil seeds"
    route = result["matches"]["01.11"]["routes"][0]
    assert route["status"] == "reviewed"
    assert any(s["source"] == "S22" and s["location"] for s in route["steps"])
    assert all(sid in result["sources"] for sid in [s["source"] for s in route["steps"]])
    result["codes"].clear()
    route["steps"][0]["location"] = "mutated"
    fresh = db.get_concordances(item="Growing wheat", details=True)["Growing wheat"]
    assert fresh["codes"] == ["01.11"]
    assert fresh["matches"]["01.11"]["routes"][0]["steps"][0]["location"] != "mutated"


@pytest.mark.parametrize("classification, expected", [("NACE Rev. 2", ["01.11"]),
    ("ISIC Rev. 4", ["0111"]), ("ISIC 3.1", ["0111"]), ("NACE 1.1", ["01.11", "01.12"])])
def test_explicit_revisions_and_other_activity_classifications(classification, expected):
    assert sut().get_concordances(classification=classification, item="Growing wheat") == {"Growing wheat": expected}


def test_exiobase_commodity_hs_uses_supplied_product_aliases_and_preserves_leading_zeroes():
    db = sut("EXIOBASE monetary SUT", {"IT": ["Cultivation of wheat"]}, {"IT": ["Wheat", "Cattle"]})
    result = db.get_concordances(set="commodity", classification="HS2007", item="Wheat", details=True)["Wheat"]
    assert result["codes"] == ["100110", "100190"]
    assert result["sources"]["H01"]["filename"] == "ex2hs07_1ton.xlsx"
    assert all(route["status"] == "partial" for m in result["matches"].values() for route in m["routes"])
    cattle = db.get_concordances(set="commodity", classification="HS", item="Cattle")["Cattle"]
    assert cattle and all(len(code) == 6 and code.startswith("01") for code in cattle)
    with pytest.raises(WrongInput, match="Unknown classification"):
        db.get_concordances(set="commodity", classification="HS 2022")


def test_current_product_links_stay_qualified_and_secondary_bridges_expose_direction():
    db = sut("EXIOBASE monetary SUT", {"IT": ["Cultivation of paddy rice"]}, {"IT": ["Wheat"]})
    assert db.get_concordances(classification="NACE", item="Cultivation of paddy rice") == {"Cultivation of paddy rice": ["01.12"]}
    assert db.get_concordances(set="Commodity", classification="CPA")["Wheat"] == ["01.11.11", "01.11.12"]
    old = db.get_concordances(classification="NACE Rev. 2", details=True)["Cultivation of paddy rice"]
    assert old["codes"] == ["01.12"]
    assert old["matches"]["01.12"]["routes"][0]["steps"][-1]["direction"] == "reverse"
    assert old["matches"]["01.12"]["routes"][0]["status"] == "partial"


def test_unknown_and_aggregated_native_identities_remain_empty_instead_of_fuzzy_matches():
    db = sut(activities={"IT": ["All farming", "Growing wheat (renamed)"]}, commodities={"IT": ["All products"]})
    assert db.get_concordances() == {"All farming": [], "Growing wheat (renamed)": []}
    assert db.get_concordances(details=True)["All farming"]["status"] == "unknown_native_identity"
    with pytest.raises(WrongInput, match="Unknown items"):
        db.get_concordances(item="Growing wheat")


@pytest.mark.parametrize("bad", ["Region", "Satellite account", "Sector"])
def test_sut_rejects_nonproductive_or_ambiguous_set(bad):
    with pytest.raises(WrongInput, match="Activity.*Commodity"):
        sut().get_concordances(set=bad)


def test_unknown_source_and_unsupported_release_explain_unavailability():
    db = sut("My custom database")
    with pytest.raises(WrongInput, match="source metadata"):
        db.get_concordances()
    with pytest.raises(WrongInput, match="release 060"):
        sut("GLORIA (release 057)").get_concordances()
    with pytest.raises(WrongInput, match="unavailable"):
        sut().get_concordances(classification="HS2007")


@pytest.mark.parametrize("method, kind, classification", [("B", "Commodity", "CPA 2.2"), ("D", "Activity", "NACE Rev. 2.1")])
def test_transformed_iot_remembers_which_native_side_became_sectors(method, kind, classification):
    db = sut()
    db.to_iot(method=method)
    assert db.meta.sector_type == kind
    assert list(db.get_concordances()) == db.get_index("Sector", flat=True)
    assert db.get_concordances(item="Growing wheat", details=True)["Growing wheat"]["classification"] == classification
    with pytest.raises(WrongInput, match="represents"):
        db.get_concordances(set="Activity" if kind == "Commodity" else "Commodity")


def test_available_classifications_follow_native_set_and_source():
    gloria = sut().available_concordances
    assert "NACE Rev. 2.1" in gloria["Activity"]
    assert "CPA 2.2" in gloria["Commodity"]
    assert "HS 2007" not in gloria["Commodity"]
    exio = sut("EXIOBASE monetary SUT").available_concordances
    assert "HS 2007" in exio["Commodity"]
    assert "HS 2007" not in exio["Activity"]


def test_bonsai_hiot_activity_projection_retains_actual_reference_product_keys():
    db = sut("BONSAI HIOT b2", {"IT": ["A_POWG"]}, {"IT": ["C_elec_POWG"]})
    db.to_iot(method="B")
    assert db.get_concordances(set="Sector", classification="CPA") == {"C_elec_POWG": ["35.11.00"]}
    assert db.get_concordances(set="Sector", classification="NACE") == {"C_elec_POWG": ["35.11"]}
    detail = db.get_concordances(set="Activity", classification="NACE", details=True)["C_elec_POWG"]
    assert detail["matches"]["35.11"]["routes"][0]["nodes"][:2] == [["BONSAIHIOT", "C_elec_POWG"], ["BONSAIA", "A_POWG"]]


@pytest.mark.parametrize("hybrid", [False, True])
def test_product_iot_source_is_recognized_without_new_transformation_metadata(hybrid):
    source = "EXIOBASE Hybrid" if hybrid else "EXIOBASE monetary IOT (version 3.11.2, pxp)"
    db = sut(source, {"IT": ["Cultivation of paddy rice"]}, {"IT": ["Paddy rice"]})
    db.to_iot(method="B")
    del db.meta.sector_type
    db.meta._history.clear()
    assert db.get_concordances(details=True)["Paddy rice"]["classification"] == "CPA 2.2"
    assert "01.12.00" in db.get_concordances()["Paddy rice"]


def test_real_exiobase_parser_metadata_selects_native_concordance(tmp_path):
    from mario import parse_exiobase_3
    from tests.parsers.test_exiobase_iot_parser import _write_legacy_exiobase
    _write_legacy_exiobase(tmp_path)
    for path in tmp_path.rglob('*.txt'):
        text = path.read_text().replace('sec_a', 'Cultivation of paddy rice').replace('sec_b', 'Cultivation of wheat')
        path.write_text(text)
    db = parse_exiobase_3(tmp_path)
    assert db.get_concordances(item='Cultivation of paddy rice') == {'Cultivation of paddy rice': ['01.12']}
    assert db.database_profile['ghg']['selected_profile'] == 'exiobase_monetary'


def test_broad_bonsai_anchors_are_exposed_only_at_their_supplied_level():
    db = sut("BONSAI Balanced HSUT", {"IT": ["A_CMNT"]}, {"IT": ["C_CMNT"]})
    assert db.get_concordances(classification="NACE2") == {"A_CMNT": ["23.5"]}
    assert db.get_concordances(classification="NACE2.1") == {"A_CMNT": []}


def test_packaged_primary_concordances_equal_the_published_explorer_for_every_native_item():
    root = Path(__file__).resolve().parents[2]
    published = json.loads((root / 'doc/source/_static/data/economy/sectoral-scope.json').read_text())
    for kind, columns in published['columns'].items():
        target = 'NACE2.1' if kind == 'activity' else 'CPA2.2'
        for column in columns:
            bundle = _bundle(column['family'])
            profile = next(p for p in bundle['profiles'] if p['id'] == column['id'])
            for native, original in zip(profile['native'], column['native']):
                assert native['code'] == original['code']
                assert list(_project(native, profile, bundle, target, False)) == sorted(original['links']), (column['id'], native['code'])
