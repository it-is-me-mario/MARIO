"""Numerical geography and accounting checks for newly activated producers."""

import numpy as np
import pandas as pd
import pytest

from mario import Database
from mario.log_exc.exceptions import WrongInput
from tests.api.test_regional_indexes import regional_database


REGIONS = ["IT", "DE", "FR"]
ITEMS = ["old", "new", "feed", "extra"]


def recipe_database(kind="IOT", sparse=False):
    """DE/FR produce 100/300 new; IT buys feed 25% domestically/75% DE."""
    level = "Sector" if kind == "IOT" else "Activity"
    axis = pd.MultiIndex.from_product([REGIONS, [level], ITEMS], names=["Region", "Level", "Item"])
    products = ["product", "feed", "extra"] if kind == "Activity" else ITEMS
    inputs = axis if kind == "IOT" else pd.MultiIndex.from_product(
        [REGIONS, ["Commodity"], products], names=axis.names
    )
    demands = pd.MultiIndex.from_product([REGIONS, ["Consumption category"], ["HH"]], names=axis.names)
    u = pd.DataFrame(0., index=inputs, columns=axis)

    def key(region, item):
        return (region, level, item)

    def row(region, item):
        return (region, inputs[0][1], item)

    u.loc[row("IT", "feed"), key("IT", "old")] = .1
    u.loc[row("DE", "feed"), key("IT", "old")] = .3
    u.loc[row("IT", "feed"), key("DE", "new")] = .1
    u.loc[row("DE", "feed"), key("DE", "new")] = .1
    u.loc[row("FR", "feed"), key("FR", "new")] = .6
    u.loc[row("DE", "extra"), key("DE", "new")] = .1
    u.loc[row("FR", "extra"), key("FR", "new")] = .3
    x = pd.Series(0., index=axis)
    for r, item, value in [("IT", "old", 100), ("DE", "new", 100), ("FR", "new", 300),
                           ("IT", "feed", 20), ("DE", "feed", 40), ("FR", "feed", 180),
                           ("DE", "extra", 10), ("FR", "extra", 90)]:
        x.loc[key(r, item)] = value
    flows = u.mul(x, axis=1)
    y = pd.DataFrame(0., index=inputs, columns=demands)
    for r, item, value in [("IT", "old", 100), ("DE", "new", 100), ("FR", "new", 300)]:
        y.loc[row(r, "product" if kind == "Activity" else item), (r, "Consumption category", "HH")] += value
    e = pd.DataFrame(0., index=pd.Index(["CO2"], name="Item"), columns=axis)
    v = pd.DataFrame([1 - u.sum(axis=0)], index=pd.Index(["VA"], name="Item"), columns=axis)
    e.loc["CO2", key("DE", "new")] = 2.
    e.loc["CO2", key("FR", "new")] = 6.
    # Explicitly absent coefficients at the inactive target.
    v.loc[:, key("IT", "new")] = 0.
    if kind == "IOT":
        units = {"Sector": pd.DataFrame({"unit": "EUR"}, index=ITEMS),
                 "Satellite account": pd.DataFrame({"unit": "kg"}, index=["CO2"]),
                 "Factor of production": pd.DataFrame({"unit": "EUR"}, index=["VA"])}
        db = Database(table="IOT", Z=flows, Y=y, E=e.mul(x, axis=1), V=v.mul(x, axis=1),
                      EY=pd.DataFrame(0., index=e.index, columns=demands), units=units, calc_all=False)
    else:
        db = regional_database({r: ITEMS for r in REGIONS}, {r: products for r in REGIONS})
        supply = pd.DataFrame(0., index=axis, columns=inputs)
        for r, _, item in axis:
            product = "product" if kind == "Activity" and item in ["old", "new"] else item
            supply.loc[key(r, item), row(r, product)] = x.loc[key(r, item)]
        blocks = db.matrices["baseline"]
        blocks.update(U=flows, S=supply, Yc=y, Ya=pd.DataFrame(0., index=axis, columns=demands),
                      Ea=e.mul(x, axis=1), Va=v.mul(x, axis=1))
        # Nonzero commodity-side extensions in donors are independently weighted.
        for name, values in [("Ec", [10., 30.]), ("Vc", [.2, .4])]:
            frame = blocks[name].sparse.to_dense()
            for r, value in zip(["DE", "FR"], values):
                frame.loc[:, row(r, "product" if kind == "Activity" else "new")] = value * x.loc[key(r, "new")]
            blocks[name] = frame
    if sparse:
        db.reset_to_coefficients("baseline")
        for name, frame in list(db.matrices["baseline"].items()):
            db.matrices["baseline"][name] = frame.astype(pd.SparseDtype(np.float32, 0.))
    return db


