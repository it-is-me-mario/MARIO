"""Guard public downloads against cached data and lost source notices."""
import importlib.util
import json
import re
from io import BytesIO
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'doc/source'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'


def compatibility_bindings(xml):
    """Validate prefix-valued OOXML metadata, which XML parsers do not check."""
    pending, scopes, bindings = [], [{}], []
    prefix_lists = {f'{{{MC}}}Ignorable', f'{{{MC}}}MustUnderstand'}
    qname_lists = {f'{{{MC}}}ProcessContent', f'{{{MC}}}PreserveAttributes',
                   f'{{{MC}}}PreserveElements'}
    for event, item in ET.iterparse(BytesIO(xml), events=('start-ns', 'start', 'end')):
        if event == 'start-ns':
            pending.append(item)
        elif event == 'start':
            scopes.append({**scopes[-1], **dict(pending)})
            pending.clear()
            for attr, value in item.attrib.items():
                if attr in prefix_lists or (item.tag == f'{{{MC}}}Choice' and attr == 'Requires'):
                    prefixes = value.split()
                elif attr in qname_lists:
                    prefixes = [q.split(':')[0] for q in value.split() if ':' in q]
                else:
                    continue
                for prefix in prefixes:
                    assert prefix in scopes[-1], f'Undeclared prefix {prefix!r} in {attr}={value!r}'
                    bindings.append((item.tag, attr, prefix, scopes[-1][prefix]))
        else:
            scopes.pop()
    return bindings


def test_excel_compatibility_prefixes_are_declared():
    for book in (SOURCE / '_static/data').rglob('*.xlsx'):
        with zipfile.ZipFile(book) as archive:
            for part in ('xl/workbook.xml', 'xl/styles.xml'):
                try:
                    compatibility_bindings(archive.read(part))
                except AssertionError as exc:
                    raise AssertionError(f'{book.name}: {part}: {exc}') from exc


@pytest.mark.parametrize('has_notice', [False, True])
def test_appending_notice_preserves_excel_metadata_and_calculations(tmp_path, has_notice):
    script = ROOT / 'doc/scripts/append_workbook_notice.py'
    spec = importlib.util.spec_from_file_location('append_workbook_notice', script)
    appender = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(appender)
    original = SOURCE / '_static/data/supporting_files/Nomenclature_and_formulas.xlsx'
    if not has_notice:
        without_notice = tmp_path / 'original.xlsx'
        with zipfile.ZipFile(original) as src, zipfile.ZipFile(without_notice, 'w') as out:
            book = minidom.parseString(src.read('xl/workbook.xml'))
            sheet = next(s for s in book.getElementsByTagNameNS(NS['m'], 'sheet')
                         if s.getAttribute('name') == 'Read me')
            rid = sheet.getAttributeNS(appender.R, 'id')
            sheet.parentNode.removeChild(sheet)
            rels = minidom.parseString(src.read('xl/_rels/workbook.xml.rels'))
            rel = next(r for r in rels.getElementsByTagNameNS(appender.P, 'Relationship')
                       if r.getAttribute('Id') == rid)
            target = rel.getAttribute('Target')
            notice_part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            rel.parentNode.removeChild(rel)
            types = minidom.parseString(src.read('[Content_Types].xml'))
            override = next(t for t in types.getElementsByTagNameNS(appender.C, 'Override')
                            if t.getAttribute('PartName') == '/' + notice_part)
            override.parentNode.removeChild(override)
            changed = {'xl/workbook.xml': book, 'xl/_rels/workbook.xml.rels': rels,
                       '[Content_Types].xml': types}
            for name in src.namelist():
                if name != notice_part:
                    payload = changed[name].toxml(encoding='utf-8') if name in changed else src.read(name)
                    out.writestr(name, payload)
        original = without_notice
    notice, output = tmp_path / 'notice.xlsx', tmp_path / 'output.xlsx'
    with zipfile.ZipFile(notice, 'w') as out:
        out.writestr('xl/styles.xml', f'''<styleSheet xmlns="{NS['m']}">
            <numFmts count="1"><numFmt numFmtId="164" formatCode="0.00"/></numFmts>
            <fonts count="1"><font><b/></font></fonts>
            <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
            <borders count="1"><border/></borders>
            <cellStyleXfs count="1"><xf numFmtId="164" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
            <cellXfs count="1"><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
            </styleSheet>''')
        out.writestr('xl/sharedStrings.xml', f'<sst xmlns="{NS["m"]}"><si><t>Updated notice</t></si></sst>')
        out.writestr('xl/worksheets/sheet1.xml', f'''<worksheet xmlns="{NS['m']}">
            <sheetData><row r="1"><c r="A1" s="0" t="s"><v>0</v></c></row></sheetData></worksheet>''')
    appender.append(original, notice, output)
    assert list(texts(output, 'Read me')) == ['Updated notice']
    with zipfile.ZipFile(original) as before, zipfile.ZipFile(output) as after:
        for name in ('xl/workbook.xml', 'xl/styles.xml'):
            assert compatibility_bindings(before.read(name)) == compatibility_bindings(after.read(name))
        for name in before.namelist():
            if name.startswith(('xl/worksheets/sheet', 'xl/calcChain', 'xl/metadata', 'xl/sharedStrings')):
                assert before.read(name) == after.read(name), name
        old_styles = ET.fromstring(before.read('xl/styles.xml'))
        new_styles = ET.fromstring(after.read('xl/styles.xml'))
        for group in old_styles:
            updated = new_styles.find(group.tag)
            assert [ET.tostring(e) for e in group] == [ET.tostring(e) for e in list(updated)[:len(group)]]
        book = ET.fromstring(after.read('xl/workbook.xml'))
        assert sum(s.get('name') == 'Read me' for s in book.findall('m:sheets/m:sheet', NS)) == 1
        rels = ET.fromstring(after.read('xl/_rels/workbook.xml.rels'))
        ids = [r.get('Id') for r in rels]
        assert len(ids) == len(set(ids))


