"""Enums shared by the new MARIO 2 core."""

from __future__ import annotations

from enum import Enum


class TableKind(str, Enum):
    """Supported table kinds."""

    IOT = "IOT"
    SUT = "SUT"

    @classmethod
    def coerce(cls, value: "TableKind | str") -> "TableKind":
        if isinstance(value, cls):
            return value

        normalized = str(value).upper()
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Unsupported table kind: {value!r}") from exc


class BlockRole(str, Enum):
    """High-level semantic role for a block."""

    FLOW = "flow"
    COEFFICIENT = "coefficient"
    OPERATOR = "operator"
    RESULT = "result"
    VIEW = "view"
