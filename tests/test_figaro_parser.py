from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput
from mario.parsers.figaro import parse_figaro_iot, parse_figaro_sut


def _write_csv_zip(path: Path, csv_name: str, frame: pd.DataFrame) -> None:
    """Write one dataframe as a zipped CSV with the requested member name."""
    csv_payload = frame.to_csv(index=False).encode("utf-8")
    with ZipFile(path, "w") as archive:
        archive.writestr(csv_name, csv_payload)


def _write_figaro_year(tmp_path: Path, year: int, *, suffix: str = "25ed") -> None:
    """Create one minimal FIGARO supply/use bundle for a specific year."""
    supply = pd.DataFrame(
        [
            ["IT_CPA_A01", "IT_A01", "IT", "CPA_A01", "IT", "A01", 100.0],
            ["ME_CPA_A01", "IT_A01", "ME", "CPA_A01", "IT", "A01", 7.0],
            ["IT_CPA_A01", "ME_A01", "IT", "CPA_A01", "ME", "A01", 3.0],
            ["ME_CPA_A01", "ME_A01", "ME", "CPA_A01", "ME", "A01", 40.0],
        ],
        columns=["icsupRow", "icsupCol", "refArea", "rowPi", "counterpartArea", "colPi", "obsValue"],
    )
    use = pd.DataFrame(
        [
            ["IT_CPA_A01", "IT_A01", "IT", "CPA_A01", "IT", "A01", 10.0],
            ["ME_CPA_A01", "IT_A01", "ME", "CPA_A01", "IT", "A01", 1.0],
            ["IT_CPA_A01", "ME_A01", "IT", "CPA_A01", "ME", "A01", 2.0],
            ["ME_CPA_A01", "ME_A01", "ME", "CPA_A01", "ME", "A01", 20.0],
            ["IT_CPA_A01", "IT_P3_S14", "IT", "CPA_A01", "IT", "P3_S14", 30.0],
            ["ME_CPA_A01", "IT_P3_S14", "ME", "CPA_A01", "IT", "P3_S14", 5.0],
            ["IT_CPA_A01", "ME_P51G", "IT", "CPA_A01", "ME", "P51G", 4.0],
            ["W2_D1", "IT_A01", "W2", "D1", "IT", "A01", 40.0],
            ["W2_D1", "ME_A01", "W2", "D1", "ME", "A01", 50.0],
            ["W2_B2A3G", "IT_A01", "W2", "B2A3G", "IT", "A01", 60.0],
            ["W2_B2A3G", "ME_A01", "W2", "B2A3G", "ME", "A01", 70.0],
        ],
        columns=["icuseRow", "icuseCol", "refArea", "rowPi", "counterpartArea", "colPi", "obsValue"],
    )

    _write_csv_zip(
        tmp_path / f"flatfile_eu-ic-supply_{suffix}_{year}.zip",
        f"flatfile_eu-ic-supply_{suffix}_{year}.csv",
        supply,
    )
    _write_csv_zip(
        tmp_path / f"flatfile_eu-ic-use_{suffix}_{year}.zip",
        f"flatfile_eu-ic-use_{suffix}_{year}.csv",
        use,
    )


