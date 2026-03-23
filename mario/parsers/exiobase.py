"""Dataset-oriented wrappers for EXIOBASE parsers."""

from __future__ import annotations

import logging

from mario.log_exc.logger import log_time
from mario.model import Dataset
from mario.parsers.base import BaseParser
from mario.parsers.helpers import build_dataset_from_parser_output
from mario.parsers.registry import register_parser
from mario.storage.base import BlockRepository
from mario.parsers.tabular import monetary_sut_exiobase

logger = logging.getLogger(__name__)

EXIOBASE_SUT_SOURCE = (
    "Exiobase Monetary Multi Regional Supply and Use Table "
    "(https://www.exiobase.eu/)"
)


class ExiobaseSUTParser(BaseParser):
    name = "exiobase_sut"

    def parse(
        self,
        path: str,
        *,
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        repository: BlockRepository | None = None,
    ) -> Dataset:
        log_time(logger, f"Parser: exiobase_sut reading from {path}.", "info")
        matrices, indexes, units = monetary_sut_exiobase(path)
        dataset = build_dataset_from_parser_output(
            table="SUT",
            matrices=matrices,
            indexes=indexes,
            units=units,
            parser_name=self.name,
            mode="flows",
            name=name,
            source=source or EXIOBASE_SUT_SOURCE,
            year=year,
            price=price,
            source_path=path,
            repository=repository,
        )
        log_time(logger, "Parser: exiobase_sut dataset ready.", "info")
        return dataset


def parse_dataset_exiobase_sut(path: str, **kwargs) -> Dataset:
    return ExiobaseSUTParser().parse(path=path, **kwargs)


register_parser("exiobase_sut", ExiobaseSUTParser())
