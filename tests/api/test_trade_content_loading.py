"""Trade-content methods resolve only their required indicator rows."""

import numpy as np
import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.test.mario_test import load_test
from tests.api.test_regional_indexes import regional_database
from tests.api.test_regional_trades import reference


@pytest.fixture(params=["IOT", "Isard", "Chenery"])
def model(request):
    if request.param == "IOT":
        return load_test("IOT"), "Agriculture", False
    database = load_test("SUT")
    chenery = request.param == "Chenery"
    if chenery:
        database = database.to_chenery_moses(inplace=False)
    return database, "Goods", chenery


def row_names(database, chenery, indicator_kind):
    factor = indicator_kind != "satellite"
    if database.table_type == "IOT":
        return ("v", "m") if factor else ("e", "f")
    if chenery:
        return ("va", "ma") if factor else ("ea", "fa")
    return ("vc", "mc") if factor else ("ec", "fc")


def indicator_for(database, kind):
    if kind == "total_va":
        return "total value added"
    level = "Satellite account" if kind == "satellite" else "Factor of production"
    return database.get_index(level)[0]


@pytest.mark.parametrize("method", ["direct", "total", "upstream"])
@pytest.mark.parametrize("kind", ["satellite", "factor", "total_va"])
def test_public_methods_request_only_required_rows_and_preserve_values(
    model, monkeypatch, method, kind
):
    database, item, chenery = model
    indicator = indicator_for(database, kind)
    direct_name, total_name = row_names(database, chenery, kind)
    blocks = {name: database.query(name).copy() for name in (direct_name, total_name)}
    rows = {
        name: block.sum(axis=0) if kind == "total_va" else block.loc[indicator]
        for name, block in blocks.items()
    }
    weights = rows[direct_name] if method == "direct" else rows[total_name]
    if method == "upstream":
        weights = rows[total_name].subtract(rows[direct_name], fill_value=0.0)
    regions = database.get_index("Region")
    flow_names = (
        ["S"]
        if chenery
        else ["U", "Yc"] if database.table_type == "SUT" else ["Z", "Y"]
    )
    expected = sum(
        (
            reference(
                database.query(name).mul(weights, axis=0), item, regions, supply=chenery
            )
            for name in flow_names
        )
    )
    original = database.query
    requests = []
    required = (
        {direct_name}
        if method == "direct"
        else {total_name} if method == "total" else {direct_name, total_name}
    )

    def guarded(matrices=None, *args, **kwargs):
        names = [matrices] if isinstance(matrices, str) else list(matrices or [])
        requests.extend(names)
        unneeded = set(names).intersection({direct_name, total_name}) - required
        assert not unneeded, f"Unnecessary row request: {unneeded}"
        return original(matrices, *args, **kwargs)

    monkeypatch.setattr(database, "query", guarded)
    result = database.calc_trades_content(indicator, item=item, method=method)
    pd.testing.assert_frame_equal(result, expected)
    for name in required:
        assert requests.count(name) == 1


def regional_model(sparse):
    database = regional_database(
        {"IT": ["A1", "A2"], "DE": ["A3"]},
        {"IT": ["C1"], "DE": ["C2", "C3"]},
        {"IT": ["HH"], "DE": ["HH", "GOV"]},
    )
    for name, source in list(database.matrices["baseline"].items()):
        values = np.arange(source.size, dtype=float).reshape(source.shape) + 1
        if name == "S":
            values = np.array([[10.0, 0.0, 0.0], [5.0, 0.0, 0.0], [0.0, 10.0, 5.0]])
        frame = pd.DataFrame(values, index=source.index, columns=source.columns)
        if sparse:
            frame = frame.astype(pd.SparseDtype(float, 0))
        database.matrices["baseline"][name] = frame
    return database


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("kind", ["satellite", "factor", "total_va"])
def test_direct_on_fresh_regional_database_never_requests_total_multipliers(
    sparse, kind, monkeypatch
):
    database = regional_model(sparse)
    indicator = indicator_for(database, kind)
    original = database.query
    direct_name, _ = row_names(database, False, kind)
    direct = original(direct_name)
    weights = direct.sum(axis=0) if kind == "total_va" else direct.loc[indicator]
    expected = sum(
        reference(
            database.matrices["baseline"][name].mul(weights, axis=0),
            "C1",
            database.get_index("Region"),
        )
        for name in ("U", "Yc")
    )

    def no_total(matrices=None, *args, **kwargs):
        names = [matrices] if isinstance(matrices, str) else list(matrices or [])
        assert not set(names).intersection({"f", "m", "fa", "fc", "ma", "mc"})
        return original(matrices, *args, **kwargs)

    monkeypatch.setattr(database, "query", no_total)
    result = database.calc_trades_content(indicator, item="C1", method="direct")
    pd.testing.assert_frame_equal(result, expected)
    assert (
        result.to_numpy().sum() > 0
    )  # A zero-only fixture would not verify weighting.
    assert not any(
        name.lower().startswith("w") or name in {"fa", "fc", "ma", "mc"}
        for name in database.matrices["baseline"]
    )


@pytest.mark.parametrize("kind", ["satellite", "factor", "total_va"])
def test_total_breakdown_does_not_load_or_construct_direct_weights(
    model, kind, monkeypatch
):
    database, item, _ = model
    indicator = indicator_for(database, kind)
    expected = database.calc_trades_content(indicator, item=item, method="total")

    def no_direct(*args, **kwargs):
        raise AssertionError("Total breakdown constructed unnecessary direct weights")

    monkeypatch.setattr(database, "_resolve_trade_content_row", no_direct)
    monkeypatch.setattr(database, "_explode_trade_content_direct_row", no_direct)
    result = database.calc_trades_content(
        indicator, item=item, method="total", breakdown=True
    )
    pd.testing.assert_frame_equal(result.groupby(level=0, sort=False).sum(), expected)


def test_invalid_method_or_indicator_does_not_resolve_rows(monkeypatch):
    database = regional_model(False)

    def no_query(*args, **kwargs):
        raise AssertionError("Invalid selection triggered matrix calculation")

    monkeypatch.setattr(database, "query", no_query)
    with pytest.raises(WrongInput, match="method should"):
        database.calc_trades_content("CO2", item="C1", method="invalid")
    with pytest.raises(WrongInput, match="indicator should"):
        database.calc_trades_content("missing", item="C1", method="direct")
