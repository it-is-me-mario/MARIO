from __future__ import annotations

import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.parsers import figaro


def _figaro_sut_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return minimal normalized FIGARO API frames for SUT tests."""
    supply = pd.DataFrame(
        [
            ["IT", "CPA_A01", "IT", "A01", 100.0],
            ["ME", "CPA_A01", "IT", "A01", 7.0],
            ["IT", "CPA_A01", "ME", "A01", 3.0],
            ["ME", "CPA_A01", "ME", "A01", 40.0],
        ],
        columns=["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    )
    use = pd.DataFrame(
        [
            ["IT", "CPA_A01", "IT", "A01", 10.0],
            ["ME", "CPA_A01", "IT", "A01", 1.0],
            ["IT", "CPA_A01", "ME", "A01", 2.0],
            ["ME", "CPA_A01", "ME", "A01", 20.0],
            ["IT", "CPA_A01", "IT", "P3_S14", 30.0],
            ["ME", "CPA_A01", "IT", "P3_S14", 5.0],
            ["IT", "CPA_A01", "ME", "P51G", 4.0],
            ["W2", "D1", "IT", "A01", 40.0],
            ["W2", "D1", "ME", "A01", 50.0],
            ["W2", "B2A3G", "IT", "A01", 60.0],
            ["W2", "B2A3G", "ME", "A01", 70.0],
        ],
        columns=["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    )
    return supply, use


def _figaro_iot_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return minimal normalized FIGARO API frames for IOT tests."""
    product = pd.DataFrame(
        [
            ["IT", "CPA_A01", "IT", "CPA_A01", 100.0],
            ["ME", "CPA_A01", "IT", "CPA_A01", 7.0],
            ["IT", "CPA_A01", "ME", "CPA_A01", 3.0],
            ["ME", "CPA_A01", "ME", "CPA_A01", 40.0],
            ["IT", "CPA_A01", "IT", "P3_S14", 30.0],
            ["ME", "CPA_A01", "IT", "P3_S14", 5.0],
            ["IT", "CPA_A01", "ME", "P51G", 4.0],
            ["W2", "D1", "IT", "CPA_A01", 40.0],
            ["W2", "D1", "ME", "CPA_A01", 50.0],
            ["W2", "B2A3G", "IT", "CPA_A01", 60.0],
            ["W2", "B2A3G", "ME", "CPA_A01", 70.0],
        ],
        columns=["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    )
    industry = pd.DataFrame(
        [
            ["IT", "A01", "IT", "A01", 100.0],
            ["ME", "A01", "IT", "A01", 7.0],
            ["IT", "A01", "ME", "A01", 3.0],
            ["ME", "A01", "ME", "A01", 40.0],
            ["IT", "A01", "IT", "P3_S14", 30.0],
            ["ME", "A01", "IT", "P3_S14", 5.0],
            ["IT", "A01", "ME", "P51G", 4.0],
            ["W2", "D1", "IT", "A01", 40.0],
            ["W2", "D1", "ME", "A01", 50.0],
            ["W2", "B2A3G", "IT", "A01", 60.0],
            ["W2", "B2A3G", "ME", "A01", 70.0],
        ],
        columns=["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    )
    return product, industry


def _patch_figaro_api(monkeypatch) -> None:
    """Patch the network layer with minimal normalized dataframes."""
    supply, use = _figaro_sut_frames()
    product, industry = _figaro_iot_frames()

    def fake_download(dataflow, **kwargs):
        assert kwargs["year"] == 2023
        assert kwargs["unit"] == "MIO_EUR"
        assert kwargs["countries"] == ["IT", "ME"]
        if dataflow == "naio_10_fcp_s4":
            return supply
        if dataflow == "naio_10_fcp_u4":
            return use
        if dataflow == "naio_10_fcp_ip4":
            return product
        if dataflow == "naio_10_fcp_ii4":
            return industry
        raise AssertionError(dataflow)

    monkeypatch.setattr(figaro, "_download_figaro_api_frame", fake_download)


def test_figaro_region_labels_use_country_converter_and_special_overrides():
    assert figaro._resolve_figaro_region_label("AL", {}) == "Albania"
    assert figaro._resolve_figaro_region_label("EL", {}) == "Greece"
    assert figaro._resolve_figaro_region_label("FIGW1", {}) == "Rest of the world"
    assert figaro._resolve_figaro_region_label("W2", {}) == "Domestic (home or reference area)"


def test_parse_figaro_sut_resolves_missing_region_metadata_with_country_converter(monkeypatch):
    supply = pd.DataFrame(
        [
            ["AL", "CPA_A01", "EL", "A01", 100.0],
            ["EL", "CPA_A01", "AL", "A01", 40.0],
        ],
        columns=["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    )
    use = pd.DataFrame(
        [
            ["AL", "CPA_A01", "EL", "A01", 10.0],
            ["EL", "CPA_A01", "AL", "A01", 20.0],
            ["AL", "CPA_A01", "EL", "P3_S14", 30.0],
            ["W2", "D1", "AL", "A01", 40.0],
            ["W2", "D1", "EL", "A01", 50.0],
        ],
        columns=["refArea", "rowCode", "counterpartArea", "colCode", "obsValue"],
    )

    def fake_download(dataflow, **kwargs):
        assert kwargs["countries"] == ["AL", "EL"]
        if dataflow == "naio_10_fcp_s4":
            return supply
        if dataflow == "naio_10_fcp_u4":
            return use
        raise AssertionError(dataflow)

    monkeypatch.setattr(figaro, "_download_figaro_api_frame", fake_download)

    matrices, indeces, _, _ = figaro.parse_figaro_sut(year=2023, countries=["AL", "EL"])

    assert indeces["r"]["main"] == ["Albania", "Greece"]
    assert matrices["baseline"]["S"].index.get_level_values(0).tolist() == ["Albania", "Greece"]
    assert matrices["baseline"]["S"].columns.get_level_values(0).tolist() == ["Albania", "Greece"]


def test_parse_figaro_sut_returns_split_native_blocks_from_api(monkeypatch):
    _patch_figaro_api(monkeypatch)

    matrices, indeces, units, layout = figaro.parse_figaro_sut(year=2023, countries=["IT", "ME"])
    base = matrices["baseline"]

    assert layout.year == 2023
    assert layout.supply_dataflow == "naio_10_fcp_s4"
    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert base["S"].shape == (2, 2)
    assert base["U"].shape == (2, 2)
    assert base["Yc"].shape == (2, 4)
    assert base["Va"].shape == (2, 2)
    assert indeces["r"]["main"] == ["Italy", "Montenegro"]
    assert indeces["f"]["main"] == [
        "Compensation of employees",
        "Gross operating surplus",
    ]
    assert units["Satellite account"].index.tolist() == ["-"]

    assert float(base["S"].iloc[0, 0]) == 100.0
    assert float(base["S"].iloc[0, 1]) == 7.0
    assert float(base["S"].iloc[1, 0]) == 3.0
    assert float(base["S"].iloc[1, 1]) == 40.0

    assert float(base["U"].iloc[0, 0]) == 10.0
    assert float(base["U"].iloc[1, 0]) == 1.0
    assert float(base["U"].iloc[0, 1]) == 2.0
    assert float(base["U"].iloc[1, 1]) == 20.0

    assert float(base["Yc"].iloc[0, 0]) == 30.0
    assert float(base["Yc"].iloc[1, 0]) == 5.0
    assert float(base["Yc"].iloc[0, 3]) == 4.0

    assert float(base["Va"].iloc[0, 0]) == 40.0
    assert float(base["Va"].iloc[0, 1]) == 50.0
    assert float(base["Va"].iloc[1, 0]) == 60.0
    assert float(base["Va"].iloc[1, 1]) == 70.0


def test_figaro_dataflow_groups_and_validation():
    assert figaro.detect_figaro_sut_layout(2010).supply_dataflow == "naio_10_fcp_s1"
    assert figaro.detect_figaro_sut_layout(2014).supply_dataflow == "naio_10_fcp_s2"
    assert figaro.detect_figaro_sut_layout(2018).supply_dataflow == "naio_10_fcp_s3"
    assert figaro.detect_figaro_sut_layout(2023).supply_dataflow == "naio_10_fcp_s4"
    assert figaro.detect_figaro_iot_layout(2023).dataflow == "naio_10_fcp_ip4"

    with pytest.raises(WrongInput):
        figaro.detect_figaro_sut_layout(2009)
    with pytest.raises(WrongInput):
        figaro.detect_figaro_iot_layout(2023, mode="bad")


def test_public_parse_figaro_returns_database(monkeypatch):
    _patch_figaro_api(monkeypatch)

    database = mario.parse_figaro(table="SUT", year=2023, countries=["IT", "ME"], calc_all=False)

    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"]
    assert "Z" not in database["baseline"]
    assert database.Z.shape == (4, 4)
    assert database.Y.shape == (4, 4)
    assert database.V.shape == (2, 4)
    assert "FIGARO database via Eurostat API" in database.meta.source

    with pytest.raises(WrongInput):
        mario.parse_figaro(table="SUT", calc_all=False)


def test_figaro_api_download_uses_cache_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(
        figaro,
        "_load_figaro_dimensions",
        lambda *args, **kwargs: {
            "c_orig": ["IT"],
            "c_dest": ["IT"],
            "prd_ava": ["CPA_A01"],
            "prd_use": ["CPA_A01"],
        },
    )
    calls = {"count": 0}

    def fake_request(dataflow, *, params, **kwargs):
        calls["count"] += 1
        return {
            "id": ["c_orig", "c_dest", "prd_ava", "prd_use"],
            "size": [1, 1, 1, 1],
            "dimension": {
                "c_orig": {"category": {"index": {"IT": 0}}},
                "c_dest": {"category": {"index": {"IT": 0}}},
                "prd_ava": {"category": {"index": {"CPA_A01": 0}}},
                "prd_use": {"category": {"index": {"CPA_A01": 0}}},
            },
            "value": {"0": 42.0},
        }

    monkeypatch.setattr(figaro, "_request_figaro_json", fake_request)

    first = figaro._download_figaro_api_frame(
        "test_flow",
        year=2023,
        unit="MIO_EUR",
        row_dim="prd_ava",
        col_dim="prd_use",
        countries=["IT"],
        cache_path=tmp_path,
    )
    second = figaro._download_figaro_api_frame(
        "test_flow",
        year=2023,
        unit="MIO_EUR",
        row_dim="prd_ava",
        col_dim="prd_use",
        countries=["IT"],
        cache_path=tmp_path,
    )

    assert calls["count"] == 1
    assert len(list(tmp_path.glob("test_flow_2023_MIO_EUR_*.csv"))) == 1
    assert first.to_dict("records") == second.to_dict("records")


def test_parse_figaro_iot_supports_product_and_industry_variants(monkeypatch):
    _patch_figaro_api(monkeypatch)

    matrices, indeces, units, layout = figaro.parse_figaro_iot(
        year=2023,
        countries=["IT", "ME"],
    )
    base = matrices["baseline"]

    assert layout.mode == "product"
    assert set(base) == {"Z", "Y", "V", "E", "EY"}
    assert base["Z"].shape == (2, 2)
    assert base["Y"].shape == (2, 4)
    assert base["V"].shape == (2, 2)
    assert indeces["s"]["main"] == ["Products of agriculture, hunting and related services"]
    assert float(base["Z"].iloc[0, 0]) == 100.0
    assert float(base["Z"].iloc[0, 1]) == 3.0
    assert float(base["Z"].iloc[1, 0]) == 7.0
    assert float(base["Y"].iloc[0, 0]) == 30.0
    assert float(base["V"].iloc[0, 0]) == 40.0
    assert units["Sector"].shape[0] == 1

    matrices_i, indeces_i, _, layout_i = figaro.parse_figaro_iot(
        year=2023,
        mode="industry",
        countries=["IT", "ME"],
    )
    assert layout_i.mode == "industry"
    assert indeces_i["s"]["main"] == [
        "Crop and animal production, hunting and related service activities"
    ]
    assert float(matrices_i["baseline"]["Z"].iloc[0, 0]) == 100.0


def test_public_parse_figaro_iot_returns_database_and_validates_mode(monkeypatch):
    _patch_figaro_api(monkeypatch)

    database = mario.parse_figaro(
        table="IOT",
        year=2023,
        countries=["IT", "ME"],
        calc_all=False,
    )

    assert sorted(database["baseline"].keys()) == ["E", "EY", "V", "Y", "Z"]
    assert database.Z.shape == (2, 2)
    assert database.Y.shape == (2, 4)
    assert database.V.shape == (2, 2)

    with pytest.raises(WrongInput):
        mario.parse_figaro(table="IOT", year=2023, iot_mode="bad", calc_all=False)


def test_figaro_jsonstat_converter_handles_sparse_payload():
    payload = {
        "id": ["freq", "prd_ava", "c_dest"],
        "size": [1, 2, 2],
        "dimension": {
            "freq": {"category": {"index": {"A": 0}}},
            "prd_ava": {"category": {"index": {"CPA_A01": 0, "CPA_A02": 1}}},
            "c_dest": {"category": {"index": {"IT": 0, "ME": 1}}},
        },
        "value": {"0": 10.0, "3": 20.0},
    }

    frame = figaro._jsonstat_to_frame(payload)

    assert frame.to_dict("records") == [
        {"freq": "A", "prd_ava": "CPA_A01", "c_dest": "IT", "obsValue": 10.0},
        {"freq": "A", "prd_ava": "CPA_A02", "c_dest": "ME", "obsValue": 20.0},
    ]
