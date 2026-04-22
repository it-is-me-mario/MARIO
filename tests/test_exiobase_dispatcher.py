import pytest

from mario import parse_exiobase
from mario.log_exc.exceptions import WrongInput


def test_parse_exiobase_download_monetary_iot_uses_downloaded_extract(monkeypatch, tmp_path):
    extracted = tmp_path / "IOT_2011_ixi"
    extracted.mkdir()
    calls = {}
    sentinel = object()

    def fake_download(path, **kwargs):
        calls["download"] = {"path": path, **kwargs}
        return {"extracted": [str(extracted)]}

    def fake_parser(**kwargs):
        calls["parser"] = kwargs
        return sentinel

    monkeypatch.setattr("mario.parsers.entrypoints.download_exiobase3", fake_download)
    monkeypatch.setattr("mario.parsers.entrypoints.parse_exiobase_3", fake_parser)

    parsed = parse_exiobase(
        table="IOT",
        unit="Monetary",
        path=str(tmp_path),
        year=2011,
        download=True,
        system="pxp",
        version="3.10.1",
        calc_all=False,
    )

    assert parsed is sentinel
    assert calls["download"]["table"] == "IOT"
    assert calls["download"]["years"] == 2011
    assert calls["download"]["system"] == "pxp"
    assert calls["download"]["version"] == "3.10.1"
    assert calls["parser"]["path"] == str(extracted)
    assert calls["parser"]["system"] == "pxp"
    assert calls["parser"]["version"] == "3.10.1"


def test_parse_exiobase_download_monetary_requires_year(tmp_path):
    with pytest.raises(WrongInput, match="requires 'year'"):
        parse_exiobase(
            table="IOT",
            unit="Monetary",
            path=str(tmp_path),
            download=True,
        )


def test_parse_exiobase_download_monetary_sut_uses_downloaded_extract(monkeypatch, tmp_path):
    extracted = tmp_path / "MRSUT_2011"
    extracted.mkdir()
    calls = {}
    sentinel = object()

    def fake_download(path, **kwargs):
        calls["download"] = {"path": path, **kwargs}
        return {"extracted": [str(extracted)]}

    def fake_parser(**kwargs):
        calls["parser"] = kwargs
        return sentinel

    monkeypatch.setattr("mario.parsers.entrypoints.download_exiobase3", fake_download)
    monkeypatch.setattr("mario.parsers.entrypoints.parse_exiobase_sut", fake_parser)

    parsed = parse_exiobase(
        table="SUT",
        unit="Monetary",
        path=str(tmp_path),
        year=2011,
        download=True,
        version="3.8.2",
        calc_all=False,
    )

    assert parsed is sentinel
    assert calls["download"]["table"] == "SUT"
    assert calls["download"]["years"] == 2011
    assert calls["download"]["version"] == "3.8.2"
    assert calls["parser"]["path"] == str(extracted)
    assert calls["parser"]["version"] == "3.8.2"


def test_parse_exiobase_download_hybrid_uses_download_dir(monkeypatch, tmp_path):
    calls = {}
    sentinel = object()

    def fake_download(path, **kwargs):
        calls["download"] = {"path": path, **kwargs}
        return {"download_dir": str(tmp_path)}

    def fake_parser(**kwargs):
        calls["parser"] = kwargs
        return sentinel

    monkeypatch.setattr("mario.parsers.entrypoints.download_hybrid_exiobase", fake_download)
    monkeypatch.setattr("mario.parsers.entrypoints.hybrid_iot_exiobase", fake_parser)

    parsed = parse_exiobase(
        table="IOT",
        unit="Hybrid",
        path=str(tmp_path),
        download=True,
        calc_all=False,
    )

    assert parsed is sentinel
    assert calls["download"]["table"] == "IOT"
    assert calls["parser"]["path"] == str(tmp_path)

