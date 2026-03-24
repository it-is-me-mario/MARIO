"""Public parser entry points that return ``Database`` objects."""

from __future__ import annotations

from importlib import import_module


__all__ = [
    "BaseParser",
    "ParserRegistry",
    "parse_adb",
    "build_database_from_parser_output",
    "build_database_from_state",
    "build_parser_state",
    "get_parser_registry",
    "hybrid_iot_exiobase",
    "hybrid_sut_exiobase",
    "parse_eora",
    "parse_eurostat",
    "parse_figaro",
    "parse_gloria",
    "parse_exiobase",
    "parse_exiobase_3",
    "parse_exiobase_sut",
    "parse_exiobase_3_9_4",
    "parse_from_excel",
    "parse_from_parquet",
    "parse_from_pymrio",
    "parse_from_txt",
    "parse_oecd",
    "parse_statcan",
    "parse_wiod",
    "register_parser",
    "validate_parse_request",
]


def __getattr__(name: str):
    """Lazily expose parser classes and entry points without eager imports."""
    if name in {
        "BaseParser",
        "ParserRegistry",
        "parse_adb",
        "build_database_from_parser_output",
        "build_database_from_state",
        "build_parser_state",
        "get_parser_registry",
        "hybrid_iot_exiobase",
        "hybrid_sut_exiobase",
        "parse_eora",
        "parse_eurostat",
        "parse_figaro",
        "parse_gloria",
        "parse_exiobase",
        "parse_exiobase_3",
        "parse_exiobase_sut",
        "parse_from_excel",
        "parse_from_parquet",
        "parse_from_pymrio",
        "parse_from_txt",
        "parse_oecd",
        "parse_statcan",
        "parse_wiod",
        "register_parser",
        "validate_parse_request",
    }:
        if name in {
            "BaseParser",
            "ParserRegistry",
            "get_parser_registry",
            "register_parser",
        }:
            module = import_module("mario.parsers.registry" if name != "BaseParser" else "mario.parsers.base")
            return getattr(module, name)

        if name in {
            "build_database_from_parser_output",
            "build_database_from_state",
            "build_parser_state",
            "validate_parse_request",
        }:
            module = import_module("mario.parsers.api")
            return getattr(module, name)

        module = import_module("mario.parsers.entrypoints")
        return getattr(module, name)

    if name in {"parse_exiobase_3_9_4"}:
        module = import_module("mario.parsers.handshake")
        return getattr(module, name)

    raise AttributeError(name)
