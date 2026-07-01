import warnings
from copy import deepcopy

import mario
import mario.parsers as public_parsers
import pandas as pd
import pandas.testing as pdt
import pytest
from pathlib import Path

from mario.clusters.coverage import build_region_aggregation_index, resolve_region_labels_to_iso3_members
from mario.compute.runtime import effective_compute_options
from mario.compute.types import ComputeOptions, ResolutionContext
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.log_exc.logger import set_log_verbosity
from mario.ops import export as export_module
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.primitives import calc_w, calc_z
from mario.compute.views import (
    concat_sut_e,
    concat_sut_f,
    concat_sut_p,
    concat_sut_v,
    extract_ea_from_e,
    extract_ec_from_e,
    extract_fa_from_f,
    extract_fc_from_f,
    extract_pa_from_p,
    extract_pc_from_p,
    extract_va_from_v,
    extract_vc_from_v,
)
from mario.settings.settings import (
    download_settings,
    reset_settings,
    set_compute_method,
    set_linear_solver,
    set_linear_strategy,
    upload_settings,
)
from mario.parsers.api import build_database_from_state, build_parser_state
from mario.test.mario_test import load_test
from mario.model.conventions import _ENUM, _MASTER_INDEX
from mario.ops.workbook_specs import SHOCK_COLUMNS, SHOCK_FLAT_COLUMNS


def _build_flat_iot_template_database(tmp_path):
    path = tmp_path / "custom_iot_template.xlsx"
    mario.write_parse_template(
        str(path),
        table="IOT",
        sets={
            "regions": ["Reg"],
            "sectors": ["Sector A", "Sector B"],
            "final demand": ["Final demand"],
            "factors": ["Value Added"],
            "satellites": ["CO2"],
        },
        units={
            "sectors": {"Sector A": "t", "Sector B": "t"},
            "factors": "EUR",
            "satellites": "kg",
        },
    )
    return mario.parse_from_excel(str(path), "IOT", "flows")


def test_calc_all_iot_uses_catalog_path_for_missing_blocks():
    database = load_test("IOT")
    assert _ENUM.X not in database["baseline"]

    database.calc_all([_ENUM.w])

    expected_z = calc_z(database.Z, database.X)
    expected_w = calc_w(expected_z)

    pdt.assert_frame_equal(database.z, expected_z)
    pdt.assert_frame_equal(database.w, expected_w)


def test_calc_all_iot_solve_method_resolves_f_without_materializing_w():
    database = load_test("IOT")
    assert _ENUM.w not in database["baseline"]

    database.calc_all(
        [_ENUM.f],
        compute_options=ComputeOptions(backend_override="sparse_direct"),
    )

    expected_z = calc_z(database.Z, database.X)
    expected_w = calc_w(expected_z)
    expected_f = database.e.dot(expected_w)

    pdt.assert_frame_equal(database.f, expected_f)
    assert _ENUM.w not in database["baseline"]


def test_calc_all_rejects_legacy_runtime_kwargs():
    database = load_test("IOT")

    with pytest.raises(TypeError):
        database.calc_all([_ENUM.f], compute_method="solve")


def test_calc_all_iot_accepts_advanced_compute_options():
    database = load_test("IOT")
    assert _ENUM.w not in database["baseline"]

    database.calc_all(
        [_ENUM.f],
        compute_options=ComputeOptions(planning_override="prefer_direct_targets"),
    )

    expected_z = calc_z(database.Z, database.X)
    expected_w = calc_w(expected_z)
    expected_f = database.e.dot(expected_w)

    pdt.assert_frame_equal(database.f, expected_f)
    assert _ENUM.w not in database["baseline"]


def test_dotted_sut_access_materializes_only_requested_target():
    database = load_test("SUT")
    initial = set(database["baseline"])

    resolved = database.fc

    assert "fc" in database["baseline"]
    assert "Xa" not in database["baseline"]
    assert "ea" not in database["baseline"]
    assert "Xc" not in database["baseline"]
    assert "s" not in database["baseline"]
    assert "u" not in database["baseline"]
    assert "wcc" not in database["baseline"]
    assert "ec" not in database["baseline"]
    assert set(database["baseline"]) == initial | {"fc"}
    pdt.assert_frame_equal(resolved, database.get_block("fc"))


def test_effective_compute_options_translates_public_advanced_options():
    context = ResolutionContext(
        compute=ComputeOptions(
            backend_override="sparse_direct",
            auto_memory_fraction=0.4,
            auto_inverse_overhead_factor=5.0,
        )
    )

    options = effective_compute_options(context)

    assert options.compute_method == "solve"
    assert options.linear_strategy == "direct"
    assert options.auto_w_memory_fraction == 0.4
    assert options.auto_w_overhead_factor == 5.0


def test_dotted_access_logs_selected_iot_runtime_method(capsys):
    try:
        reset_settings()
        set_compute_method("solve")
        set_linear_solver("scipy")
        set_linear_strategy("auto")
        set_log_verbosity("info", capture_warnings=False, include_dependency_logs=False)

        database = load_test("IOT")
        _ = database.f

        captured = capsys.readouterr().out
        assert "build_iot_f_from_e_z" in captured
        assert "compute_method=solve" in captured
        assert "runtime=solve" in captured
        assert "Compute: solving IOT linear system" not in captured
    finally:
        reset_settings()


def test_dotted_access_logs_selected_sut_runtime_method(capsys):
    try:
        reset_settings()
        set_compute_method("solve")
        set_linear_solver("scipy")
        set_linear_strategy("auto")
        set_log_verbosity("info", capture_warnings=False, include_dependency_logs=False)

        database = load_test("SUT")
        _ = database.f

        captured = capsys.readouterr().out
        assert "runtime=solve" in captured
        assert "Compute: solving SUT linear system" not in captured
        assert (
            "build_sut_fa_from_ea_s_u" in captured
            or "build_sut_fc_from_ea_s_u" in captured
        )
    finally:
        reset_settings()


def test_debug_logs_include_linear_strategy_details_for_solve_backend(capsys):
    try:
        reset_settings()
        set_compute_method("solve")
        set_linear_solver("scipy")
        set_linear_strategy("auto")
        set_log_verbosity("debug", capture_warnings=False, include_dependency_logs=False)

        database = load_test("IOT")
        _ = database.f

        captured = capsys.readouterr().out
        assert "Compute: solving IOT linear system" in captured
        assert "linear_solver=scipy" in captured
        assert "linear_strategy=" in captured
    finally:
        reset_settings()


def test_calc_all_sut_resolves_unified_blocks_from_split_dependencies():
    database = load_test("SUT")
    assert _ENUM.X not in database["baseline"]

    database.calc_all([_ENUM.z, _ENUM.u, _ENUM.s, _ENUM.w])

    expected_z = calc_z(database.Z, database.X)
    expected_u = expected_z.loc[
        (slice(None), _MASTER_INDEX["c"], slice(None)),
        (slice(None), _MASTER_INDEX["a"], slice(None)),
    ]
    expected_s = expected_z.loc[
        (slice(None), _MASTER_INDEX["a"], slice(None)),
        (slice(None), _MASTER_INDEX["c"], slice(None)),
    ]
    expected_w = calc_w(expected_z)

    pdt.assert_frame_equal(database.z, expected_z)
    pdt.assert_frame_equal(database.u, expected_u)
    pdt.assert_frame_equal(database.s, expected_s)
    pdt.assert_frame_equal(database.w, expected_w)
    assert "wcc" not in database["baseline"]
    assert "wca" not in database["baseline"]
    assert "wac" not in database["baseline"]
    assert "waa" not in database["baseline"]


def test_calc_linkages_supports_sut_specific_ghosh_blocks():
    database = load_test("SUT")

    linkages = database.calc_linkages(multi_mode=False)

    assert list(linkages.columns) == [
        "Total Forward",
        "Total Backward",
        "Direct Forward",
        "Direct Backward",
        "Forward Amplification",
        "Backward Amplification",
    ]
    assert len(linkages) == len(database.query(_ENUM.z))
    assert {"bu", "bs", "gcc", "gca", "gac", "gaa"}.issubset(set(database["baseline"]))
    assert _ENUM.b not in database["baseline"]
    assert _ENUM.g not in database["baseline"]


def test_calc_linkages_adds_amplification_ratios_in_single_mode():
    database = load_test("IOT")

    linkages = database.calc_linkages(multi_mode=False, normalized=False)

    expected_forward = linkages["Total Forward"] / linkages["Direct Forward"]
    expected_backward = linkages["Total Backward"] / linkages["Direct Backward"]

    pdt.assert_series_equal(
        linkages["Forward Amplification"],
        expected_forward,
        check_names=False,
    )
    pdt.assert_series_equal(
        linkages["Backward Amplification"],
        expected_backward,
        check_names=False,
    )


