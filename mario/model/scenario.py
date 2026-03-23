"""Scenario container for the new MARIO 2 model."""

from __future__ import annotations

from dataclasses import dataclass, field

from mario.model.block import Block


@dataclass
class Scenario:
    name: str
    parent: str | None = None
    blocks: dict[str, Block] = field(default_factory=dict)
    provenance: list[str] = field(default_factory=list)

    def has_local_block(self, name: str) -> bool:
        return name in self.blocks

    def get_local_block(self, name: str) -> Block:
        return self.blocks[name]

    def set_block(self, block: Block) -> None:
        self.blocks[block.name] = block

    def list_local_blocks(self) -> tuple[str, ...]:
        return tuple(sorted(self.blocks))

    def add_provenance(self, note: str) -> None:
        self.provenance.append(note)
