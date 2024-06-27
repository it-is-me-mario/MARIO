# -*- coding: utf-8 -*-
"""
mario plots are written in this module
"""

from mario.log_exc.exceptions import WrongInput
from mario.tools.constants import _MASTER_INDEX, _MATRICES_NAMES, _INDECES

from mario.tools.plots_manager import _PLOTS_LAYOUT, Color, _PALETTES

from mario.tools.utilities import run_from_jupyter

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pltly
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def set_palette(mario_palettes=None, user_palette=None):
    """Sets the default palette of plots

    .. note::
        if enough colors are not assigned to the palette non-duplicate random
        colors will be added to palette when needed

    Parameters
    ----------
    mario_palettes : str
        choosing betwwn mario default palettes

    user_palette : list
        a list of user palettes

    """

    if user_palette is not None:
        palette = user_palette

    else:
        if mario_palettes is not None:
            if mario_palettes not in _PALETTES:
                raise ValueError(f"Default palettes in mario are \n:{[*_PALETTES]}.")

            palette = _PALETTES[mario_palettes]
        else:
            palette = _PALETTES[7]

    _PLOTS_LAYOUT["palette"] = palette


def _plot_linkages(
    data: [pd.DataFrame, dict],
    path: str,
    multi_mode: bool,
    plot: str,
    annotations=True,
    auto_open: bool = False,
    **config,
):
    if isinstance(data, pd.DataFrame):
        links = {"Baseline": data}
    elif isinstance(data, dict):
        links = data
    else:
        raise WrongInput("data can be dict of pd.DataFrame or a DataFrame")

    # initializing the colors
    colors = Color()

    # to iterate over the scenarios which are the keys of the dictionary
    scenarios = [*links]

    backward = f"{plot} Backward"
    forward = f"{plot} Forward"

    counter = []

    layout = {
        "template": config.get("template", _PLOTS_LAYOUT["template"]),
        "font_family": config.get("template", _PLOTS_LAYOUT["font_family"]),
        "font_size": config.get("template", _PLOTS_LAYOUT["font_size"]),
    }

    if multi_mode:
        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=(forward, backward),
            shared_yaxes=True,
            horizontal_spacing=0.05,
        )

        layout[
            "title"
        ] = f"Sectors classification according to {plot} Backward and Forward linkages"
        layout[
            "legend_title_text"
        ] = "Regions<br><i>Foreign (light) over Total (opaque)"

        geo_types = ["Local", "Foreign"]

        for index, scenario in enumerate(scenarios):
            data = links[scenario]
            # removing the negative numbers
            legends = set()

            for col, ll in enumerate([forward, backward]):
                for gg in geo_types:
                    for color, region in enumerate(
                        data.index.unique(level=0)
                    ):  # iterating over regions
                        x = data.loc[(region, slice(None), slice(None)), (ll, gg)]
                        y = (
                            data.loc[(region, slice(None), slice(None)), (ll, gg)]
                            .index.get_level_values(2)
                            .tolist()
                        )

                        if gg == "Local":
                            base = data.loc[
                                (region, slice(None), slice(None)), (ll, "Foreign")
                            ]
                            # removing negatives if exists
                            base[base < 0] = 0
                            opacity = 1

                        else:
                            base = None
                            opacity = 0.5

                        fig.add_trace(
                            go.Bar(
                                x=x,
                                y=y,
                                name=region,
                                orientation="h",
                                marker_color=colors[color],
                                opacity=opacity,
                                offsetgroup=region,
                                legendgroup=region,
                                base=base,
                                showlegend=True if region not in legends else False,
                                visible=True if index == 0 else False,
                            ),
                            row=1,
                            col=1 + col,
                        )

                        legends.add(region)

                    # Show in hover text for each trace the region, value
                    fig.update_traces(hovertemplate="%{y}<br>%{x:.4f}")

            # geo_type * links_type * regions
            counter.append(2 * 2 * len(data.index.unique(level=0)))

    else:
        fig = go.Figure()
        # defining a margin for plots
        margin_max = config.get("margin_max", 1.05)
        margin_min = config.get("margin_max", 0.95)

        layout[
            "title"
        ] = "Sectors classification according to {} Backward and Forward Multipliers".format(
            plot
        )
        layout["legend_title_text"] = "Sectors"

        for index, scenario in enumerate(scenarios):
            data = links[scenario]

            # for backward margins
            max_b = margin_max * data[backward].max()
            min_b = margin_min * data[backward].min()

            # for forward margins
            max_f = margin_max * data[forward].max()
            min_f = margin_min * data[forward].min()

            counter.append(len(data.index.unique(level=-1)))
            # iterating over the columns of the links
            for color, sector in enumerate(data.index.unique(level=-1)):
                x = data.loc[
                    (slice(None), slice(None), sector), forward
                ]  # forward on the x axis
                y = data.loc[
                    (slice(None), slice(None), sector), backward
                ]  # backward on the y axis

                text = (
                    data.loc[(slice(None), slice(None), sector), :]
                    .index.get_level_values(0)
                    .tolist()
                )

                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y,
                        mode="markers",
                        name=sector,
                        text=text,
                        marker_color=colors[color],
                        visible=True if index == 0 else False,
                    )
                )

            # Setting the annotations
            fig.add_annotation(x=0.5, y=1.5, text="Dependent on Interindustry supply")
            fig.add_annotation(x=1.5, y=1.5, text="Generally Dependent")
            fig.add_annotation(x=0.5, y=0.5, text="Generally Independent")
            fig.add_annotation(x=1.5, y=0.5, text="Dependent on Interindustry demand")
            fig.add_shape(type="line", x0=1, y0=0, x1=1, y1=max_b)
            fig.add_shape(type="line", x0=0, y0=1, x1=max_f, y1=1)

            fig.update_xaxes(
                range=[min_f, max_f], title="Normalized {} Linkage".format(forward)
            )
            fig.update_yaxes(
                range=[min_b, max_b], title="Normalized {} Linkage".format(backward)
            )

    if len(scenarios) - 1:
        layout = _set_layout(
            fig=fig,
            layout=layout,
            mode=config.get("mode", "sliders"),
            counter=counter,
            iterator=scenarios,
            prefix=config.get("prefix", "Scenario"),
            x=config.get("xanchor"),
            y=config.get("yanchor"),
        )

    fig.update_layout(**layout)
    _plotter(fig=fig, directory=path, auto_open=auto_open)