def test_calc_linkages_adds_local_and_foreign_shares_in_multi_mode():
    database = load_test("IOT")

    linkages = database.calc_linkages(multi_mode=True, normalized=False)

    assert ("Total Forward", "Local Share") in linkages.columns
    assert ("Total Forward", "Foreign Share") in linkages.columns
    assert ("Direct Backward", "Local Share") in linkages.columns
    assert ("Direct Backward", "Foreign Share") in linkages.columns

    for measure in [
        "Total Forward",
        "Total Backward",
        "Direct Forward",
        "Direct Backward",
    ]:
        total_share = linkages[(measure, "Local Share")] + linkages[(measure, "Foreign Share")]
        nonzero_mask = (
            linkages[(measure, "Local")] + linkages[(measure, "Foreign")]
        ) != 0
        pdt.assert_series_equal(
            total_share.loc[nonzero_mask],
            pd.Series(1.0, index=total_share.loc[nonzero_mask].index),
            check_names=False,
        )


def test_calc_linkages_avoids_incompatible_dtype_warnings():
    database = load_test("IOT")

    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        multi_region = database.calc_linkages()
        normalized = database.calc_linkages(multi_mode=False)

    assert all(dtype.kind == "f" for dtype in multi_region.dtypes)
    assert all(dtype.kind == "f" for dtype in normalized.dtypes)


