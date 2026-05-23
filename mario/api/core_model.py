# -*- coding: utf-8 -*-
"""Core model primitives used by the public ``Database`` API."""
from mario.log_exc.exceptions import (
    DataMissing,
    LackOfInput,
    WrongInput,
    NotImplementable,
)
from mario.log_exc.logger import log_time
from mario.api.metadata import MARIOMetaData
from mario.internal.access import block_to_matrix, block_to_pandas, block_to_table
from mario.model.assumptions import resolve_tech_assumption
from mario.parsers.tabular import dataframe_parser
from mario.settings.settings import IndexAliases, Nomenclature
from mario.model.conventions import TABLE_LEVELS
from tabulate import tabulate
from collections import namedtuple
from collections.abc import MutableMapping

import numpy as np
import pandas as pd
import logging
import os
import copy
import re

# constants
from mario.model.conventions import (
    _MASTER_INDEX,
    _ENUM,
)

logger = logging.getLogger(__name__)

try:
    import cvxpy as cp

    __cvxpy__ = True
except ModuleNotFoundError:
    __cvxpy__ = False


def _prune_eager_parser_blocks(matrices: dict[str, object]) -> dict[str, object]:
    """Drop blocks that should remain demand-driven after parsing."""
    matrices.pop(_ENUM.X, None)
    return matrices


def _resolver_module():
    """Import the resolver lazily to avoid circular imports at module load time."""
    from mario.compute import resolver as resolver_module

    return resolver_module


def _normalize_requested_matrices(matrices) -> list[str]:
    """Normalize one or many matrix names to a plain list."""
    if isinstance(matrices, str):
        return [matrices]
    return list(matrices)


def _matrix_nomenclature() -> Nomenclature:
    """Return the current matrix nomenclature from live settings."""
    return Nomenclature()


def _resolve_canonical_matrix_name(name: str) -> str:
    """Resolve one public or canonical matrix token to its canonical name."""
    token = str(name)
    nomenclature = _matrix_nomenclature()
    if token in nomenclature.setting:
        return token

    try:
        return nomenclature.reverse(token)
    except KeyError:
        return token


def _resolve_storage_matrix_name(name: str) -> str:
    """Resolve one matrix token to the stored public name used by datasets."""
    canonical = _resolve_canonical_matrix_name(name)
    nomenclature = _matrix_nomenclature()
    if canonical in nomenclature.setting:
        return nomenclature[canonical]
    return str(name)


def _normalize_parsed_matrix_name(name: str) -> str:
    """Map parser block names through MARIO nomenclature when available."""
    try:
        return _matrix_nomenclature()[name]
    except Exception:
        return name


def _main_index_count(indeces: dict[str, dict[str, list[object]]], code: str) -> int | None:
    """Return the size of one main database index when available."""
    levels = indeces.get(code)
    if not levels:
        return None
    values = levels.get("main")
    if values is None:
        return None
    return len(values)


def available_matrices(table_type: str) -> tuple[str, ...]:
    """Return the built-in matrix names accepted for one table type.

    Parameters
    ----------
    table_type:
        Table kind understood by MARIO, typically ``"IOT"`` or ``"SUT"``.

    Returns
    -------
    tuple[str, ...]
        Matrix and block names exposed by the built-in compute catalog for the
        requested table type.
    """
    from mario.compute.catalog import available_matrix_names

    return available_matrix_names(table_type)


class _ResolvedSetDict(MutableMapping):
    """Dict-like wrapper that resolves MARIO set aliases on access."""

    def __init__(self, data: dict, resolver):
        self._data = data
        self._resolver = resolver

    def _canonical_key(self, key, *, allow_passthrough: bool = False):
        if key in self._data:
            return key

        resolved = self._resolver(key)
        if resolved is not None and resolved in self._data:
            return resolved

        if allow_passthrough:
            return key

        raise KeyError(key)

    def __getitem__(self, key):
        return self._data[self._canonical_key(key)]

    def __setitem__(self, key, value):
        self._data[self._canonical_key(key, allow_passthrough=True)] = value

    def __delitem__(self, key):
        del self._data[self._canonical_key(key)]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        try:
            self._canonical_key(key)
        except KeyError:
            return False
        return True

    def __repr__(self):
        return repr(self._data)

    def __deepcopy__(self, memo):
        return copy.deepcopy(self._data, memo)


