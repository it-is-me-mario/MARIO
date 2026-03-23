"""Storage abstractions for MARIO 2 blocks."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BlockRepository(ABC):
    """Minimal repository interface used by the internal block-state model."""

    @abstractmethod
    def has(self, key: str) -> bool:
        """Return whether a value exists for the given storage key."""
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str):
        """Load one value by storage key."""
        raise NotImplementedError

    @abstractmethod
    def put(self, key: str, value) -> None:
        """Persist one value under the given storage key."""
        raise NotImplementedError

    @abstractmethod
    def list_keys(self) -> tuple[str, ...]:
        """List all stored keys visible through the repository."""
        raise NotImplementedError
