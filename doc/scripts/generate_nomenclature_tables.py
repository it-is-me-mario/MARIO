from __future__ import annotations

from html import escape
from pathlib import Path
import sys

from openpyxl import load_workbook


DOC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOC_ROOT.parent))
from mario.compute.import_catalog import IMPORT_DESCRIPTIONS, import_catalog
from mario.model.configuration import IMPORT_FLOW_BLOCKS, REGIONAL_TOPOLOGY
WORKBOOK = DOC_ROOT / "source" / "_static" / "data" / "supporting_files" / "Nomenclature_and_formulas.xlsx"
OUTPUT_DIR = DOC_ROOT / "source" / "get_started" / "_generated"


def normalize_rows(sheet_name: str):
    workbook = load_workbook(WORKBOOK, data_only=True)
    worksheet = workbook[sheet_name]
    rows = list(worksheet.iter_rows(values_only=True))
    workbook.close()
    headers = [str(value).strip() for value in rows[0] if value not in (None, "")]
    width = len(headers)
    body = []
    for row in rows[1:]:
        values = list(row[:width])
        if all(value in (None, "") for value in values):
            continue
        body.append(["" if value is None else str(value).strip() for value in values])
    return headers, body


def render_table(
    table_id: str,
    headers: list[str],
    rows: list[list[str]],
    preview_rows: int | None = None,
    preview_label: str = "rows",
) -> str:
    """Render one filterable table.

    With ``preview_rows``, the page shows only the first rows and a toggle to
    expand the rest (see ``_static/terminology-tables.js``). Without JavaScript
    the whole table stays visible.
    """
    preview = ""
    if preview_rows:
        preview = f' data-preview-rows="{preview_rows}" data-preview-label="{escape(preview_label)}"'
    html = []
    html.append(f'<div class="terminology-table-wrapper">')
    html.append(f'  <table id="{table_id}" class="terminology-table"{preview}>')
    html.append("    <thead>")
    html.append("      <tr>")
    for header in headers:
        html.append(f"        <th>{escape(header)}</th>")
    html.append("      </tr>")
    html.append('      <tr class="terminology-column-filters">')
    for index, header in enumerate(headers):
        html.append("        <th>")
        html.append(
            f'          <input class="terminology-column-filter" data-col-index="{index}" '
            f'type="search" aria-label="Filter {escape(header)}" placeholder="Filter {escape(header)}..." />'
        )
        html.append("        </th>")
    html.append("      </tr>")
    html.append("    </thead>")
    html.append("    <tbody>")
    for row in rows:
        search_blob = " ".join(row).lower()
        html.append(f'      <tr data-search="{escape(search_blob)}">')
        for index, cell in enumerate(row):
            if headers and headers[0] == "Matrix" and index == 0:
                html.append(f"        <td><strong>{escape(cell)}</strong></td>")
            else:
                html.append(f"        <td>{escape(cell)}</td>")
        html.append("      </tr>")
    html.append("    </tbody>")
    html.append("  </table>")
    html.append("</div>")
    return "\n".join(html) + "\n"


# Layout and reading order are editorial; names, definitions and axes come from
# the same workbook as the complete reference. Keep the first view on native
# blocks; the full runtime catalogue remains linked from each format page.
FORMATS = {
    "iot": {
        "columns": ["Sectors", "Final demand"],
        "rows": ["Sectors", "Factors", "Satellite accounts"],
        "blocks": [["Z", "Y"], ["V", "VY"], ["E", "EY"]],
        "derived": ["X", "z", "v", "e", "w", "f", "F", "m", "M", "p"],
    },
    "sut": {
        "columns": ["Commodities", "Activities", "Final demand"],
        "rows": ["Commodities", "Activities", "Factors", "Satellite accounts"],
        "blocks": [[None, "U", "Yc"], ["S", None, "Ya"],
                   ["Vc", "Va", "VY"], ["Ec", "Ea", "EY"]],
        "derived": ["Xa", "Xc", "u", "s", "c", "va", "vc", "ea", "ec",
                    "waa", "wcc", "wac", "wca", "fa", "fc", "Fa", "Fc",
                    "ma", "mc", "pa", "pc"],
    },
}
BLOCK_LABELS = {"Z": "Transactions", "U": "Use", "S": "Supply", "Y": "Final demand",
                "V": "Factors", "E": "Satellite accounts"}


COEFFICIENT_NAMES = {"Z": "z", "S": "s", "U": "u", "V": "v", "E": "e",
                     "Va": "va", "Vc": "vc", "Ea": "ea", "Ec": "ec",
                     "IMP": "imp", "IMP_a": "imp_a", "IMP_c": "imp_c"}


