"""Internal TXT parser built on top of the shared normalizer."""

from __future__ import annotations

from pathlib import Path
import logging

from mario.log_exc.logger import log_time
from mario.internal import ModelState
from mario.parsers.api import build_parser_state
from mario.parsers.base import BaseParser
from mario.parsers.registry import register_parser
from mario.storage.base import BlockRepository
from mario.parsers.tabular import txt_parser

logger = logging.getLogger(__name__)


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
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        repository: BlockRepository | None = None,
    ) -> ModelState:
        """Parse a folder of text files into a canonical ``ModelState``."""
        log_time(logger, f"Parser: txt reading {table} {mode} from {path}.", "info")
        matrices, indexes, units = txt_parser(path, table, mode, sep)
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
    **kwargs,
) -> ModelState:
    """Convenience wrapper around ``TxtParser`` for internal use."""
    return TxtParser().parse(
        path=path,
        table=table,
        mode=mode,
        sep=sep,
        **kwargs,
    )


register_parser("txt", TxtParser())