class CoreModel:
    """Base class for MARIO database objects."""

    def __init__(
        self,
        name=None,
        table=None,
        Z=None,
        E=None,
        V=None,
        Y=None,
        EY=None,
        VY=None,
        units=None,
        price=None,
        source=None,
        tech_assumption: str | None = None,
        calc_all=True,
        year=None,
        **kwargs,
    ):
        """Initialize the core data container behind ``Database``.

        Parameters
        ----------
        name:
            Human-readable database name stored in metadata.
        table:
            Table kind, usually ``"IOT"`` or ``"SUT"``.
        Z, E, V, Y, EY, VY:
            Baseline matrices used when constructing an instance directly from
            pandas objects. ``VY`` is optional.
        units:
            Units mapping matching the table structure.
        price:
            Price system label stored in metadata.
        source:
            Source label stored in metadata.
        tech_assumption:
            Optional technology assumption for SUT databases. Accepted values
            are ``"industry-based"``, ``"product-based"``, ``"IT"`` and
            ``"PT"``. IOT databases do not accept this argument.
        calc_all:
            When ``True``, compute the standard dependent matrices right after
            initialization.
        year:
            Optional reference year stored in metadata.
        **kwargs:
            Additional initialization options. Parsers pass
            ``init_by_parsers=...`` to build the instance from parsed matrices
            without re-running dataframe parsing.
        """
        self._dir = ""
        self._custom_operator_registry = None
        self._custom_block_specs = {}
        # A dictionary for storing info if it is given.
        self.info = {}

        # Initializing backup
        self._backup_ = namedtuple("backup", ["matrices", "indeces", "units"])

        # Initializing metadata
        self.meta = MARIOMetaData(name=name)

        if "init_by_parsers" in kwargs:
            matrices = kwargs["init_by_parsers"]["matrices"]["baseline"]
            renamed_matrices = {}

            for m, v in matrices.items():
                renamed_matrices[_normalize_parsed_matrix_name(m)] = v

            renamed_matrices = _prune_eager_parser_blocks(renamed_matrices)
            kwargs["init_by_parsers"]["matrices"]["baseline"] = renamed_matrices

            for item in ["matrices", "units", "_indeces"]:
                setattr(self, item, kwargs["init_by_parsers"][item])

            nan_keys = [key for key, df in renamed_matrices.items() if isinstance(df, pd.DataFrame) and df.isna().any().any()]
            if nan_keys:
                raise ValueError(f"NaN values found in the following matrices: {nan_keys}")

            log_time(logger, "Metadata: initialized.")

        else:
            if not all(
                [matrix is not None for matrix in [Y, E, Z, V, EY, units, table]]
            ):
                raise LackOfInput(
                    "For building an instance using dataframes, all the data [Y,E,Z,V,EY,units,table] should be given. VY is optional."
                )
            else:
                if isinstance(units, _ResolvedSetDict):
                    units = copy.deepcopy(units._data)
                self.matrices, self._indeces, self.units = dataframe_parser(
                    Z, Y, E, V, EY, units, table, VY=VY
                )

                matrices = self.matrices["baseline"]
                renamed_matrices = {}

                for m, v in matrices.items():
                    renamed_matrices[_normalize_parsed_matrix_name(m)] = v

                renamed_matrices = _prune_eager_parser_blocks(renamed_matrices)
                self.matrices["baseline"] = renamed_matrices

                log_time(logger, "Metadata: initialized by dataframes.")

        resolved_tech_assumption, tech_note = self._resolve_structural_tech_assumption(
            table=table,
            tech_assumption=tech_assumption,
        )
        self.meta._add_attribute(
            table=table,
            price=price,
            source=source,
            year=year,
            tech_assumption=resolved_tech_assumption,
        )
        if tech_note is not None:
            log_time(logger, f"Metadata: {tech_note}", "warning")
            self.meta._add_history(tech_note)

        # Adding notes if passed by user or the parsers
        if kwargs.get("notes"):
            for note in kwargs["notes"]:
                self.meta._add_history(note)

        if calc_all:
            self.calc_all()

    def calc_all(
        self,
        matrices=[_ENUM.z, _ENUM.v, _ENUM.e, _ENUM.Z, _ENUM.V, _ENUM.E],
        scenario="baseline",
        force_rewrite=False,
        compute_method: str | None = None,
        linear_solver: str | None = None,
        linear_strategy: str | None = None,
        **kwargs,
    ):
        """Compute and materialize one or more matrices for a scenario.

        Parameters
        ----------
        matrices:
            One matrix name or an iterable of matrix names to materialize.
        scenario:
            Scenario from which dependencies should be read and where the
            computed matrices should be stored.
        force_rewrite:
            When ``True``, recompute requested matrices even if they already
            exist in the scenario.
        compute_method:
            Optional per-call override for demand-driven calculations.
            Accepted values are ``"auto"``, ``"inverse"`` and ``"solve"``.
            When omitted, MARIO uses the globally configured default from
            :func:`mario.set_compute_method`.
        linear_solver:
            Optional per-call override for solve-based formulas. When
            omitted, MARIO uses the globally configured default from
            :func:`mario.set_linear_solver`.
        linear_strategy:
            Optional per-call override for the sparse solve strategy used under
            ``compute_method="solve"``. Accepted values are ``"auto"``,
            ``"direct"`` and ``"iterative"``. When omitted, MARIO uses the
            globally configured default from :func:`mario.set_linear_strategy`.
        **kwargs:
            Reserved for backward compatibility with historical callers.

        Returns
        -------
        None
            The method materializes matrices in ``self.matrices``.

        Notes
        -----
        The runtime options above matter mainly for large IOT databases, where
        MARIO can compute the ``X`` total production vector, ``f`` total
        (direct+indirect) environmental transaction coefficients matrix, ``F``
        total (direct+indirect) environmental transaction flows matrix, ``m``
        total (direct+indirect) value added coefficients matrix, ``M`` total
        (direct+indirect) value added transaction matrix and ``p`` price index
        vector without materializing the full ``w`` Leontief inverse matrix.
        """
        requested = [
            _resolve_canonical_matrix_name(name)
            for name in _normalize_requested_matrices(matrices)
        ]
        self._validate_scenario(scenario)
        self._validate_matrices(requested)

        from mario.compute.types import ResolutionContext

        context = ResolutionContext(
            compute_method=compute_method,
            linear_solver=linear_solver,
            linear_strategy=linear_strategy,
        )
        resolver = _resolver_module().Resolver(self, scenario=scenario, context=context)

        for item in requested:
            if self.has_matrix(item, scenario=scenario) and not force_rewrite:
                continue

            removed = False
            previous = None
            if force_rewrite and self.has_matrix(item, scenario=scenario):
                previous = self.get_block(item, scenario=scenario)
                self.matrices[scenario].pop(_resolve_storage_matrix_name(item), None)
                removed = True

            try:
                resolver.resolve(item)
            except self._resolver_failure_types() as exc:
                if removed:
                    self.set_block(item, previous, scenario=scenario)
                raise DataMissing(
                    f"MARIO is not able to calculate {item} because of missing or unresolved dependencies.\n{exc}"
                ) from exc

    def _validate_scenario(self, scenario: str) -> None:
        """Ensure that the requested scenario exists on the database."""
        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

    def _validate_matrices(self, matrices: list[str]) -> None:
        """Ensure that all requested matrix names are valid for the table kind."""
        acceptable = list(self.available_matrices())
        builtin = set(available_matrices(self.table_type))
        for item in matrices:
            resolved = _resolve_canonical_matrix_name(item)
            storage_name = _resolve_storage_matrix_name(item)
            if resolved in builtin or item in acceptable or storage_name in acceptable:
                continue
            if item not in acceptable:
                raise WrongInput(
                    f"{item} not present in acceptable item for calc_all. "
                    f"Acceptable matrices are {acceptable}"
                )

    def available_matrices(self) -> tuple[str, ...]:
        """Return all matrix names available on the current instance.

        Returns
        -------
        tuple[str, ...]
            Sorted union of built-in matrices, registered custom operators and
            registered custom block specifications.
        """
        from mario.compute.operators import (
            list_registered_block_specs,
            list_registered_operator_names,
        )

        available = {
            _resolve_storage_matrix_name(name)
            for name in available_matrices(self.table_type)
        }
        available.update(list_registered_operator_names(self))
        available.update(list_registered_block_specs(self))
        return tuple(sorted(available))

    def available_blocks(self) -> tuple[str, ...]:
        """Backward-compatible alias for :meth:`available_matrices`."""
        return self.available_matrices()

    def _resolver_failure_types(self):
        """Return the exception types that indicate a resolution failure."""
        return (_resolver_module().ResolutionError, LookupError, NotImplementedError)

    def _resolve_structural_tech_assumption(
        self,
        *,
        table: str,
        tech_assumption: str | None,
    ) -> tuple[str | None, str | None]:
        """Resolve the effective technology assumption for the current data shape."""
        return resolve_tech_assumption(
            table=table,
            tech_assumption=tech_assumption,
            activity_count=_main_index_count(self._indeces, "a"),
            commodity_count=_main_index_count(self._indeces, "c"),
        )

    def _resolve_one(
        self,
        item: str,
        *,
        scenario: str,
        force_rewrite: bool,
        compute_method: str | None = None,
        linear_solver: str | None = None,
        linear_strategy: str | None = None,
    ):
        """Resolve one matrix and restore previous state if forced recompute fails."""
        from mario.compute.types import ResolutionContext

        removed = False
        previous = None

        if force_rewrite and self.has_matrix(item, scenario=scenario):
            previous = self.get_block(item, scenario=scenario)
            self.matrices[scenario].pop(_resolve_storage_matrix_name(item), None)
            removed = True

        try:
            context = ResolutionContext(
                compute_method=compute_method,
                linear_solver=linear_solver,
                linear_strategy=linear_strategy,
            )
            return _resolver_module().resolve(item, self, scenario=scenario, context=context)
        except self._resolver_failure_types() as exc:
            if removed:
                self.set_block(item, previous, scenario=scenario)
            raise DataMissing(
                f"MARIO is not able to calculate {item} because of missing or unresolved dependencies.\n{exc}"
            ) from exc

    def resolve(
        self,
        matrix: str,
        *,
        scenario: str = "baseline",
        force_rewrite: bool = False,
        compute_method: str | None = None,
        linear_solver: str | None = None,
        linear_strategy: str | None = None,
    ):
        """Resolve and materialize one matrix through the compute resolver.

        Parameters
        ----------
        matrix:
            Matrix or block name to compute.
        scenario:
            Scenario used as the resolution context.
        force_rewrite:
            When ``True``, drop and recompute an already materialized block.
        compute_method:
            Optional per-call override for the runtime method. See
            :meth:`calc_all` for the accepted values and semantics.
        linear_solver:
            Optional per-call override for the solve backend used by
            solve-based formulas.
        linear_strategy:
            Optional per-call override for the sparse linear strategy used by
            solve-based formulas.

        Returns
        -------
        object
            The resolved block as stored in ``self.matrices[scenario]``.
        """
        matrix = _resolve_canonical_matrix_name(matrix)
        self._validate_scenario(scenario)
        self._validate_matrices([matrix])
        return self._resolve_one(
            matrix,
            scenario=scenario,
            force_rewrite=force_rewrite,
            compute_method=compute_method,
            linear_solver=linear_solver,
            linear_strategy=linear_strategy,
        )

    def resolve_many(
        self,
        matrices,
        *,
        scenario: str = "baseline",
        force_rewrite: bool = False,
        compute_method: str | None = None,
        linear_solver: str | None = None,
        linear_strategy: str | None = None,
    ) -> dict[str, object]:
        """Resolve and materialize several matrices through the compute resolver.

        Parameters
        ----------
        matrices:
            One matrix name or an iterable of names to compute.
        scenario:
            Scenario used as the resolution context.
        force_rewrite:
            When ``True``, recompute already materialized blocks as well.
        compute_method:
            Optional per-call override for the runtime method. See
            :meth:`calc_all` for the accepted values and semantics.
        linear_solver:
            Optional per-call override for the solve backend used by
            solve-based formulas.
        linear_strategy:
            Optional per-call override for the sparse linear strategy used by
            solve-based formulas.

        Returns
        -------
        dict[str, object]
            Mapping from requested matrix name to resolved block.
        """
        requested = _normalize_requested_matrices(matrices)
        resolved_names = [_resolve_canonical_matrix_name(name) for name in requested]
        self._validate_scenario(scenario)
        self._validate_matrices(resolved_names)
        if not force_rewrite:
            from mario.compute.types import ResolutionContext

            context = ResolutionContext(
                compute_method=compute_method,
                linear_solver=linear_solver,
                linear_strategy=linear_strategy,
            )
            resolved = _resolver_module().resolve_many(
                resolved_names,
                self,
                scenario=scenario,
                context=context,
            )
            return {
                requested_name: resolved[resolved_name]
                for requested_name, resolved_name in zip(requested, resolved_names)
            }
        return {
            requested_name: self._resolve_one(
                resolved_name,
                scenario=scenario,
                force_rewrite=force_rewrite,
                compute_method=compute_method,
                linear_solver=linear_solver,
                linear_strategy=linear_strategy,
            )
            for requested_name, resolved_name in zip(requested, resolved_names)
        }

    def explain(self, matrix: str, *, scenario: str = "baseline") -> str:
        """Explain how MARIO would resolve one matrix.

        Parameters
        ----------
        matrix:
            Matrix or block name to explain.
        scenario:
            Scenario used to inspect available dependencies.

        Returns
        -------
        str
            Human-readable dependency explanation from the resolver.
        """
        return _resolver_module().explain(
            _resolve_canonical_matrix_name(matrix),
            self,
            scenario=scenario,
        )

    def register_block_spec(
        self,
        spec=None,
        *,
        name: str | None = None,
        row_axes=None,
        col_axes=None,
        replace: bool = False,
    ):
        """Register a semantic block specification on the current database.

        Parameters
        ----------
        spec:
            Pre-built block specification. When omitted, ``name``,
            ``row_axes`` and ``col_axes`` are used to build one.
        name:
            Name of the custom block to register when ``spec`` is not passed.
        row_axes, col_axes:
            Axis descriptors used to build a block specification on the fly.
        replace:
            When ``True``, replace an already registered custom specification
            with the same name.

        Returns
        -------
        object
            The registered block specification.
        """
        from mario.compute.operators import register_block_spec
        from mario.compute.semantics import block_spec

        if spec is None:
            if name is None or row_axes is None or col_axes is None:
                raise WrongInput("Pass either a BlockSpec or name/row_axes/col_axes.")
            spec = block_spec(name=name, row_axes=row_axes, col_axes=col_axes)

        return register_block_spec(self, spec, replace=replace)

    def get_block_spec(self, name: str):
        """Return the semantic block specification for a block name.

        Parameters
        ----------
        name:
            Built-in or custom block name.

        Returns
        -------
        object
            Block specification describing the row and column axes of the
            requested block.
        """
        from mario.compute.catalog import get_matrix_spec
        from mario.compute.operators import get_registered_block_spec
        from mario.compute.semantics import axis_ref, block_spec

        spec = get_registered_block_spec(self, name)
        if spec is not None:
            return spec

        try:
            matrix_spec = get_matrix_spec(self.table_type, name)
        except KeyError as exc:
            raise WrongInput(f"No block specification is known for {name!r}.") from exc

        return block_spec(
            name=name,
            row_axes=tuple(axis_ref(axis, axis) for axis in matrix_spec.axes.rows),
            col_axes=tuple(axis_ref(axis, axis) for axis in matrix_spec.axes.cols),
        )

    def list_custom_block_specs(self) -> tuple[str, ...]:
        """List custom block specifications registered on the instance.

        Returns
        -------
        tuple[str, ...]
            Names of custom block specifications currently attached to the
            database.
        """
        from mario.compute.operators import list_registered_block_specs

        return list_registered_block_specs(self)

    def register_operator(self, spec, *, replace: bool = False):
        """Register a custom compute operator on the current database.

        Parameters
        ----------
        spec:
            Operator specification describing the output block and the function
            used to compute it.
        replace:
            When ``True``, replace an already registered operator with the same
            name.

        Returns
        -------
        object
            The registered operator specification.

        Notes
        -----
        Custom operators complement the built-in compute catalog. They are
        typically created through helpers in ``mario.compute``, such as
        ``ratio_operator(...)`` or ``matrix_product_operator(...)``.
        """
        from mario.compute.operators import register_operator

        if spec.name in available_matrices(self.table_type) and not replace:
            raise WrongInput(
                f"{spec.name} is already a built-in block. Use another output name or replace=True."
            )
        return register_operator(self, spec, replace=replace)

    def list_custom_operators(self) -> tuple[str, ...]:
        """List custom compute operators registered on the instance.

        Returns
        -------
        tuple[str, ...]
            Names of custom operators currently attached to the database.
        """
        from mario.compute.operators import list_registered_operator_names

        return list_registered_operator_names(self)

    def _get_matrix(self, matrix: str, *, scenario: str, auto_calc: bool):
        """Return a deep copy of one matrix, computing it when allowed."""
        if not self.has_matrix(matrix, scenario=scenario):
            if not auto_calc:
                raise DataMissing(
                    f"{matrix} is not calculated. Using auto_calc = True, can track the missing data and calculate them"
                )
            self.calc_all([matrix], scenario=scenario)
        return self.get_block_as_pandas(matrix, scenario=scenario)

    def list_matrices(self, scenario: str = "baseline") -> tuple[str, ...]:
        """List all matrices currently materialized for one scenario.

        Parameters
        ----------
        scenario:
            Scenario whose stored matrices should be listed.

        Returns
        -------
        tuple[str, ...]
            Sorted matrix names already materialized for the scenario.
        """
        self._validate_scenario(scenario)
        return tuple(sorted(self.matrices[scenario]))

    def has_matrix(self, name: str, scenario: str = "baseline") -> bool:
        """Return whether one matrix is materialized for a scenario.

        Parameters
        ----------
        name:
            Matrix name to test.
        scenario:
            Scenario to inspect.

        Returns
        -------
        bool
            ``True`` when the matrix is already stored in the scenario.
        """
        self._validate_scenario(scenario)
        return _resolve_storage_matrix_name(name) in self.matrices[scenario]

    def has_block(self, name: str, scenario: str = "baseline") -> bool:
        """Backward-compatible alias for :meth:`has_matrix`."""
        return self.has_matrix(name, scenario=scenario)

    def get_block(self, name: str, scenario: str = "baseline"):
        """Return the stored block object for a scenario without conversion.

        Parameters
        ----------
        name:
            Block name to retrieve.
        scenario:
            Scenario to read from.

        Returns
        -------
        object
            Raw stored block object as kept in ``self.matrices``.
        """
        self._validate_scenario(scenario)
        return self.matrices[scenario][_resolve_storage_matrix_name(name)]

    def set_block(self, name: str, value, scenario: str = "baseline") -> None:
        """Store one block in the selected scenario.

        Parameters
        ----------
        name:
            Block name to store.
        value:
            Block payload to assign.
        scenario:
            Scenario to update.
        """
        self._validate_scenario(scenario)
        self.matrices[scenario][_resolve_storage_matrix_name(name)] = value

    def get_block_as_pandas(self, name: str, scenario: str = "baseline"):
        """Return one block converted to a pandas object.

        Parameters
        ----------
        name:
            Block name to retrieve.
        scenario:
            Scenario to read from.

        Returns
        -------
        pandas.DataFrame | pandas.Series
            Pandas representation of the requested block.
        """
        return block_to_pandas(self.get_block(name, scenario=scenario))

    def get_block_as_table(
        self,
        name: str,
        scenario: str = "baseline",
        *,
        backend: str = "auto",
    ):
        """Return one block in the requested tabular backend.

        Parameters
        ----------
        name:
            Block name to retrieve.
        scenario:
            Scenario to read from.
        backend:
            Tabular backend passed to ``block_to_table(...)``.

        Returns
        -------
        object
            Table representation of the requested block in the selected
            backend.
        """
        return block_to_table(self.get_block(name, scenario=scenario), backend=backend)

    def get_block_as_matrix(
        self,
        name: str,
        scenario: str = "baseline",
        *,
        backend: str = "numpy",
        prefer_sparse: bool = False,
    ):
        """Return one block in a numeric matrix backend.

        Parameters
        ----------
        name:
            Block name to retrieve.
        scenario:
            Scenario to read from.
        backend:
            Matrix backend passed to ``block_to_matrix(...)``.
        prefer_sparse:
            When ``True``, prefer sparse output when supported by the backend.

        Returns
        -------
        object
            Numeric matrix representation of the requested block.
        """
        return block_to_matrix(
            self.get_block(name, scenario=scenario),
            backend=backend,
            prefer_sparse=prefer_sparse,
        )

    def get_data(
        self,
        matrices,
        units=True,
        indeces=True,
        auto_calc=True,
        format="object",
        scenarios=["baseline"],
        base_scenario=None,
        type="absolute",
    ):
        """Return matrices, units and indexes in a structured payload.

        Parameters
        ----------
        matrices:
            One matrix name or an iterable of names to retrieve.
        units:
            When ``True``, include the database unit tables in the returned
            payload.
        indeces:
            When ``True``, include the index dictionaries in the returned
            payload.
        auto_calc:
            When ``True``, automatically compute missing matrices before
            returning them.
        format:
            ``"object"`` returns namedtuples; ``"dict"`` returns nested
            dictionaries keyed by scenario.
        scenarios:
            Scenario name or iterable of scenario names to retrieve.
        base_scenario:
            Optional reference scenario used to return scenario differences
            instead of absolute values.
        type:
            Difference type used with ``base_scenario``. Accepted values are
            ``"absolute"`` and ``"relative"``.

        Returns
        -------
        object | dict
            Namedtuple payload or nested dictionary, depending on ``format``.
        """
        requested = _normalize_requested_matrices(matrices)
        resolved_names = [_resolve_canonical_matrix_name(name) for name in requested]
        options = list(self.available_matrices())

        if isinstance(scenarios, str):
            scenarios = [scenarios]
        else:
            scenarios = list(scenarios)

        if type not in ["absolute", "relative"]:
            raise WrongInput("Acceptable values for type are:\n['absolute', 'relative']")

        invalid = [
            name
            for name, resolved_name in zip(requested, resolved_names)
            if resolved_name not in available_matrices(self.table_type) and name not in options
        ]
        if invalid:
            raise WrongInput(
                f"{set(invalid)} is/are not an acceptable input/s. Acceptabel values are:\n{options}"
            )

        for scenario in scenarios:
            if scenario not in [*self.matrices]:
                raise WrongInput(
                    f"{scenario} is not an acceptable scenario. Acceptable scenarios are:\n{[*self.matrices]}"
                )

        if base_scenario is not None and base_scenario not in [*self.matrices]:
            raise WrongInput(
                f"{base_scenario} is not an acceptable scenario for base_scenario. "
                f"Acceptabel scenarios are:\n{[*self.matrices]}"
            )

        output_fields = list(requested)
        if units:
            output_fields.append("units")
        if indeces:
            output_fields.append("indeces")

        dict_scenarios = {}
        for scenario in scenarios:
            data = {}
            for requested_name, resolved_name in zip(requested, resolved_names):
                value = self._get_matrix(resolved_name, scenario=scenario, auto_calc=auto_calc)
                if base_scenario is None:
                    data[requested_name] = value
                    continue

                base_value = self._get_matrix(
                    resolved_name,
                    scenario=base_scenario,
                    auto_calc=auto_calc,
                )
                if type == "absolute":
                    data[requested_name] = value - base_value
                else:
                    data[requested_name] = (value - base_value) / base_value

            if units:
                data["units"] = copy.deepcopy(self.units)
            if indeces:
                data["indeces"] = copy.deepcopy(self._indeces)

            if format == "dict":
                dict_scenarios[scenario] = data
            else:
                mini_object = namedtuple("data", output_fields)
                if len(scenario) == 1:
                    dict_scenarios = mini_object(**data)
                else:
                    dict_scenarios[scenario] = mini_object(**data)

        return dict_scenarios

    def query(
        self,
        matrices,
        scenarios=["baseline"],
        base_scenario=None,
        type="absolute",
    ):
        """Return matrices from one or more scenarios with a compact shape.

        Parameters
        ----------
        matrices:
            One matrix name or an iterable of names to retrieve.
        scenarios:
            Scenario name or iterable of scenario names to query.
        base_scenario:
            Optional reference scenario used to return scenario differences.
        type:
            Difference type used with ``base_scenario``. Accepted values are
            ``"absolute"`` and ``"relative"``.

        Returns
        -------
        pandas object | dict
            If one matrix and one scenario are requested, return the matrix
            directly. Otherwise return a dictionary keyed by scenario and
            possibly matrix name.
        """
        requested = _normalize_requested_matrices(matrices)
        data = self.get_data(
            matrices=requested,
            units=False,
            indeces=False,
            format="dict",
            scenarios=scenarios,
            base_scenario=base_scenario,
            type=type,
        )

        if isinstance(scenarios, str):
            scenarios = [scenarios]
        else:
            scenarios = list(scenarios)

        if len(requested) == 1:
            for scenario in scenarios:
                data[scenario] = data[scenario][requested[0]]

        if len(scenarios) == 1:
            return data[scenarios[0]]

        return data

    @staticmethod
    def _explode_with_left_diagonal(
        direct: pd.DataFrame,
        transfer: pd.DataFrame,
        *,
        outer_name: str,
    ) -> pd.DataFrame:
        """Explode one direct matrix by left-diagonal scaling of a transfer matrix.

        For each row ``i`` in ``direct`` this builds ``diag(direct_i) @ transfer``
        and stacks results with one extra outer index level.
        """
        if not isinstance(direct, pd.DataFrame):
            raise TypeError("direct should be a pandas DataFrame.")
        if not isinstance(transfer, pd.DataFrame):
            raise TypeError("transfer should be a pandas DataFrame.")

        if direct.shape[0] == 0:
            return pd.DataFrame(columns=transfer.columns)

        missing = direct.columns.difference(transfer.index)
        if len(missing):
            raise WrongInput(
                f"direct columns are not aligned with transfer index. Missing labels in transfer: {list(missing)}"
            )

        aligned_transfer = transfer.loc[direct.columns, :]

        blocks = []
        for account, weights in direct.iterrows():
            exploded = aligned_transfer.mul(weights, axis=0)
            if isinstance(exploded.index, pd.MultiIndex):
                exploded_index = pd.MultiIndex.from_tuples(
                    [(account, *idx) for idx in exploded.index.tolist()],
                    names=[outer_name, *exploded.index.names],
                )
            else:
                exploded_index = pd.MultiIndex.from_arrays(
                    [[account] * len(exploded.index), exploded.index.tolist()],
                    names=[outer_name, exploded.index.name],
                )
            exploded.index = exploded_index
            blocks.append(exploded)

        return pd.concat(blocks, axis=0)

    @staticmethod
    def _normalize_exploded_selector(values, *, available: pd.Index, label: str) -> list:
        """Normalize optional exploded-matrix selectors and validate membership."""
        if values is None:
            return list(available)

        if isinstance(values, str):
            requested = [values]
        else:
            requested = list(values)

        missing = [item for item in requested if item not in available]
        if missing:
            raise WrongInput(
                f"Unknown {label}: {missing}. Available values are: {list(available)}"
            )

        return requested

    def f_ex(
        self,
        *,
        satellite_accounts=None,
        scenario: str = "baseline",
    ):
        """Return exploded satellite footprints for IOT: ``diag(e) @ w``.

        Parameters
        ----------
        satellite_accounts:
            Optional subset of satellite rows to explode. Accepts one label or
            an iterable of labels.
        scenario:
            Scenario used to read source matrices.

        Returns
        -------
        pandas.DataFrame
            DataFrame with a 3-level MultiIndex on the rows
            ``(satellite account, region, sector)``.

        Notes
        -----
        For SUT models use :meth:`fa_ex` (activity side) or
        :meth:`fc_ex` (commodity side).
        """
        if self.table_type != "IOT":
            raise WrongInput("f_ex is only available for IOT. Use fa_ex or fc_ex for SUT.")
        self._validate_scenario(scenario)
        e = self.query(_ENUM.e, scenarios=[scenario])
        w = self.query("w", scenarios=[scenario])
        selected = self._normalize_exploded_selector(
            satellite_accounts,
            available=e.index,
            label="satellite accounts",
        )
        return self._explode_with_left_diagonal(
            e.loc[selected],
            w,
            outer_name=_MASTER_INDEX["k"],
        )

    def fa_ex(
        self,
        *,
        satellite_accounts=None,
        scenario: str = "baseline",
    ):
        """Return activity-side exploded satellite footprints for SUT: ``diag(ea) @ waa``.

        Parameters
        ----------
        satellite_accounts:
            Optional subset of satellite rows to explode. Accepts one label or
            an iterable of labels.
        scenario:
            Scenario used to read source matrices.

        Returns
        -------
        pandas.DataFrame
            DataFrame with a 3-level MultiIndex on the rows
            ``(satellite account, region, activity)``.

        Notes
        -----
        For IOT models use :meth:`f_ex`. For the commodity side use :meth:`fc_ex`.
        """
        if self.table_type != "SUT":
            raise WrongInput("fa_ex is only available for SUT. Use f_ex for IOT.")
        self._validate_scenario(scenario)
        ea = self.query("ea", scenarios=[scenario])
        waa = self.query("waa", scenarios=[scenario])
        selected = self._normalize_exploded_selector(
            satellite_accounts,
            available=ea.index,
            label="satellite accounts",
        )
        return self._explode_with_left_diagonal(
            ea.loc[selected],
            waa,
            outer_name=_MASTER_INDEX["k"],
        )

    def fc_ex(
        self,
        *,
        satellite_accounts=None,
        scenario: str = "baseline",
    ):
        """Return commodity-side exploded satellite footprints for SUT: ``diag(ea_k) @ (s @ wcc)``.

        Parameters
        ----------
        satellite_accounts:
            Optional subset of satellite rows to explode. Accepts one label or
            an iterable of labels.
        scenario:
            Scenario used to read source matrices.

        Returns
        -------
        pandas.DataFrame
            DataFrame with a 3-level MultiIndex on the rows
            ``(satellite account, region, activity)`` and commodity columns.

        Notes
        -----
        For IOT models use :meth:`f_ex`. For the activity side use :meth:`fa_ex`.
        """
        if self.table_type != "SUT":
            raise WrongInput("fc_ex is only available for SUT. Use f_ex for IOT.")
        self._validate_scenario(scenario)
        ea = self.query("ea", scenarios=[scenario])
        s = self.query("s", scenarios=[scenario])
        wcc = self.query("wcc", scenarios=[scenario])
        selected = self._normalize_exploded_selector(
            satellite_accounts,
            available=ea.index,
            label="satellite accounts",
        )
        transfer = s.dot(wcc)
        return self._explode_with_left_diagonal(
            ea.loc[selected],
            transfer,
            outer_name=_MASTER_INDEX["k"],
        )

    def m_ex(
        self,
        *,
        factors=None,
        scenario: str = "baseline",
    ):
        """Return exploded value-added multipliers for IOT: ``diag(v) @ w``.

        Parameters
        ----------
        factors:
            Optional subset of factor rows to explode. Accepts one label or
            an iterable of labels.
        scenario:
            Scenario used to read source matrices.

        Returns
        -------
        pandas.DataFrame
            DataFrame with a 3-level MultiIndex on the rows
            ``(factor, region, sector)``.

        Notes
        -----
        For SUT models use :meth:`ma_ex` (activity side) or
        :meth:`mc_ex` (commodity side).
        """
        if self.table_type != "IOT":
            raise WrongInput("m_ex is only available for IOT. Use ma_ex or mc_ex for SUT.")
        self._validate_scenario(scenario)
        v = self.query(_ENUM.v, scenarios=[scenario])
        w = self.query("w", scenarios=[scenario])
        selected = self._normalize_exploded_selector(
            factors,
            available=v.index,
            label="factors of production",
        )
        return self._explode_with_left_diagonal(
            v.loc[selected],
            w,
            outer_name=_MASTER_INDEX["f"],
        )

    def ma_ex(
        self,
        *,
        factors=None,
        scenario: str = "baseline",
    ):
        """Return activity-side exploded value-added multipliers for SUT: ``diag(va) @ waa``.

        Parameters
        ----------
        factors:
            Optional subset of factor rows to explode. Accepts one label or
            an iterable of labels.
        scenario:
            Scenario used to read source matrices.

        Returns
        -------
        pandas.DataFrame
            DataFrame with a 3-level MultiIndex on the rows
            ``(factor, region, activity)``.

        Notes
        -----
        For IOT models use :meth:`m_ex`. For the commodity side use :meth:`mc_ex`.
        """
        if self.table_type != "SUT":
            raise WrongInput("ma_ex is only available for SUT. Use m_ex for IOT.")
        self._validate_scenario(scenario)
        va = self.query("va", scenarios=[scenario])
        waa = self.query("waa", scenarios=[scenario])
        selected = self._normalize_exploded_selector(
            factors,
            available=va.index,
            label="factors of production",
        )
        return self._explode_with_left_diagonal(
            va.loc[selected],
            waa,
            outer_name=_MASTER_INDEX["f"],
        )

    def mc_ex(
        self,
        *,
        factors=None,
        scenario: str = "baseline",
    ):
        """Return commodity-side exploded value-added multipliers for SUT: ``diag(va) @ (s @ wcc)``.

        Parameters
        ----------
        factors:
            Optional subset of factor rows to explode. Accepts one label or
            an iterable of labels.
        scenario:
            Scenario used to read source matrices.

        Returns
        -------
        pandas.DataFrame
            DataFrame with a 3-level MultiIndex on the rows
            ``(factor, region, activity)`` and commodity columns.

        Notes
        -----
        For IOT models use :meth:`m_ex`. For the activity side use :meth:`ma_ex`.
        """
        if self.table_type != "SUT":
            raise WrongInput("mc_ex is only available for SUT. Use m_ex for IOT.")
        self._validate_scenario(scenario)
        va = self.query("va", scenarios=[scenario])
        s = self.query("s", scenarios=[scenario])
        wcc = self.query("wcc", scenarios=[scenario])
        selected = self._normalize_exploded_selector(
            factors,
            available=va.index,
            label="factors of production",
        )
        transfer = s.dot(wcc)
        return self._explode_with_left_diagonal(
            va.loc[selected],
            transfer,
            outer_name=_MASTER_INDEX["f"],
        )

    def add_note(self, notes):
        """Append one or more user notes to the metadata history.

        Parameters
        ----------
        notes:
            A single string or an iterable of strings to append to metadata
            history.
        """

        if isinstance(notes, str):
            notes = [notes]

        for note in notes:
            self.meta._add_history(f"User Note: {note}")

    def update_scenarios(self, scenario, **matrices):
        """Replace selected matrices in an existing scenario.

        Parameters
        ----------
        scenario:
            Existing scenario name to update.
        **matrices:
            Keyword mapping ``matrix_name=dataframe`` for the blocks to replace.

        Returns
        -------
        None
            The method mutates the stored scenario in place.
        """

        if scenario not in self.scenarios:
            raise WrongInput(f"Existing scenarios are {self.scenarios}")

        if not all([isinstance(value, pd.DataFrame) for value in matrices.values()]):
            raise WrongInput("items should be DataFrame")

        for matrix, value in matrices.items():
            self.set_block(matrix, value, scenario=scenario)

    def clone_scenario(
        self,
        scenario,
        name,
    ):
        """Clone an existing scenario into a new scenario name.

        Parameters
        ----------
        scenario:
            Source scenario to copy.
        name:
            Name for the new scenario.

        Returns
        -------
        None
            The new scenario is stored on the current instance.
        """

        if scenario not in self.scenarios:
            raise WrongInput("f{scenario} does not exist.")

        if name in self.scenarios:
            raise WrongInput(f"{name} already exists and cannot be overwritten.")

        self.matrices[name] = copy.deepcopy(self[scenario])
        self.meta._add_history(
            "Scenarios: {name} added to scearios by cloning {scenario}"
        )

    def rename_scenario(self, scenario, name):
        """Rename one existing scenario.

        Parameters
        ----------
        scenario:
            Existing scenario name to rename.
        name:
            New scenario name.

        Returns
        -------
        None
            The scenario key is renamed in place.
        """

        target_name = str(name)

        if scenario not in self.scenarios:
            raise WrongInput(f"{scenario} does not exist.")

        if target_name in self.scenarios:
            raise WrongInput(f"{target_name} already exists and cannot be overwritten.")

        self.matrices[target_name] = self.matrices.pop(scenario)
        self.meta._add_history(
            f"Scenarios: {scenario} renamed to {target_name}"
        )

    def reset_to_flows(
        self,
        scenario,
    ):
        """Reset a scenario so only flow-side matrices remain materialized.

        Parameters
        ----------
        scenario:
            Scenario to rewrite.

        Returns
        -------
        None
            The selected scenario is replaced with its flow blocks only.
        """

        if self.table_type == "SUT":
            keep = ["U", "S", "Ea", "Ec", "Va", "Vc", "Ya", "Yc", _ENUM.EY, _ENUM.VY]
        else:
            keep = [_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.EY, _ENUM.VY, _ENUM.Y]

        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

        matrices = {}
        for key in keep:
            if self.has_matrix(key, scenario=scenario):
                matrices[key] = self.get_block_as_pandas(key, scenario=scenario)
            else:
                self.calc_all(matrices=[key], scenario=scenario)
                matrices[key] = self.get_block_as_pandas(key, scenario=scenario)

        log_time(logger, "Databases: reset to flows.")
        self.matrices[scenario] = matrices

    def reset_to_coefficients(self, scenario):
        """Reset a scenario so only coefficient-side matrices remain materialized.

        Parameters
        ----------
        scenario:
            Scenario to rewrite.

        Returns
        -------
        None
            The selected scenario is replaced with its coefficient blocks only.
        """
        if self.table_type == "SUT":
            keep = ["u", "s", "ea", "ec", "va", "vc", "Ya", "Yc", _ENUM.EY, _ENUM.VY]
        else:
            keep = [_ENUM.z, _ENUM.e, _ENUM.v, _ENUM.EY, _ENUM.VY, _ENUM.Y]

        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

        matrices = {}
        for key in keep:
            if self.has_matrix(key, scenario=scenario):
                matrices[key] = self.get_block_as_pandas(key, scenario=scenario)
            else:
                self.calc_all(matrices=[key], scenario=scenario)
                matrices[key] = self.get_block_as_pandas(key, scenario=scenario)

        log_time(logger, "Databases: reset to coefficients.")
        self.matrices[scenario] = matrices

    def change_assumption(self, tech_assumption: str) -> None:
        """Change the structural SUT technology assumption.

        The technology assumption is a dataset-level property, so the change is
        applied to the whole database rather than to one scenario only. Before
        updating the metadata, all scenarios are reset to their flow-side
        matrices so any coefficient-side blocks can be rebuilt consistently
        under the new assumption on demand.

        Parameters
        ----------
        tech_assumption:
            Target technology assumption. Accepted values are
            ``"industry-based"``, ``"product-based"``, ``"IT"`` and ``"PT"``.

        Returns
        -------
        None
            The database is updated in place.
        """
        resolved_tech_assumption, tech_note = self._resolve_structural_tech_assumption(
            table=self.table_type,
            tech_assumption=tech_assumption,
        )

        current_tech_assumption = self.tech_assumption

        if current_tech_assumption == resolved_tech_assumption:
            if tech_note is not None:
                log_time(logger, f"Database: {tech_note}", "warning")
                self.meta._add_history(tech_note)
            return

        scenarios = list(self.scenarios)
        for scenario in scenarios:
            self.reset_to_flows(scenario=scenario)

        self.meta._add_attribute(tech_assumption=resolved_tech_assumption)
        self.meta._add_history(
            "Database: technology assumption changed from "
            f"{current_tech_assumption} to {resolved_tech_assumption}. "
            "All scenarios were reset to flows."
        )

        if tech_note is not None:
            log_time(logger, f"Database: {tech_note}", "warning")
            self.meta._add_history(tech_note)

    def get_index(self, index, level="main"):
        """Return one index level or the full index mapping for the database.

        Parameters
        ----------
        index:
            Set name such as ``Region`` or ``Sector``. Pass ``"all"`` to
            retrieve every available set for the table type.
        level:
            Index variant to return, typically ``"main"`` or ``"aggregated"``.

        Returns
        -------
        list | dict
            Requested index labels, or a dictionary of all labels when
            ``index="all"``.
        """

        if isinstance(index, str) and index.lower() == "all":
            return {
                key: self._indeces[value].get(level)
                for key, value in TABLE_LEVELS[self.table_type].items()
            }

        index = self._resolve_set_name(index, raise_on_missing=False)

        if index not in self.sets:
            raise WrongInput(
                "'{}' is not a valid index. Valid indeces are: \n{}".format(
                    index, self.sets
                )
            )

        if level not in [*self._indeces[TABLE_LEVELS[self.table_type][index]]]:
            raise WrongInput(
                "'{}' is not a valid level for '{}' . Valid levels are: \n{}".format(
                    level, index, [*self._indeces[TABLE_LEVELS[self.meta.table][index]]]
                )
            )

        return copy.deepcopy(self._indeces[TABLE_LEVELS[self.table_type][index]][level])

    @staticmethod
    def _normalize_set_token(value):
        """Collapse one user-facing set token to a comparison-friendly key."""
        return re.sub(r"[^0-9a-z]+", "", str(value).strip().lower())

    def _resolve_set_name(self, value, *, allow_codes=True, raise_on_missing=True):
        """Resolve one set label from an exact label, alias or short code."""
        if value in self.sets:
            return value

        normalized = self._normalize_set_token(value)
        aliases = {}
        alias_settings = IndexAliases()
        for set_name, code in TABLE_LEVELS[self.table_type].items():
            aliases[self._normalize_set_token(set_name)] = set_name
            if allow_codes:
                aliases[self._normalize_set_token(code)] = set_name
            for alias in alias_settings[code]:
                aliases[self._normalize_set_token(alias)] = set_name

        resolved = aliases.get(normalized)
        if resolved is not None:
            return resolved

        if raise_on_missing:
            raise WrongInput(f"Acceptable items are {self.sets}")

        return None

    def _resolve_unit_set_name(self, value):
        """Resolve one units key through the same set alias rules used elsewhere."""
        if getattr(self.meta, "table", None) is None:
            return value if value in getattr(self, "_units", {}) else None

        return self._resolve_set_name(value, raise_on_missing=False)

    def is_balanced(
        self,
        method,
        data_set="baseline",
        margin=0.05,
        as_dataframe=False,
    ):
        """Check whether a scenario is balanced under a chosen criterion.

        Parameters
        ----------
        method:
            Balance criterion. Accepted values are ``"flows"``,
            ``"coefficients"`` and ``"prices"``.
        data_set:
            Scenario to test.
        margin:
            Allowed tolerance around the expected balance condition.
        as_dataframe:
            When ``True``, return the imbalance table instead of printing it.

        Returns
        -------
        bool | pandas.DataFrame
            ``True`` when balanced, ``False`` when imbalances are found, or the
            imbalance dataframe when ``as_dataframe=True``.
        """

        methods = {
            "flows": {"matrices": [_ENUM.V, _ENUM.Z, _ENUM.X], "header": ["\u0394X"]},
            "coefficients": {
                "matrices": [_ENUM.v, _ENUM.z],
                "header": [f"{_ENUM.v}+{_ENUM.z}"],
            },
            "prices": {"matrices": [_ENUM.p], "header": ["\u0394p"]},
        }

        if method not in methods:
            raise WrongInput(f"Acceptable methods are {[*methods]}")
        if self.is_hybrid:
            raise NotImplementable(
                "Balance test is not applicable for hybrid units tables."
            )

        data = self.query(
            matrices=methods[method]["matrices"],
            scenarios=[data_set],
        )

        if method == "flows":
            balance = (
                data[_ENUM.Z].sum() + data[_ENUM.V].sum() - data[_ENUM.X].sum(1)
            ).to_frame()
            balance.columns = ["col"]

            imbalances = balance[
                (balance["col"] >= margin) | (balance["col"] <= -margin)
            ]

        elif method == "coefficients":
            balance = (data[_ENUM.z].sum() + data[_ENUM.v].sum()).to_frame()
            balance.columns = ["col"]

            imbalances = balance[
                (balance["col"] >= 1 + margin)
                | (balance["col"] <= 1 - margin) & (balance["col"] != 0)
            ]

        elif method == "prices":
            balance = data
            imbalances = balance[
                (balance["price index"] >= 1 + margin)
                | (balance["price index"] <= 1 - margin) & (balance["price index"] != 0)
            ]

        if len(imbalances):
            tabul_meta = tabulate(imbalances, headers="keys", tablefmt="psql")
            imbalances.columns = methods[method]["header"]
            tabul = tabulate(imbalances, headers="keys", tablefmt="psql")
            log_time(
                logger, f"Database: based on {method} test, {data_set} is not balance."
            )
            self.meta._add_history(
                f"Balance Test: imbalances found in {data_set} scenario"
                f" on {method} with a margion of +-{margin} test in following items\n {tabul_meta}"
            )
            if as_dataframe:
                return imbalances

            print(tabul)
            return False

        log_time(logger, f"Database: based on {method} test, {data_set} is balance.")
        self.meta._add_history(
            f"Balance Test: based on {method} test, {data_set} is balance."
        )
        return True

    def is_isard(self, scenario: str = "baseline") -> bool:
        """Test whether a multi-regional SUT follows the Isard format.

        Parameters
        ----------
        scenario:
            Scenario whose use-side block should be tested.

        Returns
        -------
        bool
            ``True`` when the table is in Isard format, ``False`` otherwise.
        """

        if self.meta.table != "SUT":
            raise NotImplementable("This test is implementable only on SUT tables")
        elif len(self.get_index(_MASTER_INDEX["r"])) == 1:
            raise NotImplementable(
                "This test is not implementable on single-region tables"
            )

        if scenario not in self.scenarios:
            raise WrongInput("Acceptable data_sets are:\n{}".format(self.scenarios))

        if self.has_matrix(
            _ENUM.z, scenario=scenario
        ):  # this avoid to calculate z or Z in case one of them is missing, to avoid losing time
            matrix = self.get_block_as_pandas(_ENUM.z, scenario=scenario)
        else:
            matrix = self._get_matrix(_ENUM.Z, scenario=scenario, auto_calc=True)

        sN = slice(None)
        matrix = matrix.loc[
            (sN, _MASTER_INDEX["c"], sN), (sN, _MASTER_INDEX["a"], sN)
        ]  # extract the use side from z or Z
        matrix = matrix.groupby(level=[_MASTER_INDEX["r"]]).sum()
        matrix = matrix.T.groupby(level=[_MASTER_INDEX["r"]]).sum().T

        is_diagonal = np.all(matrix.values == np.diag(np.diagonal(matrix)))

        if is_diagonal:
            log_time(logger, "Test: table is not in Isard format")

            return False

        else:
            log_time(logger, "Test: table is in Isard format")

            return True

    def is_chenerymoses(self, scenario: str = "baseline") -> bool:
        """Test whether a multi-regional SUT follows the Chenery-Moses format.

        Parameters
        ----------
        scenario:
            Scenario whose supply-side block should be tested.

        Returns
        -------
        bool
            ``True`` when the table is in Chenery-Moses format, ``False``
            otherwise.
        """

        if self.meta.table != "SUT":
            raise NotImplementable("This test is implementable only on SUT tables")
        elif len(self.get_index(_MASTER_INDEX["r"])) == 1:
            raise NotImplementable(
                "This test is not implementable on single-region tables"
            )

        if scenario not in self.scenarios:
            raise WrongInput(
                "{} is not an acceptable scenario. Acceptable data_sets are:\n{}".format(
                    scenario, self.scenarios
                )
            )

        if self.has_matrix(
            _ENUM.z, scenario=scenario
        ):  # this avoid to calculate z or Z in case one of them is missing, to avoid losing time
            matrix = self.get_block_as_pandas(_ENUM.z, scenario=scenario)
        else:
            matrix = self._get_matrix(_ENUM.Z, scenario=scenario, auto_calc=True)

        sN = slice(None)
        matrix = matrix.loc[
            (sN, _MASTER_INDEX["a"], sN), (sN, _MASTER_INDEX["c"], sN)
        ]  # extract the supply side from z or Z
        matrix = matrix.groupby(level=[_MASTER_INDEX["r"]]).sum()
        matrix = matrix.T.groupby(level=[_MASTER_INDEX["r"]]).sum().T

        is_diagonal = np.all(matrix.values == np.diag(np.diagonal(matrix)))

        if is_diagonal:
            log_time(logger, "Test: table is not in Chenery-Moses format")

            return False

        else:
            log_time(logger, "Test: table is in Chenery-Moses format")

            return True

    def copy(self):
        """Return a deep copy of the database object.

        Returns
        -------
        CoreModel
            Independent copy of the current object with copied matrices,
            indices, units and metadata.
        """
        new = copy.deepcopy(self)
        new.meta._add_history("deep copy created from object")
        return new

    def save_meta(self, path, format="txt"):
        """Persist metadata history to disk.

        Parameters
        ----------
        path:
            Output path prefix or file path, depending on ``format``.
        format:
            Metadata output format accepted by ``MARIOMetaData._save``:
            ``"txt"``, ``"json"`` or ``"binary"``.
        """
        self.meta._save(path, format)

    def __str__(self):
        """Render a compact structural summary of the database."""
        to_print = (
            "name = {}\n"
            "table = {}\n".format(self.meta.name, self.meta.table)
        )
        tech_assumption = getattr(self.meta, "tech_assumption", None)
        if tech_assumption is not None:
            to_print += f"tech_assumption = {tech_assumption}\n"
        to_print += "scenarios = {}\n".format(self.scenarios)
        for item in TABLE_LEVELS[self.meta.table]:
            to_print += "{} = {}\n".format(item, len(self.get_index(item)))

        return to_print

    def __repr__(self):
        """Return the same structural summary used by ``__str__``."""
        return self.__str__()

    def GDP(
        self,
        exclude=[],
        scenario="baseline",
        total=True,
        share=False,
    ):
        """Return GDP totals or sector-level GDP for a scenario.

        Parameters
        ----------
        exclude:
            Factor-of-production labels to exclude from the GDP sum.
        scenario:
            Scenario used to compute GDP.
        total:
            When ``True``, aggregate GDP by region. When ``False``, keep one row
            per region and sector or activity.
        share:
            When ``True``, append the share of each sector or activity within
            its region.

        Returns
        -------
        pandas.DataFrame
            GDP table indexed by region, and optionally by sector/activity.
        """
        differnce = set(exclude).difference(set(self.get_index(_MASTER_INDEX["f"])))
        if differnce:
            raise WrongInput(
                "{} is/are not valid {}".format(
                    differnce, self.get_index(_MASTER_INDEX["f"])
                )
            )

        slicer = _MASTER_INDEX["s"] if self.table_type == "IOT" else _MASTER_INDEX["a"]

        data = self.query(
            matrices=[_ENUM.V],
            scenarios=[scenario],
        )

        GDP = (
            data.drop(exclude).sum().to_frame().loc[(slice(None), slicer, slice(None))]
        )
        GDP.columns = ["GDP"]

        GDP.index.names = (
            ["Region", "Sector"] if self.table_type == "IOT" else ["Region", "Activity"]
        )

        if total:
            GDP = GDP.groupby(
                level=0,
                sort=False,
            ).sum()

        if share:
            region_gdp = GDP.groupby(
                level=0,
                sort=False,
            ).sum()
            share = GDP.div(region_gdp) * 100
            GDP["Share of sector by region"] = share["GDP"]

        return GDP

    def search(self, item=None, search=None, ignore_case=True):
        """Search index values matching a pattern within one set or across all sets.

        Parameters
        ----------
        item:
            Optional set name to search in, such as ``Region`` or ``Sector``.
            When omitted, search every set and return grouped matches.
        search:
            Regular-expression fragment matched against the labels.
        ignore_case:
            When ``True``, perform a case-insensitive search.

        Returns
        -------
        list | dict
            Matching labels in their stored order, or a dictionary grouped by
            set when searching globally.
        """

        if search is None:
            search = item
            item = None
        if search is None:
            raise WrongInput("search requires a pattern.")

        flags = re.IGNORECASE if ignore_case else 0
        pattern = re.compile(f"{search}", flags)

        if item is None:
            found = {}
            for set_name in self.sets:
                matches = [
                    label for label in self.get_index(set_name) if pattern.search(str(label))
                ]
                if matches:
                    found[set_name] = matches
            return found

        item = self._resolve_set_name(item)
        items = self.get_index(item)
        found = [label for label in items if pattern.search(str(label))]

        return found

    @property
    def scenarios(self):
        """Return the list of available scenario names.

        Returns
        -------
        list[str]
            Scenario names in storage order.
        """
        return [*self.matrices]

    @property
    def table_type(self):
        """Return the database table type.

        Returns
        -------
        str
            Table kind stored in metadata, typically ``"IOT"`` or ``"SUT"``.
        """
        return self.meta.table

    @property
    def tech_assumption(self):
        """Return the structural technology assumption stored on the database."""
        return getattr(self.meta, "tech_assumption", None)

    @property
    def is_multi_region(self):
        """Return whether the database contains more than one region.

        Returns
        -------
        bool
            ``True`` for multi-regional databases, ``False`` otherwise.
        """
        if len(self.get_index(_MASTER_INDEX["r"])) - 1:
            return True

        return False

    @property
    def units(self):
        """Return database units with alias-aware access on set labels.

        Returns
        -------
        MutableMapping
            Dict-like mapping keyed by canonical set names, while accepting the
            same aliases and short codes supported by :meth:`get_index`.
        """
        proxy = getattr(self, "_units_proxy", None)
        raw_units = getattr(self, "_units", None)
        if not isinstance(proxy, _ResolvedSetDict) or proxy._data is not raw_units:
            proxy = _ResolvedSetDict(raw_units if raw_units is not None else {}, self._resolve_unit_set_name)
            self._units_proxy = proxy
        return proxy

    @units.setter
    def units(self, value):
        """Store the raw units mapping behind the alias-aware units view."""
        if isinstance(value, _ResolvedSetDict):
            value = value._data
        self._units = value if value is not None else {}
        self._units_proxy = _ResolvedSetDict(self._units, self._resolve_unit_set_name)

    @property
    def sets(self):
        """Return the named index levels exposed by the current table type.

        Returns
        -------
        list[str]
            Set names available for the current table structure.
        """
        return [*TABLE_LEVELS[self.table_type]]

    @property
    def is_hybrid(self):
        """Return whether the database mixes multiple measurement units.

        Returns
        -------
        bool
            ``True`` when more than one unit is found across the core accounts.
        """
        if self.table_type == "IOT":
            check = set(self.units[_MASTER_INDEX["s"]]["unit"].unique())
            check.update(set(self.units[_MASTER_INDEX["f"]]["unit"].unique()))
        else:
            check = set(self.units[_MASTER_INDEX["a"]]["unit"].unique())
            check.update(set(self.units[_MASTER_INDEX["c"]]["unit"].unique()))
            check.update(set(self.units[_MASTER_INDEX["f"]]["unit"].unique()))

        if len(check) - 1:
            return True

        return False

    def _getdir(self, path, subfolder, file):
        """Resolve an output path, falling back to the database default directory."""

        if path is None:
            if not os.path.exists(r"{}/{}".format(self.directory, subfolder)):
                try:
                    os.mkdir(r"{}/{}".format(self.directory, subfolder))
                except:
                    raise ValueError(
                        "Can not create default path. Please specify the path"
                    )
            path = r"{}/{}/{}".format(self.directory, subfolder, file)
            log_time(
                logger,
                f"DIRECTORY: default path = {path} is choosen to save the data.",
                "warning",
            )

        return path

    @property
    def directory(self):
        """Return the default output directory used by the database.

        Returns
        -------
        str
            Absolute or relative directory used by helper exporters when no
            explicit path is provided.
        """

        if self._dir == "":
            self.directory = r"{}/Output".format(os.getcwd())

        return self._dir

    @directory.setter
    def directory(self, _dir):
        """Set and create, when needed, the default output directory.

        Parameters
        ----------
        _dir:
            Directory path to use as the new default output location.
        """
        _dir = r"{}".format(_dir)
        if os.path.exists(_dir):
            self._dir = _dir
            log_time(logger, f"DIRECTORY: default directory changed to {_dir}.")

        else:
            try:
                os.mkdir(_dir)
                self.directory = _dir
            except:
                raise ValueError(f"MARIO could not set the directory to {_dir}")

    @property
    def meta_history(self):
        """Print the full metadata history.

        Returns
        -------
        None
            The method prints the history to stdout for interactive use.
        """
        history = "\n".join(self.meta._history[:])
        print(history)

    @property
    def f_ex_all(self):
        """Exploded satellite footprints (IOT, all accounts, baseline).

        Shorthand for ``db.f_ex()`` with default arguments.  For filtering or
        non-baseline scenarios call :meth:`f_ex` directly.

        Returns
        -------
        pandas.DataFrame
        """
        return self.f_ex()

    @property
    def fa_ex_all(self):
        """Activity-side exploded satellite footprints (SUT, all accounts, baseline).

        Shorthand for ``db.fa_ex()`` with default arguments.  For filtering or
        non-baseline scenarios call :meth:`fa_ex` directly.

        Returns
        -------
        pandas.DataFrame
        """
        return self.fa_ex()

    @property
    def fc_ex_all(self):
        """Commodity-side exploded satellite footprints (SUT, all accounts, baseline).

        Shorthand for ``db.fc_ex()`` with default arguments.  For filtering or
        non-baseline scenarios call :meth:`fc_ex` directly.

        Returns
        -------
        pandas.DataFrame
        """
        return self.fc_ex()

    @property
    def m_ex_all(self):
        """Exploded value-added multipliers (IOT, all factors, baseline).

        Shorthand for ``db.m_ex()`` with default arguments.  For filtering or
        non-baseline scenarios call :meth:`m_ex` directly.

        Returns
        -------
        pandas.DataFrame
        """
        return self.m_ex()

    @property
    def ma_ex_all(self):
        """Activity-side exploded value-added multipliers (SUT, all factors, baseline).

        Shorthand for ``db.ma_ex()`` with default arguments.  For filtering or
        non-baseline scenarios call :meth:`ma_ex` directly.

        Returns
        -------
        pandas.DataFrame
        """
        return self.ma_ex()

    @property
    def mc_ex_all(self):
        """Commodity-side exploded value-added multipliers (SUT, all factors, baseline).

        Shorthand for ``db.mc_ex()`` with default arguments.  For filtering or
        non-baseline scenarios call :meth:`mc_ex` directly.

        Returns
        -------
        pandas.DataFrame
        """
        return self.mc_ex()

    def __getitem__(self, key):
        """Return the matrix dictionary stored for one scenario."""
        if key not in self.scenarios:
            raise WrongInput(
                "{} is not a valid scenario. Valid scenarios are {}".format(
                    key, self.scenarios
                )
            )

        return self.matrices[key]

    def __iter__(self):
        """Start iteration over available scenarios."""
        self.__it__ = self.scenarios
        return self

    def __next__(self):
        """Iterate over ``(scenario_name, matrices)`` pairs."""
        if len(self.__it__):
            key = self.__it__[0]
            value = self.matrices[key]

            self.__it__.pop(0)

            return (key, value)

        else:
            raise StopIteration

    def __getattr__(self, attr):
        """Auto-compute missing matrix attributes requested through dotted access.

        Notes
        -----
        Access patterns such as ``db.f`` and ``db.F`` delegate to
        :meth:`calc_all` without explicit runtime overrides. This means they
        use the globally configured compute defaults, including the active
        values set through :func:`mario.set_compute_method` and
        :func:`mario.set_linear_solver` and
        :func:`mario.set_linear_strategy`.
        """
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            if attr.startswith(("parse_", "hybrid_")) and hasattr(type(self), "parse_scenario"):
                resolver = getattr(type(self), "_resolve_parser_entrypoint", None)
                if callable(resolver):
                    try:
                        resolver(attr)
                    except WrongInput:
                        pass
                    else:
                        def parser_proxy(*args, **kwargs):
                            return self.parse_scenario(attr, *args, **kwargs)

                        return parser_proxy

            resolved_set = self._resolve_set_name(
                attr,
                allow_codes=False,
                raise_on_missing=False,
            )
            if resolved_set is not None:
                return self.get_index(resolved_set)

            resolved_matrix = _resolve_canonical_matrix_name(attr)
            all_mat = list(self.available_matrices())

            if resolved_matrix in available_matrices(self.table_type) or attr in all_mat:
                self.calc_all(matrices=[attr])
                return self.get_block(attr, scenario="baseline")

            else:
                raise AttributeError(attr)

    def __getstate__(self):
        """Return the instance state for pickle serialization."""
        return self.__dict__

    def __setstate__(self, value):
        """Restore the instance state after pickle deserialization."""
        self.__dict__ = value

    def __eq__(self, other):
        """Return ``True`` when two databases expose the same sets and indexes."""
        main_sets = sorted(self.sets)
        other_sets = sorted(other.sets)

        if main_sets != other_sets:
            return False

        for item in self.sets:
            main_index = set(self.get_index(item))
            other_index = set(other.get_index(item))

            if main_index != other_index:
                return False

        return True

    def backup(self):
        """Store a deep-copy backup of matrices, indexes and units.

        Returns
        -------
        None
            Backup data is stored on ``self._backup``.
        """
        self._backup = self._backup_(
            copy.deepcopy(self.matrices),
            copy.deepcopy(self._indeces),
            copy.deepcopy(self.units),
        )
