from pathlib import Path

import pandas as pd
import pandas.testing as pdt
import pytest

from mario.parsers.entrypoints import (
    parse_from_excel,
    parse_from_parquet,
    parse_from_txt,
)


REALDATA_ROOT = Path(__file__).parent / "fixtures" / "realdata"
REALDATA_DATA = REALDATA_ROOT / "data"
REALDATA_AGGREGATIONS = REALDATA_ROOT / "aggregations"


# Note:
# - ``IOT_Vsr_Esr.xlsx`` currently exposes ``E``/``EY`` only by ``Region``.
# - ``SUT_Vsr_Er.xlsx`` currently exposes ``E`` by ``Region`` and ``Activity``.
REALDATA_DATASETS = {
    "IOT_legacy.xlsx": {
        "table": "IOT",
        "matrix_layouts": {},
        "aggregation_files": [
            "IOT_r.xlsx",
            "IOT_rf.xlsx",
            "IOT_s.xlsx",
            "IOT_sf.xlsx",
        ],
    },
    "IOT_Vr_Er.xlsx": {
        "table": "IOT",
        "matrix_layouts": {"V": "Region", "E": "Region", "EY": "Region"},
        "aggregation_files": [
            "IOT_r.xlsx",
            "IOT_rf.xlsx",
            "IOT_s.xlsx",
            "IOT_sf.xlsx",
        ],
    },
    "IOT_Vr_Esr.xlsx": {
        "table": "IOT",
        "matrix_layouts": {"V": "Region", "E": ("Region", "Sector"), "EY": ("Region", "Sector")},
        "aggregation_files": [
            "IOT_r.xlsx",
            "IOT_rf.xlsx",
            "IOT_s.xlsx",
            "IOT_sf.xlsx",
        ],
    },
    "IOT_Vsr_Er.xlsx": {
        "table": "IOT",
        "matrix_layouts": {"V": ("Region", "Sector"), "E": "Region", "EY": "Region"},
        "aggregation_files": [
            "IOT_r.xlsx",
            "IOT_rf.xlsx",
            "IOT_s.xlsx",
            "IOT_sf.xlsx",
        ],
    },
    "IOT_Vsr_Esr.xlsx": {
        "table": "IOT",
        "matrix_layouts": {"V": ("Region", "Sector"), "E": "Region", "EY": "Region"},
        "aggregation_files": [
            "IOT_r.xlsx",
            "IOT_rf.xlsx",
            "IOT_s.xlsx",
            "IOT_sf.xlsx",
        ],
    },
    "SUT_legacy.xlsx": {
        "table": "SUT",
        "matrix_layouts": {},
        "aggregation_files": [
            "SUT_a.xlsx",
            "SUT_ac.xlsx",
            "SUT_acf.xlsx",
            "SUT_af.xlsx",
            "SUT_c.xlsx",
            "SUT_cf.xlsx",
            "SUT_f.xlsx",
            "SUT_r.xlsx",
            "SUT_ra.xlsx",
            "SUT_rac.xlsx",
            "SUT_racf.xlsx",
            "SUT_raf.xlsx",
            "SUT_rc.xlsx",
            "SUT_rcf.xlsx",
            "SUT_rf.xlsx",
        ],
    },
    "SUT_Vr_Er.xlsx": {
        "table": "SUT",
        "matrix_layouts": {"V": "Region", "E": "Region"},
        "aggregation_files": [
            "SUT_a.xlsx",
            "SUT_ac.xlsx",
            "SUT_acf.xlsx",
            "SUT_af.xlsx",
            "SUT_c.xlsx",
            "SUT_cf.xlsx",
            "SUT_f.xlsx",
            "SUT_r.xlsx",
            "SUT_ra.xlsx",
            "SUT_rac.xlsx",
            "SUT_racf.xlsx",
            "SUT_raf.xlsx",
            "SUT_rc.xlsx",
            "SUT_rcf.xlsx",
            "SUT_rf.xlsx",
        ],
    },
    "SUT_Vr_Esr.xlsx": {
        "table": "SUT",
        "matrix_layouts": {"V": "Region", "E": ("Region", "Activity")},
        "aggregation_files": [
            "SUT_a.xlsx",
            "SUT_ac.xlsx",
            "SUT_acf.xlsx",
            "SUT_af.xlsx",
            "SUT_c.xlsx",
            "SUT_cf.xlsx",
            "SUT_f.xlsx",
            "SUT_r.xlsx",
            "SUT_ra.xlsx",
            "SUT_rac.xlsx",
            "SUT_racf.xlsx",
            "SUT_raf.xlsx",
            "SUT_rc.xlsx",
            "SUT_rcf.xlsx",
            "SUT_rf.xlsx",
        ],
    },
    "SUT_Vsr_Er.xlsx": {
        "table": "SUT",
        "matrix_layouts": {"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        "aggregation_files": [
            "SUT_a.xlsx",
            "SUT_ac.xlsx",
            "SUT_acf.xlsx",
            "SUT_af.xlsx",
            "SUT_c.xlsx",
            "SUT_cf.xlsx",
            "SUT_f.xlsx",
            "SUT_r.xlsx",
            "SUT_ra.xlsx",
            "SUT_rac.xlsx",
            "SUT_racf.xlsx",
            "SUT_raf.xlsx",
            "SUT_rc.xlsx",
            "SUT_rcf.xlsx",
            "SUT_rf.xlsx",
        ],
    },
    "SUT_Vsr_Esr.xlsx": {
        "table": "SUT",
        "matrix_layouts": {"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        "aggregation_files": [],
    },
}


def _dataset_case_id(filename: str) -> str:
    return filename.removesuffix(".xlsx")


def _sorted_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sort_index(axis=0).sort_index(axis=1)


def _normalized_unit_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.fillna("").sort_index().copy()
    normalized.index = normalized.index.rename(None)
    return normalized


def _flow_block_names(table: str) -> tuple[str, ...]:
    if table == "IOT":
        return ("Z", "Y", "V", "E", "EY", "VY")
    return ("U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY")


def _get_block_frame(database, block: str) -> pd.DataFrame:
    try:
        return getattr(database, block)
    except Exception:
        return database["baseline"][block]


def _load_realdata_database(filename: str, *, calc_all: bool = False):
    spec = REALDATA_DATASETS[filename]
    return parse_from_excel(
        path=str(REALDATA_DATA / filename),
        table=spec["table"],
        mode="flows",
        matrix_layouts=spec["matrix_layouts"],
        calc_all=calc_all,
    )


def _aggregate_realdata_database(filename: str, aggregation_name: str):
    spec = REALDATA_DATASETS[filename]
    database = _load_realdata_database(filename)
    aggregated = database.aggregate(
        io=str(REALDATA_AGGREGATIONS / aggregation_name),
        ignore_nan=True,
        inplace=False,
        calc_all=False,
    )
    return aggregated, spec


def _compare_flow_blocks(original, roundtrip, table: str) -> None:
    for block in _flow_block_names(table):
        pdt.assert_frame_equal(
            _sorted_frame(_get_block_frame(original, block)),
            _sorted_frame(_get_block_frame(roundtrip, block)),
        )

    for label, original_unit in original.units.items():
        pdt.assert_frame_equal(
            _normalized_unit_frame(original_unit),
            _normalized_unit_frame(roundtrip.units[label]),
        )

    pdt.assert_frame_equal(_sorted_frame(original.V), _sorted_frame(roundtrip.V))
    pdt.assert_frame_equal(_sorted_frame(original.E), _sorted_frame(roundtrip.E))


def _expected_row_names(table: str, matrix_name: str, matrix_layouts: dict[str, object]) -> list[str]:
    def _layout_tuple(value):
        if value in (None, ()):
            return ()
        if isinstance(value, str):
            return (value,)
        return tuple(value)

    if table == "IOT":
        if matrix_name == "V":
            layout = _layout_tuple(matrix_layouts.get("V", matrix_layouts.get("v", ())))
            return ["Item"] if not layout else [*layout, "Factor of production"]
        layout = _layout_tuple(matrix_layouts.get("E", matrix_layouts.get("e", ())))
        return ["Item"] if not layout else [*layout, "Satellite account"]

    if matrix_name == "V":
        layout = _layout_tuple(matrix_layouts.get("V", matrix_layouts.get("v", ())))
        return ["Item"] if not layout else [*layout, "Factor of production"]
    layout = _layout_tuple(matrix_layouts.get("E", matrix_layouts.get("e", ())))
    return ["Item"] if not layout else [*layout, "Satellite account"]


def _aggregation_expectations(path: Path) -> dict[str, list[object]]:
    workbook = pd.ExcelFile(path)
    expectations = {}
    for sheet_name in workbook.sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet_name, index_col=0)
        labels = [item for item in frame.iloc[:, 0].tolist() if pd.notna(item)]
        if labels:
            expectations[sheet_name] = list(dict.fromkeys(labels))
    return expectations


