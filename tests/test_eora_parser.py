import pandas as pd

from mario import parse_eora
from mario.model.conventions import _MASTER_INDEX


def _write_tsv(path, frame, *, header=True, index=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t", header=header, index=index)


def _build_single_region_frame():
    rows = pd.MultiIndex.from_tuples(
        [
            ("Italy", "ITA", "Industries", "Activity 1"),
            ("Italy", "ITA", "Commodities", "Commodity 1"),
            ("Italy", "ITA", "Primary Inputs", "Compensation of employees D.1"),
            ("France", "FRA", "ImportsFrom", "Total"),
            ("1", "I-ENERGY", "Energy Usage (TJ)", "Natural Gas"),
        ]
    )
    columns = pd.MultiIndex.from_tuples(
        [
            ("Italy", "ITA", "Industries", "Activity 1"),
            ("Italy", "ITA", "Commodities", "Commodity 1"),
            ("Italy", "ITA", "Final Demand", "Household final consumption P.3h"),
            ("France", "FRA", "ExportsTo", "Total"),
        ]
    )
    values = [
        [1.0, 2.0, 3.0, 4.0],
        [5.0, 6.0, 7.0, 8.0],
        [9.0, 10.0, 11.0, 12.0],
        [13.0, 14.0, 15.0, 16.0],
        [17.0, 18.0, 19.0, 20.0],
    ]
    return pd.DataFrame(values, index=rows, columns=columns)


def _build_single_region_iot_frame_without_industries():
    rows = pd.MultiIndex.from_tuples(
        [
            ("China", "CHN", "Commodities", "Sector 1"),
            ("China", "CHN", "Commodities", "Sector 2"),
            ("China", "CHN", "Primary Inputs", "Compensation of employees D.1"),
        ]
    )
    columns = pd.MultiIndex.from_tuples(
        [
            ("China", "CHN", "Commodities", "Sector 1"),
            ("China", "CHN", "Commodities", "Sector 2"),
            ("China", "CHN", "Final Demand", "Household final consumption P.3h"),
        ]
    )
    return pd.DataFrame(
        [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ],
        index=rows,
        columns=columns,
    )


def _build_single_region_sut_with_duplicate_commodities():
    rows = pd.MultiIndex.from_tuples(
        [
            ("Chile", "CHL", "Industries", "Activity 1"),
            ("Chile", "CHL", "Industries", "Activity 2"),
            ("Chile", "CHL", "Commodities", "Seafood"),
            ("Chile", "CHL", "Commodities", "Seafood"),
            ("Chile", "CHL", "Primary Inputs", "Compensation of employees D.1"),
        ]
    )
    columns = pd.MultiIndex.from_tuples(
        [
            ("Chile", "CHL", "Industries", "Activity 1"),
            ("Chile", "CHL", "Industries", "Activity 2"),
            ("Chile", "CHL", "Commodities", "Seafood"),
            ("Chile", "CHL", "Commodities", "Seafood"),
            ("Chile", "CHL", "Final Demand", "Household final consumption P.3h"),
        ]
    )
    return pd.DataFrame(
        [
            [1.0, 0.0, 2.0, 3.0, 4.0],
            [0.5, 1.5, 4.0, 5.0, 6.0],
            [7.0, 8.0, 0.0, 0.0, 1.0],
            [9.0, 10.0, 0.0, 0.0, 2.0],
            [11.0, 12.0, 0.0, 0.0, 0.0],
        ],
        index=rows,
        columns=columns,
    )


def _write_eora26_fixture(root):
    labels_t = pd.DataFrame(
        [
            ["AFG", "AFG", "Industries", "Agriculture"],
            ["AFG", "AFG", "Industries", "Manufacturing"],
            ["ROW", "ROW", "Industries", "TOTAL"],
        ]
    )
    labels_fd = pd.DataFrame(
        [
            ["AFG", "AFG", "Final demand", "Household final consumption P.3h"],
            ["AFG", "AFG", "Final demand", "Government final consumption P.3g"],
            ["ROW", "ROW", "Final demand", "Household final consumption P.3h"],
            ["ROW", "ROW", "Final demand", "Government final consumption P.3g"],
        ]
    )
    labels_va = pd.DataFrame(
        [
            ["Primary input", "Compensation of employees D.1"],
            ["Primary input", "Taxes on production D.29"],
        ]
    )
    labels_q = pd.DataFrame(
        [
            ["Energy Usage (TJ)", "Natural Gas"],
            ["I-GHG-CO2 emissions (Gg)", "Public electricity and heat production"],
        ]
    )

    Z = pd.DataFrame(
        [
            [1.0, 2.0, 9.0],
            [3.0, 4.0, 8.0],
            [7.0, 6.0, 5.0],
        ]
    )
    Y = pd.DataFrame(
        [
            [10.0, 11.0, 12.0, 13.0],
            [14.0, 15.0, 16.0, 17.0],
            [18.0, 19.0, 20.0, 21.0],
        ]
    )
    V = pd.DataFrame(
        [
            [22.0, 23.0, 24.0],
            [25.0, 26.0, 27.0],
        ]
    )
    E = pd.DataFrame(
        [
            [1.0, 1.5, 2.0],
            [2.5, 3.0, 3.5],
        ]
    )
    EY = pd.DataFrame(
        [
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8],
        ]
    )

    _write_tsv(root / "labels_T.txt", labels_t, header=False, index=False)
    _write_tsv(root / "labels_FD.txt", labels_fd, header=False, index=False)
    _write_tsv(root / "labels_VA.txt", labels_va, header=False, index=False)
    _write_tsv(root / "labels_Q.txt", labels_q, header=False, index=False)
    _write_tsv(root / "Eora26_2017_bp_T.txt", Z, header=False, index=False)
    _write_tsv(root / "Eora26_2017_bp_FD.txt", Y, header=False, index=False)
    _write_tsv(root / "Eora26_2017_bp_VA.txt", V, header=False, index=False)
    _write_tsv(root / "Eora26_2017_bp_Q.txt", E, header=False, index=False)
    _write_tsv(root / "Eora26_2017_bp_QY.txt", EY, header=False, index=False)


