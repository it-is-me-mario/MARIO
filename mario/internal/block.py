"""Stored block metadata used by the internal state model."""

from __future__ import annotations

from dataclasses import dataclass, field

from mario.compute.catalog import get_matrix_spec
from mario.compute.types import AxisSpec
from mario.model.enums import BlockRole, TableKind


def _infer_role(name: str) -> BlockRole | None:
    """Infer a coarse semantic role for a block name."""
    if name in {"w", "g", "b"}:
        return BlockRole.OPERATOR
    if name in {"X", "M", "F", "p"}:
        return BlockRole.RESULT
    if name[:1].isupper():
        return BlockRole.FLOW
    if name[:1].islower():
        return BlockRole.COEFFICIENT
    return None


@dataclass(frozen=True)
class StoredBlock:
    """Immutable metadata record describing one stored internal block."""

    name: str
    scenario: str
    storage_key: str
    table_kind: TableKind
    axes: AxisSpec | None = None
    role: BlockRole | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_name(
        cls,
        *,
        name: str,
        scenario: str,
        storage_key: str,
        table_kind: TableKind,
        metadata: dict[str, object] | None = None,
    ) -> "StoredBlock":
        """Build a stored-block record from context and a block name."""
        axes = None
        try:
            axes = get_matrix_spec(table_kind, name).axes
        except KeyError:
            pass

        return cls(
            name=name,
            scenario=scenario,
            storage_key=storage_key,
            table_kind=table_kind,
            axes=axes,
            role=_infer_role(name),
            metadata={} if metadata is None else metadata,
        )
