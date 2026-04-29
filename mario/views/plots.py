"""Unified plotting helpers built on top of Plotly Express."""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

import pandas as pd
import plotly.express as px
import plotly.offline as pltly

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import MATRIX_TITLES, _MASTER_INDEX
from mario.utils import run_from_jupyter
from mario.views.plot_specs import _PALETTES, _PLOTS_LAYOUT

logger = logging.getLogger(__name__)


def set_palette(mario_palettes=None, user_palette=None):
    """Set the default discrete palette used by MARIO plots."""
    if user_palette is not None:
        palette = user_palette
    else:
        if mario_palettes is not None:
            if mario_palettes not in _PALETTES:
                raise ValueError(f"Default palettes in mario are \n:{[*_PALETTES]}.")
            palette = _PALETTES[mario_palettes]
        else:
            palette = _PALETTES["mario"]

    _PLOTS_LAYOUT["palette"] = palette


def _plotter(fig, directory, auto_open):
    """Render a figure inline in notebooks and persist it to HTML."""
    if run_from_jupyter():
        pltly.init_notebook_mode(connected=False)
        pltly.iplot({"data": fig.data, "layout": fig.layout})

    fig.write_html(directory, auto_open=auto_open)


def _default_color_sequence() -> list[str]:
    palette = _PLOTS_LAYOUT.get("palette")
    if palette:
        return list(palette)
    return list(_PALETTES["mario"])


def _normalize_layout(layout=None) -> dict:
    merged = {
        "template": _PLOTS_LAYOUT["template"],
        "font_family": _PLOTS_LAYOUT["font_family"],
        "font_size": _PLOTS_LAYOUT["font_size"],
    }
    if layout:
        merged.update(layout)
    return merged


def _as_list(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple, set, pd.Index)):
        return list(value)
    return [value]


def _make_unique_names(names: Sequence[str | None], *, prefix: str) -> list[str]:
    counts: dict[str, int] = {}
    resolved = []
    for index, name in enumerate(names):
        base = str(name).strip() if name not in (None, "") else f"{prefix}_{index + 1}"
        counts[base] = counts.get(base, 0) + 1
        if counts[base] == 1:
            resolved.append(base)
        else:
            resolved.append(f"{base}_{counts[base]}")
    return resolved


def _deduplicate_axis_labels(row_names: list[str], col_names: list[str]) -> tuple[list[str], list[str]]:
    duplicates = set(row_names).intersection(col_names)
    row_labels = [f"{name}_from" if name in duplicates else name for name in row_names]
    col_labels = [f"{name}_to" if name in duplicates else name for name in col_names]
    return row_labels, col_labels


def _attach_level_aliases(data: pd.DataFrame) -> pd.DataFrame:
    for side in ["from", "to"]:
        level_column = f"Level_{side}"
        item_column = f"Item_{side}"
        if level_column not in data.columns or item_column not in data.columns:
            continue

        for level_name in data[level_column].dropna().astype(str).unique():
            alias = f"{level_name}_{side}"
            if alias in data.columns:
                continue
            values = pd.Series(pd.NA, index=data.index, dtype="object")
            mask = data[level_column].astype(str) == level_name
            values.loc[mask] = data.loc[mask, item_column].astype("object")
            data[alias] = values

    return data


def _flatten_frame(frame: pd.DataFrame, *, scenario: str | None = None) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame should be a pandas DataFrame.")

    working = frame.copy()
    if isinstance(working.index, pd.MultiIndex):
        row_names = _make_unique_names(working.index.names, prefix="row")
    else:
        row_names = _make_unique_names([working.index.name], prefix="row")
        working.index = pd.Index(working.index, name=row_names[0])

    if isinstance(working.columns, pd.MultiIndex):
        col_names = _make_unique_names(working.columns.names, prefix="column")
    else:
        col_names = _make_unique_names([working.columns.name], prefix="column")
        working.columns = pd.Index(working.columns, name=col_names[0])

    row_labels, col_labels = _deduplicate_axis_labels(row_names, col_names)
    working.index.names = row_labels
    working.columns.names = col_labels
    stacked = working.stack(list(range(working.columns.nlevels))).rename("Value")
    data = stacked.reset_index()
    data = _attach_level_aliases(data)
    if scenario is not None:
        data["Scenario"] = scenario
    return data


