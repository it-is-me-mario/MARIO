"""Dataset-oriented Excel parser built on top of the shared normalizer."""

from __future__ import annotations

from pathlib import Path
import logging

from mario.log_exc.logger import log_time
from mario.model import Dataset
from mario.parsers.base import BaseParser
from mario.parsers.helpers import build_dataset_from_parser_output
from mario.parsers.registry import register_parser
from mario.storage.base import BlockRepository
from mario.parsers.tabular import excel_parser

logger = logging.getLogger(__name__)


class ExcelParser(BaseParser):
    """Dataset parser for generic Excel workbooks following MARIO conventions."""

    name = "excel"

    def parse(
        self,
        path: str,
        table: str,
        mode: str,
        data_sheet: str | int = 0,
        unit_sheet: str | int = "units",
        *,
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        repository: BlockRepository | None = None,
    ) -> Dataset:
        """Parse a generic Excel workbook into a canonical ``Dataset``."""
        log_time(logger, f"Parser: excel reading {table} {mode} from {path}.", "info")
        matrices, indexes, units = excel_parser(path, table, mode, data_sheet, unit_sheet)
        dataset = build_dataset_from_parser_output(
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
        log_time(logger, f"Parser: excel dataset ready for {table}.", "info")
        return dataset


def parse_dataset_from_excel(
    path: str,
    table: str,
    mode: str,
    data_sheet: str | int = 0,
    unit_sheet: str | int = "units",
    **kwargs,
) -> Dataset:
    """Convenience wrapper around ``ExcelParser``."""
    return ExcelParser().parse(
        path=path,
        table=table,
        mode=mode,
        data_sheet=data_sheet,
        unit_sheet=unit_sheet,
        **kwargs,
    )


register_parser("excel", ExcelParser())
