"""Lightweight semantic specs for blocks and axes.

This module intentionally stays small. The goal is not to replace the current
catalog overnight, but to let parsers and custom operators declare richer axis
layouts when the classic fixed MARIO shapes are not enough.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxisRef:
    """Describe one logical axis used by a block specification.

    ``id`` is the local semantic name used inside a block specification
    (for example ``sector_output`` or ``sector_descriptor``), while ``base``
    links that axis back to a familiar MARIO family such as ``s`` or ``r``.
    """

    id: str
    base: str

    @classmethod
    def coerce(cls, value: "AxisRef | str | tuple[str, str]") -> "AxisRef":
        """Normalize a shorthand axis declaration to an ``AxisRef``."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(id=value, base=value)
        if isinstance(value, tuple) and len(value) == 2:
            return cls(id=str(value[0]), base=str(value[1]))
        raise TypeError("Axis declarations must be AxisRef, string, or (id, base) tuples.")


def axis_ref(id: str, base: str) -> AxisRef:
    """Build one semantic axis reference."""
    return AxisRef(id=id, base=base)


def _normalize_axes(values) -> tuple[AxisRef, ...]:
    """Normalize a sequence of axis declarations."""
    return tuple(AxisRef.coerce(value) for value in values)


@dataclass(frozen=True)
class BlockSpec:
    """Describe the semantic row/column layout of one block."""

    name: str
    row_axes: tuple[AxisRef, ...]
    col_axes: tuple[AxisRef, ...]


def block_spec(
    name: str,
    *,
    row_axes,
    col_axes,
) -> BlockSpec:
    """Build one semantic block specification."""
    return BlockSpec(
        name=name,
        row_axes=_normalize_axes(row_axes),
        col_axes=_normalize_axes(col_axes),
    )
