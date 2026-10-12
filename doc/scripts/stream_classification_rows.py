"""Stream typed inventory rows into a workbook layout authored by Artifact Tool.

This supplies the large-file serialization capability missing from the
monolithic exporter. It neither invents workbook structure nor calculates
formulas. Headers, formulas, tables, styles, panes and widths come from the
Artifact Tool export; all inventory values come from the reviewed JS builder.
"""
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ET.register_namespace('', NS['m'])
ET.register_namespace('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')


def column(index):
    result = ''
    while index:
        index, rem = divmod(index-1, 26)
        result = chr(65+rem)+result
    return result


def cell_xml(address, value, style):
    attr = f' r="{address}"'+(f' s="{style}"' if style is not None else '')
    if value is None or value == '':
        return f'<c{attr}/>'
    if isinstance(value, bool):
        return f'<c{attr} t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f'Non-finite number: {address}')
        return f'<c{attr} t="n"><v>{value}</v></c>'
    assert isinstance(value, str), (address, type(value))
    assert len(value) <= 32767, (address, len(value))
    assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value), address
    # inlineStr keeps official identifiers exact, including leading zeroes and
    # hash IDs that resemble scientific notation. It never evaluates formulas.
    return f'<c{attr} t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'


def stream(template, payload, output):
    inventory = json.loads(Path(payload).read_text())
    pending = Path(str(output)+'.pending')
    try:
        with zipfile.ZipFile(template) as source, zipfile.ZipFile(pending, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as result:
            # The authoring builder adds sheets in a fixed, validated order.
            workbook = ET.fromstring(source.read('xl/workbook.xml'))
            names = [s.attrib['name'] for s in workbook.find('m:sheets', NS)]
            assert names == list(inventory), (names, list(inventory))
            replaced = {}
            for index, name in enumerate(names, 1):
                if name == 'Overview':
                    continue  # Preserve Artifact Tool formulas and their caches.
                part = f'xl/worksheets/sheet{index}.xml'
                xml = source.read(part).decode('utf-8')
                sheet = ET.fromstring(xml)
                # Normalize the authoring export's namespace prefix before
                # inserting rows, so new elements inherit the main namespace.
                xml = ET.tostring(sheet, encoding='unicode')
                body = sheet.find('m:sheetData', NS)
                rows = inventory[name]['rows']
                header = inventory[name]['headers']
                assert inventory[name]['start'] == 1
                assert len(body) >= 13
                header_row = ET.tostring(body[0], encoding='unicode')
                # Retain the common authored body styles from rows 12/13.
                # The preview rows must not create a separate formatting regime.
                styles = {}
                heights = {}
                for authored in body:
                    number = int(authored.attrib['r'])
                    styles[number] = {re.sub(r'\d+', '', c.attrib['r']): c.get('s') for c in authored}
                    heights[number] = authored.get('ht', '22')
                bound = f'A1:{column(len(header))}{len(rows)+1}'
                replaced[part] = (xml, header_row, rows, styles, heights, bound, len(header))
                print(f'Streaming {name}: {len(rows):,} rows', flush=True)
            table_bounds = {name.replace(' ', '')+'Table': f"A{d['start']}:{column(len(d['headers']))}{d['start']+len(d['rows'])}" for name, d in inventory.items()}
            for info in source.infolist():
                if info.filename in replaced:
                    xml, first, rows, styles, heights, bound, width = replaced[info.filename]
                    match = re.search(r'<sheetData\b[^>]*>.*?</sheetData>', xml, re.S)
                    assert match, info.filename
                    prefix = re.sub(r'<dimension\b[^>]*/>', f'<dimension ref="{bound}"/>', xml[:match.start()])
                    with result.open(info.filename, 'w', force_zip64=True) as destination:
                        destination.write((prefix+'<sheetData>'+first).encode('utf-8'))
                        for number, values in enumerate(rows, 2):
                            assert len(values) == width
                            authored = 12+(number % 2)
                            style = styles[authored]
                            cells = ''.join(cell_xml(f'{column(c)}{number}', v, style.get(column(c))) for c, v in enumerate(values, 1))
                            height = heights[authored]
                            destination.write((f'<row r="{number}" ht="{height}" customHeight="1">'+cells+'</row>').encode('utf-8'))
                        destination.write(('</sheetData>'+xml[match.end():]).encode('utf-8'))
                elif re.fullmatch(r'xl/tables/table\d+\.xml', info.filename):
                    xml = source.read(info.filename).decode('utf-8')
                    table = ET.fromstring(xml)
                    bound = table_bounds[table.attrib['name']]
                    old = table.attrib['ref']
                    # Table and its autoFilter share the original authored bound.
                    xml = xml.replace(f'ref="{old}"', f'ref="{bound}"')
                    result.writestr(info, xml.encode('utf-8'))
                else:
                    result.writestr(info, source.read(info.filename))
        pending.replace(output)
    except BaseException:
        pending.unlink(missing_ok=True)
        raise
    print(f'Saved {output}', flush=True)


if __name__ == '__main__':
    assert len(sys.argv) == 4, 'layout.xlsx rows.json output.xlsx'
    stream(*sys.argv[1:])