def test_parse_eora_single_region_directory_supports_country_selection(tmp_path):
    root = tmp_path / "IO_All_2017"
    frame = _build_single_region_frame()
    _write_tsv(root / "IO_ITA_2017_BasicPrice.txt", frame)

    database = parse_eora(
        str(root),
        multi_region=False,
        table=None,
        country="ITA",
        calc_all=False,
    )

    assert database.table_type == "SUT"
    assert database.meta.year == 2017
    assert database.meta.price == "BasicPrice"
    assert database.get_index(_MASTER_INDEX["r"]) == ["Italy"]
    assert database.get_index(_MASTER_INDEX["a"]) == ["Activity 1"]
    assert database.get_index(_MASTER_INDEX["c"]) == ["Commodity 1"]
    assert database.get_index(_MASTER_INDEX["f"]) == [
        "Compensation of employees D.1",
        "Imports",
    ]
    assert database.get_index(_MASTER_INDEX["n"]) == [
        "Household final consumption P.3h",
        "Exports",
    ]
    assert database.get_index(_MASTER_INDEX["k"]) == ["Natural Gas (I-ENERGY)"]
    assert database.units[_MASTER_INDEX["k"]].loc["Natural Gas (I-ENERGY)", "unit"] == "TJ"
    assert database.Z.shape == (2, 2)
    assert database.Y.shape == (2, 2)
    assert database.V.shape == (2, 2)
    assert database.E.shape == (1, 2)
    assert database.EY.shape == (1, 2)
    assert "X" not in database["baseline"]


def test_parse_eora26_reads_colocated_labels_and_normalizes_row(tmp_path):
    root = tmp_path / "Eora26_2017_bp"
    _write_eora26_fixture(root)

    database = parse_eora(
        str(root),
        multi_region=True,
        table="IOT",
        calc_all=False,
    )

    assert database.table_type == "IOT"
    assert database.meta.year == 2017
    assert database.meta.price == "bp"
    assert database.meta.name == "Eora26_2017_bp"
    assert database.get_index(_MASTER_INDEX["r"]) == ["AFG"]
    assert database.get_index(_MASTER_INDEX["s"]) == ["Agriculture", "Manufacturing"]
    assert database.get_index(_MASTER_INDEX["f"]) == [
        "Compensation of employees D.1",
        "Taxes on production D.29",
        "Import from ROW",
    ]
    assert database.get_index(_MASTER_INDEX["n"]) == [
        "Household final consumption P.3h",
        "Government final consumption P.3g",
        "Export to ROW",
    ]
    assert database.get_index(_MASTER_INDEX["k"]) == [
        "Energy Usage (TJ) - Natural Gas",
        "I-GHG-CO2 emissions (Gg) - Public electricity and heat production",
    ]
    assert database.units[_MASTER_INDEX["k"]].loc["Energy Usage (TJ) - Natural Gas", "unit"] == "TJ"
    assert database.Z.shape == (2, 2)
    assert database.Y.shape == (2, 3)
    assert database.V.shape == (3, 2)
    assert database.E.shape == (2, 2)
    assert database.EY.shape == (2, 3)
    assert "ROW" not in database.get_index(_MASTER_INDEX["r"])


def test_parse_eora_single_region_detects_iot_when_only_commodities_are_present(tmp_path):
    root = tmp_path / "IO_All_2017"
    _write_tsv(root / "IO_CHN_2017_BasicPrice.txt", _build_single_region_iot_frame_without_industries())

    database = parse_eora(
        str(root),
        multi_region=False,
        table=None,
        country="CHN",
        calc_all=False,
    )

    assert database.table_type == "IOT"
    assert database.get_index(_MASTER_INDEX["s"]) == ["Sector 1", "Sector 2"]
    assert database.Z.shape == (2, 2)


def test_parse_eora_single_region_preserves_duplicate_commodity_names(tmp_path):
    root = tmp_path / "IO_All_2017"
    _write_tsv(root / "IO_CHL_2017_BasicPrice.txt", _build_single_region_sut_with_duplicate_commodities())

    database = parse_eora(
        str(root),
        multi_region=False,
        table=None,
        country="CHL",
        calc_all=False,
    )

    assert database.table_type == "SUT"
    assert database.get_index(_MASTER_INDEX["c"]) == ["Seafood", "Seafood [2]"]
    assert database.Z.shape == (4, 4)
