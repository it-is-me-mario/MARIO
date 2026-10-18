"""Regression tests for interrupted and cached Zenodo downloads."""

import hashlib
import io
from pathlib import Path
import zipfile

import pytest
import requests

from mario.download import _download_to_path, _extract_zip, download_exiobase3
from mario.log_exc.exceptions import WrongInput


class Response:
    def __init__(self, content=b"", *, status=200, headers=None, interrupted=False, payload=None):
        self.content = content
        self.status_code = status
        self.headers = headers or {}
        self.interrupted = interrupted
        self.payload = payload
        self.closed = False

    def raise_for_status(self):
        assert self.status_code < 400

    def json(self):
        return self.payload

    def iter_content(self, chunk_size):
        yield self.content
        if self.interrupted:
            raise requests.ConnectionError("transfer interrupted")

    def close(self):
        self.closed = True


def _checksum(content):
    return "md5:" + hashlib.md5(content, usedforsecurity=False).hexdigest()


def _archive():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("Z.txt", b"complete transaction matrix")
    return stream.getvalue()


@pytest.mark.parametrize("system", ["ixi", "pxp"])
@pytest.mark.parametrize("cached", [None, "archive", "partial"])
def test_exiobase_latest_resumes_and_verifies_before_extraction(monkeypatch, tmp_path, system, cached):
    content = _archive()
    filename = f"IOT_2022_{system}.zip"
    prefix = len(content) // 2
    if cached:
        target = tmp_path / (filename + (".part" if cached == "partial" else ""))
        target.write_bytes(content[:prefix])
    record = {"files": [{
        "key": filename, "size": len(content), "checksum": _checksum(content),
        "links": {"self": "https://files/archive"},
    }]}
    ranges, responses = [], []

    def get(url, **kwargs):
        if url == "https://zenodo.org/api/records/23039074":
            return Response(payload=record)
        assert url == "https://files/archive"
        headers = kwargs.get("headers")
        ranges.append(headers)
        if headers:
            assert headers == {"Range": f"bytes={prefix}-"}
            response = Response(content[prefix:], status=206, headers={
                "Content-Range": f"bytes {prefix}-{len(content) - 1}/{len(content)}",
                "Content-Length": str(len(content) - prefix),
            })
        else:
            response = Response(content[:prefix], interrupted=True)
        responses.append(response)
        return response

    monkeypatch.setattr("mario.download.requests.get", get)
    result = download_exiobase3(
        tmp_path, years=2022, system=system, version="3.11.2", keep_archives=True,
    )

    assert ranges == ([None] if cached is None else []) + [{"Range": f"bytes={prefix}-"}]
    assert all(response.closed for response in responses)
    assert Path(result["archives"][0]).read_bytes() == content
    assert (Path(result["extracted"][0]) / "Z.txt").read_bytes() == b"complete transaction matrix"
    assert not (tmp_path / (filename + ".part")).exists()


@pytest.mark.parametrize("system", ["ixi", "pxp"])
def test_exiobase_reuses_only_verified_cached_archive(monkeypatch, tmp_path, system):
    content = _archive()
    filename = f"IOT_2022_{system}.zip"
    target = tmp_path / filename
    record = {"files": [{
        "key": filename, "size": len(content), "checksum": _checksum(content),
        "links": {"self": "https://files/archive"},
    }]}
    binary_calls = []

    def get(url, **kwargs):
        if "/api/records/" in url:
            return Response(payload=record)
        binary_calls.append(url)
        return Response(content)

    monkeypatch.setattr("mario.download.requests.get", get)
    target.write_bytes(content)
    download_exiobase3(tmp_path, years=2022, system=system, version="3.11.2", extract=False)
    assert binary_calls == []

    # Same size, wrong checksum: the cached file must be replaced.
    target.write_bytes(b"x" * len(content))
    download_exiobase3(tmp_path, years=2022, system=system, version="3.11.2", extract=False)
    assert binary_calls == ["https://files/archive"]
    assert target.read_bytes() == content


