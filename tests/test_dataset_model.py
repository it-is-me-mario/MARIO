import pandas.testing as pdt

from mario.model import Dataset, DatasetMetadata
from mario.model.enums import TableKind
from mario.storage import InMemoryBlockRepository, ParquetBlockRepository
from mario.test.mario_test import load_test
from mario.model.conventions import _ENUM


def test_dataset_from_database_preserves_blocks_and_can_compute():
    database = load_test("IOT")
    dataset = Dataset.from_database(database)

    assert dataset.table_kind == TableKind.IOT
    assert dataset.list_scenarios() == ("baseline",)
    assert "Z" in dataset.list_blocks()
    assert not dataset.has_block("w")

    expected = database.copy()
    expected.calc_all([_ENUM.w])
    resolved = dataset.compute("w")

    pdt.assert_frame_equal(resolved, expected.w)
    assert dataset.has_block("w")


def test_dataset_scenario_inheritance_and_override():
    database = load_test("IOT")
    dataset = Dataset.from_database(database, repository=InMemoryBlockRepository())
    dataset.create_scenario("policy", parent="baseline")

    assert dataset.has_block("Z", scenario="policy")
    pdt.assert_frame_equal(dataset.get_block("Z", scenario="policy"), dataset.get_block("Z"))

    new_x = dataset.get_block("X").copy() * 0
    dataset.set_block("X", new_x, scenario="policy")

    pdt.assert_frame_equal(dataset.get_block("X", scenario="policy"), new_x)
    assert not dataset.get_block("X").equals(new_x)


def test_dataset_exports_to_polars_and_sparse():
    database = load_test("IOT")
    dataset = Dataset.from_database(database)

    polars_frame = dataset.to_polars("Z")
    sparse_matrix = dataset.to_sparse("Z")

    assert polars_frame.shape == database.Z.shape
    assert sparse_matrix.shape == database.Z.shape


def test_parquet_repository_roundtrip(tmp_path):
    repository = ParquetBlockRepository(tmp_path / "parquet_repo")
    dataset = Dataset(
        metadata=DatasetMetadata(table_kind=TableKind.IOT, name="roundtrip"),
        repository=repository,
    )

    database = load_test("IOT")
    dataset.set_block("Z", database.Z)
    dataset.set_block("X", database.X)

    pdt.assert_frame_equal(dataset.get_block("Z"), database.Z)
    pdt.assert_frame_equal(dataset.get_block("X"), database.X)
    assert repository.list_keys() == ("baseline/X", "baseline/Z")