@pytest.mark.parametrize(
    "filename",
    sorted(REALDATA_DATASETS),
    ids=_dataset_case_id,
)
def test_realdata_excel_parser_reads_all_vendored_workbooks(filename):
    spec = REALDATA_DATASETS[filename]
    database = _load_realdata_database(filename)

    assert set(_flow_block_names(spec["table"])) <= set(database["baseline"])
    assert database.V.index.names == _expected_row_names(spec["table"], "V", spec["matrix_layouts"])
    assert database.E.index.names == _expected_row_names(spec["table"], "E", spec["matrix_layouts"])

    for block in _flow_block_names(spec["table"]):
        assert not database["baseline"][block].isna().any().any()


@pytest.mark.parametrize(
    "filename",
    sorted(REALDATA_DATASETS),
    ids=_dataset_case_id,
)
def test_realdata_excel_export_roundtrip_preserves_flow_blocks(filename, tmp_path):
    spec = REALDATA_DATASETS[filename]
    database = _load_realdata_database(filename)

    export_path = tmp_path / f"{_dataset_case_id(filename)}.xlsx"
    database.to_excel(path=str(export_path), flows=True, coefficients=False)

    roundtrip = parse_from_excel(
        path=str(export_path),
        table=spec["table"],
        mode="flows",
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )

    _compare_flow_blocks(database, roundtrip, spec["table"])