def _plotter(fig, directory, auto_open):
    if run_from_jupyter():
        pltly.init_notebook_mode(connected=False)
        pltly.iplot({"data": fig.data, "layout": fig.layout})

    fig.write_html(directory, auto_open=auto_open)


def _set_layout(fig, layout, mode, counter, iterator, prefix, x, y):
    steps = []
    for index, item in enumerate(iterator):
        if index == 0:
            start = 0
            end = counter[index]
        else:
            start = counter[index - 1]
            end = start + counter[index]

        steps.append(
            dict(
                label=item,
                method="update",
                args=[
                    {
                        "visible": [
                            True if start <= i < end else False
                            for i in range(len(fig.data))
                        ]
                    },
                    {"title": "{}".format(layout["title"])},
                ],
            )
        )

    modifications = dict(
        active=0,
        pad={"t": 50},
    )

    if mode == "sliders":
        modifications["steps"] = steps
        modifications["currentvalue"] = {"prefix": prefix + ": "}

    elif mode == "updatemenus":
        modifications["buttons"] = steps
        modifications["x"] = y
        modifications["xanchor"] = "left"
        modifications["y"] = x
        modifications["yanchor"] = "bottom"

    else:
        raise WrongInput("Acceptable modes are ['sliders','updatemenus']")

    layout[mode] = [modifications]

    return layout


