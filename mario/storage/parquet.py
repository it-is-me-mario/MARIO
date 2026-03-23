"""Parquet-backed repository for pandas blocks."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mario.storage.base import BlockRepository


class ParquetBlockRepository(BlockRepository):
    """Persist DataFrame or Series blocks on disk using Parquet files."""

    def __init__(self, root: str | Path) -> None:
        """Initialize a parquet-backed repository rooted on disk."""
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _data_path(self, key: str) -> Path:
        """Map a storage key to its parquet payload path."""
        relative = Path(*key.split("/"))
        return (self.root / relative).with_suffix(".parquet")

    def _meta_path(self, key: str) -> Path:
        """Map a storage key to its JSON metadata sidecar path."""
        relative = Path(*key.split("/"))
        return (self.root / relative).with_suffix(".json")

    def has(self, key: str) -> bool:
        """Return whether a parquet payload exists for the key."""
        return self._data_path(key).exists()

    def get(self, key: str):
        """Load a dataframe or series block from parquet storage."""
        data_path = self._data_path(key)
        meta_path = self._meta_path(key)

        if not data_path.exists():
            raise KeyError(key)

        frame = pd.read_parquet(data_path)
        metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {"kind": "dataframe"}

        if metadata["kind"] == "series":
            series = frame.iloc[:, 0]
            series.name = metadata.get("name")
            return series

        return frame

    def put(self, key: str, value) -> None:
        """Persist a dataframe or series block to parquet storage."""
        data_path = self._data_path(key)
        meta_path = self._meta_path(key)
        data_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(value, pd.Series):
            frame = value.to_frame(name=value.name if value.name is not None else "__value__")
            metadata = {"kind": "series", "name": value.name}
        elif isinstance(value, pd.DataFrame):
            frame = value
            metadata = {"kind": "dataframe"}
        else:
            raise TypeError("ParquetBlockRepository supports only pandas DataFrame or Series values.")

        frame.to_parquet(data_path)
        meta_path.write_text(json.dumps(metadata))

    def list_keys(self) -> tuple[str, ...]:
        """List all stored parquet-backed keys."""
        keys = []
        for path in self.root.rglob("*.parquet"):
            relative = path.relative_to(self.root).with_suffix("")
            keys.append(relative.as_posix())
        return tuple(sorted(keys))
