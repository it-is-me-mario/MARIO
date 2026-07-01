"""Metadata attached to the internal block-state model."""

from __future__ import annotations

from dataclasses import dataclass, field

from mario.model.enums import TableKind


@dataclass
class ModelStateMetadata:
    """Serializable metadata attached to an internal ``ModelState``."""

    table_kind: TableKind
    name: str | None = None
    source: str | None = None
    license: str | None = None
    version: str | None = None
    year: int | None = None
    price: str | None = None
    tech_assumption: str | None = None
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
            "license": self.license,
            "version": self.version,
            "year": self.year,
            "price": self.price,
            "tech_assumption": self.tech_assumption,
            "history": list(self.history),
            "extra": dict(self.extra),
        }

    @classmethod
    def from_database_metadata(cls, metadata) -> "ModelStateMetadata":
        """Translate ``Database.meta`` into internal state metadata."""
        return cls(
            table_kind=TableKind.coerce(metadata.table),
            name=getattr(metadata, "name", None),
            source=getattr(metadata, "source", None),
            license=getattr(metadata, "license", None),
            version=getattr(metadata, "version", None),
            year=getattr(metadata, "year", None),
            price=getattr(metadata, "price", None),
            tech_assumption=getattr(metadata, "tech_assumption", None),
            history=list(getattr(metadata, "_history", [])),
        )