def _plotX(
    instance,
    matrix,
    x,
    y,
    color,
    facet_row,
    facet_col,
    animation_frame,
    base_scenario,
    path,
    item_from,
    chart,
    mode,
    auto_open,
    layout,
    shared_yaxes,
    shared_xaxes,
    filters,
):
    # Extracting raw data
    scenarios = instance.scenarios
    if base_scenario != None:
        scenarios.remove(base_scenario)
    to_plot = instance.get_data(
        matrices=matrix, format="dict", scenarios=scenarios, base_scenario=base_scenario
    )

    # Processing raw data for plottinh
    data = pd.DataFrame()
    for scenario in scenarios:
        to_append = to_plot[scenario][matrix]
        to_append.columns = [scenario]
        to_append = to_append.stack(level=0).to_frame()
        to_append.columns = [f"Value_{scenario}"]
        data = pd.concat([data, to_append], axis=1)
    data.fillna(0, inplace=True)
    data = data.sum(1).to_frame()
    data.columns = ["Value"]

    # Slicing according to filters
    data.index.names = [
        f"{_MASTER_INDEX['r']}_from",
        "Level_from",
        "Item_from",
        "Scenario",
    ]
    if instance.table_type == "IOT":
        data = data.loc[
            (
                filters[f"filter_{_MASTER_INDEX['r']}_from"],
                slice(None),
                filters[f"filter_{_MASTER_INDEX['s']}_from"],
                slice(None),
            ),
            :,
        ]
    elif instance.table_type == "SUT":
        data1 = data.loc[
            (
                filters[f"filter_{_MASTER_INDEX['r']}_from"],
                _MASTER_INDEX["a"],
                filters[f"filter_{_MASTER_INDEX['a']}_from"],
                slice(None),
            ),
            :,
        ]
        data2 = data.loc[
            (
                filters[f"filter_{_MASTER_INDEX['r']}_from"],
                _MASTER_INDEX["c"],
                filters[f"filter_{_MASTER_INDEX['c']}_from"],
                slice(None),
            ),
            :,
        ]
        data = data1.append(data2)

    data.reset_index(inplace=True)
    data = data[data["Level_from"] == item_from]
    cols = []
    for col in data.columns:
        if col == "Item_from":
            if instance.table_type == "SUT":
                if item_from == _MASTER_INDEX["c"]:
                    cols += [f"{_MASTER_INDEX['c']}_from"]
                else:
                    cols += [f"{_MASTER_INDEX['a']}_from"]
            else:
                cols += [f"{_MASTER_INDEX['s']}_from"]
        elif col == "Item_to":
            if instance.table_type == "SUT":
                if item_from == _MASTER_INDEX["c"]:
                    cols += [f"{_MASTER_INDEX['a']}_to"]
                else:
                    cols += [f"{_MASTER_INDEX['c']}_to"]
            else:
                cols += [f"{_MASTER_INDEX['s']}_to"]
        else:
            cols += [col]
    data.columns = cols

    # Other input management
    if animation_frame.capitalize() not in data.columns:
        raise WrongInput(
            f"'{animation_frame}' not a valid option for 'animation_frame'. Valid options are: {data.columns}"
        )

    plot_parameters_to_cap = {
        "x": x,
        "y": y,
        "color": color,
        "facet_row": facet_row,
        "facet_col": facet_col,
        "animation_frame": animation_frame,
    }
    plot_parameters_to_low = {
        "chart": chart,
        "mode": mode,
    }

    for param, given in plot_parameters_to_cap.items():
        if given != None:
            plot_parameters_to_cap[param] = given.capitalize()
    for param, given in plot_parameters_to_low.items():
        if given != None:
            plot_parameters_to_low[param] = given.lower()

    plot_parameters = plot_parameters_to_cap.copy()
    plot_parameters.update(plot_parameters_to_low)
    # for param,given in plot_parameters.items():
    # if given != None:
    #     if _MASTER_INDEX['s'] in given:
    #         plot_parameters[param] = given.replace(_MASTER_INDEX['s'],'Item')
    #     if _MASTER_INDEX['a'] in given:
    #         plot_parameters[param] = given.replace(_MASTER_INDEX['a'],'Item')
    #     if _MASTER_INDEX['c'] in given:
    #         plot_parameters[param] = given.replace(_MASTER_INDEX['c'],'Item')

    for key, value in plot_parameters.items():
        if value != None:
            if value.split("_")[-1] == "from":
                indices = _INDECES[instance.table_type][matrix]["indices"]
                elements = []
                for i in indices:
                    elements += [i]
                if value.split("_")[0] not in elements:
                    raise WrongInput(
                        f"Matrix {matrix} does not accept '{value}' as a valid option for '{key}'. Please rearrange your inputs"
                    )

            if value.split("_")[-1] == "to":
                columns = _INDECES[instance.table_type][matrix]["columns"]
                elements = []
                for i in columns:
                    elements += [i]
                if value.split("_")[0] not in elements:
                    raise WrongInput(
                        f"Matrix {matrix} does not accept '{value}' as a valid option for '{key}'. Please rearrange your inputs"
                    )

    # Plotting
    colors = Color()
    colors.has_enough_colors(plot_parameters["color"])
    if chart == "bar":
        fig = px.bar(
            data,
            x=plot_parameters["x"],
            y=plot_parameters["y"],
            color=plot_parameters["color"],
            animation_frame=plot_parameters["animation_frame"],
            facet_row=plot_parameters["facet_row"],
            facet_col=plot_parameters["facet_col"],
            barmode=plot_parameters["mode"],
            color_discrete_sequence=colors,
        )

    for key in layout:
        try:
            fig["layout"][key] = layout[key]
        except:
            pass

    _plotter(fig, path, auto_open=auto_open)


