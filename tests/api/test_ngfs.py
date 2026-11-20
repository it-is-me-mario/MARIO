import hashlib
import json
from io import BytesIO
from unittest.mock import Mock

import pandas as pd
import pytest
import requests

import mario
from mario.model import ngfs
from scripts import download_ngfs_gcam


def workbook(model, scenario, year=2050):
    data = pd.DataFrame(
        [
            (model, scenario, "NA", "Electricity|Wind", "EJ/yr", 3),
            ("© IIASA", None, None, None, None, None),
        ],
        columns=["Model", "Scenario", "Region", "Variable", "Unit", year],
    )
    with BytesIO() as stream:
        data.to_excel(stream, index=False)
        return stream.getvalue()


@pytest.fixture
def explorer(monkeypatch):
    runs = [
        dict(model="M", scenario="A", run_id=1, version=2),
        dict(model="M", scenario="B", run_id=2, version=1),
        dict(model="Other", scenario="A", run_id=3, version=4),
    ]
    payloads = {1: workbook("M", "A"), 2: workbook("M", "B", year=2060)}
    downloads = []

    def get(session, url, **kwargs):
        response = Mock(spec=requests.Response)
        if url == ngfs._AUTH:
            response.text = '"guest-token"'
        elif url == ngfs._API + "/runs":
            assert session.headers["Authorization"] == "Bearer guest-token"
            assert kwargs["params"] == {"getOnlyDefaultRuns": "true"}
            response.json.return_value = runs
        else:
            assert kwargs["headers"]["Accept"] == ngfs._XLSX
            run_id = int(url.split("/")[-2])
            downloads.append(run_id)
            payload = payloads[run_id]
            if isinstance(payload, Exception):
                response.raise_for_status.side_effect = payload
            else:
                response.content = payload
        return response

    monkeypatch.setattr(requests.Session, "get", get)
    return runs, payloads, downloads


def test_catalog_lists_default_runs_without_downloading_workbooks(explorer):
    runs, _, downloads = explorer
    assert mario.list_ngfs_runs().to_dict("records") == runs
    assert mario.list_ngfs_runs(model="Other").to_dict("records") == runs[2:]
    assert downloads == []


def test_download_combines_scenarios_and_preserves_provenance(explorer):
    runs, _, downloads = explorer
    selection = mario.list_ngfs_runs("M").iloc[::-1]["scenario"]
    data = mario.download_ngfs("M", selection)
    assert isinstance(data, mario.IamData)
    assert data.frame.Scenario.tolist() == ["B", "A"]
    assert data.frame.Region.tolist() == ["NA", "NA"]
    assert data.frame.loc[0, 2060] == data.frame.loc[1, 2050] == 3
    assert pd.isna(data.frame.loc[0, 2050]) and pd.isna(data.frame.loc[1, 2060])
    assert data.frame.attrs["ngfs_runs"] == [
        {**run, "url": f"{ngfs._API}/runs/{run['run_id']}/ts"} for run in runs[1::-1]
    ]
    assert downloads == [2, 1]
    single = mario.download_ngfs("M", "A")
    assert single.frame.Scenario.tolist() == ["A"]


@pytest.mark.parametrize(
    "model,scenarios,error",
    [
        ("M", ["A", "C"], "Unknown scenarios"),
        ("X", "A", "Unknown NGFS"),
        ("M", ["A", "A"], "distinct"),
        ("M", [], "non-empty"),
    ],
)
def test_invalid_selection_downloads_nothing(explorer, model, scenarios, error):
    with pytest.raises(ValueError, match=error):
        mario.download_ngfs(model, scenarios)
    assert explorer[2] == []


def test_ambiguous_default_is_rejected_before_first_download(explorer):
    runs, _, downloads = explorer
    runs.append(dict(model="M", scenario="B", run_id=4, version=3))
    with pytest.raises(ValueError, match="Multiple default"):
        mario.download_ngfs("M", ["A", "B"])
    assert downloads == []


def test_failed_or_inconsistent_workbook_is_rejected(explorer):
    _, payloads, _ = explorer
    payloads[2] = requests.HTTPError("503")
    with pytest.raises(requests.HTTPError, match="503"):
        mario.download_ngfs("M", ["A", "B"])
    payloads[2] = b"<html/>"
    with pytest.raises(ValueError, match="XLSX"):
        mario.download_ngfs("M", "B")
    payloads[2] = workbook("Other", "B")
    with pytest.raises(ValueError, match="labels disagree"):
        mario.download_ngfs("M", "B")


def test_archive_script_preserves_original_workbooks_and_manifest(
    explorer, monkeypatch, tmp_path
):
    _, payloads, _ = explorer
    monkeypatch.setattr(download_ngfs_gcam, "MODEL", "M")
    monkeypatch.setattr(download_ngfs_gcam, "SCENARIOS", ["B", "A"])
    download_ngfs_gcam.download(tmp_path)
    manifest = json.loads((tmp_path / "source.json").read_text())
    assert manifest["source"] == ngfs.PORTAL
    assert [run["scenario"] for run in manifest["runs"]] == ["B", "A"]
    for run in manifest["runs"]:
        content = (tmp_path / run["file"]).read_bytes()
        assert content == payloads[run["run_id"]]
        assert hashlib.sha256(content).hexdigest() == run["sha256"]
