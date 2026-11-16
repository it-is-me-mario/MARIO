"""Keep channel inventories, referenced downloads and frozen JSON independent."""
import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "versioned_docs", Path(__file__).parents[2] / "doc/scripts/build_versioned_docs.py"
)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


def test_unreferenced_frozen_json_is_shared_without_removing_downloads(tmp_path):
    payload = b'{"padding":"' + b'x' * 70000 + b'"}'
    versions = {}
    for channel in ('latest', 'dev'):
        root = tmp_path / 'en' / channel
        data = root / '_static/data'
        data.mkdir(parents=True)
        for name in ('unused.json', 'linked.json', 'changed.json'):
            (data / name).write_bytes(payload if name != 'changed.json' else payload + channel.encode())
        (data / 'classification.xlsx').write_bytes(b'workbook')
        (root / 'index.html').write_text(
            '<nav class="mario-versions__options"></nav>'
            '<a href="_static/data/linked.json">Download</a>'
        )
        versions[channel] = {'label': channel.title(), 'url': f'https://example/en/{channel}/',
                             'documents': {'index': []}}
    catalogue = {'versions': versions}
    publisher.write_catalogue(tmp_path, catalogue)
    publisher.deduplicate_legacy_json(tmp_path, catalogue)
    for channel in ('dev',):
        root = tmp_path / 'en' / channel
        assert not (root / '_static/data/unused.json').exists()
        for name in ('linked.json', 'changed.json', 'classification.xlsx'):
            assert (root / '_static/data' / name).is_file()
        page = (root / 'index.html').read_text()
        assert page.count('data-docs-version=') == 2
        assert f'data-docs-version="{channel}" aria-current="page"' in page
        shared = json.loads((root / 'legacy-data-manifest.json').read_text())
        assert shared['_static/data/unused.json']['url'] == 'https://example/en/latest/_static/data/unused.json'
    assert (tmp_path / 'en/latest/_static/data/unused.json').read_bytes() == payload
