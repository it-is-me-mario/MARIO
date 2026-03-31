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
from mario.parsers.tabular import dataframe_parser
from mario.model.conventions import TABLE_LEVELS
from tabulate import tabulate
from collections import namedtuple

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


def _normalize_parsed_matrix_name(name: str) -> str:
    """Map parser block names through MARIO nomenclature when available."""
    try:
        return _ENUM[name]
    except Exception:
        return name


def available_matrices(table_type: str) -> tuple[str, ...]:
    """Return the catalog-backed matrix names accepted by the public API."""
    from mario.compute.catalog import available_matrix_names

    return available_matrix_names(table_type)


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
        calc_all=True,
        year=None,
        **kwargs,
    ):
        """Initialize the core model from parser output or explicit dataframes."""
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
            self.meta._add_attribute(table=table, price=price, source=source, year=year)

        else:
            if not all(
                [matrix is not None for matrix in [Y, E, Z, V, EY, units, table]]
            ):
                raise LackOfInput(
                    "For building an instance using dataframes, all the data [Y,E,Z,V,EY,units,table] should be given. VY is optional."
                )
            else:
                self.matrices, self._indeces, self.units = dataframe_parser(
                    Z, Y, E, V, EY, units, table, VY=VY
                )

                matrices = self.matrices["baseline"]
                renamed_matrices = {}

                for m, v in matrices.items():
                    renamed_matrices[_normalize_parsed_matrix_name(m)] = v

                renamed_matrices = _prune_eager_parser_blocks(renamed_matrices)
                self.matrices["baseline"] = renamed_matrices

                self.meta._add_attribute(table=table, price=price)

                log_time(logger, "Metadata: initialized by dataframes.")

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
        **kwargs,
    ):
        """Compute one or more matrices for a scenario."""
        requested = _normalize_requested_matrices(matrices)
        self._validate_scenario(scenario)
        self._validate_matrices(requested)

        for item in requested:
            if item in self.matrices[scenario] and not force_rewrite:
                continue
            self._resolve_one(item, scenario=scenario, force_rewrite=force_rewrite)

    def _validate_scenario(self, scenario: str) -> None:
        """Ensure that the requested scenario exists on the database."""
        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

    def _validate_matrices(self, matrices: list[str]) -> None:
        """Ensure that all requested matrix names are valid for the table kind."""
        acceptable = list(self.available_blocks())
        for item in matrices:
            if item not in acceptable:
                raise WrongInput(
                    f"{item} not present in acceptable item for calc_all. "
                    f"Acceptable matrices are {acceptable}"
                )

    def available_blocks(self) -> tuple[str, ...]:
        """Return built-in and custom block names visible on the instance."""
        from mario.compute.operators import (
            list_registered_block_specs,
            list_registered_operator_names,
        )

        available = set(available_matrices(self.table_type))
        available.update(list_registered_operator_names(self))
        available.update(list_registered_block_specs(self))
        return tuple(sorted(available))

    def _resolver_failure_types(self):
        """Return the exception types that indicate a resolution failure."""
        return (_resolver_module().ResolutionError, LookupError, NotImplementedError)

    def _resolve_one(self, item: str, *, scenario: str, force_rewrite: bool):
        """Resolve one matrix and restore previous state if forced recompute fails."""
        removed = False
        previous = None

        if force_rewrite and item in self.matrices[scenario]:
            previous = self.matrices[scenario].pop(item)
            removed = True

        try:
            return _resolver_module().resolve(item, self, scenario=scenario)
        except self._resolver_failure_types() as exc:
            if removed:
                self.matrices[scenario][item] = previous
            raise DataMissing(
                f"MARIO is not able to calculate {item} because of missing or unresolved dependencies.\n{exc}"
            ) from exc

    def resolve(self, matrix: str, *, scenario: str = "baseline", force_rewrite: bool = False):
        """Resolve and materialize one matrix through the compute resolver."""
        self._validate_scenario(scenario)
        self._validate_matrices([matrix])
        return self._resolve_one(matrix, scenario=scenario, force_rewrite=force_rewrite)

    def resolve_many(
        self,
        matrices,
        *,
        scenario: str = "baseline",
        force_rewrite: bool = False,
    ) -> dict[str, object]:
        """Resolve and materialize several matrices through the compute resolver."""
        requested = _normalize_requested_matrices(matrices)
        self._validate_scenario(scenario)
        self._validate_matrices(requested)
        return {
            matrix: self._resolve_one(matrix, scenario=scenario, force_rewrite=force_rewrite)
            for matrix in requested
        }

    def explain(self, matrix: str, *, scenario: str = "baseline") -> str:
        """Return a dependency explanation for one matrix."""
        return _resolver_module().explain(matrix, self, scenario=scenario)

    def register_block_spec(
        self,
        spec=None,
        *,
        name: str | None = None,
        row_axes=None,
        col_axes=None,
        replace: bool = False,
    ):
        """Register one semantic block specification on the current database.

        The simplest form is either passing a pre-built ``BlockSpec`` or
        passing ``name``, ``row_axes`` and ``col_axes`` directly.
        """
        from mario.compute.operators import register_block_spec
        from mario.compute.semantics import block_spec

        if spec is None:
            if name is None or row_axes is None or col_axes is None:
                raise WrongInput("Pass either a BlockSpec or name/row_axes/col_axes.")
            spec = block_spec(name=name, row_axes=row_axes, col_axes=col_axes)

        return register_block_spec(self, spec, replace=replace)

    def get_block_spec(self, name: str):
        """Return the semantic block specification for one block name."""
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
        """List the custom block specifications registered on the instance."""
        from mario.compute.operators import list_registered_block_specs

        return list_registered_block_specs(self)

    def register_operator(self, spec, *, replace: bool = False):
        """Register one custom operator on the current database.

        Custom operators complement the built-in compute catalog. They are best
        created through the helper builders in ``mario.compute``, such as
        ``ratio_operator(...)`` or ``matrix_product_operator(...)``.
        """
        from mario.compute.operators import register_operator

        if spec.name in available_matrices(self.table_type) and not replace:
            raise WrongInput(
                f"{spec.name} is already a built-in block. Use another output name or replace=True."
            )
        return register_operator(self, spec, replace=replace)

    def list_custom_operators(self) -> tuple[str, ...]:
        """List the custom operators registered on the instance."""
        from mario.compute.operators import list_registered_operator_names

        return list_registered_operator_names(self)

    def _get_matrix(self, matrix: str, *, scenario: str, auto_calc: bool):
        """Return a deep copy of one matrix, computing it when allowed."""
        if not self.has_block(matrix, scenario=scenario):
            if not auto_calc:
                raise DataMissing(
                    f"{matrix} is not calculated. Using auto_calc = True, can track the missing data and calculate them"
                )
            self.calc_all([matrix], scenario=scenario)
        return self.get_block_as_pandas(matrix, scenario=scenario)

    def list_blocks(self, scenario: str = "baseline") -> tuple[str, ...]:
        """List all blocks materialized for one scenario."""
        self._validate_scenario(scenario)
        return tuple(sorted(self.matrices[scenario]))

    def has_block(self, name: str, scenario: str = "baseline") -> bool:
        """Return whether one block is materialized for the scenario."""
        self._validate_scenario(scenario)
        return name in self.matrices[scenario]

    def get_block(self, name: str, scenario: str = "baseline"):
        """Return the stored block object for the scenario without conversion."""
        self._validate_scenario(scenario)
        return self.matrices[scenario][name]

    def set_block(self, name: str, value, scenario: str = "baseline") -> None:
        """Store one block in the selected scenario."""
        self._validate_scenario(scenario)
        self.matrices[scenario][name] = value

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
        """Return one block in the requested tabular backend."""
        return block_to_table(self.get_block(name, scenario=scenario), backend=backend)

    def get_block_as_matrix(
        self,
        name: str,
        scenario: str = "baseline",
        *,
        backend: str = "numpy",
        prefer_sparse: bool = False,
    ):
        """Return one block in a numeric matrix backend."""
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
        """Return matrices, units and indexes in a structured payload."""
        requested = _normalize_requested_matrices(matrices)
        options = list(available_matrices(self.table_type))

        if isinstance(scenarios, str):
            scenarios = [scenarios]
        else:
            scenarios = list(scenarios)

        if type not in ["absolute", "relative"]:
            raise WrongInput("Acceptable values for type are:\n['absolute', 'relative']")

        diff = set(requested).difference(set(options))
        if diff:
            raise WrongInput(
                f"{diff} is/are not an acceptable input/s. Acceptabel values are:\n{options}"
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
            for item in requested:
                value = self._get_matrix(item, scenario=scenario, auto_calc=auto_calc)
                if base_scenario is None:
                    data[item] = value
                    continue

                base_value = self._get_matrix(item, scenario=base_scenario, auto_calc=auto_calc)
                if type == "absolute":
                    data[item] = value - base_value
                else:
                    data[item] = (value - base_value) / base_value

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
        """Query matrices from one or more scenarios."""
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

    def add_note(self, notes):
        """Append one or more user notes to the metadata history."""

        if isinstance(notes, str):
            notes = [notes]

        for note in notes:
            self.meta._add_history(f"User Note: {note}")

    def update_scenarios(self, scenario, **matrices):
        """Replace selected matrices in an existing scenario."""

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
        """Clone an existing scenario into a new scenario name."""

        if scenario not in self.scenarios:
            raise WrongInput("f{scenario} does not exist.")

        if name in self.scenarios:
            raise WrongInput(f"{name} already exists and cannot be overwritten.")

        self.matrices[name] = copy.deepcopy(self[scenario])
        self.meta._add_history(
            "Scenarios: {name} added to scearios by cloning {scenario}"
        )

    def reset_to_flows(
        self,
        scenario,
    ):
        """Drop coefficient matrices for a scenario and keep only flow matrices."""

        keep = [_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.EY, _ENUM.VY, _ENUM.Y]

        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

        matrices = {}
        for key in keep:
            if self.has_block(key, scenario=scenario):
                matrices[key] = self.get_block_as_pandas(key, scenario=scenario)
            else:
                self.calc_all(matrices=[key], scenario=scenario)
                matrices[key] = self.get_block_as_pandas(key, scenario=scenario)

        log_time(logger, "Databases: reset to flows.")
        self.matrices[scenario] = matrices

    def reset_to_coefficients(self, scenario):
        """Drop flow matrices for a scenario and keep only coefficient matrices."""
        keep = [_ENUM.z, _ENUM.e, _ENUM.v, _ENUM.EY, _ENUM.VY, _ENUM.Y]

        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

        matrices = {}
        for key in keep:
            if self.has_block(key, scenario=scenario):
                matrices[key] = self.get_block_as_pandas(key, scenario=scenario)
            else:
                self.calc_all(matrices=[key], scenario=scenario)
                matrices[key] = self.get_block_as_pandas(key, scenario=scenario)

        log_time(logger, "Databases: reset to coefficients.")
        self.matrices[scenario] = matrices

    def get_index(self, index, level="main"):
        """Return one index level or the full index mapping for the database."""

        if index == "all":
            return {
                key: self._indeces[value].get(level)
                for key, value in TABLE_LEVELS[self.table_type].items()
            }

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

    def is_balanced(
        self,
        method,
        data_set="baseline",
        margin=0.05,
        as_dataframe=False,
    ):
        """Check whether a scenario is balanced under the requested criterion."""

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
        """Return ``True`` if a multi-regional SUT is in Isard format."""

        if self.meta.table != "SUT":
            raise NotImplementable("This test is implementable only on SUT tables")
        elif len(self.get_index(_MASTER_INDEX["r"])) == 1:
            raise NotImplementable(
                "This test is not implementable on single-region tables"
            )

        if scenario not in self.scenarios:
            raise WrongInput("Acceptable data_sets are:\n{}".format(self.scenarios))

        if self.has_block(
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
        """Return ``True`` if a multi-regional SUT is in Chenery-Moses format."""

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

        if self.has_block(
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
        """Return a deep copy of the database object."""
        new = copy.deepcopy(self)
        new.meta._add_history("deep copy created from object")
        return new

    def save_meta(self, path, format="txt"):
        """Persist metadata history to disk."""
        self.meta._save(path, format)

    def __str__(self):
        """Render a compact structural summary of the database."""
        to_print = (
            "name = {}\n"
            "table = {}\n"
            "scenarios = {}\n".format(self.meta.name, self.meta.table, self.scenarios)
        )
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
        """Return GDP totals or sectoral GDP for a scenario."""
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

    def search(self, item, search, ignore_case=True):
        """Search index values matching a pattern within one set."""

        if item not in self.sets:
            raise WrongInput(f"Acceptable items are {self.sets}")

        items = self.get_index(item)

        if ignore_case:
            r = re.compile(f".*{search}", re.IGNORECASE)
        else:
            r = re.compile(f".*{search}")

        found = list(filter(r.match, items))

        return found

    @property
    def scenarios(self):
        """Return the list of available scenario names."""
        return [*self.matrices]

    @property
    def table_type(self):
        """Return the database table type."""
        return self.meta.table

    @property
    def is_multi_region(self):
        """Return ``True`` when the database contains more than one region."""
        if len(self.get_index(_MASTER_INDEX["r"])) - 1:
            return True

        return False

    @property
    def sets(self):
        """Return the named index levels exposed by the current table type."""
        return [*TABLE_LEVELS[self.table_type]]

    @property
    def is_hybrid(self):
        """Return ``True`` when the database mixes multiple measurement units."""
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
        """Return the default output directory used by the database."""

        if self._dir == "":
            self.directory = r"{}/Output".format(os.getcwd())

        return self._dir

    @directory.setter
    def directory(self, _dir):
        """Set and create, when needed, the default output directory."""
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
        """Print the full metadata history."""
        history = "\n".join(self.meta._history[:])
        print(history)

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
        """Auto-compute matrix attributes requested through dotted access."""
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            all_mat = list(self.available_blocks())

            if attr in all_mat:
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
        """Store a deep-copy backup of matrices, indexes and units."""
        self._backup = self._backup_(
            copy.deepcopy(self.matrices),
            copy.deepcopy(self._indeces),
            copy.deepcopy(self.units),
        )
