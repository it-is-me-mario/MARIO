"""Guard public downloads against cached data and lost source notices."""
import importlib.util
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'doc/source'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


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
