import pandas as pd
import pandas.testing as pdt
import pytest

from mario.internal import ModelState, ModelStateMetadata
from mario.model.enums import TableKind
from mario.ops.export_specs import FLAT_DATA_COLUMNS, FLAT_UNIT_COLUMNS
from mario.parsers.api import build_database_from_state
from mario.parsers.excel import parse_state_from_excel
from mario.parsers.txt import parse_state_from_txt
from mario.parsers.registry import ParserRegistry, get_parser_registry, register_parser
from mario.parsers.entrypoints import parse_from_excel, parse_from_txt
from mario.test.mario_test import load_test


def test_parse_state_from_excel_iot_preserves_blocks_indexes_and_units():
    state = get_parser_registry().parse(
        "excel",
        path="mario/test/IOT.xlsx",
        table="IOT",
        mode="flows",
        name="IOT dataset",
    )
    database = load_test("IOT")

    assert state.table_kind == TableKind.IOT
    assert state.metadata.extra["parser"] == "excel"
    assert set(state.list_blocks()) == {"E", "EY", "V", "Y", "Z"}
    assert not state.has_block("X")
    assert state.get_index("s") == tuple(database._indeces["s"]["main"])

    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)
    pdt.assert_frame_equal(state.get_units("s"), database.units["Sector"])


def test_parse_from_excel_sut_returns_split_native_baseline_blocks():
    database = parse_from_excel(
        path="mario/test/SUT.xlsx",
        table="SUT",
        mode="flows",
        name="SUT dataset",
    )

    assert not database.is_hybrid
    assert "Z" not in database["baseline"]
    assert "X" not in database["baseline"]
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"} <= set(database["baseline"])


def test_parser_authoring_api_builds_database_from_state():
    state = parse_state_from_excel(
        "mario/test/IOT.xlsx",
        table="IOT",
        mode="flows",
        name="IOT dataset",
    )
    database = build_database_from_state(state, calc_all=False)

    assert database.table_type == "IOT"
    assert set(database["baseline"]) == {"E", "EY", "V", "Y", "Z"}
    pdt.assert_frame_equal(database.Z, state.get_block("Z"))


def test_parse_state_from_excel_sut_promotes_split_native_blocks():
    state = parse_state_from_excel(
        "mario/test/SUT.xlsx",
        table="SUT",
        mode="flows",
        name="SUT dataset",
    )
    database = load_test("SUT")

    assert state.table_kind == TableKind.SUT
    assert not state.has_block("Z")
    assert not state.has_block("X")
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"} <= set(state.list_blocks())
    assert "Xa" not in state.list_blocks()
    assert "Xc" not in state.list_blocks()
    assert state.get_index("a") == tuple(database._indeces["a"]["main"])

    pdt.assert_frame_equal(state.compute("Z"), database.Z)
    pdt.assert_frame_equal(state.compute("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("V"), database.V)
    pdt.assert_frame_equal(state.compute("E"), database.E)
    pdt.assert_frame_equal(state.compute("Xa"), database.Xa)
    pdt.assert_frame_equal(state.compute("Xc"), database.Xc)
    pdt.assert_frame_equal(state.compute("X"), database.X)
    pdt.assert_frame_equal(state.get_units("a"), database.units["Activity"])


def test_parse_state_from_txt_iot_roundtrip_preserves_blocks(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",")

    state = parse_state_from_txt(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT txt dataset",
        sep=",",
    )

    assert state.table_kind == TableKind.IOT
    assert set(state.list_blocks()) == {"E", "EY", "V", "Y", "Z"}
    assert not state.has_block("X")
    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)


def test_parse_from_txt_sut_roundtrip_returns_split_native_blocks(tmp_path):
    database = load_test("SUT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",")

    parsed = parse_from_txt(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        sep=",",
        name="SUT txt dataset",
    )

    assert "Z" not in parsed["baseline"]
    assert "X" not in parsed["baseline"]
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"} <= set(parsed["baseline"])
    pdt.assert_frame_equal(parsed.Z, database.Z)
    pdt.assert_frame_equal(parsed.Y, database.Y)
    pdt.assert_frame_equal(parsed.V, database.V)
    pdt.assert_frame_equal(parsed.E, database.E)


def test_to_txt_flat_exports_canonical_schema(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)

    data = pd.read_csv(tmp_path / "flows" / "data.txt", sep=",", keep_default_na=False)
    units = pd.read_csv(tmp_path / "flows" / "units.txt", sep=",", keep_default_na=False)

    assert list(data.columns) == list(FLAT_DATA_COLUMNS)
    assert list(units.columns) == list(FLAT_UNIT_COLUMNS)
    assert set(data["Matrix"]) == {"Z", "Y", "V", "E", "EY"}
    assert set(data["Scenario"]) == {"baseline"}


def test_parse_state_from_txt_iot_flat_roundtrip_preserves_blocks(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)

    state = parse_state_from_txt(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT flat txt dataset",
        sep=",",
        flat=True,
    )

    assert state.table_kind == TableKind.IOT
    assert set(state.list_blocks()) == {"E", "EY", "V", "Y", "Z"}
    assert not state.has_block("X")
    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)


def test_parse_from_txt_sut_flat_roundtrip_uses_unified_export_and_split_parse(tmp_path):
    database = load_test("SUT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)

    data = pd.read_csv(tmp_path / "flows" / "data.txt", sep=",", keep_default_na=False)
    parsed = parse_from_txt(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        sep=",",
        name="SUT flat txt dataset",
        flat=True,
    )

    assert "Z" in set(data["Matrix"])
    assert "U" not in set(data["Matrix"])
    assert "S" not in set(data["Matrix"])
    assert "Z" not in parsed["baseline"]
    assert "X" not in parsed["baseline"]
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"} <= set(parsed["baseline"])
    pdt.assert_frame_equal(parsed.Z, database.Z)
    pdt.assert_frame_equal(parsed.Y, database.Y)
    pdt.assert_frame_equal(parsed.V, database.V)
    pdt.assert_frame_equal(parsed.E, database.E)


def test_to_parquet_flat_exports_canonical_schema(tmp_path):
    pytest.importorskip("pyarrow")

    database = load_test("IOT")
    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=True)

    data = pd.read_parquet(tmp_path / "flows" / "data.parquet")
    units = pd.read_parquet(tmp_path / "flows" / "units.parquet")

    assert list(data.columns) == list(FLAT_DATA_COLUMNS)
    assert list(units.columns) == list(FLAT_UNIT_COLUMNS)
    assert set(data["Matrix"]) == {"Z", "Y", "V", "E", "EY"}


def test_parser_registry_supports_third_party_registration():
    registry = ParserRegistry()

    @register_parser("dummy", registry=registry)
    def parse_dummy(**kwargs):
        return ModelState(
            metadata=ModelStateMetadata(
                table_kind=TableKind.IOT,
                name=kwargs.get("name"),
            )
        )

    state = registry.parse("dummy", name="custom")

    assert isinstance(state, ModelState)
    assert state.metadata.name == "custom"
    assert registry.names() == ("dummy",)