def matrix_cell(flow_name, mode, *, trade=None, origin=None, destination=None):
    """Render one native block at its declared regional coordinates."""
    if flow_name is None:
        return '<td class="table-map__empty"><span aria-label="No native block">—</span></td>', None
    name = COEFFICIENT_NAMES.get(flow_name, flow_name) if mode == "coefficients" else flow_name
    family = {"Y": "demand", "V": "factors", "E": "satellite", "I": "imports"}.get(flow_name[0], "core")
    topology = REGIONAL_TOPOLOGY.get(trade, {}).get(flow_name, "bilateral")
    zero = origin is not None and topology == "diagonal" and origin != destination
    coordinates = ""
    label = name
    if destination is not None:
        coordinates = f' data-region-to="{destination}"'
        label += f" to {destination}"
    if origin is not None:
        coordinates += f' data-region-from="{origin}"'
        label = f"{name} from {origin} to {destination}"
    if zero:
        label += ", structural zero"
    cell = (f'<td class="table-map__block is-{family}{" is-zero" if zero else ""}"{coordinates}>'
            f'<a href="#matrix-{name}" data-matrix-link="matrix-{name}" aria-label="{label}">'
            f'<code>{"0" if zero else name}</code></a></td>')
    return cell, name


def regional_grid(kind, trade, mode, caption):
    """Put Region outside the productive and final-demand classifications."""
    layout = FORMATS[kind]
    regions = ("R1", "R2")
    productive_rows = 2 if kind == "sut" else 1
    parts = ['<table class="table-map__grid table-map__grid--regional">', caption,
             '<colgroup><col class="table-map__row-region"><col class="table-map__row-type"></colgroup>']
    parts.extend(f'<colgroup span="{len(layout["columns"])}"></colgroup>' for _ in regions)
    parts.append('<thead><tr><th colspan="2" rowspan="2"></th>')
    parts.extend(f'<th scope="colgroup" colspan="{len(layout["columns"])}" '
                 f'class="table-map__region-heading">{region}</th>' for region in regions)
    parts.append('</tr><tr>')
    for region in regions:
        parts.extend(f'<th scope="col" data-region="{region}">{label}</th>' for label in layout["columns"])
    parts.append('</tr></thead>')
    names = []
    for origin in regions:
        parts.append(f'<tbody class="table-map__regional-body" data-region="{origin}">')
        for position in range(productive_rows):
            parts.append('<tr>')
            if position == 0:
                parts.append(f'<th scope="rowgroup" rowspan="{productive_rows}" '
                             f'class="table-map__region-heading">{origin}</th>')
            parts.append(f'<th scope="row">{layout["rows"][position]}</th>')
            for destination in regions:
                for flow_name in layout["blocks"][position]:
                    cell, name = matrix_cell(flow_name, mode, trade=trade, origin=origin, destination=destination)
                    parts.append(cell)
                    if name is not None:
                        names.append(name)
            parts.append('</tr>')
        parts.append('</tbody>')
    parts.append('<tbody class="table-map__common-accounts">')
    for label, row in zip(layout["rows"][productive_rows:], layout["blocks"][productive_rows:]):
        parts.append(f'<tr><th scope="row" colspan="2">{label}</th>')
        for destination in regions:
            for flow_name in row:
                cell, name = matrix_cell(flow_name, mode, destination=destination)
                parts.append(cell)
                names.append(name)
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return '\n'.join(parts), names


def configuration_grid(kind, scope, trade, imports, mode):
    label = trade.replace("-", " ").title() if scope == "multi-region" else imports.replace("-", " ")
    caption = f'<caption>{kind.upper()} · {scope} · {label} · {mode} · rows × columns</caption>'
    if scope == "multi-region":
        return regional_grid(kind, trade, mode, caption)
    layout = FORMATS[kind]
    rows = list(layout["rows"])
    blocks = [list(row) for row in layout["blocks"]]
    if imports == "separate":
        rows.insert(-1, "External imports")
        imported = IMPORT_FLOW_BLOCKS[kind.upper()]
        # SUT's diagram reads commodity columns before activity columns.
        blocks.insert(-1, [imported[1], imported[0], imported[2]] if kind == "sut" else list(imported))
    parts = ['<table class="table-map__grid">', caption, '<thead><tr><td></td>']
    parts.extend(f'<th scope="col">{name}</th>' for name in layout["columns"])
    parts.append('</tr></thead><tbody>')
    names = []
    for label, row in zip(rows, blocks):
        parts.append(f'<tr><th scope="row">{label}</th>')
        for flow_name in row:
            cell, name = matrix_cell(flow_name, mode)
            parts.append(cell)
            if name is not None:
                names.append(name)
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return '\n'.join(parts), names


