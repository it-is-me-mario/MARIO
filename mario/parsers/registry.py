"""Simple registry for pluggable MARIO 2 parsers."""

from __future__ import annotations

from collections.abc import Callable

from mario.model import Dataset
from mario.parsers.base import BaseParser

ParserEntry = BaseParser | Callable[..., Dataset]


class ParserRegistry:
    """Registry that lets third-party parsers plug into MARIO without core edits."""

    def __init__(self) -> None:
        """Initialize an empty parser registry."""
        self._parsers: dict[str, ParserEntry] = {}

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize parser names for stable lookup keys."""
        return str(name).strip().lower().replace("-", "_")

    def register(self, name: str, parser: ParserEntry) -> ParserEntry:
        """Register a parser implementation under a normalized name."""
        parse_method = getattr(parser, "parse", None)
        if not callable(parser) and not callable(parse_method):
            raise TypeError("Parser must be callable or expose a callable parse() method.")

        self._parsers[self._normalize_name(name)] = parser
        return parser

    def unregister(self, parser_name: str) -> None:
        """Remove a parser from the registry."""
        del self._parsers[self._normalize_name(parser_name)]

    def get(self, parser_name: str) -> ParserEntry:
        """Return a registered parser by name."""
        key = self._normalize_name(parser_name)
        if key not in self._parsers:
            raise KeyError(
                f"Parser {parser_name!r} is not registered. Available parsers: {self.names()}"
            )
        return self._parsers[key]

    def names(self) -> tuple[str, ...]:
        """List registered parser names."""
        return tuple(sorted(self._parsers))

    def parse(self, parser_name: str, **kwargs) -> Dataset:
        """Resolve a parser and execute it."""
        parser = self.get(parser_name)
        parse_method = getattr(parser, "parse", None)

        if callable(parse_method):
            return parse_method(**kwargs)

        return parser(**kwargs)


DEFAULT_PARSER_REGISTRY = ParserRegistry()


def get_parser_registry() -> ParserRegistry:
    """Return the process-wide default parser registry."""
    return DEFAULT_PARSER_REGISTRY


def register_parser(
    name: str,
    parser: ParserEntry | None = None,
    *,
    registry: ParserRegistry | None = None,
):
    """Register a parser immediately or return a decorator for delayed registration."""
    target = registry or DEFAULT_PARSER_REGISTRY

    if parser is not None:
        return target.register(name, parser)

    def decorator(candidate: ParserEntry) -> ParserEntry:
        target.register(name, candidate)
        return candidate

    return decorator