def test_download_restarts_when_server_ignores_range(monkeypatch, tmp_path):
    target = tmp_path / "archive.zip"
    target.with_suffix(".zip.part").write_bytes(b"prefix")
    content = b"complete file"

    def get(url, **kwargs):
        assert kwargs["headers"] == {"Range": "bytes=6-"}
        return Response(content, headers={"Content-Length": str(len(content))})

    monkeypatch.setattr("mario.download.requests.get", get)
    _download_to_path("https://files/archive", target, overwrite=False,
                      expected_size=len(content), checksum=_checksum(content))
    assert target.read_bytes() == content


def test_download_preserves_partial_after_exhausted_attempts_then_resumes(monkeypatch, tmp_path):
    target = tmp_path / "archive.zip"
    partial = target.with_suffix(".zip.part")
    content = b"0123456789"
    responses = []

    def get(url, **kwargs):
        headers = kwargs.get("headers")
        offset = int(headers["Range"].split("=")[1].split("-")[0]) if headers else 0
        response = Response(
            content[offset:offset + 3], status=206 if offset else 200,
            headers={"Content-Range": f"bytes {offset}-9/10"}, interrupted=True,
        )
        responses.append(response)
        return response

    monkeypatch.setattr("mario.download._DOWNLOAD_ATTEMPTS", 2)
    monkeypatch.setattr("mario.download.requests.get", get)
    with pytest.raises(WrongInput, match="after 2 attempts"):
        _download_to_path("https://files/archive", target, overwrite=False,
                          expected_size=len(content), checksum=_checksum(content))
    assert not target.exists()
    assert partial.read_bytes() == content[:6]
    assert all(response.closed for response in responses)

    def resumed_get(url, **kwargs):
        assert kwargs["headers"] == {"Range": "bytes=6-"}
        return Response(content[6:], status=206, headers={"Content-Range": "bytes 6-9/10"})

    monkeypatch.setattr("mario.download.requests.get", resumed_get)
    _download_to_path("https://files/archive", target, overwrite=False,
                      expected_size=len(content), checksum=_checksum(content))
    assert target.read_bytes() == content
    assert not partial.exists()


def test_download_rejects_checksum_mismatch_without_promoting_file(monkeypatch, tmp_path):
    target = tmp_path / "archive.zip"
    response = Response(b"bad")
    monkeypatch.setattr("mario.download.requests.get", lambda *a, **kw: response)
    with pytest.raises(WrongInput, match="Integrity verification failed"):
        _download_to_path("https://files/archive", target, overwrite=False,
                          expected_size=3, checksum=_checksum(b"yes"))
    assert response.closed
    assert not target.exists()
    assert not target.with_suffix(".zip.part").exists()


def test_download_promotes_complete_verified_partial_without_request(monkeypatch, tmp_path):
    target = tmp_path / "archive.zip"
    target.with_suffix(".zip.part").write_bytes(b"done")

    def unexpected_get(*args, **kwargs):
        pytest.fail("A verified partial should not be downloaded again")

    monkeypatch.setattr("mario.download.requests.get", unexpected_get)
    _download_to_path("https://files/archive", target, overwrite=False,
                      expected_size=4, checksum=_checksum(b"done"))
    assert target.read_bytes() == b"done"


def test_failed_extraction_removes_incomplete_directory(monkeypatch, tmp_path):
    target = tmp_path / "archive.zip"
    target.write_bytes(_archive())
    extracted = tmp_path / "archive"

    def failed_extract(self, path):
        (path / "incomplete.txt").write_bytes(b"partial")
        raise zipfile.BadZipFile("broken member")

    monkeypatch.setattr(zipfile.ZipFile, "extractall", failed_extract)
    with pytest.raises(zipfile.BadZipFile, match="broken member"):
        _extract_zip(target, extracted, overwrite=False, keep_archive=False)
    assert not extracted.exists()
    assert target.exists()
