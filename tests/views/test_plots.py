from unittest.mock import Mock, patch

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
