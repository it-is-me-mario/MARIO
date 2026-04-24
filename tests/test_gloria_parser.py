from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers import entrypoints as parser_entrypoints
from mario.parsers import gloria as gloria_parser
from mario.parsers.gloria import parse_gloria_sut


def _write_gloria_readme(path: Path) -> None:
    """Create a minimal GLORIA ReadMe workbook."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Lfd_Nr": [1, 2],
                "Region_acronyms": ["IT", "ME"],
                "Region_names": ["Italy", "Montenegro"],
            }
        ).to_excel(writer, sheet_name="Regions", index=False)
        pd.DataFrame(
            {"Lfd_Nr": [1, 2], "Sector_names": ["Wheat", "Steel"]}
        ).to_excel(writer, sheet_name="Sectors", index=False)
        pd.DataFrame(
            {
                "Lfd_Nr": [1, 2],
                "Value_added_names": ["Compensation", "Operating surplus"],
                "Final_demand_names": ["Household", "Investment"],
            }
        ).to_excel(writer, sheet_name="Value added and final demand", index=False)
        pd.DataFrame(
            {
                "Lfd_Nr": [1, 2, 3, 4, 5],
                "Valuation_names": [
                    "Basic prices",
                    "Trade margins",
                    "Transport margins",
                    "Taxes on products",
                    "Subsidies on products",
                ],
            }
        ).to_excel(writer, sheet_name="Valuations", index=False)
        pd.DataFrame(
            {
                "Lfd_Nr": [1, 2],
                "Sat_head_indicator": ["Emissions", "Employment"],
                "Sat_indicator": ["CO2", "Persons"],
                "Sat_unit": ["kg", "kpp"],
            }
        ).to_excel(writer, sheet_name="Satellites", index=False)


def _write_gloria_year(root: Path, *, year: int = 2025) -> Path:
    """Create one minimal GLORIA monetary SUT bundle."""
    gloria_root = root / f"GLORIA_MRIOs_60_{year}"
    satellite_root = root / f"GLORIA_SatelliteAccounts_060_{year}"
    gloria_root.mkdir(parents=True, exist_ok=True)
    satellite_root.mkdir(parents=True, exist_ok=True)
    _write_gloria_readme(root / "GLORIA_ReadMe_060.xlsx")

    T1 = np.array(
        [
            [0, 0, 100, 0, 0, 0, 7, 0],
            [0, 0, 0, 200, 0, 0, 0, 0],
            [10, 20, 0, 0, 2, 0, 0, 0],
            [0, 30, 0, 0, 0, 3, 0, 0],
            [0, 0, 4, 0, 0, 0, 300, 0],
            [0, 0, 0, 0, 0, 0, 0, 400],
            [1, 0, 0, 0, 40, 0, 0, 0],
            [0, 5, 0, 0, 0, 50, 0, 0],
        ],
        dtype=np.float32,
    )
    Y1 = np.array(
        [
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [11, 12, 1, 0],
            [21, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 31, 0],
            [0, 2, 0, 41],
        ],
        dtype=np.float32,
    )
    V1 = np.array(
        [
            [1000, 2000, 0, 0, 0, 0, 0, 0],
            [3000, 4000, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 5000, 6000, 0, 0],
            [0, 0, 0, 0, 7000, 8000, 0, 0],
        ],
        dtype=np.float32,
    )
    TQ = np.array(
        [
            [1, 2, 10, 20, 3, 4, 30, 40],
            [5, 6, 50, 60, 7, 8, 70, 80],
        ],
        dtype=np.float32,
    )
    YQ = np.array(
        [
            [100, 200, 300, 400],
            [500, 600, 700, 800],
        ],
        dtype=np.float32,
    )
    T2 = T1 * 10
    Y2 = Y1 * 10

    np.savetxt(
        gloria_root / f"20260121_120secMother_AllCountries_002_T-Results_{year}_060_Markup001(full).csv",
        T1,
        delimiter=",",
        fmt="%.6g",
    )
    np.savetxt(
        gloria_root / f"20260121_120secMother_AllCountries_002_Y-Results_{year}_060_Markup001(full).csv",
        Y1,
        delimiter=",",
        fmt="%.6g",
    )
    np.savetxt(
        gloria_root / f"20260122_120secMother_AllCountries_002_V-Results_{year}_060_Markup001(full).csv",
        V1,
        delimiter=",",
        fmt="%.6g",
    )
    np.savetxt(
        gloria_root / f"20260121_120secMother_AllCountries_002_T-Results_{year}_060_Markup002(full).csv",
        T2,
        delimiter=",",
        fmt="%.6g",
    )
    np.savetxt(
        gloria_root / f"20260122_120secMother_AllCountries_002_Y-Results_{year}_060_Markup002(full).csv",
        Y2,
        delimiter=",",
        fmt="%.6g",
    )
    np.savetxt(
        satellite_root / f"20240417_120secMother_AllCountries_002_TQ-Results_{year}_060_Markup001(full).csv",
        TQ,
        delimiter=",",
        fmt="%.6g",
    )
    np.savetxt(
        satellite_root / f"20240417_120secMother_AllCountries_002_YQ-Results_{year}_060_Markup001(full).csv",
        YQ,
        delimiter=",",
        fmt="%.6g",
    )
    return gloria_root


def test_parse_gloria_sut_returns_split_native_blocks(tmp_path):
    root = _write_gloria_year(tmp_path)

    matrices, indeces, units, layout = parse_gloria_sut(root)
    base = matrices["baseline"]

    assert layout.year == 2025
    assert layout.valuation_name == "Basic prices"
    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert base["S"].shape == (4, 4)
    assert base["U"].shape == (4, 4)
    assert base["Va"].shape == (2, 4)
    assert indeces["r"]["main"] == ["IT", "ME"]
    assert indeces["a"]["main"] == ["Wheat", "Steel"]
    assert indeces["f"]["main"] == ["Compensation", "Operating surplus"]
    assert indeces["k"]["main"] == ["Emissions | CO2", "Employment | Persons"]
    assert units["Activity"].iloc[0, 0] == "current 000 US$"
    assert units["Satellite account"].iloc[0, 0] == "kg"

    np.testing.assert_allclose(
        base["S"].astype(np.float32).to_numpy(),
        np.array(
            [
                [100, 0, 7, 0],
                [0, 200, 0, 0],
                [4, 0, 300, 0],
                [0, 0, 0, 400],
            ],
            dtype=np.float32,
        ),
    )
    np.testing.assert_allclose(
        base["U"].to_numpy(),
        np.array(
            [
                [10, 20, 2, 0],
                [0, 30, 0, 3],
                [1, 0, 40, 0],
                [0, 5, 0, 50],
            ],
            dtype=np.float32,
        ),
    )
    np.testing.assert_allclose(
        base["Yc"].to_numpy(),
        np.array(
            [
                [11, 12, 1, 0],
                [21, 0, 0, 0],
                [0, 0, 31, 0],
                [0, 2, 0, 41],
            ],
            dtype=np.float32,
        ),
    )
    np.testing.assert_allclose(
        base["Va"].to_numpy(),
        np.array(
            [
                [1000, 2000, 5000, 6000],
                [3000, 4000, 7000, 8000],
            ],
            dtype=np.float32,
        ),
    )
    np.testing.assert_allclose(
        base["Ea"].astype(np.float32).to_numpy(),
        np.array([[1, 2, 3, 4], [5, 6, 7, 8]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        base["Ec"].astype(np.float32).to_numpy(),
        np.array([[10, 20, 30, 40], [50, 60, 70, 80]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        base["EY"].astype(np.float32).to_numpy(),
        np.array([[100, 200, 300, 400], [500, 600, 700, 800]], dtype=np.float32),
    )


def test_parse_gloria_sut_supports_google_drive_release_layout(tmp_path):
    release_root = tmp_path / "060"
    part_i = release_root / "GLORIA_MRIO_Loop060_part_I_MRIOdatabase"
    part_iii = release_root / "GLORIA_MRIO_Loop060_part_III_satelliteaccounts"
    part_i.mkdir(parents=True)
    part_iii.mkdir(parents=True)

    data_root = _write_gloria_year(part_i)
    (part_i / "GLORIA_ReadMe_060.xlsx").rename(release_root / "GLORIA_ReadMe_060.xlsx")
    (part_i / "GLORIA_SatelliteAccounts_060_2025").rename(
        part_iii / "GLORIA_SatelliteAccounts_060_2025"
    )

    for path in (release_root, part_i):
        matrices, indeces, units, layout = parse_gloria_sut(path, satellites="Emissions")

        assert layout.root == release_root
        assert layout.data_root == data_root
        assert layout.satellite_root == part_iii / "GLORIA_SatelliteAccounts_060_2025"
        assert indeces["k"]["main"] == ["Emissions | CO2"]
        assert units["Satellite account"].iloc[0, 0] == "kg"
        np.testing.assert_allclose(
            matrices["baseline"]["Ea"].astype(np.float32).to_numpy(),
            np.array([[1, 2, 3, 4]], dtype=np.float32),
        )


def test_parse_gloria_sut_supports_region_subset_and_markup_fallback(tmp_path):
    root = _write_gloria_year(tmp_path)

    matrices, _, _, layout = parse_gloria_sut(root, valuation="trade", regions=["ME"])
    base = matrices["baseline"]

    assert layout.valuation_name == "Trade margins"
    assert layout.notes == ("No markup-specific GLORIA V file was found; value added was read from Markup001.",)
    assert base["S"].shape == (2, 2)
    assert base["U"].shape == (2, 2)
    assert base["Yc"].shape == (2, 2)
    assert base["Va"].shape == (2, 2)

    np.testing.assert_allclose(
        base["S"].astype(np.float32).to_numpy(),
        np.array([[3000, 0], [0, 4000]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        base["U"].to_numpy(),
        np.array([[400, 0], [0, 500]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        base["Yc"].to_numpy(),
        np.array([[310, 0], [0, 410]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        base["Va"].to_numpy(),
        np.array([[5000, 6000], [7000, 8000]], dtype=np.float32),
    )


def test_parse_gloria_sut_can_filter_satellites_by_group(tmp_path):
    root = _write_gloria_year(tmp_path)

    matrices, indeces, units, _ = parse_gloria_sut(root, satellites="Emissions")
    base = matrices["baseline"]

    assert indeces["k"]["main"] == ["Emissions | CO2"]
    assert units["Satellite account"].index.tolist() == ["Emissions | CO2"]
    assert units["Satellite account"].iloc[0, 0] == "kg"
    assert base["Ea"].shape == (1, 4)
    assert base["Ec"].shape == (1, 4)
    assert base["EY"].shape == (1, 4)

    np.testing.assert_allclose(
        base["Ea"].astype(np.float32).to_numpy(),
        np.array([[1, 2, 3, 4]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        base["Ec"].astype(np.float32).to_numpy(),
        np.array([[10, 20, 30, 40]], dtype=np.float32),
    )
    np.testing.assert_allclose(
        base["EY"].astype(np.float32).to_numpy(),
        np.array([[100, 200, 300, 400]], dtype=np.float32),
    )


def test_public_parse_gloria_rejects_invalid_satellites_before_reading_transactions(tmp_path, monkeypatch):
    _write_gloria_year(tmp_path)

    def _unexpected_read(*args, **kwargs):
        raise AssertionError("GLORIA transaction reader should not run for invalid satellite selections")

    monkeypatch.setattr(gloria_parser, "_read_transaction_blocks", _unexpected_read)

    with pytest.raises(WrongInput) as exc_info:
        mario.parse_gloria(str(tmp_path), table="SUT", satellites="not-a-real-satellite", calc_all=False)

    assert "Unknown GLORIA satellites/groups" in str(exc_info.value)


def test_public_parse_gloria_returns_database_and_rejects_iot(tmp_path):
    root = _write_gloria_year(tmp_path)

    database = mario.parse_gloria(str(tmp_path), table="SUT", calc_all=False, satellites="Emissions")

    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"]
    assert "GLORIA MRIO release local files" in database.meta.source
    assert database.meta.price == "Basic prices"
    assert database.Z.shape == (8, 8)
    assert database.Y.shape == (8, 4)
    assert database.V.shape == (2, 8)
    assert database.E.shape == (1, 8)
    assert database.EY.shape == (1, 4)

    with pytest.raises(NotImplementable):
        mario.parse_gloria(str(tmp_path), table="IOT", calc_all=False)


def test_parse_gloria_sut_falls_back_to_placeholder_extensions_when_tq_yq_are_missing(tmp_path):
    root = _write_gloria_year(tmp_path)
    satellite_root = tmp_path / "GLORIA_SatelliteAccounts_060_2025"
    for child in satellite_root.iterdir():
        child.unlink()
    satellite_root.rmdir()

    matrices, indeces, units, layout = parse_gloria_sut(root)
    base = matrices["baseline"]

    assert layout.TQ_path is None
    assert layout.YQ_path is None
    assert indeces["k"]["main"] == ["-"]
    assert units["Satellite account"].iloc[0, 0] == "None"
    assert base["Ea"].shape == (1, 4)
    assert base["Ec"].shape == (1, 4)
    assert base["EY"].shape == (1, 4)
    assert float(base["Ea"].astype(np.float32).to_numpy().sum()) == 0.0
    assert float(base["Ec"].astype(np.float32).to_numpy().sum()) == 0.0
    assert float(base["EY"].astype(np.float32).to_numpy().sum()) == 0.0


def test_public_parse_gloria_can_reload_from_parquet_cache(tmp_path, monkeypatch):
    _write_gloria_year(tmp_path)

    first = mario.parse_gloria(str(tmp_path), table="SUT", calc_all=False, cache=True)
    cache_root = tmp_path / ".mario_cache"
    assert cache_root.exists()

    def _unexpected_parse(*args, **kwargs):
        raise AssertionError("raw GLORIA parser should not run on cache hit")

    monkeypatch.setattr(parser_entrypoints, "parse_gloria_sut", _unexpected_parse)
    second = mario.parse_gloria(str(tmp_path), table="SUT", calc_all=False, cache=True)

    assert second.meta.source == first.meta.source
    assert second.meta.price == first.meta.price
    np.testing.assert_allclose(
        second.Z.sort_index().sort_index(axis=1).to_numpy(),
        first.Z.sort_index().sort_index(axis=1).to_numpy(),
    )