def _normalize_scenarios(scenarios) -> list[str]:
    if isinstance(scenarios, str):
        return [scenarios]
    return list(scenarios)


def _apply_filters(data: pd.DataFrame, filters: dict | None) -> pd.DataFrame:
    if not filters:
        return data

    filtered = data
    for column, accepted in filters.items():
        if accepted in (None, "all"):
            continue
        if column not in filtered.columns:
            raise WrongInput(
                f"'{column}' is not a valid plot filter. Available columns are: {list(filtered.columns)}"
            )
        accepted_values = _as_list(accepted)
        filtered = filtered[filtered[column].isin(accepted_values)]
    return filtered


def _infer_plot_dimensions(data: pd.DataFrame) -> dict[str, str | None]:
    categorical = [
        column
        for column in data.columns
        if column != "Value" and not pd.api.types.is_numeric_dtype(data[column])
    ]
    row_like = [column for column in categorical if column.endswith("_from")]
    col_like = [column for column in categorical if column.endswith("_to")]
    account_like = [
        _MASTER_INDEX["k"],
        _MASTER_INDEX["f"],
        _MASTER_INDEX["n"],
    ]

    def first_available(candidates: Iterable[str]) -> str | None:
        for candidate in candidates:
            if candidate in data.columns:
                return candidate
        return None

    return {
        "row_item": first_available(["Item_from", *reversed(row_like)]),
        "col_item": first_available(["Item_to", *reversed(col_like)]),
        "row_region": first_available([f"{_MASTER_INDEX['r']}_from"]),
        "col_region": first_available([f"{_MASTER_INDEX['r']}_to"]),
        "scenario": first_available(["Scenario"]),
        "account": first_available(account_like),
        "categorical": categorical[0] if categorical else None,
    }


def _aggregate_plot_data(data: pd.DataFrame, *, dimensions: list[str], value: str, agg: str) -> pd.DataFrame:
    valid_dimensions = [dimension for dimension in dimensions if dimension in data.columns]
    if not valid_dimensions:
        return pd.DataFrame({value: [getattr(data[value], agg)()]})
    return data.groupby(valid_dimensions, dropna=False, as_index=False)[value].agg(agg)


def _select_top_n(data: pd.DataFrame, *, x: str | None, value: str, top_n: int | None) -> pd.DataFrame:
    if top_n is None or x is None or x not in data.columns:
        return data
    ranking = (
        data.assign(__abs__=data[value].abs())
        .groupby(x, as_index=False)["__abs__"]
        .sum()
        .sort_values("__abs__", ascending=False)
        .head(top_n)
    )
    return data[data[x].isin(ranking[x])]


def _apply_preset(
    data: pd.DataFrame,
    *,
    preset: str | None,
    kind: str | None,
    x: str | None,
    color: str | None,
    facet_col: str | None,
    top_n: int | None,
) -> tuple[str, str | None, str | None, str | None, int | None]:
    inferred = _infer_plot_dimensions(data)
    active_preset = preset or (None if x is not None else "overview")

    if active_preset is None:
        return kind or "bar", x, color, facet_col, top_n

    if active_preset == "overview":
        scenario_col = "Scenario" if "Scenario" in data.columns and data["Scenario"].nunique() > 1 else None
        return (
            kind or "bar",
            x or inferred["row_item"] or inferred["col_item"] or inferred["categorical"],
            color or inferred["account"] or inferred["col_region"] or inferred["col_item"] or inferred["row_region"],
            facet_col or scenario_col,
            20 if top_n is None else top_n,
        )

    if active_preset == "composition":
        return (
            kind or "bar",
            x or inferred["row_region"] or inferred["row_item"] or inferred["categorical"],
            color or inferred["row_item"] or inferred["account"] or inferred["col_item"],
            facet_col,
            15 if top_n is None else top_n,
        )

    if active_preset == "trend":
        return (
            kind or "line",
            x or inferred["scenario"],
            color or inferred["row_item"] or inferred["account"] or inferred["categorical"],
            facet_col,
            12 if top_n is None else top_n,
        )

    if active_preset == "heatmap":
        return (
            kind or "heatmap",
            x or inferred["col_item"] or inferred["scenario"] or inferred["categorical"],
            color,
            facet_col,
            top_n,
        )

    if active_preset in {"treemap", "sunburst"}:
        return active_preset, x, color, facet_col, top_n

    raise WrongInput(
        "Unknown plot preset '{}'. Acceptable presets are: ['overview', 'composition', 'trend', 'heatmap', 'treemap', 'sunburst']".format(
            active_preset
        )
    )