def _plotZYUS(
    instance,
    matrix,
    x,
    y,
    color,
    facet_row,
    facet_col,
    animation_frame,
    base_scenario,
    path,
    item_from,
    chart,
    mode,
    auto_open,
    layout,
    shared_yaxes,
    shared_xaxes,
    filters,
):
    # Extracting raw data
    scenarios = instance.scenarios
    if base_scenario != None:
        scenarios.remove(base_scenario)
    to_plot = instance.get_data(
        matrices=matrix, format="dict", scenarios=scenarios, base_scenario=base_scenario
    )

    # Processing raw data for plottinh
    data = pd.DataFrame()
    for scenario in scenarios:
        to_append = to_plot[scenario][matrix]
        to_append = to_append.stack(level=[0, 1, 2]).to_frame()
        to_append.columns = [scenario]
        to_append = to_append.stack(level=[0]).to_frame()
        to_append.columns = [f"Value_{scenario}"]
        data = pd.concat([data, to_append], axis=1)
    data.fillna(0, inplace=True)
    data = data.sum(1).to_frame()
    data.columns = ["Value"]

    # Slicing according to filters
    if matrix in ["Z", "z", "U", "u", "S", "s", "f_dis"]:
        data.index.names = [
            f"{_MASTER_INDEX['r']}_from",
            "Level_from",
            "Item_from",
            f"{_MASTER_INDEX['r']}_to",
            "Level_to",
            "Item_to",
            "Scenario",
        ]
        if instance.table_type == "IOT":
            data = data.loc[
                (
                    filters[f"filter_{_MASTER_INDEX['r']}_from"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['s']}_from"],
                    filters[f"filter_{_MASTER_INDEX['r']}_to"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['s']}_to"],
                    slice(None),
                ),
                :,
            ]
        elif instance.table_type == "SUT":
            if matrix == "S" or matrix == "s":
                data = data.loc[
                    (
                        filters[f"filter_{_MASTER_INDEX['r']}_from"],
                        _MASTER_INDEX["a"],
                        filters[f"filter_{_MASTER_INDEX['a']}_from"],
                        filters[f"filter_{_MASTER_INDEX['r']}_to"],
                        _MASTER_INDEX["c"],
                        filters[f"filter_{_MASTER_INDEX['c']}_to"],
                        slice(None),
                    ),
                    :,
                ]
            if matrix == "U" or matrix == "u":
                data = data.loc[
                    (
                        filters[f"filter_{_MASTER_INDEX['r']}_from"],
                        _MASTER_INDEX["c"],
                        filters[f"filter_{_MASTER_INDEX['c']}_from"],
                        filters[f"filter_{_MASTER_INDEX['r']}_to"],
                        _MASTER_INDEX["a"],
                        filters[f"filter_{_MASTER_INDEX['a']}_to"],
                        slice(None),
                    ),
                    :,
                ]

    elif matrix in ["Y"]:
        data.index.names = [
            f"{_MASTER_INDEX['r']}_from",
            "Level_from",
            "Item_from",
            f"{_MASTER_INDEX['r']}_to",
            "Level_to",
            f"{_MASTER_INDEX['n']}".replace(" ", "_"),
            "Scenario",
        ]
        if instance.table_type == "IOT":
            data = data.loc[
                (
                    filters[f"filter_{_MASTER_INDEX['r']}_from"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['s']}_from"],
                    filters[f"filter_{_MASTER_INDEX['r']}_to"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['n']}".replace(" ", "_")],
                    slice(None),
                ),
                :,
            ]
        elif instance.table_type == "SUT":
            data1 = data.loc[
                (
                    filters[f"filter_{_MASTER_INDEX['r']}_from"],
                    _MASTER_INDEX["a"],
                    filters[f"filter_{_MASTER_INDEX['a']}_from"],
                    filters[f"filter_{_MASTER_INDEX['r']}_to"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['n']}".replace(" ", "_")],
                    slice(None),
                ),
                :,
            ]
            data2 = data.loc[
                (
                    filters[f"filter_{_MASTER_INDEX['r']}_from"],
                    _MASTER_INDEX["c"],
                    filters[f"filter_{_MASTER_INDEX['c']}_from"],
                    filters[f"filter_{_MASTER_INDEX['r']}_to"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['n']}".replace(" ", "_")],
                    slice(None),
                ),
                :,
            ]
            data = data1.append(data2)
    data.reset_index(inplace=True)
    data = data[data["Level_from"] == item_from]
    cols = []
    for col in data.columns:
        if col == "Item_from":
            if instance.table_type == "SUT":
                if item_from == _MASTER_INDEX["c"]:
                    cols += [f"{_MASTER_INDEX['c']}_from"]
                else:
                    cols += [f"{_MASTER_INDEX['a']}_from"]
            else:
                cols += [f"{_MASTER_INDEX['s']}_from"]
        elif col == "Item_to":
            if instance.table_type == "SUT":
                if item_from == _MASTER_INDEX["c"]:
                    cols += [f"{_MASTER_INDEX['a']}_to"]
                else:
                    cols += [f"{_MASTER_INDEX['c']}_to"]
            else:
                cols += [f"{_MASTER_INDEX['s']}_to"]
        else:
            cols += [col]
    data.columns = cols

    # Other input management
    if animation_frame.capitalize() not in data.columns:
        raise WrongInput(
            f"'{animation_frame}' not a valid option for 'animation_frame'. Valid options are: {data.columns}"
        )

    plot_parameters_to_cap = {
        "x": x,
        "y": y,
        "color": color,
        "facet_row": facet_row,
        "facet_col": facet_col,
        "animation_frame": animation_frame,
    }
    plot_parameters_to_low = {
        "chart": chart,
        "mode": mode,
    }

    for param, given in plot_parameters_to_cap.items():
        if given != None:
            plot_parameters_to_cap[param] = given.capitalize()
    for param, given in plot_parameters_to_low.items():
        if given != None:
            plot_parameters_to_low[param] = given.lower()

    plot_parameters = plot_parameters_to_cap.copy()
    plot_parameters.update(plot_parameters_to_low)

    for key, value in plot_parameters.items():
        if value != None:
            if value.split("_")[-1] == "from":
                indices = _INDECES[instance.table_type][matrix]["indices"]
                elements = []
                for i in indices:
                    elements += [i]
                if value.split("_")[0] not in elements:
                    raise WrongInput(
                        f"Matrix {matrix} does not accept '{value}' as a valid option for '{key}'. Please rearrange your inputs"
                    )

            if value.split("_")[-1] == "to":
                columns = _INDECES[instance.table_type][matrix]["columns"]
                elements = []
                for i in columns:
                    elements += [i]
                if value.split("_")[0] not in elements:
                    raise WrongInput(
                        f"Matrix {matrix} does not accept '{value}' as a valid option for '{key}'. Please rearrange your inputs"
                    )

    # Plotting
    colors = Color()
    colors.has_enough_colors(plot_parameters["color"])
    if chart == "bar":
        fig = px.bar(
            data,
            x=plot_parameters["x"],
            y=plot_parameters["y"],
            color=plot_parameters["color"],
            animation_frame=plot_parameters["animation_frame"],
            facet_row=plot_parameters["facet_row"],
            facet_col=plot_parameters["facet_col"],
            barmode=plot_parameters["mode"],
            color_discrete_sequence=colors,
        )

    for key in layout:
        try:
            fig["layout"][key] = layout[key]
        except:
            pass

    _plotter(fig, path, auto_open=auto_open)


