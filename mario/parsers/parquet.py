"""Internal Parquet parser aligned with the generic TXT parser semantics."""

from __future__ import annotations

from pathlib import Path
import logging

import pandas as pd

from mario.internal import ModelState
from mario.log_exc.logger import log_time
from mario.parsers.api import build_parser_state
from mario.parsers.base import BaseParser
from mario.parsers.registry import register_parser
from mario.parsers.tabular import get_index_txt, get_units, rename_index, sort_frames
from mario.parsers.txt import _find_flat_payload, parse_flat_frames
from mario.storage.base import BlockRepository

logger = logging.getLogger(__name__)


_MATRIX_FLOW_FILES = ("Z", "Y", "V", "E", "EY")
_MATRIX_COEFFICIENT_FILES = ("z", "Y", "v", "e", "EY")


def matrix_parquet_parser(path: str, table: str, mode: str):
    """Parse the matrix-per-file parquet layout exported by ``Database.to_parquet``."""
    root = Path(path)
    expected = _MATRIX_COEFFICIENT_FILES if mode == "coefficients" else _MATRIX_FLOW_FILES

    matrices = {}
    for matrix_name in expected:
        target = root / f"{matrix_name}.parquet"
        if not target.exists():
            raise FileNotFoundError(target)
        matrices[matrix_name] = pd.read_parquet(target)

    units_path = root / "units.parquet"
    if not units_path.exists():
        raise FileNotFoundError(units_path)
    units_frame = pd.read_parquet(units_path)

    sort_frames(matrices)
    indeces = get_index_txt(
        Z=matrices["z" if mode == "coefficients" else "Z"],
        V=matrices["v" if mode == "coefficients" else "V"],
        Y=matrices["Y"],
        E=matrices["e" if mode == "coefficients" else "E"],
        table=table,
    )
    units = get_units(units_frame, table, indeces)
    rename_index(matrices)
    return {"baseline": matrices}, indeces, units


def flat_parquet_parser(path: str, table: str, mode: str):
    """Parse the flat parquet layout exported by ``Database.to_parquet(flat=True)``."""
    root = Path(path)
    data_path = _find_flat_payload(root, "data", {".parquet"})
    units_path = _find_flat_payload(root, "units", {".parquet"})
    data = pd.read_parquet(data_path)
    units = pd.read_parquet(units_path)
    return parse_flat_frames(data, units, table, mode)


class ParquetParser(BaseParser):
    """State parser for directory-based parquet database dumps."""

    name = "parquet"

    def parse(
        self,
        path: str,
        table: str,
        mode: str,
        *,
        flat: bool = False,
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        repository: BlockRepository | None = None,
    ) -> ModelState:
        """Parse a folder of parquet files into a canonical ``ModelState``."""
        layout = "flat" if flat else "matrix"
        log_time(
            logger,
            f"Parser: parquet reading {table} {mode} from {path} in {layout} mode.",
            "info",
        )
        parser = flat_parquet_parser if flat else matrix_parquet_parser
        matrices, indexes, units = parser(path, table, mode)
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
        log_time(logger, f"Parser: parquet state ready for {table}.", "info")
        return state


def parse_state_from_parquet(
    path: str,
    table: str,
    mode: str,
    *,
    flat: bool = False,
    **kwargs,
) -> ModelState:
    """Convenience wrapper around ``ParquetParser`` for internal use."""
    return ParquetParser().parse(
        path=path,
        table=table,
        mode=mode,
        flat=flat,
        **kwargs,
    )


register_parser("parquet", ParquetParser())