def test_excel_package_roots_can_be_read_by_strict_opc_readers():
    for book in (SOURCE / '_static/data').rglob('*.xlsx'):
        with zipfile.ZipFile(book) as archive:
            for part, tag, namespace in [
                ('[Content_Types].xml', 'Types', 'http://schemas.openxmlformats.org/package/2006/content-types'),
                ('xl/_rels/workbook.xml.rels', 'Relationships', 'http://schemas.openxmlformats.org/package/2006/relationships'),
            ]:
                xml = archive.read(part)
                assert re.search(rb'<' + tag.encode() + rb'(?=[\s>])', xml), (book, part)
                assert ET.fromstring(xml).tag == '{' + namespace + '}' + tag


def module(name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / '_ext' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def texts(book, name):
    with zipfile.ZipFile(book) as z:
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        sheet = next(s for s in workbook.findall('m:sheets/m:sheet', NS) if s.get('name') == name)
        rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rel = next(r for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')) if r.get('Id') == rid)
        target = rel.get('Target')
        part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS)]
        for c in ET.fromstring(z.read(part)).iter('{'+NS['m']+'}c'):
            if c.get('t') == 'inlineStr':
                yield ''.join(c.find('m:is', NS).itertext())
            elif c.get('t') == 'str':
                yield (c.find('m:v', NS).text or '') if c.find('m:v', NS) is not None else ''
            elif c.get('t') == 's':
                yield strings[int(c.find('m:v', NS).text)]


def test_every_native_download_has_its_own_source_terms():
    data = json.loads((SOURCE / '_static/data/economy/download-metadata.json').read_text())
    for p in data['profiles'].values():
        book = SOURCE / p['workbook']
        if not p['workbook_allowed']:
            assert not book.exists(), 'Restricted inventory must not be publicly copied'
            continue
        notice = list(texts(book, 'Read me'))
        for required in [p['source_url'], p['attribution'], p['license_url']]:
            assert required and required in notice, (book, required)


def test_notebook_download_keeps_code_but_removes_saved_results():
    clean = module('mario_downloads').clean_notebook
    paths = [*SOURCE.glob('notebooks/parsers/**/*.ipynb'), *SOURCE.glob('user_guide/**/*.ipynb')]
    for path in paths:
        original = json.loads(path.read_text())
        result = clean(path, SOURCE)
        code = [c for c in result['cells'] if c['cell_type'] == 'code']
        before = [c for c in original['cells'] if c['cell_type'] == 'code']
        assert len(code) == len(before)
        assert all(c['outputs'] == [] and c['execution_count'] is None for c in code)
        assert '/Users/' not in json.dumps(result)
        for old, new in zip(before, code):
            if '/Users/' not in ''.join(old['source']):
                assert ''.join(old['source']) == ''.join(new['source'])
        assert 'Source databases keep their own licences' in json.dumps(result)


def test_eora_download_uses_the_publisher_instead_of_repackaging_sets():
    extension = module('mario_database_profiles')
    assert extension._workbook_url(None, 'resources/material', {'guide': 'eora'}) is None


def test_relocated_bonsai_example_keeps_attribution_and_published_guide_links():
    clean = module('mario_downloads').clean_notebook
    example = clean(SOURCE / 'user_guide/examples/bonsai.ipynb', SOURCE)
    text = '\n'.join(''.join(cell['source']) for cell in example['cells'])
    assert 'BONSAI source terms' in text
    assert 'https://www.marioproject.com/en/latest/user_guide/parsers/bonsai.html' in text
    assert 'https://www.marioproject.com/en/latest/api_document/mario.parse_bonsai.html' in text


def test_concordance_workbook_matches_typed_native_sets_and_carries_terms():
    book = SOURCE / '_static/data/economy/classification-concordances.xlsx'
    assert 'Source terms' in set(texts(book, 'Sources'))
    graph = json.loads((SOURCE / '_static/data/economy/sectoral-scope.json').read_text())
    assert all(c['family'] not in ['CEDA', 'GTAP'] for c in graph['columns']['commodity'])
    # The exported overview must use the current graph, not stale audit counts.
    overview = list(texts(book, 'Overview'))
    assert sum(s == 'CEDA' for s in overview) == 1
    expected = [c['label'] for c in graph['columns']['activity'] if c['family'] == 'GTAP']
    assert sum(s in expected for s in overview) == len(expected)