def test_calc_trades_iot_aggregates_intermediate_and_final_by_default():
    database = load_test("IOT")

    trades = database.calc_trades("Agriculture")

    expected_intermediate = (
        database.Z.loc[(slice(None), slice(None), "Agriculture"), :]
        .T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected_final = (
        database.Y.loc[(slice(None), slice(None), "Agriculture"), :]
        .T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected = expected_intermediate + expected_final

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_sut_uses_u_and_yc_blocks():
    database = load_test("SUT")

    trades = database.calc_trades("Goods")

    expected_intermediate = (
        database.U.loc[(slice(None), slice(None), "Goods"), :]
        .T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected_final = (
        database.Yc.loc[(slice(None), slice(None), "Goods"), :]
        .T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected = expected_intermediate + expected_final

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_chenery_sut_uses_supply_matrix_for_commodity_trades():
    database = load_test("SUT").to_chenery_moses(inplace=False)

    trades = database.calc_trades("Goods")

    expected = (
        database.S.loc[:, (slice(None), slice(None), "Goods")]
        .groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
        .T
    )

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_chenery_sut_rejects_component_split_requests():
    database = load_test("SUT").to_chenery_moses(inplace=False)

    with pytest.raises(NotImplementable, match="Chenery-Moses"):
        database.calc_trades("Goods", aggregate=False)


def test_calc_trades_can_keep_intermediate_and_final_components_separate():
    database = load_test("IOT")

    trades = database.calc_trades("Agriculture", aggregate=False)

    expected_intermediate = (
        database.Z.loc[(slice(None), slice(None), "Agriculture"), :]
        .T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected_final = (
        database.Y.loc[(slice(None), slice(None), "Agriculture"), :]
        .T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected = pd.concat(
        {"Intermediate": expected_intermediate, "Final": expected_final},
        axis=1,
    )

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_can_add_row_and_column_totals():
    database = load_test("IOT")

    trades = database.calc_trades("Agriculture", total=True)

    assert "Total" in trades.index
    assert "Total" in trades.columns
    pdt.assert_series_equal(
        trades.loc["Total", trades.columns[:-1]],
        trades.iloc[:-1, :-1].sum(axis=0),
        check_names=False,
    )
    pdt.assert_series_equal(
        trades.loc[trades.index[:-1], "Total"],
        trades.iloc[:-1, :-1].sum(axis=1),
        check_names=False,
    )


def test_calc_trades_can_aggregate_regions_with_clusters():
    database = load_test("IOT")

    trades = database.calc_trades(
        "Agriculture",
        clusters={"Region": {"EU": ["Reg1"]}},
    )

    expected = database.calc_trades("Agriculture")
    expected.index = pd.Index(
        ["EU" if label == "Reg1" else label for label in expected.index],
        name=expected.index.name,
    )
    expected.columns = pd.Index(
        ["EU" if label == "Reg1" else label for label in expected.columns],
        name=expected.columns.name,
    )
    expected = expected.groupby(level=0, sort=False).sum().T.groupby(level=0, sort=False).sum().T
    expected = expected.reindex(index=["EU", "Reg2"], columns=["EU", "Reg2"], fill_value=0.0)

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_can_aggregate_only_origin_regions_with_clusters():
    database = load_test("IOT")

    trades = database.calc_trades(
        "Agriculture",
        clusters={"Region": {"EU": ["Reg1"]}},
        clusters_direction="origin",
    )

    expected = database.calc_trades("Agriculture")
    expected.index = pd.Index(
        ["EU" if label == "Reg1" else label for label in expected.index],
        name=expected.index.name,
    )
    expected = expected.groupby(level=0, sort=False).sum()
    expected = expected.reindex(index=["EU", "Reg2"], columns=["Reg1", "Reg2"], fill_value=0.0)

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_can_aggregate_only_destination_regions_with_clusters():
    database = load_test("IOT")

    trades = database.calc_trades(
        "Agriculture",
        clusters={"Region": {"EU": ["Reg1"]}},
        clusters_direction="destination",
    )

    expected = database.calc_trades("Agriculture")
    expected.columns = pd.Index(
        ["EU" if label == "Reg1" else label for label in expected.columns],
        name=expected.columns.name,
    )
    expected = expected.T.groupby(level=0, sort=False).sum().T
    expected = expected.reindex(index=["Reg1", "Reg2"], columns=["EU", "Reg2"], fill_value=0.0)

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_rejects_invalid_clusters_direction():
    database = load_test("IOT")

    with pytest.raises(WrongInput, match="clusters_direction"):
        database.calc_trades(
            "Agriculture",
            clusters={"Region": {"EU": ["Reg1"]}},
            clusters_direction="sideways",
        )


def test_calc_trades_accepts_region_aggregation_presets_via_clusters(monkeypatch):
    database = load_test("IOT")

    captured = {"data": None}

    class DummyFigure:
        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        captured["data"] = kwargs.get("data")
        return DummyFigure()

    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades(
        "Agriculture",
        clusters={"EU": ["Reg1"]},
        show_plot=True,
        path=False,
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert set(trades.index) == {"EU", "Reg2"}
    assert set(captured["data"]["Origin Region"]) == {"EU", "Reg2"}


def test_calc_trades_can_show_a_heatmap():
    database = load_test("IOT")

    trades = database.calc_trades(
        "Agriculture",
        aggregate=False,
        show_plot=True,
        path=False,
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)


def test_calc_trades_can_show_an_aggregated_heatmap():
    database = load_test("IOT")

    trades = database.calc_trades(
        "Agriculture",
        show_plot=True,
        path=False,
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert trades.columns.nlevels == 1


def test_calc_trades_plot_orders_regions_alphabetically(monkeypatch):
    database = load_test("IOT")

    captured = {"category_orders": None}

    class DummyFigure:
        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        captured["category_orders"] = kwargs.get("category_orders")
        return DummyFigure()

    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades(
        "Agriculture",
        clusters={"Region": {"ZZZ": ["Reg1"]}},
        show_plot=True,
        path=False,
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert trades.index.tolist() == ["ZZZ", "Reg2"]
    assert trades.columns.tolist() == ["ZZZ", "Reg2"]
    assert captured["category_orders"] == {
        "Origin Region": ["Reg2", "ZZZ"],
        "Destination Region": ["Reg2", "ZZZ"],
    }


def test_calc_trades_displays_plot_inline_but_returns_only_matrix(monkeypatch):
    database = load_test("IOT")

    displayed = {"called": False}

    class DummyFigure:
        data = [object()]

        def show(self):
            displayed["called"] = True

    def fake_plot(*args, **kwargs):
        return DummyFigure()

    monkeypatch.setattr("mario.api.database.run_from_jupyter", lambda: True)
    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades("Agriculture", show_plot=True, path=False, auto_open=False)

    assert isinstance(trades, pd.DataFrame)
    assert displayed["called"] is True


def test_calc_trades_saves_html_via_figure_write_html(monkeypatch, tmp_path):
    database = load_test("IOT")

    captured = {"plot_path": None, "saved_path": None, "auto_open": None}

    class DummyFigure:
        def write_html(self, path, auto_open=False):
            captured["saved_path"] = path
            captured["auto_open"] = auto_open

        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        captured["plot_path"] = kwargs.get("path")
        return DummyFigure()

    monkeypatch.setattr(database, "plot", fake_plot)

    output_path = tmp_path / "trades.html"
    trades = database.calc_trades(
        "Agriculture",
        show_plot=True,
        save_plot=str(output_path),
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert captured["plot_path"] is False
    assert captured["saved_path"] == str(output_path)
    assert captured["auto_open"] is False


def test_calc_trades_saves_images_via_write_image(monkeypatch, tmp_path):
    database = load_test("IOT")

    captured = {"saved_path": None}

    class DummyFigure:
        def write_html(self, path, auto_open=False):
            raise AssertionError("write_html should not be used for .png output")

        def write_image(self, path):
            captured["saved_path"] = path

        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        return DummyFigure()

    monkeypatch.setattr(database, "plot", fake_plot)

    output_path = tmp_path / "trades.png"
    trades = database.calc_trades(
        "Agriculture",
        save_plot=str(output_path),
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert captured["saved_path"] == str(output_path)


def test_calc_trades_save_plot_suppresses_inline_display(monkeypatch, tmp_path):
    database = load_test("IOT")

    displayed = {"called": False}

    class DummyFigure:
        def write_html(self, path, auto_open=False):
            return None

        def show(self):
            displayed["called"] = True

    def fake_plot(*args, **kwargs):
        return DummyFigure()

    monkeypatch.setattr("mario.api.database.run_from_jupyter", lambda: True)
    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades(
        "Agriculture",
        show_plot=True,
        save_plot=str(tmp_path / "trades.html"),
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert displayed["called"] is False


def test_calc_trades_save_plot_disables_auto_open_even_when_default(monkeypatch, tmp_path):
    database = load_test("IOT")

    captured = {"auto_open": None, "shown": False}

    class DummyFigure:
        def write_html(self, path, auto_open=False):
            captured["auto_open"] = auto_open

        def show(self):
            captured["shown"] = True

    def fake_plot(*args, **kwargs):
        return DummyFigure()

    monkeypatch.setattr("mario.api.database.run_from_jupyter", lambda: True)
    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades(
        "Agriculture",
        show_plot=False,
        save_plot=str(tmp_path / "trades.html"),
    )

    assert isinstance(trades, pd.DataFrame)
    assert captured["auto_open"] is False
    assert captured["shown"] is False


def test_calc_trades_excludes_totals_from_plot_frame(monkeypatch):
    database = load_test("IOT")

    captured = {"data": None}

    class DummyFigure:
        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        captured["data"] = kwargs.get("data")
        return DummyFigure()

    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades(
        "Agriculture",
        total=True,
        show_plot=True,
        path=False,
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert captured["data"] is not None
    assert "Total" not in set(captured["data"]["Origin Region"])
    assert "Total" not in set(captured["data"]["Destination Region"])


def test_calc_trades_can_exclude_domestic_pairs_from_plot_only(monkeypatch):
    database = load_test("IOT")

    expected = database.calc_trades("Agriculture")
    captured = {"data": None}

    class DummyFigure:
        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        captured["data"] = kwargs.get("data")
        return DummyFigure()

    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades(
        "Agriculture",
        show_plot=True,
        exclude_domestic_from_plot=True,
        path=False,
        auto_open=False,
    )

    pdt.assert_frame_equal(trades, expected)
    assert expected.values.diagonal().sum() != 0
    assert captured["data"] is not None
    assert not (
        captured["data"]["Origin Region"].astype(str)
        == captured["data"]["Destination Region"].astype(str)
    ).any()


def test_calc_trades_plot_uses_custom_title_and_table_unit(monkeypatch):
    database = load_test("IOT")

    captured = {"figure": None}

    class DummyTitle:
        def __init__(self):
            self.text = None

    class DummyColorBar:
        def __init__(self):
            self.title = DummyTitle()

    class DummyColorAxis:
        def __init__(self):
            self.colorbar = DummyColorBar()

    class DummyLayout:
        def __init__(self):
            self.title = DummyTitle()
            self.coloraxis = DummyColorAxis()

    class DummyFigure:
        def __init__(self):
            self.layout = DummyLayout()

        def update_layout(self, **kwargs):
            if "coloraxis_colorbar_title_text" in kwargs:
                self.layout.coloraxis.colorbar.title.text = kwargs[
                    "coloraxis_colorbar_title_text"
                ]
            return self

        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        figure = DummyFigure()
        figure.layout.title.text = kwargs.get("title")
        captured["figure"] = figure
        return figure

    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades(
        "Agriculture",
        show_plot=True,
        title="Nickel trade map",
        path=False,
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert captured["figure"].layout.title.text == "Nickel trade map"
    assert captured["figure"].layout.coloraxis.colorbar.title.text == "M EUR"


def test_calc_trades_can_plot_all_scenarios_with_animation_slider(monkeypatch):
    database = load_test("IOT")
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"][_ENUM.Y].iloc[0, 0] += 10

    captured = {"data": None, "animation_frame": None}

    class DummyFigure:
        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        captured["data"] = kwargs.get("data")
        captured["animation_frame"] = kwargs.get("animation_frame")
        return DummyFigure()

    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades(
        "Agriculture",
        scenario="all",
        show_plot=True,
        path=False,
        auto_open=False,
    )

    assert set(trades) == {"baseline", "policy"}
    assert captured["animation_frame"] == "Scenario"
    assert set(captured["data"]["Scenario"]) == {"baseline", "policy"}
    assert not trades["baseline"].equals(trades["policy"])


def test_calc_trades_requires_at_least_one_component():
    database = load_test("IOT")

    with pytest.raises(WrongInput, match="At least one"):
        database.calc_trades("Agriculture", intermediate=False, final=False)


def test_calc_trades_without_item_aggregates_all_items_when_units_are_homogeneous():
    database = load_test("IOT")

    trades = database.calc_trades()

    expected_intermediate = (
        database.Z.T.groupby(level=0, sort=False).sum().T.groupby(level=0, sort=False).sum()
    )
    expected_final = (
        database.Y.T.groupby(level=0, sort=False).sum().T.groupby(level=0, sort=False).sum()
    )
    expected = expected_intermediate + expected_final

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_without_item_requires_homogeneous_units():
    database = load_test("IOT")
    database.units[_MASTER_INDEX["s"]].loc["Agriculture", "unit"] = "kg"

    with pytest.raises(WrongInput, match="heterogeneous units"):
        database.calc_trades()


def test_calc_trades_content_iot_uses_total_factor_multipliers():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    trades = database.calc_trades_content(indicator, item="Agriculture", method="total")

    weights = database.query(matrices=[_ENUM.m], scenarios=["baseline"]).loc[indicator]
    expected_intermediate = database.Z.loc[(slice(None), slice(None), "Agriculture"), :].mul(
        weights.reindex(database.Z.loc[(slice(None), slice(None), "Agriculture"), :].index),
        axis=0,
    )
    expected_intermediate = (
        expected_intermediate.T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected_final = database.Y.loc[(slice(None), slice(None), "Agriculture"), :].mul(
        weights.reindex(database.Y.loc[(slice(None), slice(None), "Agriculture"), :].index),
        axis=0,
    )
    expected_final = (
        expected_final.T.groupby(level=0, sort=False).sum().T.groupby(level=0, sort=False).sum()
    )
    expected = expected_intermediate + expected_final

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_content_accepts_total_value_added_alias():
    database = load_test("IOT")

    trades = database.calc_trades_content("total value added", item="Agriculture", method="total")

    weights = database.query(matrices=[_ENUM.m], scenarios=["baseline"]).sum(axis=0)
    expected_intermediate = database.Z.loc[(slice(None), slice(None), "Agriculture"), :].mul(
        weights.reindex(database.Z.loc[(slice(None), slice(None), "Agriculture"), :].index),
        axis=0,
    )
    expected_intermediate = (
        expected_intermediate.T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected_final = database.Y.loc[(slice(None), slice(None), "Agriculture"), :].mul(
        weights.reindex(database.Y.loc[(slice(None), slice(None), "Agriculture"), :].index),
        axis=0,
    )
    expected_final = (
        expected_final.T.groupby(level=0, sort=False).sum().T.groupby(level=0, sort=False).sum()
    )
    expected = expected_intermediate + expected_final

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_content_sut_uses_commodity_side_coefficients():
    database = load_test("SUT")
    indicator = database.get_index(_MASTER_INDEX["k"])[0]

    trades = database.calc_trades_content(indicator, item="Goods", method="direct")

    weights = database.query(matrices=["ec"], scenarios=["baseline"]).loc[indicator]
    expected_intermediate = database.U.loc[(slice(None), slice(None), "Goods"), :].mul(
        weights.reindex(database.U.loc[(slice(None), slice(None), "Goods"), :].index),
        axis=0,
    )
    expected_intermediate = (
        expected_intermediate.T.groupby(level=0, sort=False)
        .sum()
        .T.groupby(level=0, sort=False)
        .sum()
    )
    expected_final = database.Yc.loc[(slice(None), slice(None), "Goods"), :].mul(
        weights.reindex(database.Yc.loc[(slice(None), slice(None), "Goods"), :].index),
        axis=0,
    )
    expected_final = (
        expected_final.T.groupby(level=0, sort=False).sum().T.groupby(level=0, sort=False).sum()
    )
    expected = expected_intermediate + expected_final

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_content_chenery_sut_uses_activity_side_coefficients():
    database = load_test("SUT").to_chenery_moses(inplace=False)
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    trades = database.calc_trades_content(indicator, item="Goods", method="direct")

    weights = database.query(matrices=["va"], scenarios=["baseline"]).loc[indicator]
    expected = database.S.loc[:, (slice(None), slice(None), "Goods")].mul(
        weights.reindex(database.S.index),
        axis=0,
    )
    expected = expected.groupby(level=0, sort=False).sum().T.groupby(level=0, sort=False).sum().T

    pdt.assert_frame_equal(trades, expected)


def test_calc_trades_content_can_show_a_heatmap():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    trades = database.calc_trades_content(
        indicator,
        item="Agriculture",
        aggregate=False,
        show_plot=True,
        path=False,
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)


def test_calc_trades_content_plot_uses_custom_title_and_indicator_unit(monkeypatch):
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    captured = {"figure": None}

    class DummyTitle:
        def __init__(self):
            self.text = None

    class DummyColorBar:
        def __init__(self):
            self.title = DummyTitle()

    class DummyColorAxis:
        def __init__(self):
            self.colorbar = DummyColorBar()

    class DummyLayout:
        def __init__(self):
            self.title = DummyTitle()
            self.coloraxis = DummyColorAxis()

    class DummyFigure:
        def __init__(self):
            self.layout = DummyLayout()

        def update_layout(self, **kwargs):
            if "coloraxis_colorbar_title_text" in kwargs:
                self.layout.coloraxis.colorbar.title.text = kwargs[
                    "coloraxis_colorbar_title_text"
                ]
            return self

        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        figure = DummyFigure()
        figure.layout.title.text = kwargs.get("title")
        captured["figure"] = figure
        return figure

    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades_content(
        indicator,
        item="Agriculture",
        method="upstream",
        show_plot=True,
        title="Nickel embodied trade map",
        path=False,
        auto_open=False,
    )

    assert isinstance(trades, pd.DataFrame)
    assert captured["figure"].layout.title.text == "Nickel embodied trade map"
    expected_unit = str(database.units[_MASTER_INDEX["f"]].loc[indicator, "unit"])
    assert captured["figure"].layout.coloraxis.colorbar.title.text == expected_unit


def test_calc_trades_content_can_plot_all_scenarios_with_animation_slider(monkeypatch):
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"][_ENUM.Y].iloc[0, 0] += 10

    captured = {"data": None, "animation_frame": None}

    class DummyFigure:
        def show(self):
            return None

    def fake_plot(*args, **kwargs):
        captured["data"] = kwargs.get("data")
        captured["animation_frame"] = kwargs.get("animation_frame")
        return DummyFigure()

    monkeypatch.setattr(database, "plot", fake_plot)

    trades = database.calc_trades_content(
        indicator,
        item="Agriculture",
        scenario="all",
        show_plot=True,
        path=False,
        auto_open=False,
    )

    assert set(trades) == {"baseline", "policy"}
    assert captured["animation_frame"] == "Scenario"
    assert set(captured["data"]["Scenario"]) == {"baseline", "policy"}


def test_calc_trades_content_breakdown_iot_sums_back_to_total_content():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    breakdown = database.calc_trades_content(
        indicator,
        item="Agriculture",
        breakdown=True,
    )
    expected = database.calc_trades_content(
        indicator,
        item="Agriculture",
        method="total",
    )

    restored = breakdown.groupby(level=0, sort=False).sum()

    pdt.assert_frame_equal(restored, expected)


def test_calc_trades_content_breakdown_sut_sums_back_to_total_content():
    database = load_test("SUT")
    indicator = database.get_index(_MASTER_INDEX["k"])[0]

    breakdown = database.calc_trades_content(
        indicator,
        item="Goods",
        breakdown=True,
    )
    expected = database.calc_trades_content(
        indicator,
        item="Goods",
        method="total",
    )

    restored = breakdown.groupby(level=0, sort=False).sum()

    pdt.assert_frame_equal(restored, expected)


def test_calc_trades_content_breakdown_chenery_sut_sums_back_to_total_content():
    database = load_test("SUT").to_chenery_moses(inplace=False)
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    breakdown = database.calc_trades_content(
        indicator,
        item="Goods",
        breakdown=True,
    )
    expected = database.calc_trades_content(
        indicator,
        item="Goods",
        method="total",
    )

    restored = breakdown.groupby(level=0, sort=False).sum()

    pdt.assert_frame_equal(restored, expected)


def test_calc_trades_content_breakdown_upstream_sums_back_to_upstream_content():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    breakdown = database.calc_trades_content(
        indicator,
        item="Agriculture",
        method="upstream",
        breakdown=True,
    )
    expected = database.calc_trades_content(
        indicator,
        item="Agriculture",
        method="upstream",
    )

    restored = breakdown.groupby(level=0, sort=False).sum()

    pdt.assert_frame_equal(restored, expected)


def test_calc_trades_content_breakdown_direct_sums_back_to_direct_content():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    breakdown = database.calc_trades_content(
        indicator,
        item="Agriculture",
        method="direct",
        breakdown=True,
    )
    expected = database.calc_trades_content(
        indicator,
        item="Agriculture",
        method="direct",
    )

    restored = breakdown.groupby(level=0, sort=False).sum()

    pdt.assert_frame_equal(restored, expected)


def test_calc_trades_content_rejects_plotting_when_breakdown_is_enabled():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    with pytest.raises(NotImplementable, match="plotting"):
        database.calc_trades_content(
            indicator,
            item="Agriculture",
            breakdown=True,
            show_plot=True,
        )


def test_calc_trades_concentration_uses_contributor_region_hhi():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    concentration = database.calc_trades_concentration(
        indicator,
        item="Agriculture",
    )

    breakdown = database.calc_trades_content(
        indicator,
        item="Agriculture",
        breakdown=True,
    )
    contributor_regions = breakdown.groupby(level=[0, 1], sort=False).sum().abs()

    expected_blocks = []
    for origin_region in contributor_regions.index.get_level_values(0).unique():
        block = contributor_regions.xs(origin_region, level=0, drop_level=True)
        shares = block.div(block.sum(axis=0).where(lambda col: col != 0), axis=1).fillna(0.0)
        hhi = shares.pow(2).sum(axis=0).to_frame().T
        hhi.index = pd.Index([origin_region], name="Region")
        expected_blocks.append(hhi)
    expected = pd.concat(expected_blocks, axis=0)

    pdt.assert_frame_equal(concentration, expected)


def test_calc_trades_exposure_returns_selected_region_share():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    exposure = database.calc_trades_exposure(
        indicator,
        exposed_to="Reg1",
        item="Agriculture",
    )

    breakdown = database.calc_trades_content(
        indicator,
        item="Agriculture",
        breakdown=True,
    )
    contributor_regions = breakdown.groupby(level=[0, 1], sort=False).sum().abs()

    expected_blocks = []
    for origin_region in contributor_regions.index.get_level_values(0).unique():
        block = contributor_regions.xs(origin_region, level=0, drop_level=True)
        selected = block.loc[["Reg1"]].sum(axis=0)
        shares = selected.div(block.sum(axis=0).where(lambda col: col != 0)).fillna(0.0)
        shares = shares.to_frame().T
        shares.index = pd.Index([origin_region], name="Region")
        expected_blocks.append(shares)
    expected = pd.concat(expected_blocks, axis=0)

    pdt.assert_frame_equal(exposure, expected)


def test_calc_trades_exposure_rejects_unknown_regions():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    with pytest.raises(WrongInput, match="Contributor Regions"):
        database.calc_trades_exposure(
            indicator,
            exposed_to="__missing__",
            item="Agriculture",
        )


def test_calc_trades_concentration_can_return_all_scenarios():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"][_ENUM.Y].iloc[0, 0] += 10

    concentration = database.calc_trades_concentration(
        indicator,
        item="Agriculture",
        scenario="all",
    )

    assert set(concentration) == {"baseline", "policy"}


def test_calc_trades_content_concentration_alias_delegates_with_warning():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    with pytest.deprecated_call(match="calc_trades_concentration"):
        result = database.calc_trades_content_concentration(indicator, item="Agriculture")

    expected = database.calc_trades_concentration(indicator, item="Agriculture")
    pdt.assert_frame_equal(result, expected)


def test_calc_trades_content_exposure_alias_delegates_with_warning():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    with pytest.deprecated_call(match="calc_trades_exposure"):
        result = database.calc_trades_content_exposure(
            indicator,
            exposed_to="Reg1",
            item="Agriculture",
        )

    expected = database.calc_trades_exposure(
        indicator,
        exposed_to="Reg1",
        item="Agriculture",
    )
    pdt.assert_frame_equal(result, expected)


def _expected_embodied_imports(trades):
    diagonal_labels = trades.index.intersection(trades.columns)
    imports = trades.sum(axis=0)
    if len(diagonal_labels):
        diagonal = pd.Series(
            [trades.loc[label, label] for label in diagonal_labels],
            index=diagonal_labels,
            dtype=float,
        )
        imports.loc[diagonal.index] = imports.loc[diagonal.index].subtract(diagonal)
    imports.index.name = trades.columns.name or "Region"
    imports.name = "Embodied imports"
    return imports


def _expected_embodied_exports(trades):
    diagonal_labels = trades.index.intersection(trades.columns)
    exports = trades.sum(axis=1)
    if len(diagonal_labels):
        diagonal = pd.Series(
            [trades.loc[label, label] for label in diagonal_labels],
            index=diagonal_labels,
            dtype=float,
        )
        exports.loc[diagonal.index] = exports.loc[diagonal.index].subtract(diagonal)
    exports.index.name = trades.index.name or "Region"
    exports.name = "Embodied exports"
    return exports


def test_calc_embodied_imports_and_exports_collapse_trade_content():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    trades = database.calc_trades_content(indicator, item="Agriculture")
    imports = database.calc_embodied_imports(indicator, item="Agriculture")
    exports = database.calc_embodied_exports(indicator, item="Agriculture")

    pdt.assert_series_equal(imports, _expected_embodied_imports(trades))
    pdt.assert_series_equal(exports, _expected_embodied_exports(trades))


def test_calc_embodied_net_imports_is_imports_minus_exports():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    imports = database.calc_embodied_imports(indicator, item="Agriculture")
    exports = database.calc_embodied_exports(indicator, item="Agriculture")
    net_imports = database.calc_embodied_net_imports(indicator, item="Agriculture")

    expected = imports.subtract(exports, fill_value=0.0)
    expected.name = "Embodied net imports"
    pdt.assert_series_equal(net_imports, expected)


def test_calc_embodied_trade_accounts_keep_intermediate_final_split():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]

    trades = database.calc_trades_content(indicator, item="Agriculture", aggregate=False)
    imports = database.calc_embodied_imports(indicator, item="Agriculture", aggregate=False)
    exports = database.calc_embodied_exports(indicator, item="Agriculture", aggregate=False)

    expected_imports = pd.concat(
        {
            component: _expected_embodied_imports(trades[component])
            for component in trades.columns.get_level_values(0).unique()
        },
        axis=1,
    )
    expected_imports.columns.name = trades.columns.names[0]

    expected_exports = pd.concat(
        {
            component: _expected_embodied_exports(trades[component])
            for component in trades.columns.get_level_values(0).unique()
        },
        axis=1,
    )
    expected_exports.columns.name = trades.columns.names[0]

    pdt.assert_frame_equal(imports, expected_imports)
    pdt.assert_frame_equal(exports, expected_exports)


def test_calc_embodied_imports_can_return_all_scenarios():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"][_ENUM.Y].iloc[0, 0] += 10

    imports = database.calc_embodied_imports(
        indicator,
        item="Agriculture",
        scenario="all",
    )

    assert set(imports) == {"baseline", "policy"}


def test_calc_embodied_imports_accepts_renamed_baseline_aliases():
    database = load_test("IOT")
    indicator = database.get_index(_MASTER_INDEX["f"])[0]
    database.rename_baseline_scenario("reference")

    internal = database.calc_embodied_imports(
        indicator,
        item="Agriculture",
        scenario="baseline",
    )
    public = database.calc_embodied_imports(
        indicator,
        item="Agriculture",
        scenario="reference",
    )

    pdt.assert_series_equal(internal, public)


def test_calc_spa_matches_truncated_direct_series_for_selected_bundle():
    database = load_test("IOT")
    indicator = database.get_index("Satellite account")[0]
    final_demand_column = ("Reg1", "Consumption category", "Final demand")

    spa = database.calc_spa(
        indicator,
        item="Agriculture",
        final_demand_region="Reg1",
        final_demand_category="Final demand",
        max_depth=2,
        cutoff=0,
        top_n=None,
    )

    selected_y = pd.Series(0.0, index=database.z.index, dtype=float)
    selected_y.loc[(slice(None), slice(None), "Agriculture")] = database.Y.loc[
        (slice(None), slice(None), "Agriculture"),
        final_demand_column,
    ]

    expected_truncated = float(
        database.e.loc[indicator].dot(
            selected_y + database.z.dot(selected_y) + database.z.dot(database.z.dot(selected_y))
        )
    )
    expected_total = float(database.f.loc[indicator].dot(selected_y))

    assert float(spa["contribution"].sum()) == pytest.approx(expected_truncated)
    assert spa["depth"].max() == 2
    assert spa.attrs["total_footprint"] == pytest.approx(expected_total)
    assert spa.attrs["reported_contribution"] == pytest.approx(expected_truncated)


def test_calc_spa_sorts_by_absolute_contribution_and_applies_top_n():
    database = load_test("IOT")
    indicator = database.get_index("Satellite account")[0]

    spa = database.calc_spa(
        indicator,
        item="Agriculture",
        max_depth=3,
        cutoff=0,
        top_n=10,
    )

    assert len(spa) == 10
    assert spa["contribution"].abs().is_monotonic_decreasing
    assert spa["cumulative_share"].is_monotonic_increasing


def test_calc_spa_accepts_renamed_baseline_aliases():
    database = load_test("IOT")
    indicator = database.get_index("Satellite account")[0]
    database.rename_baseline_scenario("reference")

    internal = database.calc_spa(
        indicator,
        scenario="baseline",
        item="Agriculture",
        max_depth=1,
        cutoff=0,
        top_n=20,
    )
    public = database.calc_spa(
        indicator,
        scenario="reference",
        item="Agriculture",
        max_depth=1,
        cutoff=0,
        top_n=20,
    )

    pdt.assert_frame_equal(internal, public)
    assert internal.attrs == public.attrs


def test_calc_spa_is_currently_iot_only():
    database = load_test("SUT")
    indicator = database.get_index("Satellite account")[0]

    with pytest.raises(NotImplementable, match="only for IOT"):
        database.calc_spa(indicator)


def test_calc_spa_can_request_integrated_plot(monkeypatch):
    database = load_test("IOT")
    indicator = database.get_index("Satellite account")[0]
    captured = {}

    def fake_plot(*, data=None, kind=None, x=None, y=None, color=None, path=None, title=None, **kwargs):
        captured["data"] = data.copy()
        captured["kind"] = kind
        captured["x"] = x
        captured["y"] = y
        captured["color"] = color
        captured["path"] = path
        captured["title"] = title
        captured["kwargs"] = kwargs

        class Figure:
            def update_traces(self, *args, **kwargs):
                return None

            def update_layout(self, *args, **kwargs):
                return None

        return Figure()

    monkeypatch.setattr(database, "plot", fake_plot)

    spa = database.calc_spa(
        indicator,
        item="Agriculture",
        max_depth=1,
        cutoff=0,
        top_n=5,
        show_plot=True,
    )

    assert len(spa) == 5
    assert captured["kind"] == "bar"
    assert captured["x"] == "Share of total"
    assert captured["y"] == "Path label"
    assert captured["color"] == "Depth"
    assert captured["path"] is False
    assert "Path label" in captured["data"].columns
    assert "Final demand" in captured["data"].columns
    assert captured["data"]["Path label"].iloc[0].startswith("1. ")


def test_calc_spa_can_request_depth_plot(monkeypatch):
    database = load_test("IOT")
    indicator = database.get_index("Satellite account")[0]
    captured = {}

    def fake_plot(*, data=None, kind=None, x=None, y=None, color=None, path=None, title=None, **kwargs):
        captured["data"] = data.copy()
        captured["kind"] = kind
        captured["x"] = x
        captured["y"] = y
        captured["color"] = color
        captured["path"] = path
        captured["title"] = title
        captured["kwargs"] = kwargs

        class Figure:
            def update_traces(self, *args, **kwargs):
                return None

            def update_layout(self, *args, **kwargs):
                return None

            def update_yaxes(self, *args, **kwargs):
                return None

        return Figure()

    monkeypatch.setattr(database, "plot", fake_plot)

    spa = database.calc_spa(
        indicator,
        item="Agriculture",
        max_depth=2,
        cutoff=0,
        top_n=10,
        show_plot=True,
        plot="depth",
    )

    assert len(spa) == 10
    assert captured["kind"] == "bar"
    assert captured["x"] == "Depth"
    assert captured["y"] == "Share of total"
    assert captured["color"] == "Depth"
    assert captured["path"] is False
    assert "Share label" in captured["data"].columns
    assert captured["data"]["Depth"].tolist() == sorted(
        captured["data"]["Depth"].tolist(),
        key=int,
    )


def test_calc_spa_can_request_sankey_plot(monkeypatch, tmp_path):
    database = load_test("IOT")
    indicator = database.get_index("Satellite account")[0]
    captured = {}

    def fake_save(figure, output_path, *, auto_open):
        captured["figure"] = figure
        captured["output_path"] = output_path
        captured["auto_open"] = auto_open

    monkeypatch.setattr(database, "_save_trade_plot_figure", fake_save)

    output_path = tmp_path / "spa-sankey.html"
    spa = database.calc_spa(
        indicator,
        item="Agriculture",
        max_depth=2,
        cutoff=0,
        top_n=8,
        plot="sankey",
        save_plot=output_path,
    )

    assert len(spa) == 8
    assert captured["output_path"] == output_path
    assert captured["auto_open"] is False
    assert captured["figure"].data[0].type == "sankey"
    assert len(captured["figure"].data[0].node.label) > 0
    assert len(captured["figure"].data[0].link.source) > 0


def test_calc_spa_rejects_unknown_plot_mode():
    database = load_test("IOT")
    indicator = database.get_index("Satellite account")[0]

    with pytest.raises(WrongInput, match="plot should be one of 'paths', 'sankey', or 'depth'"):
        database.calc_spa(indicator, item="Agriculture", plot="unknown")


def test_calc_spa_can_save_integrated_plot(monkeypatch, tmp_path):
    database = load_test("IOT")
    indicator = database.get_index("Satellite account")[0]
    calls = {}

    class Figure:
        def update_traces(self, *args, **kwargs):
            return None

        def update_layout(self, *args, **kwargs):
            return None

    def fake_plot(**kwargs):
        calls["plot"] = kwargs
        return Figure()

    def fake_save(figure, output_path, *, auto_open):
        calls["save"] = {
            "figure": figure,
            "output_path": output_path,
            "auto_open": auto_open,
        }

    monkeypatch.setattr(database, "plot", fake_plot)
    monkeypatch.setattr(database, "_save_trade_plot_figure", fake_save)

    output_path = tmp_path / "spa.html"
    spa = database.calc_spa(
        indicator,
        item="Agriculture",
        max_depth=1,
        cutoff=0,
        top_n=5,
        save_plot=output_path,
        auto_open=True,
    )

    assert len(spa) == 5
    assert calls["plot"]["path"] is False
    assert calls["save"]["output_path"] == output_path
    assert calls["save"]["auto_open"] is False


def test_parse_exiobase_imports_a_new_parser_scenario(monkeypatch):
    database = load_test("IOT")
    raw_blocks = {
        name: deepcopy(value)
        for name, value in database["baseline"].items()
        if name in {_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.Y, _ENUM.EY, _ENUM.VY}
    }

    def fake_parse_exiobase(*, model="Database", calc_all=False, year=None, **kwargs):
        state = build_parser_state(
            table=database.meta.table,
            matrices=raw_blocks,
            indexes=deepcopy(database._indeces),
            units=deepcopy(database.units),
            parser_name="parse_exiobase",
            source="EXIOBASE",
            year=year,
        )
        return build_database_from_state(state, model=model, calc_all=calc_all)

    monkeypatch.setattr("mario.parsers.entrypoints.parse_exiobase", fake_parse_exiobase)

    database.parse_exiobase(
        table="IOT",
        unit="Monetary",
        path="ignored",
        year=2023,
        new_scenario=2023,
    )

    assert "2023" in database.scenarios
    for matrix, value in raw_blocks.items():
        pdt.assert_frame_equal(database["2023"][matrix], value)
    assert database.info["scenario_metadata"]["2023"]["year"] == 2023
    assert _ENUM.X not in database["2023"]


def test_parse_from_parquet_imports_a_new_parser_scenario(monkeypatch):
    database = load_test("SUT")
    sut_native_blocks = {"U", "S", "Ya", "Yc", "Ea", "Ec", "EY", "Va", "Vc", "VY"}
    raw_blocks = {
        name: deepcopy(value)
        for name, value in database["baseline"].items()
        if name in sut_native_blocks
    }

    def fake_parse_from_parquet(*, model="Database", calc_all=False, name=None, source=None, year=None, **kwargs):
        state = build_parser_state(
            table=database.meta.table,
            matrices=raw_blocks,
            indexes=deepcopy(database._indeces),
            units=deepcopy(database.units),
            parser_name="parse_from_parquet",
            source=source,
            name=name,
            year=year,
        )
        return build_database_from_state(state, model=model, calc_all=calc_all)

    monkeypatch.setattr("mario.parsers.entrypoints.parse_from_parquet", fake_parse_from_parquet)

    database.parse_from_parquet(
        path="ignored",
        table="SUT",
        mode="flows",
        flat=True,
        year=2023,
        source="GLORIA",
        name="GLORIA parquet",
        new_scenario=2023,
    )

    assert "2023" in database.scenarios
    for matrix, value in raw_blocks.items():
        pdt.assert_frame_equal(database["2023"][matrix], value)
    assert database.info["scenario_metadata"]["2023"]["year"] == 2023
    assert database.info["scenario_metadata"]["2023"]["source"] == "GLORIA"
    assert _ENUM.Z not in database["2023"]


def test_database_exposes_all_public_parser_entrypoints_as_callables():
    database = load_test("IOT")

    parser_names = {
        name
        for name in public_parsers.__all__
        if name.startswith(("parse_", "hybrid_"))
    }

    for parser_name in parser_names:
        assert callable(getattr(database, parser_name))


def test_database_dynamic_parser_attr_imports_parser_scenario(monkeypatch):
    database = load_test("IOT")
    raw_blocks = {
        name: deepcopy(value)
        for name, value in database["baseline"].items()
        if name in {_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.Y, _ENUM.EY, _ENUM.VY}
    }

    def fake_parse_exiobase_3(*, model="Database", calc_all=False, year=None, version=None, **kwargs):
        assert version == "3.9.4"
        state = build_parser_state(
            table=database.meta.table,
            matrices=raw_blocks,
            indexes=deepcopy(database._indeces),
            units=deepcopy(database.units),
            parser_name="parse_exiobase_3_9_4",
            source="EXIOBASE",
            year=year,
        )
        return build_database_from_state(state, model=model, calc_all=calc_all)

    monkeypatch.setattr("mario.parsers.entrypoints.parse_exiobase_3", fake_parse_exiobase_3)

    database.parse_exiobase_3_9_4(
        "ignored",
        year=2023,
        new_scenario=2023,
    )

    assert "2023" in database.scenarios
    for matrix, value in raw_blocks.items():
        pdt.assert_frame_equal(database["2023"][matrix], value)
    assert database.info["scenario_metadata"]["2023"]["year"] == 2023


def test_parse_scenario_rejects_incompatible_parser_payload(monkeypatch):
    database = load_test("IOT")
    raw_blocks = {
        name: deepcopy(value)
        for name, value in database["baseline"].items()
        if name in {_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.Y, _ENUM.EY, _ENUM.VY}
    }
    bad_indexes = deepcopy(database._indeces)
    bad_indexes["r"]["main"][0] = "Different region"

    def fake_parse_exiobase(*, model="Database", calc_all=False, **kwargs):
        state = build_parser_state(
            table=database.meta.table,
            matrices=raw_blocks,
            indexes=bad_indexes,
            units=deepcopy(database.units),
            parser_name="parse_exiobase",
            source="EXIOBASE",
            year=2023,
        )
        return build_database_from_state(state, model=model, calc_all=calc_all)

    monkeypatch.setattr("mario.parsers.entrypoints.parse_exiobase", fake_parse_exiobase)

    with pytest.raises(WrongInput, match="not compatible"):
        database.parse_scenario(
            "parse_exiobase",
            table="IOT",
            unit="Monetary",
            path="ignored",
            new_scenario="2023",
        )


def test_query_and_get_data_auto_calc():
    database = load_test("IOT")

    queried = database.query(matrices=[_ENUM.w], scenarios=["baseline"])
    data = database.get_data(
        matrices=[_ENUM.p],
        scenarios=["baseline"],
        units=True,
        indeces=True,
        auto_calc=True,
        format="dict",
    )

    assert isinstance(queried, pd.DataFrame)
    pdt.assert_frame_equal(queried, database.w)
    assert _ENUM.w in database["baseline"]
    pdt.assert_frame_equal(data["baseline"][_ENUM.p], database.p)
    assert "units" in data["baseline"]
    assert "indeces" in data["baseline"]


def test_custom_matrix_nomenclature_aliases_work_in_runtime_api():
    original = download_settings(None)

    try:
        custom = deepcopy(original)
        custom["nomenclature"]["z"] = "A"
        custom["nomenclature"]["w"] = "L"
        upload_settings(custom)

        database = load_test("IOT")

        queried_alias_z = database.query("A")
        queried_alias_w = database.query("L")
        queried_canonical_z = database.query("z")
        queried_canonical_w = database.query("w")

        pdt.assert_frame_equal(queried_alias_z, queried_canonical_z)
        pdt.assert_frame_equal(queried_alias_w, queried_canonical_w)
        pdt.assert_frame_equal(database.A, database.z)
        pdt.assert_frame_equal(database.L, database.w)
        assert "A" in database.available_matrices()
        assert "L" in database.available_matrices()
    finally:
        upload_settings(original)


def test_query_relative_difference_shape_is_preserved():
    database = load_test("IOT")
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"][_ENUM.Z] = database.Z * 2

    diff = database.query(
        matrices=[_ENUM.Z],
        scenarios=["policy"],
        base_scenario="baseline",
        type="relative",
    )

    expected = (
        database.matrices["policy"][_ENUM.Z]
        - database.matrices["baseline"][_ENUM.Z]
    ) / database.matrices["baseline"][_ENUM.Z]
    pdt.assert_frame_equal(diff, expected)


def test_database_api_accepts_new_sut_split_matrices():
    database = load_test("SUT")

    queried = database.query(matrices=["fa"], scenarios=["baseline"])
    payload = database.get_data(
        matrices=["va", "vc", "ea", "ec", "fa", "fc", "pa", "pc"],
        scenarios=["baseline"],
        format="dict",
    )

    ordering = SUTUnifiedOrderingPolicy.from_blocks(X=database.X, Y=database.Y)
    pdt.assert_frame_equal(queried, database.fa)
    pdt.assert_frame_equal(concat_sut_v(database.va, database.vc, ordering), database.v)
    pdt.assert_frame_equal(concat_sut_e(database.ea, database.ec, ordering), database.e)
    pdt.assert_frame_equal(concat_sut_f(database.fa, database.fc, ordering), database.f)
    pdt.assert_frame_equal(concat_sut_p(database.pa, database.pc, ordering), database.p)
    pdt.assert_frame_equal(
        payload["baseline"]["va"], extract_va_from_v(database.v, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["vc"], extract_vc_from_v(database.v, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["ea"], extract_ea_from_e(database.e, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["ec"], extract_ec_from_e(database.e, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["fa"], extract_fa_from_f(database.f, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["fc"], extract_fc_from_f(database.f, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["pa"], extract_pa_from_p(database.p, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["pc"], extract_pc_from_p(database.p, ordering)
    )


def test_set_clusters_normalizes_names_and_preserves_copy_semantics():
    database = load_test("IOT")

    database.set_clusters(
        clusters={"region": {"EU": ["Reg1", "Reg2"]}},
        s={"Primary": ["Agriculture"]},
    )

    stored = database.clusters
    assert stored == {
        "Region": {"EU": ["Reg1", "Reg2"]},
        "Sector": {"Primary": ["Agriculture"]},
    }

    stored["Region"]["EU"].append("dummy")
    assert database.clusters["Region"]["EU"] == ["Reg1", "Reg2"]


def test_default_clusters_include_all_for_every_set():
    database = load_test("IOT")

    defaults = database.default_clusters

    assert set(defaults) == set(database.sets)
    for set_name in database.sets:
        assert defaults[set_name]["all"] == database.get_index(set_name)


def test_default_region_clusters_include_country_converter_groups_when_possible():
    database = load_test("IOT")
    database._indeces["r"]["main"] = ["ITA", "FRA"]

    region_clusters = database.default_clusters["Region"]

    assert "continent:Europe" in region_clusters
    assert "ITA" in region_clusters["continent:Europe"]


def test_default_region_clusters_use_manual_adb_overrides_for_nonstandard_codes():
    database = load_test("IOT")
    database._indeces["r"]["main"] = ["GER", "UKG", "SWI", "TAP"]
    database.meta._add_attribute(source="ADB MRIO test payload")

    region_clusters = database.default_clusters["Region"]

    assert region_clusters["all"] == ["GER", "UKG", "SWI", "TAP"]
    assert "continent:Europe" in region_clusters
    assert set(["GER", "UKG", "SWI"]).issubset(region_clusters["continent:Europe"])
    assert "continent:Asia" in region_clusters
    assert "TAP" in region_clusters["continent:Asia"]
    assert set(["GER", "UKG"]).issubset(region_clusters["G7"])


def test_build_region_aggregation_index_uses_packaged_country_coverage():
    database = load_test("IOT")
    database._indeces["r"]["main"] = ["GER", "UKG", "SWI", "TAP"]
    database.meta._add_attribute(source="ADB MRIO test payload")

    aggregation = build_region_aggregation_index(database, "continent")

    assert aggregation.loc["GER", "Aggregation"] == "Europe"
    assert aggregation.loc["UKG", "Aggregation"] == "Europe"
    assert aggregation.loc["TAP", "Aggregation"] == "Asia"


def test_exports_with_include_meta_delegate_to_save_meta(monkeypatch, tmp_path):
    database = load_test("IOT")
    calls = []

    def fake_save_meta(path, format="txt"):
        calls.append((Path(path), format))

    monkeypatch.setattr(database, "save_meta", fake_save_meta)
    monkeypatch.setattr(export_module, "database_excel", lambda *args, **kwargs: None)
    monkeypatch.setattr(export_module, "_export_matrix_directory", lambda *args, **kwargs: None)
    monkeypatch.setattr(export_module, "require_pyarrow", lambda *args, **kwargs: None)

    excel_path = tmp_path / "database.xlsx"
    txt_root = tmp_path / "txt_export"
    parquet_root = tmp_path / "parquet_export"

    database.to_excel(path=str(excel_path), include_meta=True)
    database.to_txt(path=str(txt_root), include_meta=True)
    database.to_parquet(path=str(parquet_root), include_meta=True)

    assert calls == [
        (excel_path.parent / "metadata", "json"),
        (txt_root / "metadata", "json"),
        (parquet_root / "metadata", "json"),
    ]


def test_resolve_region_labels_to_iso3_members_expands_exiobase_macro_regions():
    resolved = resolve_region_labels_to_iso3_members(["WA", "WM"], source="EXIOBASE test bundle")

    assert "AFG" in resolved["WA"]
    assert "VNM" in resolved["WA"]
    assert "SAU" in resolved["WM"]
    assert "ARE" in resolved["WM"]


def test_available_clusters_merge_defaults_and_user_clusters():
    database = load_test("IOT")
    database.set_clusters(clusters={"region": {"EU custom": ["Reg1", "Reg2"]}})

    available = database.available_clusters

    assert "all" in available["Region"]
    assert available["Region"]["EU custom"] == ["Reg1", "Reg2"]


def test_get_shock_excel_uses_stored_clusters(tmp_path):
    database = load_test("IOT")
    database.set_clusters(clusters={"region": {"EU": ["Reg1", "Reg2"]}})
    path = tmp_path / "clustered_shock.xlsx"

    database.get_shock_excel(path=str(path), num_shock=2)

    indeces = pd.read_excel(path, sheet_name="indeces", header=None)
    assert "EU" in indeces.iloc[:, 0].dropna().tolist()


def test_shock_calc_uses_stored_clusters(tmp_path):
    database = load_test("IOT")
    database.set_clusters(clusters={"region": {"EU": ["Reg1", "Reg2"]}})
    path = tmp_path / "clustered_iot_shock.xlsx"

    base = database.z.copy()
    col = base.columns[0]
    row_items = [
        ("Reg1", row[1], row[2])
        for row in base.index
        if row[0] == "Reg1"
    ]
    row_item = row_items[0][2]
    updated = 0.222

    z_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: "EU",
                SHOCK_FLAT_COLUMNS["sector_from"]: row_item,
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["sector_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        z_sheet.to_excel(writer, sheet_name=_ENUM.z, index=False)

    database.shock_calc(str(path), z=True, scenario="cluster shock")

    shocked = database.query(_ENUM.z, scenarios=["cluster shock"])
    for region in ["Reg1", "Reg2"]:
        assert shocked.loc[(region, _MASTER_INDEX["s"], row_item), col] == updated


def test_get_shock_excel_still_accepts_legacy_cluster_kwargs(tmp_path):
    database = load_test("IOT")
    path = tmp_path / "legacy_clustered_shock.xlsx"

    database.get_shock_excel(path=str(path), num_shock=2, Region={"EU": ["Reg1", "Reg2"]})

    indeces = pd.read_excel(path, sheet_name="indeces", header=None)
    assert "EU" in indeces.iloc[:, 0].dropna().tolist()


def test_build_new_instance_preserves_stored_clusters():
    database = load_test("IOT")
    database.set_clusters(clusters={"region": {"EU": ["Reg1", "Reg2"]}})

    new = database.build_new_instance("baseline")

    assert new.clusters == {"Region": {"EU": ["Reg1", "Reg2"]}}


@pytest.mark.parametrize("scenario_name", ["reference", "baseline"])
def test_build_new_instance_preserves_public_baseline_scenario_name(scenario_name):
    database = load_test("IOT")
    database.rename_baseline_scenario("reference")

    new = database.build_new_instance(scenario_name)

    assert new.baseline_scenario_name == "reference"
    assert new.scenarios == ["reference"]


def test_shock_calc_rejects_public_baseline_scenario_name(tmp_path):
    database = load_test("IOT")
    database.rename_baseline_scenario("reference")

    with pytest.raises(WrongInput, match="reference scenario can not be overwritten"):
        database.shock_calc(str(tmp_path / "missing.xlsx"), z=True, scenario="reference")


def test_get_shock_excel_for_sut_writes_only_nonzero_split_sheets(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_shock.xlsx"

    database.get_shock_excel(path=str(path), num_shock=2)

    with pd.ExcelFile(path) as workbook:
        assert set(workbook.sheet_names) == {"indeces", "main", _ENUM.u, _ENUM.s, "Yc", "va", "ea"}
        assert _ENUM.z not in workbook.sheet_names
        assert "Ya" not in workbook.sheet_names
        assert "vc" not in workbook.sheet_names
        assert "ec" not in workbook.sheet_names

        u_sheet = pd.read_excel(workbook, _ENUM.u)
        assert list(u_sheet.columns) == [
            SHOCK_FLAT_COLUMNS["region_from"],
            SHOCK_FLAT_COLUMNS["commodity_from"],
            SHOCK_FLAT_COLUMNS["region_to"],
            SHOCK_FLAT_COLUMNS["activity_to"],
            SHOCK_FLAT_COLUMNS["type"],
            SHOCK_FLAT_COLUMNS["value"],
        ]


def test_get_shock_excel_for_iot_uses_flat_columns_without_levels(tmp_path):
    database = load_test("IOT")
    path = tmp_path / "iot_shock.xlsx"

    database.get_shock_excel(path=str(path), num_shock=2)

    with pd.ExcelFile(path) as workbook:
        indeces = pd.read_excel(workbook, "indeces", header=None)
        assert "all" in indeces.iloc[:, 0].dropna().tolist()

        z_sheet = pd.read_excel(workbook, _ENUM.z)
        assert list(z_sheet.columns) == [
            SHOCK_FLAT_COLUMNS["region_from"],
            SHOCK_FLAT_COLUMNS["sector_from"],
            SHOCK_FLAT_COLUMNS["region_to"],
            SHOCK_FLAT_COLUMNS["sector_to"],
            SHOCK_FLAT_COLUMNS["type"],
            SHOCK_FLAT_COLUMNS["value"],
        ]


def test_shock_calc_for_sut_reads_split_u_sheet(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_u_shock.xlsx"

    base_u = database.u.copy()
    row = base_u.index[0]
    col = base_u.columns[0]
    updated = 0.123456

    u_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["commodity_from"]: row[2],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["activity_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        u_sheet.to_excel(writer, sheet_name=_ENUM.u, index=False)

    database.shock_calc(str(path), z=True, scenario="split shock")

    expected = base_u.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.u, scenarios=["split shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_sut_accepts_split_s_alias(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_s_alias_shock.xlsx"

    base_s = database.s.copy()
    row = base_s.index[0]
    col = base_s.columns[0]
    updated = 0.654321

    s_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["activity_from"]: row[2],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["commodity_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        s_sheet.to_excel(writer, sheet_name=_ENUM.s, index=False)

    database.shock_calc(str(path), s=True, scenario="split s alias shock")

    expected = base_s.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.s, scenarios=["split s alias shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_sut_reads_split_Yc_sheet(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_yc_shock.xlsx"

    base = database.query("Yc").copy()
    row = base.index[0]
    col = base.columns[0]
    updated = 42.0

    yc_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["commodity_from"]: row[2],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["category_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        yc_sheet.to_excel(writer, sheet_name="Yc", index=False)

    database.shock_calc(str(path), Y=True, scenario="split Y shock")

    expected = base.copy()
    expected.loc[row, col] = updated
    shocked = database.query("Yc", scenarios=["split Y shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_iot_accepts_flat_z_sheet(tmp_path):
    database = load_test("IOT")
    path = tmp_path / "iot_flat_z_shock.xlsx"

    base = database.z.copy()
    row = base.index[0]
    col = base.columns[0]
    updated = 0.789

    z_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["sector_from"]: row[2],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["sector_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        z_sheet.to_excel(writer, sheet_name=_ENUM.z, index=False)

    database.shock_calc(str(path), z=True, scenario="flat iot shock")

    expected = base.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.z, scenarios=["flat iot shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_flat_iot_layout_accepts_z_sheet_without_level_axis(tmp_path):
    database = _build_flat_iot_template_database(tmp_path)
    path = tmp_path / "flat_iot_z_shock.xlsx"

    base = database.z.copy()
    row = base.index[0]
    col = base.columns[0]
    updated = 0.789

    z_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["sector_from"]: row[1],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["sector_to"]: col[1],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        z_sheet.to_excel(writer, sheet_name=_ENUM.z, index=False)

    database.shock_calc(str(path), z=True, scenario="flat iot special z shock")

    expected = base.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.z, scenarios=["flat iot special z shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_flat_iot_layout_accepts_y_sheet_without_level_axis(tmp_path):
    database = _build_flat_iot_template_database(tmp_path)
    path = tmp_path / "flat_iot_y_shock.xlsx"

    base = database.Y.copy()
    row = base.index[0]
    col = base.columns[0]
    updated = 12.34

    y_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["sector_from"]: row[1],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["category_to"]: col[1],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        y_sheet.to_excel(writer, sheet_name=_ENUM.Y, index=False)

    database.shock_calc(str(path), Y=True, scenario="flat iot special y shock")

    expected = base.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.Y, scenarios=["flat iot special y shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_flat_iot_layout_reads_factor_column_for_v_sheet(tmp_path):
    database = _build_flat_iot_template_database(tmp_path)
    path = tmp_path / "flat_iot_v_shock.xlsx"

    base = database.v.copy()
    row = base.index[0]
    col = base.columns[0]
    updated = 0.3

    v_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["factor_from"]: row,
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["sector_to"]: col[1],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        v_sheet.to_excel(writer, sheet_name=_ENUM.v, index=False)

    database.shock_calc(str(path), v=True, scenario="flat iot special v shock")

    expected = base.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.v, scenarios=["flat iot special v shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_accepts_excel_file_source_for_iot(tmp_path):
    database = load_test("IOT")
    path = tmp_path / "iot_excel_file_shock.xlsx"

    base = database.z.copy()
    row = base.index[0]
    col = base.columns[0]
    updated = 0.456789

    z_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["sector_from"]: row[2],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["sector_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        z_sheet.to_excel(writer, sheet_name=_ENUM.z, index=False)

    with pd.ExcelFile(path) as workbook:
        database.shock_calc(workbook, z=True, scenario="excel file shock")

    expected = base.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.z, scenarios=["excel file shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_sut_accepts_legacy_z_sheet(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_legacy_z_shock.xlsx"

    base_u = database.u.copy()
    row = base_u.index[0]
    col = base_u.columns[0]
    updated = 0.654321

    z_sheet = pd.DataFrame(
        [
            {
                SHOCK_COLUMNS["r_reg"]: row[0],
                SHOCK_COLUMNS["r_lev"]: row[1],
                SHOCK_COLUMNS["r_sec"]: row[2],
                SHOCK_COLUMNS["c_reg"]: col[0],
                SHOCK_COLUMNS["c_lev"]: col[1],
                SHOCK_COLUMNS["c_sec"]: col[2],
                SHOCK_COLUMNS["type"]: "Update",
                SHOCK_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        z_sheet.to_excel(writer, sheet_name=_ENUM.z, index=False)

    database.shock_calc(str(path), z=True, scenario="legacy shock")

    expected = base_u.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.u, scenarios=["legacy shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_plot_returns_flat_dataframe_for_iot_matrix():
    database = load_test("IOT")

    figure, plotted = database.plot(
        matrix=_ENUM.Z,
        scenarios="baseline",
        preset=None,
        kind="bar",
        x="Sector_from",
        color="Region_to",
        path=False,
        auto_open=False,
        return_data=True,
    )

    assert "Value" in plotted.columns
    assert "Sector_from" in plotted.columns
    assert "Region_to" in plotted.columns
    assert len(figure.data) > 0


def test_plot_supports_sut_split_semantics():
    database = load_test("SUT")

    figure, plotted = database.plot(
        matrix="U",
        scenarios="baseline",
        preset=None,
        kind="bar",
        x="Commodity_from",
        color="Activity_to",
        facet_col="Region_to",
        top_n=5,
        path=False,
        auto_open=False,
        return_data=True,
    )

    assert "Commodity_from" in plotted.columns
    assert "Activity_to" in plotted.columns
    assert len(figure.data) > 0


def test_plot_accepts_prepared_dataframe_input():
    database = load_test("IOT")
    data = database.GDP(total=False).reset_index()

    figure, plotted = database.plot(
        data=data,
        kind="treemap",
        preset=None,
        y="GDP",
        color="Region",
        path_columns=["Region", "Sector"],
        path=False,
        auto_open=False,
        return_data=True,
    )

    assert "GDP" in plotted.columns
    assert len(figure.data) > 0


def test_legacy_plot_wrappers_emit_deprecation_warning():
    database = load_test("IOT")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        figure = database.plot_matrix(
            _ENUM.Z,
            x="Sector_from",
            color="Region_to",
            path=False,
            auto_open=False,
        )

    assert len(figure.data) > 0
    assert any(item.category is DeprecationWarning for item in caught)


def test_plot_linkages_wrapper_uses_new_plot_engine():
    database = load_test("IOT")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        figure = database.plot_linkages(path=False, auto_open=False)

    assert len(figure.data) > 0
    assert any(item.category is DeprecationWarning for item in caught)


@pytest.mark.parametrize("scenario_name", ["reference", "baseline"])
def test_plot_linkages_wrapper_accepts_renamed_baseline_names(scenario_name):
    database = load_test("IOT")
    database.rename_baseline_scenario("reference")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        figure = database.plot_linkages(
            scenarios=[scenario_name],
            path=False,
            auto_open=False,
        )

    assert len(figure.data) > 0
    assert any(item.category is DeprecationWarning for item in caught)
