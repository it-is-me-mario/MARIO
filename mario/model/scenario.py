"""Scenario container for the new MARIO 2 model."""

from __future__ import annotations

from dataclasses import dataclass, field

from mario.model.block import Block


@dataclass
class Scenario:
    """Container for the blocks owned locally by one scenario."""

    name: str
    parent: str | None = None
    blocks: dict[str, Block] = field(default_factory=dict)
    provenance: list[str] = field(default_factory=list)

    def has_local_block(self, name: str) -> bool:
        """Return whether the scenario owns a block directly."""
        return name in self.blocks

    def get_local_block(self, name: str) -> Block:
        """Return one locally owned block record."""
        return self.blocks[name]

    def set_block(self, block: Block) -> None:
        """Register or replace one local block record."""
        self.blocks[block.name] = block

    def list_local_blocks(self) -> tuple[str, ...]:
        """List block names stored directly on the scenario."""
        return tuple(sorted(self.blocks))

    def add_provenance(self, note: str) -> None:
        """Append a provenance note for scenario-level changes."""
        self.provenance.append(note)
