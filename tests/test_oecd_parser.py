from pathlib import Path

import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.parsers.entrypoints import parse_oecd


def _write_oecd_sample_csv(path: Path, *, year: int) -> Path:
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

    target = path / f"{year}.csv"
    data.to_csv(target)
    return target


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
