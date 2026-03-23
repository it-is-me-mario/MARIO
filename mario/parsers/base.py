"""Minimal parser protocol for internal MARIO state objects."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mario.internal import ModelState


class BaseParser(ABC):
    """Base class for parsers that materialize internal ``ModelState`` objects."""

    name: str | None = None

    @abstractmethod
    def parse(self, **kwargs) -> ModelState:
        """Parse the input payload into a ``ModelState`` instance."""
        raise NotImplementedError

    def __call__(self, **kwargs) -> ModelState:
        """Delegate call syntax to ``parse`` for registry convenience."""
        return self.parse(**kwargs)