def update(db, kind, **kwargs):
    db.update_supply_mix(
        {"IT": {"old": .5, "new": .5}},
        scenario="policy", clone_from="baseline",
        **({"level": "Activity", "commodities": "product"} if kind == "Activity"
           else {"level": "Commodity"} if kind == "Commodity" else {}),
        **kwargs,
    )


@pytest.mark.parametrize("kind", ["IOT", "Activity", "Commodity"])
@pytest.mark.parametrize("sparse", [False, True], ids=["dense", "sparse"])
def test_new_producer_has_weighted_recipe_with_recipient_sourcing(kind, sparse):
    db = recipe_database(kind, sparse)
    original = {name: frame.copy() for name, frame in db.matrices["baseline"].items()}
    update(db, kind)
    level = "Sector" if kind == "IOT" else "Activity"
    target = ("IT", level, "new")
    input_level = "Sector" if kind == "IOT" else "Commodity"
    u = db.query("z" if kind == "IOT" else "u", scenarios="policy")
    # Weighted total feed .5, using IT's 25/75 domestic/import split.
    for r, value in [("IT", .125), ("DE", .375), ("FR", 0.)]:
        assert u.loc[(r, input_level, "feed"), target] == pytest.approx(value)
    # IT never bought extra: fallback to donor origins .025/.225.
    assert u.loc[("DE", input_level, "extra"), target] == pytest.approx(.025)
    assert u.loc[("FR", input_level, "extra"), target] == pytest.approx(.225)
    assert db.query("e" if kind == "IOT" else "ea", scenarios="policy").loc["CO2", target] == pytest.approx(5.)
    assert db.query("v" if kind == "IOT" else "va", scenarios="policy").loc["VA", target] == pytest.approx(.25)
    assert float(u.loc[:, target].sum()) + float(db.query("v" if kind == "IOT" else "va", scenarios="policy").loc["VA", target]) == pytest.approx(1.)
    production = db.query("X" if kind == "IOT" else "Xa", scenarios="policy")
    assert production.loc[target].iloc[0] == pytest.approx(50.)
    if kind == "Commodity":
        commodity = ("IT", "Commodity", "new")
        assert db.query("s", scenarios="policy").loc[target, commodity] == pytest.approx(1.)
        assert db.query("ec", scenarios="policy").loc["CO2", commodity] == pytest.approx(25.)
        assert db.query("vc", scenarios="policy").loc["VA", commodity] == pytest.approx(.35)
    for name, frame in original.items():
        pd.testing.assert_frame_equal(db.matrices["baseline"][name], frame)
    assert all(isinstance(t, pd.SparseDtype) for t in u.dtypes) == sparse
    if sparse:
        assert all(t.subtype == np.float32 for t in u.dtypes)


@pytest.mark.parametrize("selection", ["DE", ["DE"], {("IT", "new"): "DE"}])
@pytest.mark.parametrize("kind", ["IOT", "Activity", "Commodity"])
def test_explicit_donors_apply_to_each_missing_recipe(selection, kind):
    db = recipe_database(kind)
    update(db, kind, recipe_regions=selection)
    key = ("IT", "Sector" if kind == "IOT" else "Activity", "new")
    recipe = db.query("z" if kind == "IOT" else "u", scenarios="policy").loc[:, key]
    assert recipe.sum() == pytest.approx(.3)
    assert db.query("e" if kind == "IOT" else "ea", scenarios="policy").loc["CO2", key] == pytest.approx(2.)


@pytest.mark.parametrize("answer,expected", [("DE", 2.), ("DE, FR", 5.), ("", 5.)])
def test_prompt_selects_donors_per_recipe(monkeypatch, answer, expected):
    prompts = []
    monkeypatch.setattr("builtins.input", lambda message: prompts.append(message) or answer)
    db = recipe_database()
    update(db, "IOT", recipe_regions="prompt")
    assert len(prompts) == 1
    assert "IT" in prompts[0] and "new" in prompts[0]
    assert db.query("e", scenarios="policy").loc["CO2", ("IT", "Sector", "new")] == pytest.approx(expected)


def test_opt_out_retains_empty_recipe():
    db = recipe_database()
    update(db, "IOT", fill_missing_recipes=False)
    assert db.query("z", scenarios="policy").loc[:, ("IT", "Sector", "new")].sum() == 0


@pytest.mark.parametrize("selection", ["IT", "missing", [], {("IT", "new"): "IT"}])
def test_invalid_or_inactive_donor_does_not_partially_write(selection):
    db = recipe_database()
    with pytest.raises(WrongInput, match="recipe|regions"):
        update(db, "IOT", recipe_regions=selection)
    # Baseline demand stays as observed even if a policy clone was prepared.
    assert db.query("Y").loc[("IT", "Sector", "new")].sum() == 0
    if "policy" in db.scenarios:
        assert db.query("Y", scenarios="policy").loc[("IT", "Sector", "new")].sum() == 0


