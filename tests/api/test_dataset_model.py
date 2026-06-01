import pytest
import pandas.testing as pdt

from mario.internal import ModelState, ModelStateMetadata
from mario.model.enums import TableKind
from mario.storage import InMemoryBlockRepository, ParquetBlockRepository
from mario.test.mario_test import load_test
from mario.model.conventions import _ENUM


def test_model_state_from_database_preserves_blocks_and_can_compute():
    database = load_test("IOT")
    state = ModelState.from_database(database)

    assert state.table_kind == TableKind.IOT
    assert state.list_scenarios() == ("baseline",)
    assert "Z" in state.list_matrices()
    assert not state.has_matrix("w")

    expected = database.copy()
    expected.calc_all([_ENUM.w])
    resolved = state.compute("w")

    pdt.assert_frame_equal(resolved, expected.w)
    assert state.has_matrix("w")


def test_model_state_scenario_inheritance_and_override():
    database = load_test("IOT")
    state = ModelState.from_database(database, repository=InMemoryBlockRepository())
    state.create_scenario("policy", parent="baseline")

    assert state.has_matrix("Z", scenario="policy")
    pdt.assert_frame_equal(state.get_block("Z", scenario="policy"), state.get_block("Z"))

    new_x = state.compute("X").copy() * 0
    state.set_block("X", new_x, scenario="policy")

    pdt.assert_frame_equal(state.get_block("X", scenario="policy"), new_x)
    assert not state.get_block("X").equals(new_x)


def test_model_state_exports_to_sparse():
    database = load_test("IOT")
    state = ModelState.from_database(database)

    pandas_frame = state.get_block_as_pandas("Z")
    sparse_matrix = state.to_sparse("Z")

    pdt.assert_frame_equal(pandas_frame, database.Z)
    assert sparse_matrix.shape == database.Z.shape


def test_model_state_exports_to_polars_when_installed():
    pytest.importorskip("polars")

    database = load_test("IOT")
    state = ModelState.from_database(database)

    polars_frame = state.to_polars("Z")

    assert polars_frame.shape == database.Z.shape


def test_parquet_repository_roundtrip(tmp_path):
    repository = ParquetBlockRepository(tmp_path / "parquet_repo")
    state = ModelState(
        metadata=ModelStateMetadata(table_kind=TableKind.IOT, name="roundtrip"),
        repository=repository,
    )

    database = load_test("IOT")
    state.set_block("Z", database.Z)
    state.set_block("X", database.X)

    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("X"), database.X)
    assert repository.list_keys() == ("baseline/X", "baseline/Z")
