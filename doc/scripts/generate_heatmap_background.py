"""Generate the heatmap background of the MARIO documentation.

The background is a real slice of EXIOBASE: the intermediate purchases ``Z`` of
the region that trades the most with the rest of the world (China in
EXIOBASE 3.11.2, 2022), bought from every other region. The other regions are
aggregated to ten macro-regions with ``Database.aggregate`` and the
``UNregion`` preset, and colors come from
``Database.plot(preset="heatmap", log_color=True)``.

The script runs once, locally. Read the Docs serves the committed images
and stylesheet; it never downloads EXIOBASE.

Usage
-----

.. code-block:: bash

   # from the repository root, so that this checkout of MARIO is imported
   PYTHONPATH=. python doc/scripts/generate_heatmap_background.py /path/to/IOT_2022_ixi.zip

The archive can be fetched with
``mario.download_exiobase3(path, years=2022, system="ixi", version="3.11.2")``.
Pillow is needed to write the PNG.

Outputs
-------

* ``doc/source/_static/images/heatmap-background.png``: one pixel per matrix
  cell, MARIO yellow with the intensity level stored in the alpha channel.
* ``doc/source/_static/images/heatmap-background-dark.png``: identical matrix
  levels and alpha, with MARIO orange for the dark theme.
* ``doc/source/_static/heatmap-background.css``: matrix size and the column
  shown at the centre of the page, as CSS custom properties.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import mario
from mario.clusters.coverage import build_region_aggregation_index

DOC_SOURCE = Path(__file__).resolve().parents[1] / "source"
PNG_PATH = DOC_SOURCE / "_static" / "images" / "heatmap-background.png"
DARK_PNG_PATH = PNG_PATH.with_name("heatmap-background-dark.png")
CSS_PATH = DOC_SOURCE / "_static" / "heatmap-background.css"

MARIO_YELLOW = (253, 202, 39)
MARIO_ORANGE = (252, 107, 60)
LEVELS = 8
COLOR_CLIP = (0.03, 0.995)
WINDOW_COLUMNS = 64
# Phones show about 13-20 columns: they get their own window without blank columns.
NARROW_COLUMNS = 20

# UN geoscheme subregions (and EXIOBASE rest-of-world codes) merged to ten groups.
MACRO_REGIONS = {
    "Western Europe": "Western Europe",
    "Northern Europe": "Northern Europe",
    "Southern Europe": "Southern Europe",
    "Eastern Europe": "Eastern Europe",
    "WE": "Eastern Europe",
    "Northern America": "Northern America",
    "Central America": "Latin America",
    "South America": "Latin America",
    "WL": "Latin America",
    "Eastern Asia": "Eastern Asia",
    "Southern Asia": "South Asia and Oceania",
    "South-eastern Asia": "South Asia and Oceania",
    "Australia and New Zealand": "South Asia and Oceania",
    "WA": "South Asia and Oceania",
    "Western Asia": "Middle East",
    "WM": "Middle East",
    "Southern Africa": "Africa",
    "WF": "Africa",
}


def region_block_sums(z: pd.DataFrame) -> pd.DataFrame:
    """Sum Z into a region-by-region table."""
    by_column = z.T.groupby(level="Region", sort=False).sum().T
    return by_column.groupby(level="Region", sort=False).sum()


def most_connected_region(z: pd.DataFrame) -> str:
    """Region with the largest intermediate imports plus exports."""
    blocks = region_block_sums(z)
    domestic = pd.Series(np.diag(blocks.to_numpy()), index=blocks.index)
    trade = blocks.sum(axis=0) + blocks.sum(axis=1) - 2 * domestic
    return str(trade.idxmax())


def macro_region_mapping(database, focus: str) -> pd.Series:
    """UNregion preset merged to ten groups, with the focus region kept alone."""
    preset = build_region_aggregation_index(database, "UNregion")["Aggregation"]
    mapping = preset.map(lambda group: MACRO_REGIONS.get(group, group))
    mapping[focus] = focus
    unknown = sorted(set(mapping.drop(focus)) - set(MACRO_REGIONS.values()))
    if unknown:
        raise ValueError(f"Regions without a macro-region: {unknown}")
    return mapping


def quantize(colors: np.ndarray, levels: int, method: str = "rank") -> np.ndarray:
    """Map finite color values to 1..levels; blank cells to 0.

    ``"linear"`` splits the color range in equal steps. ``"rank"`` puts the same
    number of cells in every level, so the texture stays varied and no single
    structure, such as same-sector trade, dominates.
    """
    finite = np.isfinite(colors)
    result = np.zeros(colors.shape, dtype=np.uint8)
    if not finite.any():
        return result
    values = colors[finite]
    if method == "rank":
        scaled = (pd.Series(values).rank(method="average", pct=True).to_numpy() - 1e-9)
    else:
        low, high = values.min(), values.max()
        scaled = (values - low) / ((high - low) or 1.0)
    result[finite] = np.minimum(levels, 1 + np.floor(scaled * levels)).astype(np.uint8)
    return result


def densest_window_centre(levels: np.ndarray, width: int) -> float:
    """Matrix column (in cells) at the centre of the densest window of columns."""
    weight = levels.astype(float).sum(axis=0)
    width = min(width, weight.size)
    sums = np.convolve(weight, np.ones(width), mode="valid")
    start = int(np.argmax(sums))
    return start + width / 2


def narrow_window_centre(levels: np.ndarray, centre: float, width: int) -> float:
    """Centre of the narrow window closest to ``centre`` whose columns are all mostly filled.

    On phones only a few columns are visible, so a fully blank column (a sector
    with no purchases from abroad) at the screen edge stands out.
    """
    filled = (levels > 0).mean(axis=0)
    starts = [
        start
        for start in range(0, levels.shape[1] - width + 1)
        if filled[start:start + width].min() > 0.5
    ]
    if not starts:
        return centre
    best = min(starts, key=lambda start: abs(start + width / 2 - centre))
    return best + width / 2


def write_png(
    levels: np.ndarray, path: Path, color: tuple[int, int, int] = MARIO_YELLOW
) -> None:
    """Write a palette PNG: one colour, one alpha value per level."""
    from PIL import Image

    alpha_ramp = [0] + [round(255 * (level / LEVELS) ** 0.9) for level in range(1, LEVELS + 1)]
    image = Image.fromarray(levels.astype(np.uint8), mode="L").convert("P")
    image.putpalette(list(color) * (LEVELS + 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True, transparency=bytes(alpha_ramp))


def write_css(meta: dict, path: Path) -> None:
    path.write_text(
        "/* Generated by doc/scripts/generate_heatmap_background.py. Do not edit. */\n"
        f"/* {meta['source']}: Z block, {meta['focus']} columns, {meta['groups']} row groups. */\n"
        ":root {\n"
        f"  --mario-heat-cols: {meta['columns']};\n"
        f"  --mario-heat-rows: {meta['rows']};\n"
        f"  --mario-heat-centre: {meta['centre']};\n"
        f"  --mario-heat-centre-narrow: {meta['centre_narrow']};\n"
        "}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("exiobase_zip", type=Path, help="EXIOBASE monetary IOT ixi archive")
    parser.add_argument("--source-label", default="EXIOBASE 3.11.2, IOT ixi, 2022")
    parser.add_argument("--levels-method", choices=["rank", "linear"], default="rank")
    parser.add_argument("--png", type=Path, default=PNG_PATH)
    parser.add_argument("--dark-png", type=Path, default=DARK_PNG_PATH)
    parser.add_argument("--css", type=Path, default=CSS_PATH)
    args = parser.parse_args()

    database = mario.parse_exiobase(table="IOT", unit="Monetary", path=str(args.exiobase_zip))
    focus = most_connected_region(database.query("Z"))
    mapping = macro_region_mapping(database, focus)
    aggregated = database.aggregate(io=None, levels="Region", region_aggregation=mapping, inplace=False)

    z = aggregated.query("Z")
    blocks = region_block_sums(z)
    groups = blocks[focus].drop(focus).sort_values(ascending=False).index.tolist()
    sectors = list(dict.fromkeys(z.index.get_level_values("Item")))
    row_order = [f"{group} · {sector}" for group in groups for sector in sectors]

    _, plotted = aggregated.plot(
        matrix="Z",
        preset="heatmap",
        filters={"Region_from": groups, "Region_to": [focus]},
        log_color=True,
        color_clip=COLOR_CLIP,
        category_orders={"Row": row_order, "Column": sectors},
        path=False,
        auto_open=False,
        return_data=True,
    )
    colors = (
        plotted.pivot(index="Row", columns="Column", values="Color")
        .reindex(index=row_order, columns=sectors)
        .to_numpy(dtype=float)
    )
    levels = quantize(colors, LEVELS, args.levels_method)
    write_png(levels, args.png)
    write_png(levels, args.dark_png, MARIO_ORANGE)

    meta = {
        "source": args.source_label,
        "focus": focus,
        "groups": len(groups),
        "group_order": groups,
        "rows": levels.shape[0],
        "columns": levels.shape[1],
        "centre": densest_window_centre(levels, WINDOW_COLUMNS),
        "levels_method": args.levels_method,
        "blank_share": round(float((levels == 0).mean()), 3),
        "generated": date.today().isoformat(),
    }
    meta["centre_narrow"] = narrow_window_centre(levels, meta["centre"], NARROW_COLUMNS)
    write_css(meta, args.css)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
