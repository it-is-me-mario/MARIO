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
    download_istat_io,
    download_statcan,
    download_statcan_openio_canada,
    download_wiod2016,
    download_wiod2016_iot_pyp,
    download_wiod2016_national_iot,
    download_wiod2016_national_sut,
    download_wiod2016_socioeconomic_accounts,
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
        self.content = content
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
    record_url = "https://zenodo.org/api/records/10956623"
    record_payload = {
        "files": [
            {"key": "global_mrio_2018.mat", "links": {"self": "https://files/emerging"}},
            {"key": "EMERGING_CO2_2018.mat", "links": {"self": "https://files/co2"}},
            {"key": "EMERGING2.5_Sector&Country list.xlsx", "links": {"self": "https://files/meta"}},
        ]
    }

    def fake_get(url, **kwargs):
        if url == record_url:
            return FakeResponse(json_data=record_payload)
        return FakeResponse(content=b"x")

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_emerging(tmp_path, version="1.0")

    assert info["source"].endswith("10956622")
    assert info["version"] == "1.0"
    assert info["version_record"].endswith("10956623")
    assert len(info["files"]) == 3
    assert (tmp_path / "global_mrio_2018.mat").exists()


def test_download_emerging_v21_supports_year_filter(monkeypatch, tmp_path):
    record_url = "https://zenodo.org/api/records/18518911"
    record_payload = {
        "files": [
            {"key": "EMERGING_V2_2021_m.mat", "links": {"self": "https://files/2021-main"}},
            {"key": "EMERGING_CO2_2021.mat", "links": {"self": "https://files/2021-co2"}},
            {"key": "EMERGING_V2_2023_m.mat", "links": {"self": "https://files/2023-main"}},
            {"key": "EMERGING_CO2_2023.mat", "links": {"self": "https://files/2023-co2"}},
            {"key": "EMERGING2.5_Sector&Country list.xlsx", "links": {"self": "https://files/meta"}},
        ]
    }

    def fake_get(url, **kwargs):
        if url == record_url:
            return FakeResponse(json_data=record_payload)
        return FakeResponse(content=b"x")

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_emerging(tmp_path, version="2.1", years=[2023])

    assert info["source"].endswith("10956622")
    assert info["version"] == "2.1"
    assert info["version_record"].endswith("18518911")
    assert info["years"] == [2023]
    assert len(info["files"]) == 3
    assert (tmp_path / "EMERGING_V2_2023_m.mat").exists()
    assert (tmp_path / "EMERGING_CO2_2023.mat").exists()


def test_download_emerging_v22_latest_supports_year_filter(monkeypatch, tmp_path):
    record_url = "https://zenodo.org/api/records/19461860"
    record_payload = {
        "files": [
            {"key": "EMERGING_V2_2021_m.mat", "links": {"self": "https://files/2021-main"}},
            {"key": "EMERGING_CO2_2021.mat", "links": {"self": "https://files/2021-co2"}},
            {"key": "EMERGING_V2_2023_m.mat", "links": {"self": "https://files/2023-main"}},
            {"key": "EMERGING_CO2_2023.mat", "links": {"self": "https://files/2023-co2"}},
        ]
    }

    def fake_get(url, **kwargs):
        if url == record_url:
            return FakeResponse(json_data=record_payload)
        return FakeResponse(content=b"x")

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_emerging(tmp_path, version="latest", years=[2023])

    assert info["version"] == "2.2"
    assert info["version_record"].endswith("19461860")
    assert info["years"] == [2023]
    assert len(info["files"]) == 2
    assert (tmp_path / "EMERGING_V2_2023_m.mat").exists()
    assert (tmp_path / "EMERGING_CO2_2023.mat").exists()


def test_download_emerging_v20_downloads_matching_files(monkeypatch, tmp_path):
    record_url = "https://zenodo.org/api/records/17557778"
    record_payload = {
        "files": [
            {"key": "EMERGING_V2_2015_m.mat", "links": {"self": "https://files/2015-main"}},
            {"key": "EMERGING_CO2_2015.mat", "links": {"self": "https://files/2015-co2"}},
            {"key": "EMERGING_V2_2021_m.mat", "links": {"self": "https://files/2021-main"}},
            {"key": "EMERGING_CO2_2021.mat", "links": {"self": "https://files/2021-co2"}},
        ]
    }

    def fake_get(url, **kwargs):
        if url == record_url:
            return FakeResponse(json_data=record_payload)
        return FakeResponse(content=b"x")

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_emerging(tmp_path, version="2.0", years=[2015])

    assert info["version"] == "2.0"
    assert info["version_record"].endswith("17557778")
    assert info["years"] == [2015]
    assert len(info["files"]) == 2
    assert (tmp_path / "EMERGING_V2_2015_m.mat").exists()
    assert (tmp_path / "EMERGING_CO2_2015.mat").exists()