def build_matrix_plot_frame(
    database,
    matrix: str,
    *,
    scenarios="baseline",
    base_scenario=None,
    difference: str = "absolute",
    filters: dict | None = None,
    item: str | None = None,
) -> pd.DataFrame:
    scenarios = _normalize_scenarios(scenarios)
    if matrix not in database.available_blocks():
        raise WrongInput(f"'{matrix}' is not a valid matrix. Available matrices are: {database.available_blocks()}")

    missing = set(scenarios).difference(database.scenarios)
    if missing:
        raise WrongInput(
            f"Scenarios {sorted(missing)} do not exist in the database. Existing scenarios are: {database.scenarios}"
        )

    queried = database.query(
        matrices=[matrix],
        scenarios=scenarios,
        base_scenario=base_scenario,
        type=difference,
    )

    if len(scenarios) == 1:
        queried = {scenarios[0]: queried}

    frames = []
    for scenario, frame in queried.items():
        flat = _flatten_frame(frame, scenario=scenario)
        flat["Matrix"] = matrix
        frames.append(flat)

    data = pd.concat(frames, ignore_index=True)

    if item is not None:
        for level_column in ["Level_from", "Level_to"]:
            if level_column in data.columns and item in set(data[level_column]):
                data = data[data[level_column] == item]

    return _apply_filters(data, filters)


def build_linkages_plot_frame(data, *, plot: str) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        links = {"baseline": data}
    elif isinstance(data, dict):
        links = data
    else:
        raise WrongInput("data can be dict of pd.DataFrame or a DataFrame")

    frames = []
    for scenario, frame in links.items():
        working = frame.copy()
        if isinstance(working.columns, pd.MultiIndex):
            working.columns.names = ["Measure", "Component"]
            long = working.stack(list(range(working.columns.nlevels)), dropna=False).rename("Value").reset_index()
            long["Scenario"] = scenario
            long["Plot kind"] = plot
            frames.append(long)
            continue

        index_names = _make_unique_names(working.index.names, prefix="index")
        working.index.names = index_names
        long = working.reset_index()
        long["Scenario"] = scenario
        long["Plot kind"] = plot
        frames.append(long)

    return pd.concat(frames, ignore_index=True)


