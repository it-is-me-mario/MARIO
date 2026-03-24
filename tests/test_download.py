from __future__ import annotations

import io
from pathlib import Path
import zipfile

import mario
import pytest

from mario.download import (
    download_eurostat,
    download_emerging,
    download_exiobase3,
    download_hybrid_exiobase,
    download_statcan,
    download_wiod2016,
)
from mario.log_exc.exceptions import NotImplementable


class FakeResponse:
    def __init__(
        self,
        *,
        json_data=None,
        content: bytes = b"",
        text: str | None = None,
        headers: dict[str, str] | None = None,
        status_code: int = 200,
        url: str = "",
    ) -> None:
        self._json_data = json_data
        self._content = content
        self.text = text if text is not None else content.decode("utf-8", errors="ignore")
        self.headers = headers or {}
        self.status_code = status_code
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data

    def iter_content(self, chunk_size: int = 1024 * 1024):
        for idx in range(0, len(self._content), chunk_size):
            yield self._content[idx : idx + chunk_size]

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_download_hybrid_exiobase_sut_selects_required_files(monkeypatch, tmp_path):
    record_url = "https://zenodo.org/api/records/7244919"
    record_payload = {
        "files": [
            {"key": "MR_HSUP_2011_v3_3_18.csv", "links": {"self": "https://files/hsup"}},
            {"key": "MR_HUSE_2011_v3_3_18.csv", "links": {"self": "https://files/huse"}},
            {"key": "MR_HSUTs_2011_v3_3_18_FD.csv", "links": {"self": "https://files/fd"}},
            {"key": "MR_HSUTs_2011_v3_3_18_extensions.xlsx", "links": {"self": "https://files/hsutext"}},
            {"key": "MR_HIOT_2011_v3_3_18_extensions.xlsx", "links": {"self": "https://files/hiotext"}},
            {"key": "Classifications_v_3_3_18.xlsx", "links": {"self": "https://files/meta"}},
            {"key": "MR_HIOT_2011_v3_3_18_by_product_technology.csv", "links": {"self": "https://files/hiot"}},
        ]
    }

    def fake_get(url, **kwargs):
        if url == record_url:
            return FakeResponse(json_data=record_payload)
        return FakeResponse(content=f"downloaded:{url}".encode())

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_hybrid_exiobase(tmp_path, table="SUT")

    downloaded = {Path(path).name for path in info["files"]}
    assert downloaded == {
        "MR_HSUP_2011_v3_3_18.csv",
        "MR_HUSE_2011_v3_3_18.csv",
        "MR_HSUTs_2011_v3_3_18_FD.csv",
        "MR_HSUTs_2011_v3_3_18_extensions.xlsx",
        "MR_HIOT_2011_v3_3_18_extensions.xlsx",
        "Classifications_v_3_3_18.xlsx",
    }


def test_download_exiobase3_extracts_selected_archive(monkeypatch, tmp_path):
    record_url = "https://zenodo.org/api/records/5589597"
    archive = _zip_bytes(
        {
            "metadata.json": b"{}",
            "Z.txt": b"",
            "Y.txt": b"",
            "unit.txt": b"",
            "satellite/F.txt": b"",
            "satellite/F_Y.txt": b"",
            "satellite/unit.txt": b"",
        }
    )
    record_payload = {
        "files": [
            {"key": "IOT_2019_ixi.zip", "links": {"self": "https://files/iot2019"}},
        ]
    }

    def fake_get(url, **kwargs):
        if url == record_url:
            return FakeResponse(json_data=record_payload)
        if url == "https://files/iot2019":
            return FakeResponse(content=archive)
        raise AssertionError(url)

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_exiobase3(
        tmp_path,
        years=[2019],
        system="ixi",
        table="IOT",
        version="3.8.2",
    )

    assert info["years"] == [2019]
    assert info["archives"] == []
    extracted = Path(info["extracted"][0])
    assert extracted.name == "IOT_2019_ixi"
    assert (extracted / "Z.txt").exists()
    assert (extracted / "satellite" / "F.txt").exists()


def test_download_exiobase3_rejects_unavailable_sut_release(tmp_path):
    with pytest.raises(NotImplementable):
        download_exiobase3(
            tmp_path,
            years=[2020],
            table="SUT",
            version="3.9.6",
        )


def test_download_emerging_v1_downloads_version_record(monkeypatch, tmp_path):
    record_url = "https://zenodo.org/api/records/14258422"
    record_payload = {
        "files": [
            {"key": "EMERGING_V2_2018.mat", "links": {"self": "https://files/emerging"}},
            {"key": "EMERGING_CO2_2018_IEA.mat", "links": {"self": "https://files/co2"}},
            {"key": "EMERGING2.5_Sector&Country list.xlsx", "links": {"self": "https://files/meta"}},
        ]
    }

    def fake_get(url, **kwargs):
        if url == record_url:
            return FakeResponse(json_data=record_payload)
        return FakeResponse(content=b"x")

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_emerging(tmp_path, version="1.0")

    assert info["source"].endswith("14258421")
    assert info["version_record"].endswith("14258422")
    assert len(info["files"]) == 3
    assert (tmp_path / "EMERGING_V2_2018.mat").exists()


def test_download_wiod2016_extracts_workbook(monkeypatch, tmp_path):
    archive = _zip_bytes({"WIOT2014_Nov16_ROW.xlsb": b"binary"})

    def fake_get(url, **kwargs):
        return FakeResponse(
            content=archive,
            headers={"content-disposition": "attachment; filename*=UTF-8''WIOTS_in_EXCEL.zip"},
            url=url,
        )

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_wiod2016(tmp_path, table="IOT")

    assert info["archive"] is None
    assert len(info["workbooks"]) == 1
    assert info["workbooks"][0].endswith("WIOT2014_Nov16_ROW.xlsb")


def test_download_eurostat_reuses_existing_local_files(monkeypatch, tmp_path):
    supply_path = tmp_path / "NAIO_10_CP15_IT_2017_MIO_EUR.csv"
    use_path = tmp_path / "NAIO_10_CP16_IT_2017_MIO_EUR.csv"
    supply_path.write_text("already here")
    use_path.write_text("already here")
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(text="should not be used")

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_eurostat(tmp_path, country="IT", year=2017, table="SUT")

    assert calls == []
    assert info["files"]["supply"] == str(supply_path)
    assert info["files"]["use"] == str(use_path)


def test_download_statcan_downloads_and_extracts_csv(monkeypatch, tmp_path):
    csv_bytes = b"REF_DATE,GEO,VALUE\n2023,Canada,1.0\n"
    archive = _zip_bytes({"table.csv": csv_bytes, "Metadata.csv": b"ignored\n"})

    def fake_get(url, **kwargs):
        if "getFullTableDownloadCSV/36100438/en" in url:
            return FakeResponse(
                json_data={"status": "SUCCESS", "object": "https://example.test/statcan.zip"}
            )
        if url == "https://example.test/statcan.zip":
            return FakeResponse(content=archive)
        raise AssertionError(url)

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_statcan(tmp_path, table="SUT", level="summary")

    csv_path = Path(info["csv"])
    assert csv_path.exists()
    assert csv_path.read_text() == csv_bytes.decode()


def test_mario_does_not_export_legacy_pymrio_downloaders():
    assert hasattr(mario, "download_wiod2016")
    assert not hasattr(mario, "download_wiod2013")
    assert not hasattr(mario, "download_eora26")
    assert not hasattr(mario, "download_exiobase1")
    assert not hasattr(mario, "download_exiobase2")
    assert not hasattr(mario, "download_oecd")
