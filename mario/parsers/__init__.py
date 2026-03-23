"""Public parser entry points that return ``Database`` objects."""

from __future__ import annotations

from importlib import import_module


__all__ = [
    "hybrid_sut_exiobase",
    "parse_eora",
    "parse_eurostat_sut",
    "parse_exiobase",
    "parse_exiobase_3",
    "parse_exiobase_sut",
    "parse_exiobase_3_9_4",
    "parse_FIGARO_SUT",
    "parse_from_excel",
    "parse_from_pymrio",
    "parse_from_txt",
    "parse_oecd",
]


def __getattr__(name: str):
    """Lazily expose parser classes and entry points without eager imports."""
    if name in {
        "hybrid_sut_exiobase",
        "parse_eora",
        "parse_eurostat_sut",
        "parse_exiobase",
        "parse_exiobase_3",
        "parse_exiobase_sut",
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
