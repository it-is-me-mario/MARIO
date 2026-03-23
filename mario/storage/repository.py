"""Concrete repository implementations for MARIO 2."""

from __future__ import annotations

from dataclasses import dataclass, field

from mario.storage.base import BlockRepository


@dataclass
class InMemoryBlockRepository(BlockRepository):
    """Simple in-memory repository used by tests and early migration steps."""

    _data: dict[str, object] = field(default_factory=dict)

    def has(self, key: str) -> bool:
        """Return whether an in-memory entry exists."""
        return key in self._data

    def get(self, key: str):
        """Load one in-memory value."""
        return self._data[key]

    def put(self, key: str, value) -> None:
        """Store one value in memory."""
        self._data[key] = value

    def list_keys(self) -> tuple[str, ...]:
        """List stored keys in sorted order."""
        return tuple(sorted(self._data))
