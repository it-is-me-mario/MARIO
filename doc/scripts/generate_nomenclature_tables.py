from __future__ import annotations

from html import escape
from pathlib import Path

from openpyxl import load_workbook


DOC_ROOT = Path(__file__).resolve().parents[1]
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


def render_structure(kind, records):
    layout = FORMATS[kind]
    parts = [f'<div class="table-map" data-table-map="{kind}">',
             '<div class="table-map__scroll"><table class="table-map__grid">',
             f'<caption>{kind.upper()} native flows · rows × columns</caption>',
             '<thead><tr><td></td>']
    parts.extend(f'<th scope="col">{name}</th>' for name in layout["columns"])
    parts.append('</tr></thead><tbody>')
    names = []
    for label, blocks in zip(layout["rows"], layout["blocks"]):
        parts.append(f'<tr><th scope="row">{label}</th>')
        for name in blocks:
            if name is None:
                parts.append('<td class="table-map__empty"><span aria-label="No native block">—</span></td>')
                continue
            names.append(name)
            family = {"Y": "demand", "V": "factors", "E": "satellite"}.get(name[0], "core")
            parts.append(f'<td class="table-map__block is-{family}">'
                         f'<a href="#matrix-{name}" data-matrix-link="matrix-{name}">'
                         f'<code>{name}</code><span>{BLOCK_LABELS[name[0]]}</span></a></td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div><div class="table-map__definitions" aria-live="polite">')
    for name in names:
        row = records[name]
        parts.append(f'<section id="matrix-{name}" class="table-map__definition" data-matrix-definition>'
                     f'<p class="table-map__symbol"><code>{name}</code><span>Native flows</span></p>'
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
