"""Storage abstractions for MARIO 2 blocks."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BlockRepository(ABC):
    """Minimal repository interface used by the new Dataset model."""

    @abstractmethod
    def has(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str):
        raise NotImplementedError

    @abstractmethod
    def put(self, key: str, value) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_keys(self) -> tuple[str, ...]:
        raise NotImplementedError
