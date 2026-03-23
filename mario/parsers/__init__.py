"""Pluggable parser layer for the MARIO 2 Dataset model."""

from __future__ import annotations

from importlib import import_module


def parse_dataset(parser: str, **kwargs):
    """Parse a ``Dataset`` through the named parser registered in the default registry."""
    from mario.parsers.registry import get_parser_registry

    return get_parser_registry().parse(parser, **kwargs)


__all__ = [
    "BaseParser",
    "build_dataset_from_parser_output",
    "ExcelParser",
    "ExiobaseSUTParser",
    "ParserRegistry",
    "get_parser_registry",
    "hybrid_sut_exiobase",
    "parse_eora",
    "parse_eurostat_sut",
    "parse_exiobase",
    "parse_exiobase_3",
    "parse_exiobase_3_9_4",
    "parse_FIGARO_SUT",
    "parse_dataset",
    "parse_dataset_exiobase_sut",
    "parse_dataset_from_excel",
    "parse_from_excel",
    "parse_from_pymrio",
    "parse_from_txt",
    "parse_oecd",
    "register_parser",
]


def __getattr__(name: str):
    """Lazily expose parser classes and entry points without eager imports."""
    if name == "BaseParser":
        module = import_module("mario.parsers.base")
        return getattr(module, name)

    if name in {"ExcelParser", "parse_dataset_from_excel"}:
        module = import_module("mario.parsers.excel")
        return getattr(module, name)

    if name in {"ExiobaseSUTParser", "parse_dataset_exiobase_sut"}:
        module = import_module("mario.parsers.exiobase")
        return getattr(module, name)

    if name == "build_dataset_from_parser_output":
        module = import_module("mario.parsers.helpers")
        return getattr(module, name)

    if name in {"ParserRegistry", "get_parser_registry", "register_parser"}:
        module = import_module("mario.parsers.registry")
        return getattr(module, name)

    if name in {
        "hybrid_sut_exiobase",
        "parse_eora",
        "parse_eurostat_sut",
        "parse_exiobase",
        "parse_exiobase_3",
        "parse_FIGARO_SUT",
        "parse_from_excel",
        "parse_from_pymrio",
        "parse_from_txt",
    }:
        module = import_module("mario.parsers.entrypoints")
        return getattr(module, name)

    if name in {"parse_exiobase_3_9_4", "parse_oecd"}:
        module = import_module("mario.parsers.handshake")
        return getattr(module, name)

    raise AttributeError(name)
