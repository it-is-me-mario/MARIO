"""Preview compression must preserve bytes, downloads and cache validation."""
import gzip
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import importlib.util
from functools import partial
from pathlib import Path
from threading import Thread

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('preview', ROOT / 'doc/scripts/serve_preview.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


@pytest.fixture
def server(tmp_path):
    content = b'{"regions": ["Italy", "France"]}\n' * 100
    (tmp_path / 'data.json').write_bytes(content)
    (tmp_path / 'book.xlsx').write_bytes(content)
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), partial(preview.PreviewHandler, directory=str(tmp_path)))
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_port, tmp_path, content
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def get(port, path, headers=None):
    connection = HTTPConnection('127.0.0.1', port)
    connection.request('GET', path, headers=headers or {})
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


def test_gzip_preserves_json_bytes_and_supports_unchanged_responses(server):
    port, directory, content = server
    status, headers, body = get(port, '/data.json', {'Accept-Encoding': 'gzip'})
    assert status == 200
    assert headers['Content-Encoding'] == 'gzip'
    assert headers['Vary'] == 'Accept-Encoding'
    assert int(headers['Content-Length']) == len(body) < len(content)
    assert gzip.decompress(body) == content
    status, _, body = get(port, '/data.json', {'Accept-Encoding': 'gzip', 'If-None-Match': headers['ETag']})
    assert status == 304 and body == b''
    (directory / 'data.json').write_bytes(content + b' ')
    status, _, body = get(port, '/data.json', {'Accept-Encoding': 'gzip', 'If-None-Match': headers['ETag']})
    assert status == 200 and gzip.decompress(body) == content + b' '


def test_excel_downloads_and_explicitly_disabled_compression_keep_original_bytes(server):
    port, _, content = server
    for path, encoding in [('/book.xlsx', 'gzip'), ('/data.json', 'gzip;q=0'), ('/data.json', 'identity')]:
        status, headers, body = get(port, path, {'Accept-Encoding': encoding})
        assert status == 200 and body == content
        assert 'Content-Encoding' not in headers