def _plotVEMF(
    instance,
    matrix,
    x,
    y,
    color,
    facet_row,
    facet_col,
    animation_frame,
    base_scenario,
    path,
    item_from,
    chart,
    mode,
    auto_open,
    layout,
    shared_yaxes,
    shared_xaxes,
    filters,
):
    # Extracting raw data
    scenarios = instance.scenarios
    if base_scenario != None:
        scenarios.remove(base_scenario)
    to_plot = instance.get_data(
        matrices=matrix, format="dict", scenarios=scenarios, base_scenario=base_scenario
    )

    # Processing raw data for plottinh
    data = pd.DataFrame()
    for scenario in scenarios:
        to_append = to_plot[scenario][matrix]
        to_append = to_append.stack(level=[0, 1, 2]).to_frame()
        to_append.columns = [scenario]
        to_append = to_append.stack(level=[0]).to_frame()
        to_append.columns = [f"Value_{scenario}"]
        data = pd.concat([data, to_append], axis=1)
    data.fillna(0, inplace=True)
    data = data.sum(1).to_frame()
    data.columns = ["Value"]

    # Slicing according to filters
    if matrix in ["V", "v", "M"]:
        data.index.names = [
            f"{_MASTER_INDEX['f']}",
            f"{_MASTER_INDEX['r']}_to",
            "Level_to",
            "Item_to",
            "Scenario",
        ]
        if instance.table_type == "IOT":
            data = data.loc[
                (
                    filters[f"filter_{_MASTER_INDEX['f']}".replace(" ", "_")],
                    filters[f"filter_{_MASTER_INDEX['r']}_to"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['s']}_to"],
                    slice(None),
                ),
                :,
            ]
        elif instance.table_type == "SUT":
            data = data.loc[
                (
                    filters[f"filter_{_MASTER_INDEX['f']}".replace(" ", "_")],
                    filters[f"filter_{_MASTER_INDEX['r']}_to"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['a']}_to"]
                    + filters[f"filter_{_MASTER_INDEX['c']}_to"],
                    slice(None),
                ),
                :,
            ]
    elif matrix in ["E", "e", "F"]:
        data.index.names = [
            f"{_MASTER_INDEX['k']}",
            f"{_MASTER_INDEX['r']}_to",
            "Level_to",
            "Item_to",
            "Scenario",
        ]
        if instance.table_type == "IOT":
            data = data.loc[
                (
                    filters[f"filter_{_MASTER_INDEX['k']}".replace(" ", "_")],
                    filters[f"filter_{_MASTER_INDEX['r']}_to"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['s']}_to"],
                    slice(None),
                ),
                :,
            ]
        elif instance.table_type == "SUT":
            data = data.loc[
                (
                    filters[f"filter_{_MASTER_INDEX['k']}".replace(" ", "_")],
                    filters[f"filter_{_MASTER_INDEX['r']}_to"],
                    slice(None),
                    filters[f"filter_{_MASTER_INDEX['a']}_to"]
                    + filters[f"filter_{_MASTER_INDEX['c']}_to"],
                    slice(None),
                ),
                :,
            ]
    elif matrix in ["EY"]:
        data.index.names = [
            f"{_MASTER_INDEX['k']}",
            f"{_MASTER_INDEX['r']}_to",
            "Level_to",
            f"{_MASTER_INDEX['n']}".replace(" ", "_"),
            "Scenario",
        ]
        data = data.loc[
            (
                filters[f"filter_{_MASTER_INDEX['k']}".replace(" ", "_")],
                filters[f"filter_{_MASTER_INDEX['r']}_to"],
                slice(None),
                filters[f"filter_{_MASTER_INDEX['n']}_to"],
                slice(None),
            ),
            :,
        ]
    data.reset_index(inplace=True)

    item_units = []
    if (
        len(
            set(
                to_plot[list(to_plot.keys())[0]]["units"][
                    list(data.columns)[0]
                ].T.values[0]
            )
        )
        > 1
    ):
        for i in range(data.shape[0]):
            s = data.iloc[i, list(data.columns).index("Scenario")]
            item_units += [
                f"{data.iloc[i,0]} [{to_plot[s]['units'][list(data.columns)[0]].loc[data.iloc[i,0],'unit']}]"
            ]
        data[list(data.columns)[0]] = item_units

    # data = data[data["Level_from"]==item_from]
    cols = []
    for col in data.columns:
        if col == "Item_from":
            if instance.table_type == "SUT":
                if item_from == _MASTER_INDEX["c"]:
                    cols += [f"{_MASTER_INDEX['c']}_from"]
                else:
                    cols += [f"{_MASTER_INDEX['a']}_from"]
            else:
                cols += [f"{_MASTER_INDEX['s']}_from"]
        elif col == "Item_to":
            if instance.table_type == "SUT":
                if item_from == _MASTER_INDEX["c"]:
                    cols += [f"{_MASTER_INDEX['c']}_to"]
                else:
                    cols += [f"{_MASTER_INDEX['a']}_to"]
            else:
                cols += [f"{_MASTER_INDEX['s']}_to"]
        else:
            cols += [col]
    data.columns = cols

    # Other input management
    if animation_frame.capitalize() not in data.columns:
        raise WrongInput(
            f"'{animation_frame}' not a valid option for 'animation_frame'. Valid options are: {data.columns}"
        )

    plot_parameters_to_cap = {
        "x": x,
        "y": y,
        "color": color,
        "facet_row": facet_row,
        "facet_col": facet_col,
        "animation_frame": animation_frame,
    }
    plot_parameters_to_low = {
        "chart": chart,
        "mode": mode,
    }

    for param, given in plot_parameters_to_cap.items():
        if given != None:
            plot_parameters_to_cap[param] = given.capitalize()
    for param, given in plot_parameters_to_low.items():
        if given != None:
            plot_parameters_to_low[param] = given.lower()

    plot_parameters = plot_parameters_to_cap.copy()
    plot_parameters.update(plot_parameters_to_low)

    for key, value in plot_parameters.items():
        if value != None:
            if value.split("_")[-1] == "from":
                indices = _INDECES[instance.table_type][matrix]["indices"]
                elements = []
                for i in indices:
                    elements += [i]
                if value.split("_")[0] not in elements:
                    raise WrongInput(
                        f"Matrix {matrix} does not accept '{value}' as a valid option for '{key}'. Please rearrange your inputs"
                    )

            if value.split("_")[-1] == "to":
                columns = _INDECES[instance.table_type][matrix]["columns"]
                elements = []
                for i in columns:
                    elements += [i]
                if value.split("_")[0] not in elements:
                    raise WrongInput(
                        f"Matrix {matrix} does not accept '{value}' as a valid option for '{key}'. Please rearrange your inputs"
                    )

    # Plotting
    colors = Color()
    colors.has_enough_colors(plot_parameters["color"])
    if chart == "bar":
        fig = px.bar(
            data,
            x=plot_parameters["x"],
            y=plot_parameters["y"],
            color=plot_parameters["color"],
            animation_frame=plot_parameters["animation_frame"],
            facet_row=plot_parameters["facet_row"],
            facet_col=plot_parameters["facet_col"],
            barmode=plot_parameters["mode"],
            color_discrete_sequence=colors,
        )

    for key in layout:
        try:
            fig["layout"][key] = layout[key]
        except:
            pass

    _plotter(fig, path, auto_open=auto_open)
