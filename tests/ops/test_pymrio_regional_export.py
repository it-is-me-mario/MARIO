"""Unsupported regional layouts fail before constructing a pymrio export."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable
from mario.ops.export import export_database_to_pymrio
from scripts.diagnose_bonsai_methods import _small_bundle
from tests.api.test_regional_indexes import regional_database


def iot(sectors, demands):
    source = regional_database(sectors, sectors, demands)
    blocks = source.matrices["baseline"]
    axis = blocks["S"].index.set_levels(["Sector"], level=1)
    indexes = {
        k: deepcopy(v) for k, v in source._indeces.items() if k not in ("a", "c")
    }
    indexes["s"] = deepcopy(source._indeces["a"])
    units = {
        k: v.copy()
        for k, v in source.units.items()
        if k not in ("Activity", "Commodity")
    }
    units["Sector"] = source.units["Activity"].copy()
    return mario.Database(
        table="IOT",
        calc_all=False,
        init_by_parsers={
            "matrices": {
                "baseline": {
                    "Z": pd.DataFrame(0.0, index=axis, columns=axis),
                    "Y": blocks["Ya"].set_axis(axis),
                    "E": blocks["Ea"].set_axis(axis, axis=1),
                    "V": blocks["Va"].set_axis(axis, axis=1),
                    "EY": blocks["EY"],
                }
            },
            "_indeces": indexes,
            "units": units,
        },
    )


@pytest.mark.parametrize("public", [False, True], ids=["operation", "database"])
@pytest.mark.parametrize(
    "sectors,demands,unsupported",
    [
        ({"IT": ["A", "B"], "DE": ["A"]}, {"IT": ["HH"], "DE": ["HH"]}, ["Sector"]),
        (
            {"IT": ["A", "B"], "DE": ["A", "C"]},
            {"IT": ["HH"], "DE": ["HH"]},
            ["Sector"],
        ),
        (
            {"IT": ["A"], "DE": ["A"]},
            {"IT": ["HH"], "DE": ["HH", "GOV"]},
            ["Consumption category"],
        ),
        (
            {"IT": ["A"], "DE": ["A"]},
            {"IT": ["HH"], "DE": ["GOV"]},
            ["Consumption category"],
        ),
        ({"IT": ["A"], "DE": []}, {"IT": ["HH"], "DE": ["HH"]}, ["Sector"]),
        (
            {"IT": ["A"], "DE": ["A"]},
            {"IT": ["HH"], "DE": []},
            ["Consumption category"],
        ),
        (
            {"IT": ["A"], "DE": ["B"]},
            {"IT": ["HH"], "DE": ["GOV"]},
            ["Sector", "Consumption category"],
        ),
    ],
)
def test_regional_export_reports_unsupported_sets_without_queries(
    sectors,
    demands,
    unsupported,
    public,
    monkeypatch,
):
    database = iot(sectors, demands)
    before = {
        name: frame.copy() for name, frame in database.matrices["baseline"].items()
    }
    indexes = deepcopy(database._indeces)
    history = deepcopy(database.meta._history)
    monkeypatch.setattr(
        database, "query", lambda *a, **k: pytest.fail("Export queried matrices")
    )
    monkeypatch.setattr(
        "mario.ops.export._install_pymrio_pandas3_compat",
        lambda: pytest.fail("An unsupported export changed pymrio globals"),
    )
    with pytest.raises(
        NotImplementable, match="region-specific classifications"
    ) as exc:
        if public:
            database.to_pymrio()
        else:
            export_database_to_pymrio(database)
    for name in unsupported:
        assert name in str(exc.value)
    assert database._indeces == indexes
    assert database.meta._history == history
    assert set(database.matrices["baseline"]) == set(before)
    for name, frame in before.items():
        pd.testing.assert_frame_equal(database.matrices["baseline"][name], frame)


def test_single_region_and_common_sets_keep_exporting():
    for sectors, demands in [
        ({"WORLD": ["IT::A", "DE::B"]}, {"WORLD": ["IT::HH", "DE::GOV"]}),
        (
            {"IT": ["A", "B"], "DE": ["B", "A"]},
            {"IT": ["HH", "GOV"], "DE": ["GOV", "HH"]},
        ),
    ]:
        database = iot(sectors, demands)
        io = database.to_pymrio()
        assert io.get_regions().tolist() == list(sectors)
        assert io.Z.index.tolist() == [
            (region, item) for region, labels in sectors.items() for item in labels
        ]
        assert io.Y.columns.tolist() == [
            (region, item) for region, labels in demands.items() for item in labels
        ]
        np.testing.assert_array_equal(io.Z.to_numpy(), database.query("Z").to_numpy())


def test_bonsai_small_to_iot_is_separate_from_unsupported_pymrio_export(
    tmp_path, monkeypatch, bonsai_without_umfpack,
):
    sut = mario.parse_bonsai(_small_bundle(tmp_path / "balanced"))
    mario.set_linear_solver("scipy")
    converted = sut.to_iot("B", inplace=False)
    assert sut.table_type == "SUT"
    assert converted.table_type == "IOT"
    assert converted.get_index("Sector") == {"AT": ["C1"], "DE": ["C2", "C3"]}
    monkeypatch.setattr(
        converted, "query", lambda *a, **k: pytest.fail("Export queried matrices")
    )
    with pytest.raises(NotImplementable, match="Sector, Consumption category"):
        converted.to_pymrio()
