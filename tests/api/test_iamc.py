import numpy as np
import pandas as pd
import pytest

import mario


def data():
    return pd.DataFrame(
        [
            ("M", "Custom steel", region, variable, "Mt/yr", quantity)
            for region, quantities in [("North", (1, 3, 4)), ("South", (2, 0, 2))]
            for variable, quantity in zip(
                ("Steel|EAF", "Steel|BF", "Steel"), quantities
            )
        ],
        columns=["Model", "Scenario", "Region", "Variable", "Unit", 2050],
    )


def mix(iam, **changes):
    settings = dict(
        model="M",
        scenario="Custom steel",
        year=2050,
        regions={"US": ["North", "South"]},
        variables={"EAF": "Steel|EAF", "Blast": "Steel|BF"},
        total="Steel",
        unit="Mt/yr",
        basis="physical",
    )
    settings.update(changes)
    return iam.supply_mix(**settings)


def test_custom_long_csv_and_value_basis(tmp_path):
    path = tmp_path / "custom.csv"
    data().melt(
        id_vars=list(data().columns[:-1]), var_name="Year", value_name="Value"
    ).to_csv(path, index=False)
    iam = mario.read_iamc(path)
    assert mix(iam) == {"US": {"EAF": 0.5, "Blast": 0.5}}
    assert mix(iam, basis="value", prices={"US": {"EAF": 3, "Blast": 1}}) == {
        "US": {"EAF": 0.75, "Blast": 0.25}
    }


def test_excel_custom_sheet_and_iiasa_footer(tmp_path):
    frame = data().replace("North", "NA")
    frame.loc[len(frame)] = [
        " © IIASA Energy Program\n generated: today",
        None,
        None,
        None,
        None,
        None,
    ]
    path = tmp_path / "export.xlsx"
    frame.to_excel(path, sheet_name="Custom results", index=False)
    result = mario.read_iamc(path, sheet_name="Custom results").frame
    assert set(result.Region) == {"NA", "South"} and len(result) == 6


@pytest.mark.parametrize(
    "option",
    [
        {"year": 2045},
        {"unit": "t/yr"},
        {"regions": {"US": ["North", "North"]}},
        {"variables": {"EAF": "Steel|EAF", "All": "Steel"}},
        {"basis": "value"},
        {"basis": "value", "prices": {"US": {"EAF": 1, "Blast": 0}}},
    ],
)
def test_rejects_ambiguous_or_incomplete_selection(option):
    with pytest.raises(ValueError):
        mix(mario.read_iamc(data()), **option)


@pytest.mark.parametrize("bad", [np.nan, -1, np.inf, 2])
def test_missing_or_inconsistent_quantities(bad):
    frame = data()
    frame[2050] = frame[2050].astype(float)
    frame.loc[0, 2050] = bad
    with pytest.raises(ValueError):
        mix(mario.read_iamc(frame))


def test_no_silent_average_of_regional_shares():
    with pytest.raises(ValueError, match="Aggregate physical"):
        mix(mario.read_iamc(data().assign(Unit="%")), unit="%")


def test_no_silent_normalization_of_missing_electricity():
    frame = data().iloc[:1].copy()
    frame["Variable"] = "Secondary Energy|Electricity|Wind"
    with pytest.raises(ValueError, match="Missing"):
        mix(mario.read_iamc(frame), variables="exiobase-electricity", total=None)
