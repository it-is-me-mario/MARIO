from __future__ import annotations

from pathlib import Path
import shutil
import zipfile

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers import entrypoints as parser_entrypoints
from mario.parsers import gloria as gloria_parser
from mario.parsers.gloria import parse_gloria_sut

pytestmark = pytest.mark.usefixtures("isolated_session_settings")


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


def _archive_directory(path: Path) -> Path:
    """Pack one GLORIA year directory into a zip archive at the same level."""
    archive_path = path.with_suffix(".zip")
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for child in sorted(path.iterdir()):
            archive.write(child, arcname=child.name)
    return archive_path


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


def test_parse_gloria_sut_supports_zipped_google_drive_release_layout(tmp_path):
    release_root = tmp_path / "060"
    part_i = release_root / "GLORIA_MRIO_Loop060_part_I_MRIOdatabase"
    part_iii = release_root / "GLORIA_MRIO_Loop060_part_III_satelliteaccounts"
    part_i.mkdir(parents=True)
    part_iii.mkdir(parents=True)

    data_root = _write_gloria_year(part_i)
    (part_i / "GLORIA_ReadMe_060.xlsx").rename(release_root / "GLORIA_ReadMe_060.xlsx")
    satellite_root = part_i / "GLORIA_SatelliteAccounts_060_2025"
    satellite_root.rename(part_iii / "GLORIA_SatelliteAccounts_060_2025")
    satellite_root = part_iii / "GLORIA_SatelliteAccounts_060_2025"

    data_zip = _archive_directory(data_root)
    satellite_zip = _archive_directory(satellite_root)
    shutil.rmtree(data_root)
    shutil.rmtree(satellite_root)

    for path in (release_root, part_i, data_zip):
        matrices, indeces, units, layout = parse_gloria_sut(path, satellites="Emissions")

        assert layout.data_root == data_zip
        assert layout.satellite_root == satellite_zip
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


def test_gloria_use_valuations_keep_import_origins_and_signed_subsidies(tmp_path):
    annual = _write_gloria_year(tmp_path)
    for markup, amount in [(3, 3.0), (4, 4.0), (5, -5.0)]:
        for block, shape in [("T", (8, 8)), ("Y", (8, 4))]:
            values = np.zeros(shape)
            # Wheat from Montenegro, bought by the first Italian buyer.
            values[6, 0] = amount
            np.savetxt(
                annual / f"20260121_120secMother_AllCountries_002_{block}-Results_2025_060_Markup{markup:03d}(full).csv",
                values,
                delimiter=",",
            )

    archive = _archive_directory(annual)
    valuations = mario.read_gloria_use_valuations(
        archive, year=2025, commodity="Wheat", destination_regions=["ME", "IT"],
    )

    assert list(valuations["basic"].index) == ["IT", "ME"]
    assert list(valuations["basic"].columns.get_level_values("Destination").unique()) == ["ME", "IT"]
    assert valuations["basic"].loc["IT", ("intermediate", "ME", "Wheat")] == 2.0
    assert valuations["basic"].loc["IT", ("final", "IT", "Household")] == 11.0
    assert valuations["subsidies"].loc["ME", ("intermediate", "IT", "Wheat")] == -5.0
    assert valuations["purchaser"].loc["ME", ("intermediate", "IT", "Wheat")] == 13.0
    assert valuations["purchaser"].loc["ME", ("final", "IT", "Household")] == 2.0


def test_gloria_use_valuations_reject_an_incomplete_price_bridge(tmp_path):
    _write_gloria_year(tmp_path)
    with pytest.raises(WrongInput, match=r"both T and Y for transport"):
        mario.read_gloria_use_valuations(tmp_path, commodity="Wheat", year=2025)


def test_parse_gloria_reconstructs_all_purchaser_uses_and_invalidates_cache(tmp_path, monkeypatch):
    annual = _write_gloria_year(tmp_path)
    for markup, amount in [(3, 3.0), (4, 4.0), (5, -5.0)]:
        for block, shape in [("T", (8, 8)), ("Y", (8, 4))]:
            values = np.zeros(shape)
            values[6, 0] = amount
            values[3, 2 if block == "Y" else 4] = 2 * amount
            # These activity rows exercise the distinction between S and Ya.
            values[0, 2 if block == "T" else 0] = amount
            np.savetxt(annual / f"test_{block}-Results_2025_060_Markup{markup:03d}(full).csv",
                       values, delimiter=",")

    options = {"year": 2025, "regions": ["ME", "IT"]}
    with pytest.raises(WrongInput, match="calc_all=False"):
        mario.parse_gloria(str(tmp_path), valuation="purchaser", calc_all=True, **options)
    basic = mario.parse_gloria(str(tmp_path), **options)["baseline"]
    first = mario.parse_gloria(str(tmp_path), valuation="purchaser", cache=True, **options)
    blocks = first["baseline"]
    assert first.meta.price == "Purchaser prices"
    for block in ("S", "Va", "Vc", "Ea", "Ec", "EY"):
        pd.testing.assert_frame_equal(blocks[block], basic[block])

    # The fixture's trade layer is ten times the basic layer. The remaining
    # three layers add signed adjustments in two commodities and in Ya.
    u = basic["U"].to_numpy() * 11
    u[0, 2] += 2
    u[3, 0] += 4
    yc = basic["Yc"].to_numpy() * 11
    yc[0, 2] += 2
    yc[3, 0] += 4
    np.testing.assert_allclose(blocks["U"].to_numpy(), u)
    np.testing.assert_allclose(blocks["Yc"].to_numpy(), yc)
    np.testing.assert_allclose(blocks["Ya"].to_numpy()[2, 2], 2)

    def unexpected_parse(*args, **kwargs):
        pytest.fail("the purchaser-price cache should be reused")

    with monkeypatch.context() as patch:
        patch.setattr(parser_entrypoints, "parse_gloria_sut", unexpected_parse)
        cached = mario.parse_gloria(str(tmp_path), valuation="purchaser", cache=True, **options)
        assert cached.meta.price == first.meta.price
        assert any("Supply, value added and satellite accounts" in note for note in cached.meta._history)
        for key in ("U", "Ya", "Yc"):
            expected = blocks[key]
            actual = cached["baseline"][key].reindex(index=expected.index, columns=expected.columns)
            np.testing.assert_allclose(actual.to_numpy(), expected.to_numpy())

    adjustment = next(annual.glob("*T-Results*Markup005*"))
    values = np.loadtxt(adjustment, delimiter=",")
    values[6, 0] -= 1
    np.savetxt(adjustment, values, delimiter=",")
    changed = mario.parse_gloria(str(tmp_path), valuation="purchaser", cache=True, **options)
    u[0, 2] -= 1
    np.testing.assert_allclose(changed["baseline"]["U"].to_numpy(), u)


def test_parse_gloria_purchaser_requires_all_layers(tmp_path):
    _write_gloria_year(tmp_path)
    with pytest.raises(WrongInput, match=r"both T and Y for transport"):
        mario.parse_gloria(str(tmp_path), valuation="purchaser", year=2025)