def _write_figaro_iot_year(tmp_path: Path, year: int, *, suffix: str = "25ed") -> None:
    """Create minimal FIGARO product and industry IOT bundles for one year."""
    product = pd.DataFrame(
        [
            ["IT_CPA_A01", "IT_CPA_A01", "IT", "CPA_A01", "IT", "CPA_A01", 100.0],
            ["ME_CPA_A01", "IT_CPA_A01", "ME", "CPA_A01", "IT", "CPA_A01", 7.0],
            ["IT_CPA_A01", "ME_CPA_A01", "IT", "CPA_A01", "ME", "CPA_A01", 3.0],
            ["ME_CPA_A01", "ME_CPA_A01", "ME", "CPA_A01", "ME", "CPA_A01", 40.0],
            ["IT_CPA_A01", "IT_P3_S14", "IT", "CPA_A01", "IT", "P3_S14", 30.0],
            ["ME_CPA_A01", "IT_P3_S14", "ME", "CPA_A01", "IT", "P3_S14", 5.0],
            ["IT_CPA_A01", "ME_P51G", "IT", "CPA_A01", "ME", "P51G", 4.0],
            ["W2_D1", "IT_CPA_A01", "W2", "D1", "IT", "CPA_A01", 40.0],
            ["W2_D1", "ME_CPA_A01", "W2", "D1", "ME", "CPA_A01", 50.0],
            ["W2_B2A3G", "IT_CPA_A01", "W2", "B2A3G", "IT", "CPA_A01", 60.0],
            ["W2_B2A3G", "ME_CPA_A01", "W2", "B2A3G", "ME", "CPA_A01", 70.0],
        ],
        columns=["iciopRow", "iciopCol", "refArea", "rowPp", "counterpartArea", "colPp", "obsValue"],
    )
    industry = pd.DataFrame(
        [
            ["IT_A01", "IT_A01", "IT", "A01", "IT", "A01", 100.0],
            ["ME_A01", "IT_A01", "ME", "A01", "IT", "A01", 7.0],
            ["IT_A01", "ME_A01", "IT", "A01", "ME", "A01", 3.0],
            ["ME_A01", "ME_A01", "ME", "A01", "ME", "A01", 40.0],
            ["IT_A01", "IT_P3_S14", "IT", "A01", "IT", "P3_S14", 30.0],
            ["ME_A01", "IT_P3_S14", "ME", "A01", "IT", "P3_S14", 5.0],
            ["IT_A01", "ME_P51G", "IT", "A01", "ME", "P51G", 4.0],
            ["W2_D1", "IT_A01", "W2", "D1", "IT", "A01", 40.0],
            ["W2_D1", "ME_A01", "W2", "D1", "ME", "A01", 50.0],
            ["W2_B2A3G", "IT_A01", "W2", "B2A3G", "IT", "A01", 60.0],
            ["W2_B2A3G", "ME_A01", "W2", "B2A3G", "ME", "A01", 70.0],
        ],
        columns=["icioiRow", "icioiCol", "refArea", "rowIi", "counterpartArea", "colIi", "obsValue"],
    )

    _write_csv_zip(
        tmp_path / f"flatfile_eu-ic-io_prod-by-prod_{suffix}_{year}.zip",
        f"flatfile_eu-ic-io_prod-by-prod_{suffix}_{year}.csv",
        product,
    )
    _write_csv_zip(
        tmp_path / f"flatfile_eu-ic-io_ind-by-ind_{suffix}_{year}.zip",
        f"flatfile_eu-ic-io_ind-by-ind_{suffix}_{year}.csv",
        industry,
    )


def test_parse_figaro_sut_returns_split_native_blocks_from_zip_bundle(tmp_path):
    _write_figaro_year(tmp_path, 2023)

    matrices, indeces, units, layout = parse_figaro_sut(tmp_path)
    base = matrices["baseline"]

    assert layout.year == 2023
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


def test_parse_figaro_requires_explicit_year_when_directory_contains_multiple_years(tmp_path):
    _write_figaro_year(tmp_path, 2023)
    _write_figaro_year(tmp_path, 2024, suffix="26ed")

    with pytest.raises(WrongInput):
        parse_figaro_sut(tmp_path)

    _, _, _, layout = parse_figaro_sut(tmp_path, year=2024)
    assert layout.year == 2024
    assert layout.edition == "26ed"


def test_public_parse_figaro_returns_database_and_rejects_iot(tmp_path):
    _write_figaro_year(tmp_path, 2023)

    database = mario.parse_figaro(str(tmp_path), table="SUT", calc_all=False)

    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"]
    assert "Z" not in database["baseline"]
    assert database.Z.shape == (4, 4)
    assert database.Y.shape == (4, 4)
    assert database.V.shape == (2, 4)
    assert "FIGARO database via CIRCABC" in database.meta.source


def test_parse_figaro_iot_supports_product_and_industry_variants(tmp_path):
    _write_figaro_iot_year(tmp_path, 2023)

    matrices, indeces, units, layout = parse_figaro_iot(tmp_path)
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

    matrices_i, indeces_i, _, layout_i = parse_figaro_iot(tmp_path, mode="industry")
    assert layout_i.mode == "industry"
    assert indeces_i["s"]["main"] == [
        "Crop and animal production, hunting and related service activities"
    ]
    assert float(matrices_i["baseline"]["Z"].iloc[0, 0]) == 100.0


def test_public_parse_figaro_iot_returns_database_and_validates_mode(tmp_path):
    _write_figaro_iot_year(tmp_path, 2023)

    database = mario.parse_figaro(str(tmp_path), table="IOT", calc_all=False)

    assert sorted(database["baseline"].keys()) == ["E", "EY", "V", "Y", "Z"]
    assert database.Z.shape == (2, 2)
    assert database.Y.shape == (2, 4)
    assert database.V.shape == (2, 2)

    with pytest.raises(WrongInput):
        mario.parse_figaro(str(tmp_path), table="IOT", iot_mode="bad", calc_all=False)