@pytest.mark.parametrize(
    "filename",
    sorted(REALDATA_DATASETS),
    ids=_dataset_case_id,
)
def test_realdata_txt_matrix_roundtrip_preserves_flow_blocks(filename, tmp_path):
    spec = REALDATA_DATASETS[filename]
    database = _load_realdata_database(filename)

    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=False)
    roundtrip = parse_from_txt(
        path=str(tmp_path / "flows"),
        table=spec["table"],
        mode="flows",
        sep=",",
        flat=False,
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )

    _compare_flow_blocks(database, roundtrip, spec["table"])


@pytest.mark.parametrize(
    "filename",
    sorted(REALDATA_DATASETS),
    ids=_dataset_case_id,
)
def test_realdata_txt_flat_roundtrip_preserves_flow_blocks(filename, tmp_path):
    spec = REALDATA_DATASETS[filename]
    database = _load_realdata_database(filename)

    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)
    roundtrip = parse_from_txt(
        path=str(tmp_path / "flows"),
        table=spec["table"],
        mode="flows",
        sep=",",
        flat=True,
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )

    _compare_flow_blocks(database, roundtrip, spec["table"])


@pytest.mark.parametrize(
    "filename",
    sorted(REALDATA_DATASETS),
    ids=_dataset_case_id,
)
def test_realdata_parquet_matrix_roundtrip_preserves_flow_blocks(filename, tmp_path):
    pytest.importorskip("pyarrow")

    spec = REALDATA_DATASETS[filename]
    database = _load_realdata_database(filename)

    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=False)
    roundtrip = parse_from_parquet(
        path=str(tmp_path / "flows"),
        table=spec["table"],
        mode="flows",
        flat=False,
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )

    _compare_flow_blocks(database, roundtrip, spec["table"])


@pytest.mark.parametrize(
    "filename",
    sorted(REALDATA_DATASETS),
    ids=_dataset_case_id,
)
def test_realdata_parquet_flat_roundtrip_preserves_flow_blocks(filename, tmp_path):
    pytest.importorskip("pyarrow")

    spec = REALDATA_DATASETS[filename]
    database = _load_realdata_database(filename)

    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=True)
    roundtrip = parse_from_parquet(
        path=str(tmp_path / "flows"),
        table=spec["table"],
        mode="flows",
        flat=True,
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )

    _compare_flow_blocks(database, roundtrip, spec["table"])


AGGREGATION_CASES = [
    (filename, aggregation)
    for filename, spec in REALDATA_DATASETS.items()
    for aggregation in spec["aggregation_files"]
]


