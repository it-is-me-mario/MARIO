from pathlib import Path

import pandas as pd
import pytest

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers.entrypoints import parse_oecd
from mario.parsers.oecd_sdmx import build_oecd_sut_from_frames


def _write_oecd_sample_csv(path: Path, *, year: int, suffix: str = "") -> Path:
    """Write a compact OECD-like ICIO csv fixture."""
    sectors = ["AAA_A01", "AAA_C17_18", "BBB_A01", "BBB_C17_18"]
    final = ["AAA_HFCE", "AAA_GFCF", "BBB_HFCE", "BBB_GFCF"]
    columns = sectors + final + ["OUT"]
    index = sectors + ["TLS", "VA", "OUT"]

    data = pd.DataFrame(0.0, index=index, columns=columns)

    for row_idx, row in enumerate(sectors, start=1):
        for col_idx, col in enumerate(sectors, start=1):
            data.loc[row, col] = row_idx * col_idx
        data.loc[row, "AAA_HFCE"] = row_idx * 10
        data.loc[row, "AAA_GFCF"] = row_idx * 20
        data.loc[row, "BBB_HFCE"] = row_idx * 30
        data.loc[row, "BBB_GFCF"] = row_idx * 40
        data.loc[row, "OUT"] = data.loc[row, sectors + final].sum()

    data.loc["TLS", sectors] = [1.0, 2.0, 3.0, 4.0]
    data.loc["VA", sectors] = [11.0, 12.0, 13.0, 14.0]
    data.loc["OUT", sectors] = data.loc[sectors, sectors].sum(axis=0).values

    target = path / f"{year}{suffix}.csv"
    data.to_csv(target)
    return target


