"""Internal TXT parser built on top of the shared normalizer."""

from __future__ import annotations

from pathlib import Path
import logging

import pandas as pd

from mario.log_exc.logger import log_time
from mario.internal import ModelState
from mario.parsers.api import build_parser_state
from mario.parsers.base import BaseParser
from mario.parsers.registry import register_parser
from mario.ops.export_specs import FLAT_DATA_COLUMNS, FLAT_UNIT_COLUMNS
from mario.model.conventions import _MASTER_INDEX
from mario.storage.base import BlockRepository
from mario.parsers.tabular import get_index_txt, get_units, rename_index, sort_frames, txt_parser

logger = logging.getLogger(__name__)


_FLAT_FLOW_MATRICES = ("Z", "Y", "V", "E", "EY")
_FLAT_COEFFICIENT_MATRICES = ("z", "Y", "v", "e", "EY")
_FLAT_ROW_SIMPLE = {"V", "v", "E", "e", "EY"}


def _find_flat_payload(path: Path, stem: str, suffixes: set[str]) -> Path:
    """Resolve one flat payload file by stem regardless of file extension."""
    candidates = [
        item
        for item in path.iterdir()
        if item.is_file() and item.stem == stem and item.suffix in suffixes
    ]
    if not candidates:
        expected = ", ".join(sorted(suffixes))
        raise FileNotFoundError(f"No {stem!r} payload found in {path} with suffixes {expected}.")
    if len(candidates) > 1:
        raise ValueError(f"More than one flat payload matches {stem!r}: {candidates}")
    return candidates[0]


def _flat_axis_columns(side: str) -> list[str]:
    """Return the canonical column names for one flat axis."""
    suffix = "from" if side == "from" else "to"
    return [f"Region_{suffix}", f"Level_{suffix}", f"Item_{suffix}"]


