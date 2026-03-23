"""Dataset model for the new MARIO 2 architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

import pandas as pd

from mario.compute.resolver import Resolver
from mario.compute.types import ResolutionContext
from mario.log_exc.logger import log_time
from mario.model.block import Block
from mario.model.enums import TableKind
from mario.model.labels import INDEX_LABELS
from mario.model.metadata import DatasetMetadata
from mario.model.scenario import Scenario
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
class Dataset:
    """Block-oriented data model backing the new MARIO core."""

    metadata: DatasetMetadata
    repository: BlockRepository = field(default_factory=InMemoryBlockRepository)
    scenarios: dict[str, Scenario] = field(default_factory=dict)
    indexes: dict[str, dict[str, tuple[object, ...]]] = field(default_factory=dict)
    units: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize constructor inputs and ensure a baseline scenario exists."""
        self.indexes = _normalize_indexes(self.indexes)
        self.units = _copy_units(self.units)
        if "baseline" not in self.scenarios:
            self.scenarios["baseline"] = Scenario(name="baseline")
        log_time(logger, f"Dataset: initialized for {self.table_kind.value}.", "debug")

    @property
    def table_kind(self) -> TableKind:
        """Return the table kind declared by the dataset metadata."""
        return self.metadata.table_kind

    def list_scenarios(self) -> tuple[str, ...]:
        """List all scenario names currently defined on the dataset."""
        return tuple(self.scenarios)

    def create_scenario(self, name: str, parent: str | None = "baseline") -> Scenario:
        """Create a new scenario with optional parent inheritance."""
        if name in self.scenarios:
            raise ValueError(f"Scenario {name!r} already exists.")

        if parent is not None and parent not in self.scenarios:
            raise KeyError(parent)

        scenario = Scenario(name=name, parent=parent)
        self.scenarios[name] = scenario
        log_time(logger, f"Dataset: scenario {name} created.", "info")
        return scenario

    def _scenario_chain(self, scenario: str) -> list[Scenario]:
        """Return the inheritance chain used to resolve scenario-local blocks."""
        if scenario not in self.scenarios:
            raise KeyError(scenario)

        chain: list[Scenario] = []
        current = self.scenarios[scenario]
        seen: set[str] = set()
        while current is not None:
            if current.name in seen:
                raise RuntimeError(f"Scenario inheritance cycle detected at {current.name!r}.")
            chain.append(current)
            seen.add(current.name)
            current = self.scenarios[current.parent] if current.parent is not None else None
        return chain

    def list_blocks(self, scenario: str = "baseline", include_inherited: bool = True) -> tuple[str, ...]:
        """List block names visible from one scenario."""
        if not include_inherited:
            return self.scenarios[scenario].list_local_blocks()

        names: set[str] = set()
        for item in self._scenario_chain(scenario):
            names.update(item.blocks)
        return tuple(sorted(names))

    def has_block(self, name: str, scenario: str = "baseline") -> bool:
        """Return whether a block is available in a scenario chain."""
        for item in self._scenario_chain(scenario):
            if item.has_local_block(name):
                return True
        return False

    def get_index(self, code: str, level: str = "main") -> tuple[object, ...]:
        """Return one logical index level stored on the dataset."""
        return tuple(self.indexes[code][level])

    def set_index(self, code: str, values, level: str = "main") -> None:
        """Store one logical index level on the dataset."""
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

    def _resolve_block_record(self, name: str, scenario: str = "baseline") -> Block:
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
    ) -> Block:
        """Store a block value and register its metadata in the scenario."""
        if scenario not in self.scenarios:
            self.create_scenario(scenario, parent="baseline" if scenario != "baseline" else None)

        storage_key = _storage_key(scenario, name)
        self.repository.put(storage_key, value)
        block = Block.from_name(
            name=name,
            scenario=scenario,
            storage_key=storage_key,
            table_kind=self.table_kind,
            metadata=metadata,
        )
        self.scenarios[scenario].set_block(block)
        log_time(logger, f"Dataset: block {name} stored in {scenario}.", "debug")
        return block

    def compute(
        self,
        name: str | list[str] | tuple[str, ...],
        scenario: str = "baseline",
        context: ResolutionContext | None = None,
    ):
        """Resolve one or more blocks through the compute resolver."""
        requested = name if isinstance(name, str) else ", ".join(name)
        log_time(logger, f"Dataset: compute {requested} for {scenario}.", "info")
        resolver = Resolver(self, scenario=scenario, context=context)
        if isinstance(name, str):
            return resolver.resolve(name)
        return resolver.resolve_many(list(name))

    def explain(self, name: str, scenario: str = "baseline", context: ResolutionContext | None = None) -> str:
        """Return a dependency explanation for one block."""
        log_time(logger, f"Dataset: explain {name} for {scenario}.", "debug")
        return Resolver(self, scenario=scenario, context=context).explain(name)

    def to_pandas(self, name: str, scenario: str = "baseline"):
        """Return a block as a pandas object."""
        value = self.get_block(name, scenario=scenario)
        if isinstance(value, (pd.DataFrame, pd.Series)):
            return value.copy()
        raise TypeError(f"Block {name!r} is not a pandas object.")

    def to_polars(self, name: str, scenario: str = "baseline"):
        """Convert a pandas-backed block into a Polars dataframe."""
        import polars as pl

        value = self.to_pandas(name, scenario=scenario)
        if isinstance(value, pd.Series):
            value = value.to_frame(name=value.name if value.name is not None else "__value__")
        return pl.from_pandas(value)

    def to_sparse(self, name: str, scenario: str = "baseline"):
        """Convert a numeric block into a SciPy CSR sparse matrix."""
        from scipy import sparse

        value = self.to_pandas(name, scenario=scenario)
        if isinstance(value, pd.Series):
            return sparse.csr_matrix(value.to_numpy().reshape(-1, 1))
        return sparse.csr_matrix(value.to_numpy())

    def validate(self) -> dict[str, object]:
        """Return a lightweight structural validation report."""
        report = {
            "table_kind": self.table_kind.value,
            "indexes": tuple(sorted(self.indexes)),
            "scenarios": {},
            "units": tuple(sorted(self.units)),
        }
        for scenario in self.list_scenarios():
            report["scenarios"][scenario] = {
                "parent": self.scenarios[scenario].parent,
                "blocks": self.list_blocks(scenario),
            }
        return report

    @classmethod
    def from_database(cls, database, repository: BlockRepository | None = None) -> "Dataset":
        """Build a dataset by importing all materialized blocks from a Database."""
        log_time(logger, "Dataset: importing database.", "info")
        metadata = DatasetMetadata.from_database_metadata(database.meta)
        dataset = cls(
            metadata=metadata,
            repository=repository or InMemoryBlockRepository(),
            indexes=_normalize_indexes(getattr(database, "_indeces", {})),
            units=_copy_units(getattr(database, "units", {})),
        )
        dataset.scenarios = {}

        for scenario_name in database.scenarios:
            dataset.scenarios[scenario_name] = Scenario(name=scenario_name)
            for block_name, value in database[scenario_name].items():
                dataset.set_block(block_name, value, scenario=scenario_name)

        if "baseline" not in dataset.scenarios:
            dataset.scenarios["baseline"] = Scenario(name="baseline")

        log_time(logger, "Dataset: database import completed.", "info")
        return dataset
