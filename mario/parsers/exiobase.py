"""Internal state-oriented wrappers for EXIOBASE parsers."""

from __future__ import annotations

import logging

from mario.log_exc.logger import log_time
from mario.internal import ModelState
from mario.parsers.base import BaseParser
from mario.parsers.helpers import build_state_from_parser_output
from mario.parsers.registry import register_parser
from mario.storage.base import BlockRepository
from mario.parsers.exiobase_sut import parse_exiobase_sut_monetary

logger = logging.getLogger(__name__)

EXIOBASE_SUT_SOURCE = (
    "Exiobase Monetary Multi Regional Supply and Use Table "
    "(https://www.exiobase.eu/)"
)


class ExiobaseSUTParser(BaseParser):
    """State parser for the monetary EXIOBASE SUT source format."""

    name = "exiobase_sut"

    def parse(
        self,
        path: str,
        *,
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        add_extensions: str | None = None,
        repository: BlockRepository | None = None,
    ) -> ModelState:
        """Parse a monetary EXIOBASE SUT source into a canonical ``ModelState``."""
        log_time(logger, f"Parser: exiobase_sut reading from {path}.", "info")
        matrices, indexes, units, layout = parse_exiobase_sut_monetary(
            path,
            add_extensions=add_extensions,
        )
        state = build_state_from_parser_output(
            table="SUT",
            matrices=matrices,
            indexes=indexes,
            units=units,
            parser_name=self.name,
            mode="flows",
            name=name or layout.dataset_name,
            source=source or layout.source,
            year=year if year is not None else layout.year,
            price=price or layout.price,
            source_path=path,
            repository=repository,
        )
        log_time(logger, "Parser: exiobase_sut state ready.", "info")
        return state


def parse_state_exiobase_sut(path: str, **kwargs) -> ModelState:
    """Convenience wrapper around ``ExiobaseSUTParser`` for internal use."""
    return ExiobaseSUTParser().parse(path=path, **kwargs)


register_parser("exiobase_sut", ExiobaseSUTParser())
