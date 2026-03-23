import pandas.testing as pdt

from mario.model import Dataset, DatasetMetadata
from mario.model.enums import TableKind
from mario.parsers import ParserRegistry, parse_dataset, parse_dataset_from_excel, register_parser
from mario.test.mario_test import load_test


def test_parse_dataset_from_excel_iot_preserves_blocks_indexes_and_units():
    dataset = parse_dataset(
        "excel",
        path="mario/test/IOT.xlsx",
        table="IOT",
        mode="flows",
        name="IOT dataset",
    )
    database = load_test("IOT")

    assert dataset.table_kind == TableKind.IOT
    assert dataset.metadata.extra["parser"] == "excel"
    assert set(dataset.list_blocks()) == {"E", "EY", "V", "X", "Y", "Z"}
    assert dataset.get_index("s") == tuple(database._indeces["s"]["main"])

    pdt.assert_frame_equal(dataset.get_block("Z"), database.Z)
    pdt.assert_frame_equal(dataset.get_block("Y"), database.Y)
    pdt.assert_frame_equal(dataset.get_units("s"), database.units["Sector"])


def test_parse_dataset_from_excel_sut_promotes_split_native_blocks():
    dataset = parse_dataset_from_excel(
        "mario/test/SUT.xlsx",
        table="SUT",
        mode="flows",
        name="SUT dataset",
    )
    database = load_test("SUT")

    assert dataset.table_kind == TableKind.SUT
    assert not dataset.has_block("Z")
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "Xa", "Xc", "EY"} <= set(dataset.list_blocks())
    assert dataset.get_index("a") == tuple(database._indeces["a"]["main"])

    pdt.assert_frame_equal(dataset.compute("Z"), database.Z)
    pdt.assert_frame_equal(dataset.compute("Y"), database.Y)
    pdt.assert_frame_equal(dataset.compute("V"), database.V)
    pdt.assert_frame_equal(dataset.compute("E"), database.E)
    pdt.assert_frame_equal(dataset.compute("X"), database.X)
    pdt.assert_frame_equal(dataset.get_units("a"), database.units["Activity"])


def test_parser_registry_supports_third_party_registration():
    registry = ParserRegistry()

    @register_parser("dummy", registry=registry)
    def parse_dummy(**kwargs):
        return Dataset(
            metadata=DatasetMetadata(
                table_kind=TableKind.IOT,
                name=kwargs.get("name"),
            )
        )

    dataset = registry.parse("dummy", name="custom")

    assert isinstance(dataset, Dataset)
    assert dataset.metadata.name == "custom"
    assert registry.names() == ("dummy",)
