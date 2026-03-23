"""Dataset metadata for the new MARIO 2 model."""

from __future__ import annotations

from dataclasses import dataclass, field

from mario.model.enums import TableKind


@dataclass
class DatasetMetadata:
    """Serializable metadata attached to a ``Dataset``."""

    table_kind: TableKind
    name: str | None = None
    source: str | None = None
    year: int | None = None
    price: str | None = None
    history: list[str] = field(default_factory=list)
    extra: dict[str, object] = field(default_factory=dict)

    def add_history(self, note: str) -> None:
        """Append one provenance or transformation note."""
        self.history.append(note)

    def to_dict(self) -> dict[str, object]:
        """Serialize metadata into a plain dictionary."""
        return {
            "table_kind": self.table_kind.value,
            "name": self.name,
            "source": self.source,
            "year": self.year,
            "price": self.price,
            "history": list(self.history),
            "extra": dict(self.extra),
        }

    @classmethod
    def from_database_metadata(cls, metadata) -> "DatasetMetadata":
        """Translate ``Database.meta`` into dataset metadata."""
        return cls(
            table_kind=TableKind.coerce(metadata.table),
            name=getattr(metadata, "name", None),
            source=getattr(metadata, "source", None),
            year=getattr(metadata, "year", None),
            price=getattr(metadata, "price", None),
            history=list(getattr(metadata, "_history", [])),
        )
