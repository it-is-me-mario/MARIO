import pytest
from copy import deepcopy

from mario import parse_from_pymrio
from mario.log_exc.exceptions import WrongInput
from mario.test.mario_test import load_test


def test_parse_from_pymrio_supports_top_level_all_shorthand():
    source = load_test("IOT")
    io = source.to_pymrio(
        satellite_account="air_emissions",
        factor_of_production="factor_inputs",
    ).calc_all()

    parsed = parse_from_pymrio(
        io=io,
        value_added="all",
        satellite_account="all",
    )

    assert set(parsed.get_index("Factor of production")) == set(
        source.get_index("Factor of production")
    )
    assert set(parsed.get_index("Satellite account")) == set(
        source.get_index("Satellite account")
    )
    assert set(parsed.get_index("Sector")) == set(source.get_index("Sector"))
    assert set(parsed.get_index("Region")) == set(source.get_index("Region"))


def test_parse_from_pymrio_calculates_uncalculated_iosystem():
    source = load_test("IOT")
    io = source.to_pymrio(
        satellite_account="air_emissions",
        factor_of_production="factor_inputs",
    )

    parsed = parse_from_pymrio(
        io=io,
        value_added="all",
        satellite_account="all",
    )

    assert set(parsed.get_index("Factor of production")) == set(
        source.get_index("Factor of production")
    )
    assert set(parsed.get_index("Satellite account")) == set(
        source.get_index("Satellite account")
    )
    assert set(parsed.get_index("Sector")) == set(source.get_index("Sector"))
    assert set(parsed.get_index("Region")) == set(source.get_index("Region"))


def test_parse_from_pymrio_fills_missing_extension_columns_with_zero():
    source = load_test("IOT")
    io = source.to_pymrio(
        satellite_account="air_emissions",
        factor_of_production="factor_inputs",
    ).calc_all()

    io.energy = deepcopy(io.air_emissions)
    io.energy.F = io.energy.F.iloc[:, :-1]
    io.energy.F_Y = io.energy.F_Y.iloc[:, :-1]
    io.energy.unit = io.energy.unit.rename(index=lambda value: f"energy::{value}")
    io.energy.F.index = io.energy.unit.index
    io.energy.F_Y.index = io.energy.unit.index

    parsed = parse_from_pymrio(
        io=io,
        value_added={"factor_inputs": "all"},
        satellite_account={"air_emissions": "all", "energy": "all"},
    )

    assert not parsed.E.isna().any().any()
    assert not parsed.EY.isna().any().any()
    assert (parsed.E.loc["energy::CO2"] == 0).any()
    assert (parsed.EY.loc["energy::CO2"] == 0).any()


def test_parse_from_pymrio_all_all_requires_one_factor_like_extension():
    source = load_test("IOT")
    io = source.to_pymrio(
        satellite_account="emissions",
        factor_of_production="primary_inputs",
    ).calc_all()

    # Remove the factor-like naming cue to force explicit classification.
    io.inputs = io.primary_inputs
    delattr(io, "primary_inputs")

    with pytest.raises(WrongInput) as excinfo:
        parse_from_pymrio(
            io=io,
            value_added="all",
            satellite_account="all",
        )

    assert "requires exactly one factor-like Extension" in str(excinfo.value)
