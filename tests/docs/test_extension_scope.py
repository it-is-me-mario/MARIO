"""Extension groups: reviewed rules cover every loaded satellite label exactly once, per reading."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "doc/scripts"))

import build_extension_scope as ext  # noqa: E402

PUBLISHED = ROOT / "doc/source/_static/data/economy/extension-scope.json"


def families():
    return {f["family"]: f for f in ext.build()["families"]}


def test_published_extension_scope_matches_a_rebuild():
    assert json.loads(PUBLISHED.read_text()) == ext.build()


def test_rules_resolve_known_ambiguities():
    rules = json.loads(ext.RULES.read_text())
    exio, eora = rules["families"]["EXIOBASE"], rules["families"]["EORA"]
    assert ext.classify("CO - combustion - air", exio)[0] == "air"
    assert ext.classify("CO2 - combustion - air", exio)[0] == "ghg"
    assert ext.classify("Cd (soil - Emiss)", exio)[0] == "other"
    assert ext.classify("Water Consumption Blue (resource)", exio)[0] == "water"
    assert ext.classify("Plastics (waste_sup)", exio)[0] == "waste"
    assert ext.classify("IEA GHG emissions (Gg) and energy use - IEA - DEPRECATED - Population", eora)[0] == "economic"
    assert ext.gas_of("GWP_100_AR5_F-gases | Chemical Industry", rules["gases"]) == "fgas"
    assert ext.gas_of("GHG | Total by substance", rules["gases"]) == "total"


def test_readings_keep_their_own_accounts():
    data = ext.build()
    f = {x["family"]: x for x in data["families"]}
    exio = {v["variant"]: v["readings"] for v in f["EXIOBASE"]["variants"]}
    assert set(exio) == {"Monetary", "Hybrid"}
    sizes = {sum(len(c["labels"]) for c in data["sets"][r["set"]].values()) for r in exio["Monetary"]}
    assert len(sizes) > 3  # releases and year groups differ, so no union is reported
    assert exio["Monetary"][0]["release"] == "3.11.2"  # newest first
    assert {v["variant"] for v in f["EORA"]["variants"]} == {"Eora1 26", "Eora2 · Common"}
    emerging = data["sets"][f["EMERGING"]["variants"][0]["readings"][0]["set"]]["ghg"]
    assert emerging["gases"] == ["co2"] and len(emerging["labels"]) == 7
    assert set(data["sets"][f["WIOD"]["variants"][0]["readings"][0]["set"]]) == {"employment", "economic"}
    assert f["ADB"]["status"] == "partial" and f["ADB"]["releases_without"]
    assert {f[name]["status"] for name in ["FIGARO", "OECD ICIO"]} == {"restricted"}
    assert f["CEDA"]["status"] == "not_published" and not f["CEDA"]["variants"]
    assert "USEEIO" not in f and "BEA" not in f  # National models are omitted.
