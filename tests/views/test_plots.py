from unittest.mock import Mock, patch

import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.views import plots


def test_plotter_writes_html_when_inline_jupyter_rendering_fails(tmp_path):
    fig = Mock()
    fig.data = []
    fig.layout = {}
    output = tmp_path / "plot.html"

    with (
        patch.object(plots, "run_from_jupyter", return_value=True),
        patch.object(plots.pltly, "init_notebook_mode"),
        patch.object(plots.pltly, "iplot", side_effect=ValueError("missing nbformat")),
    ):
        plots._plotter(fig, output, auto_open=False)

    fig.write_html.assert_called_once_with(output, auto_open=False)


def _stacked_data():
    return pd.DataFrame({
        "Sector": ["Power", "Power", "Services", "Services", "Mining", "Mining"],
        "Region": ["Italy", "RoW"] * 3,
        "Value": [4.0, 6.0, 2.0, 3.0, 0.5, 0.5],
    })


@pytest.mark.parametrize("barmode", ["relative", "stack"])
def test_bar_totals_show_one_label_per_stack_and_hide_segment_labels(barmode):
    figure = plots.plot_frame(
        _stacked_data(), kind="bar", x="Sector", color="Region",
        barmode=barmode, show_totals=True, totals_format=",.0f",
        text="Value", text_auto=True,
        category_orders={"Sector": ["Services", "Power", "Mining"]},
    )
    bars = [trace for trace in figure.data if trace.type == "bar"]
    totals = [trace for trace in figure.data if trace.type == "scatter"]
    assert len(bars) == 2
    assert all(trace.text is None and trace.texttemplate is None for trace in bars)
    assert len(totals) == 1
    labels = totals[0]
    assert dict(zip(labels.x, labels.customdata)) == {"Mining": 1.0, "Power": 10.0, "Services": 5.0}
    assert dict(zip(labels.x, labels.y)) == {"Mining": 1.0, "Power": 10.0, "Services": 5.0}
    assert labels.texttemplate == "%{customdata:,.0f}"
    assert not labels.showlegend and labels.hoverinfo == "skip"
    assert figure.layout.xaxis.categoryarray == ("Services", "Power", "Mining")


def test_bar_totals_use_only_displayed_top_n_data():
    figure, plotted = plots.plot_frame(
        _stacked_data(), kind="bar", x="Sector", color="Region",
        top_n=2, show_totals=True, return_data=True,
    )
    labels = figure.data[-1]
    assert set(labels.x) == {"Power", "Services"}
    assert sum(labels.customdata) == pytest.approx(plotted.Value.sum())


def test_bar_totals_stay_on_their_facet_axes():
    data = pd.concat([
        _stacked_data().assign(Year="2021"),
        _stacked_data().assign(Year="2022", Value=lambda frame: frame.Value * 2),
    ])
    figure = plots.plot_frame(
        data, kind="bar", x="Sector", color="Region", facet_col="Year", show_totals=True,
    )
    labels = [trace for trace in figure.data if trace.type == "scatter"]
    assert {(trace.xaxis, trace.yaxis) for trace in labels} == {("x", "y"), ("x2", "y2")}
    assert sorted(sum(trace.customdata) for trace in labels) == [16.0, 32.0]


def test_bar_totals_label_net_values_outside_signed_stacks():
    data = pd.DataFrame({
        "Sector": ["Mixed", "Mixed", "Negative", "Negative"],
        "Region": ["Italy", "RoW"] * 2,
        "Value": [10.0, -3.0, -2.0, -4.0],
    })
    figure = plots.plot_frame(data, kind="bar", x="Sector", color="Region", show_totals=True)
    labels = figure.data[-1]
    assert dict(zip(labels.x, labels.customdata)) == {"Mixed": 7.0, "Negative": -6.0}
    assert dict(zip(labels.x, labels.y)) == {"Mixed": 10.0, "Negative": -6.0}
    assert dict(zip(labels.x, labels.textposition)) == {"Mixed": "top center", "Negative": "bottom center"}


def test_bar_totals_are_opt_in():
    figure = plots.plot_frame(_stacked_data(), kind="bar", x="Sector", color="Region", text_auto=True)
    assert all(trace.type == "bar" for trace in figure.data)
    assert all(trace.texttemplate is not None for trace in figure.data)


@pytest.mark.parametrize("options", [
    {"kind": "line"},
    {"kind": "bar", "barmode": "group"},
    {"kind": "bar", "animation_frame": "Region"},
])
def test_bar_totals_reject_incompatible_plot_modes(options):
    with pytest.raises(WrongInput, match="show_totals"):
        plots.plot_frame(_stacked_data(), x="Sector", show_totals=True, **options)