def plot_frame(
    data: pd.DataFrame,
    *,
    kind: str | None = None,
    preset: str | None = None,
    x: str | None = None,
    y: str = "Value",
    color: str | None = None,
    size: str | None = None,
    facet_row: str | None = None,
    facet_col: str | None = None,
    animation_frame: str | None = None,
    hover_name: str | None = None,
    hover_data=None,
    line_group: str | None = None,
    text: str | None = None,
    path_columns: list[str] | None = None,
    path: str | None = None,
    auto_open: bool = True,
    layout: dict | None = None,
    top_n: int | None = None,
    agg: str = "sum",
    barmode: str = "relative",
    log_x: bool = False,
    log_y: bool = False,
    title: str | None = None,
    color_continuous_scale=None,
    color_discrete_sequence=None,
    category_orders=None,
    return_data: bool = False,
    **kwargs,
):
    if data.empty:
        raise WrongInput("Cannot build a plot from an empty dataframe.")

    kind, x, color, facet_col, top_n = _apply_preset(
        data,
        preset=preset,
        kind=kind,
        x=x,
        color=color,
        facet_col=facet_col,
        top_n=top_n,
    )

    for column in [x, y, color, size, facet_row, facet_col, animation_frame, hover_name, line_group, text]:
        if column is not None and column not in data.columns:
            raise WrongInput(
                f"'{column}' is not a valid plot column. Available columns are: {list(data.columns)}"
            )

    dimensions = [
        column
        for column in [x, color, size, facet_row, facet_col, animation_frame, hover_name, line_group, text]
        if column is not None and column != y
    ]
    if kind in {"treemap", "sunburst"} and path_columns is not None:
        dimensions.extend(path_columns)

    plot_data = _aggregate_plot_data(data, dimensions=dimensions, value=y, agg=agg)
    plot_data = _select_top_n(plot_data, x=x, value=y, top_n=top_n)

    color_sequence = color_discrete_sequence or _default_color_sequence()
    color_scale = color_continuous_scale or px.colors.diverging.RdBu[::-1]

    common = dict(
        data_frame=plot_data,
        title=title,
        hover_name=hover_name,
        hover_data=hover_data,
        category_orders=category_orders,
    )
    hierarchical_common = dict(
        data_frame=plot_data,
        title=title,
        hover_data=hover_data,
    )

    if kind == "bar":
        fig = px.bar(
            x=x,
            y=y,
            color=color,
            facet_row=facet_row,
            facet_col=facet_col,
            animation_frame=animation_frame,
            text=text,
            barmode=barmode,
            color_discrete_sequence=color_sequence,
            log_x=log_x,
            log_y=log_y,
            **common,
            **kwargs,
        )
    elif kind == "line":
        fig = px.line(
            x=x,
            y=y,
            color=color,
            facet_row=facet_row,
            facet_col=facet_col,
            animation_frame=animation_frame,
            line_group=line_group,
            markers=kwargs.pop("markers", True),
            color_discrete_sequence=color_sequence,
            log_x=log_x,
            log_y=log_y,
            **common,
            **kwargs,
        )
    elif kind == "scatter":
        fig = px.scatter(
            x=x,
            y=y,
            color=color,
            size=size,
            facet_row=facet_row,
            facet_col=facet_col,
            animation_frame=animation_frame,
            text=text,
            color_discrete_sequence=color_sequence,
            log_x=log_x,
            log_y=log_y,
            **common,
            **kwargs,
        )
    elif kind == "area":
        fig = px.area(
            x=x,
            y=y,
            color=color,
            facet_row=facet_row,
            facet_col=facet_col,
            animation_frame=animation_frame,
            color_discrete_sequence=color_sequence,
            log_x=log_x,
            log_y=log_y,
            **common,
            **kwargs,
        )
    elif kind == "treemap":
        hierarchy = path_columns or [column for column in [color, x] if column is not None]
        if not hierarchy:
            raise WrongInput("treemap plots require path_columns or inferable categorical columns.")
        fig = px.treemap(
            path=hierarchy,
            values=y,
            color=color,
            color_continuous_scale=color_scale,
            **hierarchical_common,
            **kwargs,
        )
    elif kind == "sunburst":
        hierarchy = path_columns or [column for column in [color, x] if column is not None]
        if not hierarchy:
            raise WrongInput("sunburst plots require path_columns or inferable categorical columns.")
        fig = px.sunburst(
            path=hierarchy,
            values=y,
            color=color,
            color_continuous_scale=color_scale,
            **hierarchical_common,
            **kwargs,
        )
    elif kind == "heatmap":
        heatmap_y = kwargs.pop("heatmap_y", None)
        if heatmap_y is None:
            inferred = _infer_plot_dimensions(plot_data)
            heatmap_y = inferred["row_item"] or inferred["account"] or inferred["categorical"]
        if heatmap_y not in plot_data.columns:
            raise WrongInput(
                f"'{heatmap_y}' is not a valid heatmap axis. Available columns are: {list(plot_data.columns)}"
            )
        fig = px.density_heatmap(
            x=x,
            y=heatmap_y,
            z="Value",
            histfunc=agg,
            facet_col=facet_col,
            facet_row=facet_row,
            animation_frame=animation_frame,
            color_continuous_scale=color_scale,
            **common,
            **kwargs,
        )
    else:
        raise WrongInput(
            "Unknown plot kind '{}'. Acceptable kinds are: ['bar', 'line', 'scatter', 'area', 'treemap', 'sunburst', 'heatmap']".format(
                kind
            )
        )

    fig.update_layout(**_normalize_layout(layout))
    if path is not None:
        _plotter(fig=fig, directory=path, auto_open=auto_open)

    if return_data:
        return fig, plot_data
    return fig


def matrix_title(matrix: str) -> str:
    return MATRIX_TITLES.get(matrix, matrix)