def render_structure(kind, records):
    parts = [f'<div class="table-map is-multiregional" data-table-map="{kind}">',
             '<div class="table-map__controls" hidden>',
             '<label>Regions<select data-config="scope"><option value="multi-region">Multi-region</option>'
             '<option value="single-region">Single-region</option></select></label>']
    if kind == "sut":
        parts.append('<label data-trade-control>Trade<select data-config="trade">'
                     '<option value="isard">Isard</option><option value="chenery-moses">Chenery–Moses</option></select></label>')
    parts.extend(['<label data-import-control hidden>Imports<select data-config="imports">'
                  '<option value="factor-accounts">Factor accounts</option><option value="separate">Separate blocks</option></select></label>',
                  '<label>View<select data-config="mode"><option value="flows">Flows</option>'
                  '<option value="coefficients">Coefficients</option></select></label></div>'])
    names = []
    default_trade = "isard" if kind == "sut" else "bilateral"
    configurations = [("multi-region", default_trade, "factor-accounts"),
                      ("single-region", "external-trade", "factor-accounts"),
                      ("single-region", "external-trade", "separate")]
    if kind == "sut":
        configurations.insert(1, ("multi-region", "chenery-moses", "factor-accounts"))
    for scope, trade, imports in configurations:
        for mode in ("flows", "coefficients"):
            grid, selected_names = configuration_grid(kind, scope, trade, imports, mode)
            key = f"{scope}/{trade}/{imports}/{mode}"
            parts.append(f'<template data-config-grid="{key}">{grid}</template>')
            names.extend(selected_names)
    default_grid, _ = configuration_grid(kind, "multi-region", default_trade, "factor-accounts", "flows")
    parts.append(f'<div class="table-map__scroll">{default_grid}</div>')
    parts.append('<p class="table-map__legend"><span data-regional-legend>'
                 'R1 and R2 identify representative regions on the axes. '
                 'Colored matrix cells allow flows. 0 marks a structural zero. — marks an absent native block. </span>'
                 '<span data-config-explanation></span></p>')
    parts.append('<div class="table-map__definitions" aria-live="polite">')
    for name in dict.fromkeys(names):
        row = records.get(name)
        if row is None:
            spec = import_catalog(kind.upper())[name]
            row = {"Description": IMPORT_DESCRIPTIONS[name],
                   "Row indices": "Import descriptors, or one total-import row",
                   "Column indices": " × ".join(axis for axis in spec.axes.cols if axis != "Item")}
        parts.append(f'<section id="matrix-{name}" class="table-map__definition" data-matrix-definition>'
                     f'<p class="table-map__symbol"><code>{name}</code></p>'
                     f'<p class="table-map__description">{escape(row["Description"])}</p><dl>'
                     f'<dt>Rows</dt><dd>{escape(row["Row indices"])}</dd>'
                     f'<dt>Columns</dt><dd>{escape(row["Column indices"])}</dd></dl></section>')
    parts.append('</div></div>')
    return '\n'.join(parts) + '\n'


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    indices_headers, indices_rows = normalize_rows("Indices")
    matrices_headers, matrices_rows = normalize_rows("Matrices")
    records = {row[0]: dict(zip(matrices_headers, row)) for row in matrices_rows}

    for kind, layout in FORMATS.items():
        (OUTPUT_DIR / f"{kind}_structure.html").write_text(render_structure(kind, records), encoding="utf-8")
        indices = [[row[0], row[3]] for row in indices_rows if row[1] in ("All", kind.upper())]
        (OUTPUT_DIR / f"{kind}_indices.html").write_text(
            render_table(f"{kind}-indices", ["Index", "Description"], indices), encoding="utf-8")
        columns = ["Matrix", "Description", "Row indices", "Column indices"]
        derived = [[records[name][column] for column in columns] for name in layout["derived"]]
        (OUTPUT_DIR / f"{kind}_derived.html").write_text(
            render_table(f"{kind}-derived", columns, derived, preview_rows=5, preview_label="matrices"),
            encoding="utf-8")

        imports = []
        for name, spec in import_catalog(kind.upper()).items():
            if name not in IMPORT_DESCRIPTIONS:
                continue
            formulas = [strategy.spreadsheet_expr for strategy in spec.strategies if hasattr(strategy, "spreadsheet_expr")]
            columns = " × ".join(axis for axis in spec.axes.cols if axis != "Item")
            imports.append([name, IMPORT_DESCRIPTIONS[name], "Import descriptors", columns, " or ".join(formulas)])
        (OUTPUT_DIR / f"{kind}_imports.html").write_text(render_table(
            f"{kind}-imports", ["Matrix", "Description", "Row indices", "Column indices", "Formula"], imports,
        ), encoding="utf-8")

    (OUTPUT_DIR / "indices_table.html").write_text(
        render_table(
            table_id="terminology-indices-table",
            headers=indices_headers,
            rows=indices_rows,
        ),
        encoding="utf-8",
    )

    (OUTPUT_DIR / "matrices_table.html").write_text(
        render_table(
            table_id="terminology-matrices-table",
            headers=matrices_headers,
            rows=matrices_rows,
            preview_rows=4,
            preview_label="matrices",
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
