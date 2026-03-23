"""Minimal parser protocol for MARIO 2 datasets."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mario.model import Dataset


class BaseParser(ABC):
    """Base class for parsers that materialize a MARIO 2 Dataset."""

    name: str | None = None

    @abstractmethod
    def parse(self, **kwargs) -> Dataset:
        raise NotImplementedError

    def __call__(self, **kwargs) -> Dataset:
        return self.parse(**kwargs)
