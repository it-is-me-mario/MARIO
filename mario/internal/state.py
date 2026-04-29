"""Internal block-oriented state model backing the new MARIO core."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

import pandas as pd

from mario.compute.resolver import Resolver
from mario.compute.types import ResolutionContext
from mario.internal.access import block_to_matrix, block_to_pandas, block_to_table
from mario.internal.block import StoredBlock
from mario.internal.metadata import ModelStateMetadata
from mario.internal.scenario import ScenarioState
from mario.log_exc.logger import log_time
from mario.model.enums import TableKind
from mario.model.labels import INDEX_LABELS
from mario.storage.base import BlockRepository
from mario.storage.repository import InMemoryBlockRepository

logger = logging.getLogger(__name__)


def _storage_key(scenario: str, name: str) -> str:
    """Build the repository key used to store one block for one scenario."""
    return f"{scenario}/{name}"


def _normalize_indexes(
    indexes: dict[str, dict[str, object]] | None,
) -> dict[str, dict[str, tuple[object, ...]]]:
    """Normalize mutable index containers into tuple-based structures."""
    normalized: dict[str, dict[str, tuple[object, ...]]] = {}
    if not indexes:
        return normalized

    for code, levels in indexes.items():
        normalized[code] = {}
        for level_name, values in levels.items():
            normalized[code][level_name] = tuple(values)

    return normalized


def _copy_units(units: dict[str, object] | None) -> dict[str, object]:
    """Return a defensive copy of the unit mapping."""
    if not units:
        return {}

    copied: dict[str, object] = {}
    for label, value in units.items():
        copied[label] = value.copy(deep=True) if hasattr(value, "copy") else value

    return copied


@dataclass
class ModelState:
    """Internal block-oriented state model used behind public MARIO APIs."""

    metadata: ModelStateMetadata
    repository: BlockRepository = field(default_factory=InMemoryBlockRepository)
    scenarios: dict[str, ScenarioState] = field(default_factory=dict)
    indexes: dict[str, dict[str, tuple[object, ...]]] = field(default_factory=dict)
    units: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize constructor inputs and ensure a baseline scenario exists."""
        self.indexes = _normalize_indexes(self.indexes)
        self.units = _copy_units(self.units)
        if "baseline" not in self.scenarios:
            self.scenarios["baseline"] = ScenarioState(name="baseline")
        log_time(logger, f"ModelState: initialized for {self.table_kind.value}.", "debug")

    @property
    def table_kind(self) -> TableKind:
        """Return the table kind declared by the state metadata."""
        return self.metadata.table_kind

    def list_scenarios(self) -> tuple[str, ...]:
        """List all scenario names currently defined on the state."""
        return tuple(self.scenarios)

    def create_scenario(self, name: str, parent: str | None = "baseline") -> ScenarioState:
        """Create a new scenario with optional parent inheritance."""
        if name in self.scenarios:
            raise ValueError(f"Scenario {name!r} already exists.")

        if parent is not None and parent not in self.scenarios:
            raise KeyError(parent)

        scenario = ScenarioState(name=name, parent=parent)
        self.scenarios[name] = scenario
        log_time(logger, f"ModelState: scenario {name} created.", "info")
        return scenario

    def _scenario_chain(self, scenario: str) -> list[ScenarioState]:
        """Return the inheritance chain used to resolve scenario-local blocks."""
        if scenario not in self.scenarios:
            raise KeyError(scenario)

        chain: list[ScenarioState] = []
        current = self.scenarios[scenario]
        seen: set[str] = set()
        while current is not None:
            if current.name in seen:
                raise RuntimeError(f"Scenario inheritance cycle detected at {current.name!r}.")
            chain.append(current)
            seen.add(current.name)
            current = self.scenarios[current.parent] if current.parent is not None else None
        return chain

    def list_matrices(self, scenario: str = "baseline", include_inherited: bool = True) -> tuple[str, ...]:
        """List matrix names visible from one scenario."""
        if not include_inherited:
            return self.scenarios[scenario].list_local_blocks()

        names: set[str] = set()
        for item in self._scenario_chain(scenario):
            names.update(item.blocks)
        return tuple(sorted(names))

    def has_matrix(self, name: str, scenario: str = "baseline") -> bool:
        """Return whether a matrix is available in a scenario chain."""
        for item in self._scenario_chain(scenario):
            if item.has_local_block(name):
                return True
        return False

    def has_block(self, name: str, scenario: str = "baseline") -> bool:
        """Backward-compatible alias for :meth:`has_matrix`."""
        return self.has_matrix(name, scenario=scenario)

    def get_index(self, code: str, level: str = "main") -> tuple[object, ...]:
        """Return one logical index level stored on the state."""
        return tuple(self.indexes[code][level])

    def set_index(self, code: str, values, level: str = "main") -> None:
        """Store one logical index level on the state."""
        levels = self.indexes.setdefault(code, {})
        levels[level] = tuple(values)

    def get_units(self, code_or_label: str):
        """Return units for one level code or label."""
        label = INDEX_LABELS.get(code_or_label, code_or_label)
        value = self.units[label]
        return value.copy(deep=True) if hasattr(value, "copy") else value

    def set_units(self, code_or_label: str, value) -> None:
        """Store units for one level code or label."""
        label = INDEX_LABELS.get(code_or_label, code_or_label)
        self.units[label] = value.copy(deep=True) if hasattr(value, "copy") else value

    def _resolve_block_record(self, name: str, scenario: str = "baseline") -> StoredBlock:
        """Return the block metadata record visible from one scenario chain."""
        for item in self._scenario_chain(scenario):
            if item.has_local_block(name):
                return item.get_local_block(name)
        raise KeyError(name)

    def get_block(self, name: str, scenario: str = "baseline"):
        """Load one block value from the backing repository."""
        block = self._resolve_block_record(name, scenario=scenario)
        return self.repository.get(block.storage_key)

    def set_block(
        self,
        name: str,
        value,
        scenario: str = "baseline",
        metadata: dict[str, object] | None = None,
    ) -> StoredBlock:
        """Store a block value and register its metadata in the scenario."""
        if scenario not in self.scenarios:
            self.create_scenario(scenario, parent="baseline" if scenario != "baseline" else None)

        storage_key = _storage_key(scenario, name)
        self.repository.put(storage_key, value)
        block = StoredBlock.from_name(
            name=name,
            scenario=scenario,
            storage_key=storage_key,
            table_kind=self.table_kind,
            metadata=metadata,
        )
        self.scenarios[scenario].set_block(block)
        log_time(logger, f"ModelState: block {name} stored in {scenario}.", "debug")
        return block

    def get_block_as_pandas(self, name: str, scenario: str = "baseline"):
        """Return one block as a pandas object."""
        return block_to_pandas(self.get_block(name, scenario=scenario))

    def get_block_as_table(
        self,
        name: str,
        scenario: str = "baseline",
        *,
        backend: str = "auto",
    ):
        """Return one block in the tabular backend requested by the caller."""
        return block_to_table(self.get_block(name, scenario=scenario), backend=backend)

    def get_block_as_matrix(
        self,
        name: str,
        scenario: str = "baseline",
        *,
        backend: str = "numpy",
        prefer_sparse: bool = False,
    ):
        """Return one block in a matrix backend suitable for compute code."""
        return block_to_matrix(
            self.get_block(name, scenario=scenario),
            backend=backend,
            prefer_sparse=prefer_sparse,
        )

    def compute(
        self,
        name: str | list[str] | tuple[str, ...],
        scenario: str = "baseline",
        context: ResolutionContext | None = None,
    ):
        """Resolve one or more blocks through the compute resolver."""
        requested = name if isinstance(name, str) else ", ".join(name)
        log_time(logger, f"ModelState: compute {requested} for {scenario}.", "info")
        resolver = Resolver(self, scenario=scenario, context=context)
        if isinstance(name, str):
            return resolver.resolve(name)
        return resolver.resolve_many(list(name))

    def explain(self, name: str, scenario: str = "baseline", context: ResolutionContext | None = None) -> str:
        """Return a dependency explanation for one block."""
        log_time(logger, f"ModelState: explain {name} for {scenario}.", "debug")
        return Resolver(self, scenario=scenario, context=context).explain(name)

    def to_pandas(self, name: str, scenario: str = "baseline"):
        """Return a block as a pandas object."""
        return self.get_block_as_pandas(name, scenario=scenario)

    def to_polars(self, name: str, scenario: str = "baseline"):
        """Convert a pandas-backed block into a Polars dataframe."""
        return self.get_block_as_table(name, scenario=scenario, backend="polars")

    def to_sparse(self, name: str, scenario: str = "baseline"):
        """Convert a pandas-backed block into a SciPy sparse matrix."""
        return self.get_block_as_matrix(
            name,
            scenario=scenario,
            backend="scipy",
            prefer_sparse=True,
        )

    def validate(self) -> dict[str, object]:
        """Return a lightweight validation summary of the current state."""
        return {
            "table_kind": self.table_kind.value,
            "scenarios": self.list_scenarios(),
            "indexes": tuple(sorted(self.indexes)),
            "units": tuple(sorted(self.units)),
            "blocks": {scenario: self.list_matrices(scenario) for scenario in self.list_scenarios()},
        }

    @classmethod
    def from_database(cls, database, repository: BlockRepository | None = None) -> "ModelState":
        """Build an internal state object by importing a ``Database``."""
        log_time(logger, "ModelState: importing database.", "info")
        metadata = ModelStateMetadata.from_database_metadata(database.meta)
        state = cls(
            metadata=metadata,
            repository=repository or InMemoryBlockRepository(),
            indexes=database._indeces,
            units=database.units,
        )

        for scenario_name, blocks in database.matrices.items():
            if scenario_name not in state.scenarios:
                state.scenarios[scenario_name] = ScenarioState(name=scenario_name)
            for block_name, value in blocks.items():
                state.set_block(block_name, value, scenario=scenario_name)

        if "baseline" not in state.scenarios:
            state.scenarios["baseline"] = ScenarioState(name="baseline")

        log_time(logger, "ModelState: database import completed.", "info")
        return state