@pytest.mark.parametrize(
    ("filename", "aggregation_name"),
    AGGREGATION_CASES,
    ids=lambda value: _dataset_case_id(value) if isinstance(value, str) and value.endswith(".xlsx") else value,
)
def test_realdata_aggregation_preserves_layouts_and_totals(filename, aggregation_name):
    aggregation_path = REALDATA_AGGREGATIONS / aggregation_name
    database = _load_realdata_database(filename)
    aggregated, spec = _aggregate_realdata_database(filename, aggregation_name)

    assert aggregated.V.index.names == database.V.index.names
    assert aggregated.E.index.names == database.E.index.names

    resolved_blocks = ("Z", "Y", "V", "E", "EY", "VY") if spec["table"] == "IOT" else (
        "U",
        "S",
        "V",
        "E",
        "EY",
        "VY",
    )
    for block in resolved_blocks:
        assert getattr(aggregated, block).to_numpy(dtype=float).sum() == pytest.approx(
            getattr(database, block).to_numpy(dtype=float).sum()
        )

    for level, expected_labels in _aggregation_expectations(aggregation_path).items():
        try:
            actual_labels = aggregated.get_index(level)
        except Exception:
            continue
        assert set(actual_labels) == set(expected_labels)


@pytest.mark.parametrize(
    ("filename", "aggregation_name"),
    AGGREGATION_CASES,
    ids=lambda value: _dataset_case_id(value) if isinstance(value, str) and value.endswith(".xlsx") else value,
)
def test_realdata_aggregated_excel_and_txt_roundtrip_preserves_flow_blocks(
    filename,
    aggregation_name,
    tmp_path,
):
    aggregated, spec = _aggregate_realdata_database(filename, aggregation_name)

    excel_path = tmp_path / "aggregated.xlsx"
    aggregated.to_excel(path=str(excel_path), flows=True, coefficients=False)
    excel_roundtrip = parse_from_excel(
        path=str(excel_path),
        table=spec["table"],
        mode="flows",
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )
    _compare_flow_blocks(aggregated, excel_roundtrip, spec["table"])

    txt_matrix_path = tmp_path / "txt_matrix"
    txt_matrix_path.mkdir()
    aggregated.to_txt(
        path=txt_matrix_path,
        flows=True,
        coefficients=False,
        sep=",",
        flat=False,
    )
    txt_matrix_roundtrip = parse_from_txt(
        path=str(txt_matrix_path / "flows"),
        table=spec["table"],
        mode="flows",
        sep=",",
        flat=False,
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )
    _compare_flow_blocks(aggregated, txt_matrix_roundtrip, spec["table"])

    txt_flat_path = tmp_path / "txt_flat"
    txt_flat_path.mkdir()
    aggregated.to_txt(
        path=txt_flat_path,
        flows=True,
        coefficients=False,
        sep=",",
        flat=True,
    )
    txt_flat_roundtrip = parse_from_txt(
        path=str(txt_flat_path / "flows"),
        table=spec["table"],
        mode="flows",
        sep=",",
        flat=True,
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )
    _compare_flow_blocks(aggregated, txt_flat_roundtrip, spec["table"])


@pytest.mark.parametrize(
    ("filename", "aggregation_name"),
    AGGREGATION_CASES,
    ids=lambda value: _dataset_case_id(value) if isinstance(value, str) and value.endswith(".xlsx") else value,
)
def test_realdata_aggregated_parquet_roundtrip_preserves_flow_blocks(
    filename,
    aggregation_name,
    tmp_path,
):
    pytest.importorskip("pyarrow")

    aggregated, spec = _aggregate_realdata_database(filename, aggregation_name)

    parquet_matrix_path = tmp_path / "parquet_matrix"
    parquet_matrix_path.mkdir()
    aggregated.to_parquet(
        path=parquet_matrix_path,
        flows=True,
        coefficients=False,
        flat=False,
    )
    parquet_matrix_roundtrip = parse_from_parquet(
        path=str(parquet_matrix_path / "flows"),
        table=spec["table"],
        mode="flows",
        flat=False,
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )
    _compare_flow_blocks(aggregated, parquet_matrix_roundtrip, spec["table"])

    parquet_flat_path = tmp_path / "parquet_flat"
    parquet_flat_path.mkdir()
    aggregated.to_parquet(
        path=parquet_flat_path,
        flows=True,
        coefficients=False,
        flat=True,
    )
    parquet_flat_roundtrip = parse_from_parquet(
        path=str(parquet_flat_path / "flows"),
        table=spec["table"],
        mode="flows",
        flat=True,
        matrix_layouts=spec["matrix_layouts"],
        calc_all=False,
    )
    _compare_flow_blocks(aggregated, parquet_flat_roundtrip, spec["table"])