def test_existing_nonzero_recipes_and_extension_columns_are_preserved():
    db = recipe_database()
    db.reset_to_coefficients("baseline")
    z = db.query("z").copy()
    target = ("IT", "Sector", "new")
    z.loc[("IT", "Sector", "feed"), target] = .17
    db.update_scenarios("baseline", z=z)
    update(db, "IOT")
    assert db.query("z", scenarios="policy").loc[("IT", "Sector", "feed"), target] == .17


def test_sparse_recipe_repair_never_densifies_a_whole_block(monkeypatch):
    db = recipe_database("Activity", sparse=True)
    original = pd.DataFrame.to_numpy

    def guard(frame, *args, **kwargs):
        if all(isinstance(t, pd.SparseDtype) for t in frame.dtypes):
            raise AssertionError("Densified sparse dataframe")
        return original(frame, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_numpy", guard)
    update(db, "Activity")


def test_sourcing_includes_final_demand_purchases():
    db = recipe_database()
    y = db.query("Y").copy()
    y.loc[("FR", "Sector", "feed"), ("IT", "Consumption category", "HH")] = 20.
    db.update_scenarios("baseline", Y=y)
    update(db, "IOT")
    recipe = db.query("z", scenarios="policy").loc[:, ("IT", "Sector", "new")]
    assert recipe.loc[("IT", "Sector", "feed")] == pytest.approx(.5 / 6)
    assert recipe.loc[("DE", "Sector", "feed")] == pytest.approx(.25)
    assert recipe.loc[("FR", "Sector", "feed")] == pytest.approx(.5 / 3)


def test_multiple_new_producers_use_the_same_source_snapshot():
    db = recipe_database()
    db.reset_to_coefficients("baseline")
    y = db.query("Y").copy()
    y.loc[("FR", "Sector", "new"), :] = 0.
    y.loc[("FR", "Sector", "old"), ("FR", "Consumption category", "HH")] = 300.
    z = db.query("z").copy()
    z.loc[:, ("FR", "Sector", "new")] = 0.
    e, v = db.query("e").copy(), db.query("v").copy()
    e.loc[:, ("FR", "Sector", "new")] = 0.
    v.loc[:, ("FR", "Sector", "new")] = 0.
    db.update_scenarios("baseline", z=z, Y=y, e=e, v=v)
    mix = {"IT": {"old": .5, "new": .5}, "FR": {"old": .5, "new": .5}}
    for scenario, shares in [("forward", mix), ("reverse", dict(reversed(list(mix.items()))))]:
        db.update_supply_mix(shares, scenario=scenario, clone_from="baseline")
        for region in ["IT", "FR"]:
            # Only DE was active before the call; IT must never become a donor
            # merely because its imputation ran first.
            assert db.query("e", scenarios=scenario).loc["CO2", (region, "Sector", "new")] == pytest.approx(2.)
    for name in ["z", "Y", "e", "v"]:
        pd.testing.assert_frame_equal(db.query(name, scenarios="forward"), db.query(name, scenarios="reverse"))


def test_nonzero_direct_coefficients_are_retained_during_recipe_fill():
    db = recipe_database()
    db.reset_to_coefficients("baseline")
    target = ("IT", "Sector", "new")
    e, v = db.query("e").copy(), db.query("v").copy()
    e.loc["CO2", target] = 9.
    v.loc["VA", target] = .123
    db.update_scenarios("baseline", e=e, v=v)
    update(db, "IOT")
    assert db.query("e", scenarios="policy").loc["CO2", target] == 9.
    assert db.query("v", scenarios="policy").loc["VA", target] == .123


def test_a_zero_share_or_empty_buyer_filter_does_not_request_a_recipe(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Unexpected recipe prompt"))
    for shares, kwargs in [({"old": 1., "new": 0.}, {}), ({"old": .5, "new": .5}, {"column_regions": []})]:
        db = recipe_database()
        db.update_supply_mix({"IT": shares}, recipe_regions="prompt", **kwargs)


def test_missing_domestic_sut_activity_raises_before_writing_the_mix():
    db = recipe_database("Commodity")
    # Keep the commodity, but remove the matching local activity from every
    # flow block, as in a database with regional classifications.
    target = ("IT", "Activity", "new")
    for name, frame in list(db.matrices["baseline"].items()):
        if target in frame.index:
            frame = frame.drop(index=target)
        if target in frame.columns:
            frame = frame.drop(columns=target)
        db.matrices["baseline"][name] = frame
    with pytest.raises(WrongInput, match="activity.*absent"):
        update(db, "Commodity")
    assert db.query("Yc", scenarios="policy").loc[("IT", "Commodity", "new")].sum() == 0.


def test_imputed_input_column_also_obeys_the_requested_bundle_split():
    db = recipe_database()
    db.reset_to_coefficients("baseline")
    z = db.query("z").copy()
    z.loc[("DE", "Sector", "old"), ("DE", "Sector", "new")] = .1
    db.update_scenarios("baseline", z=z)
    update(db, "IOT", recipe_regions="DE")
    z = db.query("z", scenarios="policy")
    assert z.loc[("IT", "Sector", "old"), ("IT", "Sector", "new")] == pytest.approx(.05)
    assert z.loc[("IT", "Sector", "new"), ("IT", "Sector", "new")] == pytest.approx(.05)


def test_no_active_donor_raises_without_writing_proposed_demand():
    db = recipe_database()
    y = db.query("Y").copy()
    y.loc[[("DE", "Sector", "new"), ("FR", "Sector", "new")], :] = 0.
    # Remove source flows as well, so no stored positive donor output remains.
    db.reset_to_coefficients("baseline")
    db.update_scenarios("baseline", Y=y)
    with pytest.raises(WrongInput, match="No active recipe donors"):
        update(db, "IOT")
    assert db.query("Y", scenarios="policy").loc[("IT", "Sector", "new")].sum() == 0.


def test_electricity_preset_fills_a_newly_activated_generation_recipe(tmp_path):
    from tests.api.test_coremodel import _build_electricity_mix_iot_database

    db = _build_electricity_mix_iot_database()
    db.reset_to_flows("baseline")
    target = ("ITA", "Sector", "production of electricity by wind")
    for name in ["Z", "Y", "E", "V"]:
        frame = db.get_block_as_pandas(name).copy()
        if target in frame.index:
            frame.loc[target, :] = 0.
        if target in frame.columns:
            frame.loc[:, target] = 0.
        db.update_scenarios("baseline", **{name: frame})
    snapshot = tmp_path / "ember.csv"
    pd.DataFrame(
        [("ITA", 2020, "Coal", 50.), ("ITA", 2020, "Wind", 50.),
         ("DEU", 2020, "Coal", 50.), ("DEU", 2020, "Wind", 50.)],
        columns=["ISO3", "Year", "Variable", "Value"],
    ).to_csv(snapshot, index=False)
    db.update_supply_mix("electricity", scenario="policy", clone_from="baseline",
                         ember_path=snapshot, year=2020, recipe_regions="DEU")
    assert db.query("z", scenarios="policy").loc[:, target].sum() == pytest.approx(.25)
    assert db.query("e", scenarios="policy").loc["CO2", target] == pytest.approx(.25)
    assert db.query("v", scenarios="policy").loc["VA", target] == pytest.approx(.25)


@pytest.mark.parametrize("override", [False, True])
def test_shared_sut_activity_needs_consistent_donor_choices(override):
    db = recipe_database("Commodity")
    # Both donor commodities are produced by one activity with its own label.
    for name, frame in list(db.matrices["baseline"].items()):
        for axis_number, axis in enumerate([frame.index, frame.columns]):
            if isinstance(axis, pd.MultiIndex):
                renamed = pd.MultiIndex.from_tuples(
                    [(r, level, "new process" if level == "Activity" and item == "new" else item)
                     for r, level, item in axis], names=axis.names,
                )
                frame = frame.set_axis(renamed, axis=axis_number)
        db.matrices["baseline"][name] = frame
    db._indeces["a"]["main"] = ["new process" if item == "new" else item for item in ITEMS]
    db.units["Activity"] = db.units["Activity"].rename(index={"new": "new process"})
    supply = db.matrices["baseline"]["S"].copy()
    for region in ["DE", "FR"]:
        commodity = (region, "Commodity", "extra")
        supply.loc[(region, "Activity", "new process"), commodity] = supply.loc[(region, "Activity", "extra"), commodity]
        supply.loc[(region, "Activity", "extra"), commodity] = 0.
    db.update_scenarios("baseline", S=supply)
    donors = {("IT", "new"): "DE", ("IT", "extra"): "FR"}
    if override:
        donors[("IT", "new process")] = ["DE", "FR"]
    kwargs = dict(scenario="policy", clone_from="baseline", level="Commodity", recipe_regions=donors)
    mix = {"IT": {"old": .4, "new": .3, "extra": .3}}
    if override:
        db.update_supply_mix(mix, **kwargs)
        assert db.query("u", scenarios="policy").loc[:, ("IT", "Activity", "new process")].sum() > 0
    else:
        with pytest.raises(WrongInput, match="Conflicting commodity donor selections"):
            db.update_supply_mix(mix, **kwargs)