def test_download_emerging_e_supports_year_filter_and_keeps_figure_workbook(monkeypatch, tmp_path):
    record_url = "https://zenodo.org/api/records/18303090"
    record_payload = {
        "files": [
            {"key": "EMERGING_E_2018.mat", "links": {"self": "https://files/e-main"}},
            {"key": "Figure data.xlsx", "links": {"self": "https://files/e-figure"}},
            {"key": "Validation_output.m", "links": {"self": "https://files/e-validation"}},
        ]
    }

    def fake_get(url, **kwargs):
        if url == record_url:
            return FakeResponse(json_data=record_payload)
        return FakeResponse(content=b"x")

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_emerging(tmp_path, version="E", years=[2018])

    assert info["source"].endswith("17612997")
    assert info["version"] == "E"
    assert info["version_record"].endswith("18303090")
    assert info["years"] == [2018]
    assert len(info["files"]) == 2
    assert (tmp_path / "EMERGING_E_2018.mat").exists()
    assert (tmp_path / "Figure data.xlsx").exists()


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


def test_download_wiod2016_iot_pyp_extracts_workbook(monkeypatch, tmp_path):
    archive = _zip_bytes({"WIOT2014_PYP_Nov16_ROW.xlsb": b"binary"})

    def fake_get(url, **kwargs):
        return FakeResponse(
            content=archive,
            headers={"content-disposition": "attachment; filename*=UTF-8''WIOTS_PYP_in_EXCEL.zip"},
            url=url,
        )

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_wiod2016_iot_pyp(tmp_path)

    assert info["archive"] is None
    assert any(item.endswith("WIOT2014_PYP_Nov16_ROW.xlsb") for item in info["files"])


def test_download_wiod2016_national_bundles_extract(monkeypatch, tmp_path):
    archive = _zip_bytes({"ITA_NIOT_nov16.xlsx": b"binary", "ITA_SUT_nov16.xlsx": b"binary"})
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        filename = "NIOTS.zip" if "199099" in url else "SUT_national.zip"
        return FakeResponse(
            content=archive,
            headers={"content-disposition": f"attachment; filename*=UTF-8''{filename}"},
            url=url,
        )

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    niot = download_wiod2016_national_iot(tmp_path / "niot")
    nsut = download_wiod2016_national_sut(tmp_path / "nsut")

    assert any(item.endswith("ITA_NIOT_nov16.xlsx") for item in niot["files"])
    assert any(item.endswith("ITA_SUT_nov16.xlsx") for item in nsut["files"])
    assert len(calls) == 2


def test_download_wiod2016_socioeconomic_accounts_saves_xlsx(monkeypatch, tmp_path):
    def fake_get(url, **kwargs):
        return FakeResponse(
            content=b"xlsx-bytes",
            headers={"content-disposition": "attachment; filename*=UTF-8''Socio_Economic_Accounts.xlsx"},
            url=url,
        )

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_wiod2016_socioeconomic_accounts(tmp_path)

    assert info["file"].endswith("Socio_Economic_Accounts.xlsx")
    assert Path(info["file"]).exists()


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


def test_download_statcan_openio_canada_downloads_workbook(monkeypatch, tmp_path):
    workbook_bytes = b"fake-openio-workbook"

    def fake_get(url, **kwargs):
        assert "zenodo.org/api/records/18304088/files" in url
        return FakeResponse(content=workbook_bytes)

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_statcan_openio_canada(tmp_path)

    xlsx_path = Path(info["xlsx"])
    assert xlsx_path.exists()
    assert xlsx_path.read_bytes() == workbook_bytes
    assert info["satellite_account"] == "openio_canada"


def test_download_istat_io_resolves_zip_from_release_page(monkeypatch, tmp_path):
    workbook_bytes = io.BytesIO()
    with zipfile.ZipFile(workbook_bytes, "w") as archive:
        archive.writestr("Tavole_I_O/SIMM_TOT_63PxP.xlsx", b"xlsx")
    page_html = '<html><body><a href="/files/Tavole_I_O.zip">Tavole</a></body></html>'

    def fake_get(url, **kwargs):
        if "tavole-di-dati" in url:
            return FakeResponse(text=page_html)
        if "Tavole_I_O.zip" in url:
            return FakeResponse(content=workbook_bytes.getvalue())
        raise AssertionError(url)

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    info = download_istat_io(tmp_path, edition="2020-2022")

    assert info["page_url"].endswith("2020-2022/")
    assert info["archive_url"].endswith("Tavole_I_O.zip")
    assert any(Path(path).name == "SIMM_TOT_63PxP.xlsx" for path in info["files"])


def test_mario_does_not_export_legacy_pymrio_downloaders():
    assert hasattr(mario, "download_wiod2016")
    assert hasattr(mario, "download_wiod2016_iot_pyp")
    assert hasattr(mario, "download_wiod2016_national_iot")
    assert hasattr(mario, "download_wiod2016_national_sut")
    assert hasattr(mario, "download_wiod2016_socioeconomic_accounts")
    assert hasattr(mario, "download_statcan_openio_canada")
    assert not hasattr(mario, "download_wiod2013")
    assert not hasattr(mario, "download_eora26")
    assert not hasattr(mario, "download_exiobase1")
    assert not hasattr(mario, "download_exiobase2")
    assert not hasattr(mario, "download_oecd")