def _write_oecd_split_region_csv(path: Path, *, year: int, suffix: str = "") -> Path:
    """Write one OECD-like ICIO csv fixture with CN/MX split-country labels."""
    sectors = [
        "CHN_A01",
        "CN1_A01",
        "CN2_A01",
        "MEX_A01",
        "MX1_A01",
        "MX2_A01",
    ]
    final = [
        "CHN_HFCE",
        "CN1_HFCE",
        "CN2_HFCE",
        "MEX_HFCE",
        "MX1_HFCE",
        "MX2_HFCE",
    ]
    columns = sectors + final + ["OUT"]
    index = sectors + ["TLS", "VA", "OUT"]

    data = pd.DataFrame(0.0, index=index, columns=columns)

    diagonal_values = {
        "CHN_A01": 10.0,
        "CN1_A01": 1.0,
        "CN2_A01": 2.0,
        "MEX_A01": 20.0,
        "MX1_A01": 3.0,
        "MX2_A01": 4.0,
    }
    final_values = {
        "CHN_HFCE": 50.0,
        "CN1_HFCE": 5.0,
        "CN2_HFCE": 6.0,
        "MEX_HFCE": 60.0,
        "MX1_HFCE": 7.0,
        "MX2_HFCE": 8.0,
    }

    for code in sectors:
        data.loc[code, code] = diagonal_values[code]
        region = code.split("_", 1)[0]
        data.loc[code, f"{region}_HFCE"] = final_values[f"{region}_HFCE"]
        data.loc[code, "OUT"] = data.loc[code, sectors + final].sum()

    data.loc["TLS", sectors] = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    data.loc["VA", sectors] = [11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
    data.loc["OUT", sectors] = data.loc[sectors, sectors].sum(axis=0).values

    target = path / f"{year}{suffix}.csv"
    data.to_csv(target)
    return target


def _write_oecd_total_iot_csv(path: Path, *, country: str, year: int) -> Path:
    """Write a compact OECD national total-table csv fixture."""
    sectors = ["A01", "C10T12"]
    final = ["HFCE", "GFCF", "EXPO", "IMPO"]
    rows = [
        "TTL_A01",
        "TTL_C10T12",
        "IMP_OTHER",
        "TXS_INT_FNL",
        "TTL_INT_FNL",
        "VALU",
        "LABR",
        "OTXS",
        "CFC",
        "NOPS",
        "OUTPUT",
    ]
    columns = sectors + final + ["TOTAL"]
    frame = pd.DataFrame(0.0, index=rows, columns=columns)

    frame.loc["TTL_A01", sectors + final] = [1.0, 2.0, 10.0, 20.0, 5.0, -2.0]
    frame.loc["TTL_C10T12", sectors + final] = [3.0, 4.0, 30.0, 40.0, 6.0, -3.0]
    frame.loc["IMP_OTHER", sectors] = [7.0, 8.0]
    frame.loc["TXS_INT_FNL", sectors] = [1.0, 2.0]
    frame.loc["LABR", sectors] = [11.0, 12.0]
    frame.loc["OTXS", sectors] = [1.0, 1.0]
    frame.loc["CFC", sectors] = [2.0, 3.0]
    frame.loc["NOPS", sectors] = [4.0, 5.0]
    frame.loc["VALU", sectors] = frame.loc[["LABR", "OTXS", "CFC", "NOPS"], sectors].sum(axis=0).values
    frame.loc["TTL_INT_FNL", final] = frame.loc[["TTL_A01", "TTL_C10T12"], final].sum(axis=0).values
    frame.loc["TTL_A01", "TOTAL"] = frame.loc["TTL_A01", sectors + final].sum()
    frame.loc["TTL_C10T12", "TOTAL"] = frame.loc["TTL_C10T12", sectors + final].sum()
    frame.loc["IMP_OTHER", "TOTAL"] = frame.loc["IMP_OTHER", sectors].sum()
    frame.loc["TXS_INT_FNL", "TOTAL"] = frame.loc["TXS_INT_FNL", sectors].sum()
    frame.loc["VALU", "TOTAL"] = frame.loc["VALU", sectors].sum()
    frame.loc["LABR", "TOTAL"] = frame.loc["LABR", sectors].sum()
    frame.loc["OTXS", "TOTAL"] = frame.loc["OTXS", sectors].sum()
    frame.loc["CFC", "TOTAL"] = frame.loc["CFC", sectors].sum()
    frame.loc["NOPS", "TOTAL"] = frame.loc["NOPS", sectors].sum()
    frame.loc["TTL_INT_FNL", "TOTAL"] = frame.loc["TTL_INT_FNL", final].sum()
    frame.loc["OUTPUT", sectors] = frame.loc[
        ["TTL_A01", "TTL_C10T12", "IMP_OTHER", "TXS_INT_FNL", "LABR", "OTXS", "CFC", "NOPS"],
        sectors,
    ].sum(axis=0).values
    frame.loc["OUTPUT", "TOTAL"] = frame.loc["OUTPUT", sectors].sum()

    target = path / f"{country}{year}ttl.csv"
    frame.to_csv(target)
    return target


def _build_oecd_sut_frames():
    """Return compact synthetic OECD SDMX frames for one balanced SUT."""
    supply_rows = []
    for activity, values in {
        "A01": {"CPA08_A01": 15.0, "CPA08_B05": 10.0, "CPA08_O": 10.0},
        "B05": {"CPA08_A01": 5.0, "CPA08_B05": 30.0, "CPA08_O": 10.0},
        "O": {"CPA08_A01": 8.0, "CPA08_B05": 7.0, "CPA08_O": 15.0},
        "A": {"CPA08_A": 0.0},
        "_T": {"_T": 0.0},
    }.items():
        for product, value in values.items():
            supply_rows.append(
                {
                    "TRANSACTION": "P1",
                    "ACTIVITY": activity,
                    "PRODUCT": product,
                    "VALUATION": "B",
                    "PRICE_BASE": "V",
                    "OBS_VALUE": value,
                    "CURRENCY": "XCU",
                }
            )
    for transaction, values in {
        "P7": {"CPA08_A01": 5.0, "CPA08_B05": 6.0, "CPA08_O": 3.0},
        "P33": {"CPA08_A01": 0.0, "CPA08_B05": 0.0, "CPA08_O": 0.0},
        "P7ADJ": {"CPA08_A01": 0.0, "CPA08_B05": 0.0, "CPA08_O": 0.0},
        "D21X31": {"CPA08_A01": 1.0, "CPA08_B05": 1.0, "CPA08_O": 1.0},
        "OTTM": {"CPA08_A01": 1.0, "CPA08_B05": 1.0, "CPA08_O": 1.0},
    }.items():
        for product, value in values.items():
            supply_rows.append(
                {
                    "TRANSACTION": transaction,
                    "ACTIVITY": "_Z",
                    "PRODUCT": product,
                    "VALUATION": "O" if transaction in {"D21X31", "OTTM"} else "B",
                    "PRICE_BASE": "V",
                    "OBS_VALUE": value,
                    "CURRENCY": "XCU",
                }
            )

    use_rows = []
    intermediate = {
        "CPA08_A01": {"A01": 4.0, "B05": 3.0, "O": 1.0},
        "CPA08_B05": {"A01": 5.0, "B05": 10.0, "O": 2.0},
        "CPA08_O": {"A01": 3.0, "B05": 4.0, "O": 2.0},
    }
    for product, activity_map in intermediate.items():
        for activity, value in activity_map.items():
            use_rows.append(
                {
                    "TRANSACTION": "P2",
                    "ACTIVITY": activity,
                    "PRODUCT": product,
                    "PRICE_BASE": "V",
                    "OBS_VALUE": value,
                    "CURRENCY": "XCU",
                }
            )
    final_demand = {
        "P3S14DC": {"CPA08_A01": 10.0, "CPA08_B05": 8.0, "CPA08_O": 12.0},
        "P3S15": {"CPA08_A01": 1.0, "CPA08_B05": 0.0, "CPA08_O": 1.0},
        "P3S13": {"CPA08_A01": 2.0, "CPA08_B05": 1.0, "CPA08_O": 6.0},
        "P51G": {"CPA08_A01": 4.0, "CPA08_B05": 10.0, "CPA08_O": 5.0},
        "P52": {"CPA08_A01": 3.0, "CPA08_B05": 4.0, "CPA08_O": 0.0},
        "P53": {"CPA08_A01": 0.0, "CPA08_B05": 2.0, "CPA08_O": 0.0},
        "P6": {"CPA08_A01": 7.0, "CPA08_B05": 13.0, "CPA08_O": 7.0},
        "P6A": {"CPA08_A01": 0.5, "CPA08_B05": 1.5, "CPA08_O": 0.0},
    }
    for transaction, product_map in final_demand.items():
        for product, value in product_map.items():
            use_rows.append(
                {
                    "TRANSACTION": transaction,
                    "ACTIVITY": "_Z",
                    "PRODUCT": product,
                    "PRICE_BASE": "V",
                    "OBS_VALUE": value,
                    "CURRENCY": "XCU",
                }
            )
    use_rows.extend(
        [
            {"TRANSACTION": "P2", "ACTIVITY": "A", "PRODUCT": "CPA08_A", "PRICE_BASE": "V", "OBS_VALUE": 0.0, "CURRENCY": "XCU"},
            {"TRANSACTION": "P3S14DC", "ACTIVITY": "_Z", "PRODUCT": "CPA08_A", "PRICE_BASE": "V", "OBS_VALUE": 0.0, "CURRENCY": "XCU"},
            {"TRANSACTION": "P2", "ACTIVITY": "_T", "PRODUCT": "_T", "PRICE_BASE": "V", "OBS_VALUE": 0.0, "CURRENCY": "XCU"},
        ]
    )

    useva_rows = []
    for transaction, activity_map in {
        "D1": {"A01": 10.0, "B05": 12.0, "O": 8.0},
        "D29X39": {"A01": 1.0, "B05": 2.0, "O": 3.0},
        "P51C": {"A01": 2.0, "B05": 4.0, "O": 4.0},
        "B2A3N": {"A01": 10.0, "B05": 10.0, "O": 10.0},
    }.items():
        for activity, value in activity_map.items():
            useva_rows.append(
                {
                    "TRANSACTION": transaction,
                    "ACTIVITY": activity,
                    "PRODUCT": "_T",
                    "PRICE_BASE": "V",
                    "OBS_VALUE": value,
                    "CURRENCY": "XCU",
                }
            )

    return (
        pd.DataFrame(supply_rows),
        pd.DataFrame(use_rows),
        pd.DataFrame(useva_rows),
    )


def test_parse_oecd_file_returns_iot_blocks(tmp_path):
    source_dir = tmp_path / "2016-2022_EXT"
    source_dir.mkdir()
    source = _write_oecd_sample_csv(source_dir, year=2022)

    database = parse_oecd(path=str(source), calc_all=False)

    assert database.table_type == "IOT"
    assert set(database["baseline"]) == {"E", "EY", "V", "Y", "Z"}
    assert database.meta.name == "OECD ICIO 2022 extended"
    assert "2025 edition" in database.meta.source
    assert database.Z.shape == (4, 4)
    assert database.Y.shape == (4, 4)
    assert database.V.shape == (2, 4)
    assert database.E.shape == (1, 4)
    assert database.EY.shape == (1, 4)
    assert list(database.V.index) == ["TLS", "VA"]
    assert list(database.E.index) == ["-"]
    assert database.get_index("Sector") == ["A01", "C17_18"]
    assert database.get_index("Consumption category") == ["HFCE", "GFCF"]


def test_parse_oecd_directory_requires_year_when_multiple_files(tmp_path):
    source_dir = tmp_path / "2016-2022_EXT"
    source_dir.mkdir()
    _write_oecd_sample_csv(source_dir, year=2021)
    _write_oecd_sample_csv(source_dir, year=2022)

    with pytest.raises(WrongInput):
        parse_oecd(path=str(source_dir), calc_all=False)


def test_parse_oecd_directory_selects_requested_year(tmp_path):
    source_dir = tmp_path / "2016-2022_EXT"
    source_dir.mkdir()
    _write_oecd_sample_csv(source_dir, year=2021)
    _write_oecd_sample_csv(source_dir, year=2022)

    database = parse_oecd(path=str(source_dir), year=2021, calc_all=False)

    assert database.meta.year == 2021
    assert database.meta.name == "OECD ICIO 2021 extended"


def test_parse_oecd_regular_sml_file_is_supported(tmp_path):
    source_dir = tmp_path / "2016-2022_SML"
    source_dir.mkdir()
    source = _write_oecd_sample_csv(source_dir, year=2022, suffix="_SML")

    database = parse_oecd(path=str(source), calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.year == 2022
    assert database.meta.name == "OECD ICIO 2022 regular"


def test_parse_oecd_icio_aggregates_split_china_and_mexico_regions(tmp_path):
    source_dir = tmp_path / "2016-2022_EXT"
    source_dir.mkdir()
    source = _write_oecd_split_region_csv(source_dir, year=2022)

    database = parse_oecd(path=str(source), calc_all=False)

    assert database.get_index("Region") == ["CHN", "MEX"]
    assert database.get_index("Sector") == ["A01"]
    assert database.Z.loc[("CHN", "Sector", "A01"), ("CHN", "Sector", "A01")] == 13.0
    assert database.Z.loc[("MEX", "Sector", "A01"), ("MEX", "Sector", "A01")] == 27.0
    assert database.Y.loc[("CHN", "Sector", "A01"), ("CHN", "Consumption category", "HFCE")] == 61.0
    assert database.Y.loc[("MEX", "Sector", "A01"), ("MEX", "Consumption category", "HFCE")] == 75.0
    assert database.V.loc["TLS", ("CHN", "Sector", "A01")] == 6.0
    assert database.V.loc["VA", ("MEX", "Sector", "A01")] == 45.0
    assert any("CN1/CN2" in note and "MX1/MX2" in note for note in database.meta._history)


def test_parse_oecd_national_total_iot(tmp_path):
    source = _write_oecd_total_iot_csv(tmp_path, country="CZE", year=2014)

    database = parse_oecd(path=str(source), dataset="IOT", calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.year == 2014
    assert database.meta.name == "OECD IOT CZE 2014"
    assert database.Z.shape == (2, 2)
    assert database.Y.shape == (2, 4)
    assert database.V.shape == (6, 2)
    assert database.get_index("Sector") == ["A01", "C10T12"]
    assert database.get_index("Consumption category") == ["HFCE", "GFCF", "EXPO", "IMPO"]
    assert list(database.V.index) == ["IMP_OTHER", "TXS_INT_FNL", "LABR", "OTXS", "CFC", "NOPS"]


def test_parse_oecd_rejects_environmental_extensions_for_now(tmp_path):
    source = _write_oecd_total_iot_csv(tmp_path, country="CZE", year=2014)

    with pytest.raises(NotImplementable, match="economic tables only"):
        parse_oecd(
            path=str(source),
            dataset="IOT",
            add_extensions=True,
            calc_all=False,
        )


def test_build_oecd_sut_from_frames_returns_balanced_split_native_blocks():
    supply_frame, use_frame, useva_frame = _build_oecd_sut_frames()

    matrices, indexes, units, layout = build_oecd_sut_from_frames(
        supply_frame,
        use_frame,
        useva_frame,
        country="CZE",
        year=2022,
    )

    blocks = matrices["baseline"]
    assert layout.dataset_name == "OECD SUT CZE 2022"
    assert blocks["S"].shape == (3, 3)
    assert blocks["U"].shape == (3, 3)
    assert blocks["Yc"].shape == (3, 7)
    assert blocks["Va"].shape == (9, 3)
    assert blocks["Vc"].shape == (9, 3)
    assert indexes["a"]["main"] == ["A01", "B05", "O"]
    assert indexes["c"]["main"] == ["A01", "B05", "O"]
    assert indexes["n"]["main"] == ["HFCE", "NPISH", "GGFC", "GFCF", "INVNT", "VALUABLES", "EXPO"]
    assert "Compensation of employees" in indexes["f"]["main"]
    assert "Imports of goods and services" in indexes["f"]["main"]
    assert units["Activity"].loc["A01", "unit"] == "XCU"
    assert units["Commodity"].loc["O", "unit"] == "XCU"

    commodity_balance = (
        blocks["S"].sum(axis=0)
        + blocks["Vc"].sum(axis=0)
        - blocks["U"].sum(axis=1)
        - blocks["Yc"].sum(axis=1)
    ).abs().max()
    activity_balance = (
        blocks["U"].sum(axis=0)
        + blocks["Va"].sum(axis=0)
        - blocks["S"].sum(axis=1)
    ).abs().max()
    assert commodity_balance < 1e-9
    assert activity_balance < 1e-9
