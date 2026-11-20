import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from tests.api.test_coremodel import (
    _build_electricity_mix_sut_database,
    _build_supply_mix_sut_database,
)


SELECT = dict(
    model="GCAM-test", scenario="Custom policy", year=2050, regions={"ITA": "Italy"}
)
MARKET = "Electricity (generation)"


def electricity():
    total = "Secondary Energy|Electricity"
    values = {
        "Coal": 1,
        "Gas": 1,
        "Nuclear": 1,
        "Hydro": 1,
        "Wind": 4,
        "Oil": 1,
        "Biomass": 1,
        "Geothermal": 1,
        "Solar|PV": 1,
        "Solar|CSP": 1,
    }
    series = {f"{total}|{label}": value for label, value in values.items()}
    series[total] = sum(values.values())
    return mario.read_iamc(
        pd.DataFrame(
            {
                "Variable": list(series),
                2050: list(series.values()),
                "Region": "Italy",
                "Unit": "EJ/yr",
                "Model": SELECT["model"],
                "Scenario": SELECT["scenario"],
            }
        )
    )


@pytest.mark.parametrize(
    "native_unit,prices,wind",
    [
        ("TJ", None, 4 / 13),
        (
            "EUR",
            "peng-2026",
            4 / (2.76 + 1.47 + 4.08 + 1.2 + 4 + 3.99 + 1.79 + 2.07 + 0.95 + 3.55),
        ),
    ],
)
def test_pool_raw_sut_then_apply_a_second_iam_case(native_unit, prices, wind):
    db = _build_electricity_mix_sut_database()
    units = db.units["Commodity"]
    units.loc[units.index.str.startswith("electricity"), "unit"] = native_unit
    db.clone_scenario("baseline", "previous")
    iam = electricity()
    case = db.shock_from_iam(iam, **SELECT, pool=True, prices=prices)
    assert case == "GCAM-test | Custom policy | 2050"
    market = ("ITA", "Commodity", MARKET)
    flows = db.query("S", scenarios=case)[market].xs(("ITA", "Activity"))
    generators = flows[flows.index.str.startswith("production of electricity")]
    assert generators[
        "production of electricity by wind"
    ] / generators.sum() == pytest.approx(wind)
    nodes = db.get_index("Commodity")
    assert MARKET in nodes and "transmission services of electricity" in nodes
    assert "electricity by coal" not in nodes
    pd.testing.assert_frame_equal(
        db.query("S", scenarios="previous"), db.query("S", scenarios="baseline")
    )
    repeated = db.shock_from_iam(
        iam, **SELECT, prices=prices, target_scenario="second", base_scenario="previous"
    )
    pd.testing.assert_frame_equal(
        db.query("S", scenarios=case), db.query("S", scenarios=repeated)
    )
    with pytest.raises(WrongInput, match="new MARIO scenario"):
        db.shock_from_iam(iam, **SELECT, prices=prices)


def test_failed_shocks_preserve_scenarios_and_original_classification(monkeypatch):
    db = _build_electricity_mix_sut_database()
    baseline = db.query("S").copy()
    history = list(db.meta._history)
    iam = electricity()
    with pytest.raises(WrongInput, match="pool=True"):
        db.shock_from_iam(iam, **SELECT)
    with pytest.raises(WrongInput, match="monetary"):
        db.shock_from_iam(iam, **SELECT, pool=True)
    with pytest.raises(WrongInput, match="Incompatible basis"):
        db.shock_from_iam(iam, **SELECT, pool=True, basis="physical")

    def fail(*args, **kwargs):
        raise WrongInput("Missing donor")

    monkeypatch.setattr(type(db), "update_supply_mix", fail)
    with pytest.raises(WrongInput, match="Missing donor"):
        db.shock_from_iam(iam, **SELECT, pool=True, prices="peng-2026")
    assert db.scenarios == ["baseline"] and db.meta._history == history
    assert "electricity by coal" in db.get_index("Commodity")
    pd.testing.assert_frame_equal(db.query("S"), baseline)


def test_custom_production_mix_and_optional_ngfs_source(monkeypatch):
    db = _build_supply_mix_sut_database()
    baseline = db.query("S").copy()
    iam = electricity()

    def fetch(model, scenarios):
        assert (model, scenarios) == (SELECT["model"], SELECT["scenario"])
        return iam

    monkeypatch.setattr("mario.model.ngfs.download_ngfs", fetch)
    case = db.shock_from_iam(
        **{**SELECT, "regions": {"R1": "Italy"}},
        shock="production_mix",
        commodity="electricity",
        variables={
            "gen coal": "Secondary Energy|Electricity|Coal",
            "gen wind": "Secondary Energy|Electricity|Wind",
        },
        unit="EJ/yr",
        prices={"R1": {"gen coal": 2, "gen wind": 1}},
    )
    flows = db.query("S", scenarios=case)[("R1", "Commodity", "electricity")].xs(
        ("R1", "Activity")
    )
    assert flows["gen wind"] / flows["gen coal"] == pytest.approx(2)
    pd.testing.assert_frame_equal(db.query("S"), baseline)