def _read_flat_text_frames(path: str, sep: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the flat long-format data and unit tables."""
    root = Path(path)
    data_path = _find_flat_payload(root, "data", {".txt", ".csv"})
    units_path = _find_flat_payload(root, "units", {".txt", ".csv"})

    data = pd.read_csv(data_path, sep=sep, keep_default_na=False)
    units = pd.read_csv(units_path, sep=sep, keep_default_na=False)

    expected_data = list(FLAT_DATA_COLUMNS)
    expected_units = list(FLAT_UNIT_COLUMNS)
    if list(data.columns) != expected_data:
        raise ValueError(f"Flat data file should expose columns {expected_data}, got {list(data.columns)}.")
    if list(units.columns) != expected_units:
        raise ValueError(f"Flat units file should expose columns {expected_units}, got {list(units.columns)}.")
    return data, units


def _reindex_from_ordered_tuples(frame: pd.DataFrame, rows: list[tuple], columns: list[tuple]) -> pd.DataFrame:
    """Reindex one pivoted flat matrix to preserve file order."""
    row_index = pd.MultiIndex.from_tuples(rows, names=_flat_axis_columns("from"))
    column_index = pd.MultiIndex.from_tuples(columns, names=_flat_axis_columns("to"))
    return frame.reindex(index=row_index, columns=column_index)


def _restore_simple_axis(index: pd.MultiIndex, *, axis: str, matrix_name: str):
    """Collapse one flat axis back to a simple item index when appropriate."""
    if matrix_name in _FLAT_ROW_SIMPLE and axis == "from":
        return pd.Index(index.get_level_values(f"Item_from"), name=None)
    return pd.MultiIndex.from_arrays(
        [index.get_level_values(name) for name in _flat_axis_columns(axis)],
        names=[_MASTER_INDEX["r"], "Level", "Item"],
    )


def _flat_matrix_to_frame(data: pd.DataFrame, matrix_name: str) -> pd.DataFrame:
    """Reconstruct one canonical matrix from the flat long format."""
    subset = data.loc[data["Matrix"] == matrix_name].copy()
    if subset.empty:
        raise ValueError(f"Matrix {matrix_name!r} is not present in the flat payload.")

    subset["Value"] = pd.to_numeric(subset["Value"], errors="raise")
    row_columns = _flat_axis_columns("from")
    column_columns = _flat_axis_columns("to")
    row_order = list(dict.fromkeys(tuple(row) for row in subset[row_columns].itertuples(index=False, name=None)))
    column_order = list(dict.fromkeys(tuple(row) for row in subset[column_columns].itertuples(index=False, name=None)))

    frame = subset.pivot(index=row_columns, columns=column_columns, values="Value")
    frame = _reindex_from_ordered_tuples(frame, row_order, column_order)
    frame.index = _restore_simple_axis(frame.index, axis="from", matrix_name=matrix_name)
    frame.columns = _restore_simple_axis(frame.columns, axis="to", matrix_name=matrix_name)
    return frame


def _flat_units_to_legacy(units: pd.DataFrame) -> pd.DataFrame:
    """Convert the flat unit table back to the historical multi-index layout."""
    values = units.copy()
    values.columns = ["level", "item", "unit"]
    values.set_index(["level", "item"], inplace=True)
    return values


def parse_flat_frames(data: pd.DataFrame, unit_table: pd.DataFrame, table: str, mode: str):
    """Parse canonical flat frames into MARIO matrices, indexes and units."""
    expected_matrices = (
        _FLAT_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_FLOW_MATRICES
    )

    matrices = {
        matrix_name: _flat_matrix_to_frame(data, matrix_name)
        for matrix_name in expected_matrices
        if matrix_name in set(data["Matrix"])
    }
    if set(expected_matrices) - set(matrices):
        missing = sorted(set(expected_matrices) - set(matrices))
        raise ValueError(f"Flat payload is missing required matrices: {missing}")

    sort_frames(matrices)
    indeces = get_index_txt(
        Z=matrices["z" if mode == "coefficients" else "Z"],
        V=matrices["v" if mode == "coefficients" else "V"],
        Y=matrices["Y"],
        E=matrices["e" if mode == "coefficients" else "E"],
        table=table,
    )
    units = get_units(_flat_units_to_legacy(unit_table), table, indeces)
    rename_index(matrices)
    return {"baseline": matrices}, indeces, units


def flat_txt_parser(path: str, table: str, mode: str, sep: str):
    """Parse the canonical flat long-format txt/csv export."""
    log_time(logger, f"Parser: reading {mode} from flat txt files.", "info")
    data, unit_table = _read_flat_text_frames(path, sep)
    return parse_flat_frames(data, unit_table, table, mode)


class TxtParser(BaseParser):
    """State parser for generic directory-based TXT or CSV database dumps."""

    name = "txt"

    def parse(
        self,
        path: str,
        table: str,
        mode: str,
        *,
        sep: str = ",",
        flat: bool = False,
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        repository: BlockRepository | None = None,
    ) -> ModelState:
        """Parse a folder of text files into a canonical ``ModelState``."""
        layout = "flat" if flat else "matrix"
        log_time(logger, f"Parser: txt reading {table} {mode} from {path} in {layout} mode.", "info")
        parser = flat_txt_parser if flat else txt_parser
        matrices, indexes, units = parser(path, table, mode, sep)
        state = build_parser_state(
            table=table,
            matrices=matrices,
            indexes=indexes,
            units=units,
            parser_name=self.name,
            mode=mode,
            name=name,
            source=source or str(Path(path)),
            year=year,
            price=price,
            source_path=path,
            repository=repository,
        )
        log_time(logger, f"Parser: txt state ready for {table}.", "info")
        return state


def parse_state_from_txt(
    path: str,
    table: str,
    mode: str,
    *,
    sep: str = ",",
    flat: bool = False,
    **kwargs,
) -> ModelState:
    """Convenience wrapper around ``TxtParser`` for internal use."""
    return TxtParser().parse(
        path=path,
        table=table,
        mode=mode,
        sep=sep,
        flat=flat,
        **kwargs,
    )


register_parser("txt", TxtParser())
