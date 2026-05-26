# -*- coding: utf-8 -*-
"""``Database`` implementation and high-level user operations."""

from mario.log_exc.exceptions import (
    LackOfInput,
    WrongInput,
    WrongExcelFormat,
    NotImplementable,
    DataMissing,
)

from mario.log_exc.logger import log_time

from mario.ops.shocks import (
    Y_shock,
    V_shock,
    Z_shock,
    U_shock,
    S_shock,
    Ya_shock,
    Yc_shock,
    va_shock,
    vc_shock,
    ea_shock,
    ec_shock,
    has_shock_sheet,
)
from mario.ops.add_sector_workbook import (
    derive_add_sector_sets,
    group_inventories_by_target,
    read_add_sector_workbook,
    write_add_sector_workbook,
    write_inventory_templates_to_workbook,
)
from mario.ops.add_sector_engine import run_add_sector_engine
from mario.ops.add_sector_engine import collect_add_sector_matrices
from mario.ops.add_sector_split import (
    apply_split_parent_renames,
    build_split_flow_scenario,
    log_split_scenario,
    normalize_split_parent_renames,
    prepare_split_support,
    validate_split_parameters,
)
from mario.ops.cvxlab_bridge import (
    create_split_input_data,
    optimize_split_in_cvxlab,
)
from mario.ops.balance import ras as ras_balance_matrix
from mario.utils import (
    _manage_indeces,
    check_clusters,
)

from mario.ops.excel import _sh_excel

from mario.views import plots as plt

from mario.compute.primitives import (
    calc_all_shock,
    calc_X,
    linkages_calculation,
)
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.views import (
    concat_sut_Y,
    concat_sut_b,
    concat_sut_e,
    concat_sut_g,
    concat_sut_v,
    concat_sut_z,
)
from mario.clusters import build_default_clusters, build_region_aggregation_index

import numpy as np
import pandas as pd
import logging
import copy
import os
import tempfile
import warnings
from typing import Dict
import plotly.express as px


from mario.model.conventions import MATRIX_TITLES, TABLE_LEVELS
from mario.model.conventions import _MASTER_INDEX, _ENUM

from mario.api.core_model import CoreModel
from mario.ops import (
    aggregate_database,
    build_new_instance_from_scenario,
    export_database_to_excel,
    export_database_to_parquet,
    export_database_to_pymrio,
    export_database_to_txt,
    transform_sut_to_iot,
    transform_to_chenery_moses,
)
from mario.views import build_database_frame

logger = logging.getLogger(__name__)

try:
    import cvxpy as cp

    __cvxpy__ = True
except ModuleNotFoundError:
    __cvxpy__ = False


class Database(CoreModel):
    """Main user-facing database class."""

    def __init__(
        self,
        name: str = "unknow",
        table: str = None,
        Z: pd.DataFrame = None,
        E: pd.DataFrame = None,
        V: pd.DataFrame = None,
        Y: pd.DataFrame = None,
        EY: pd.DataFrame = None,
        VY: pd.DataFrame = None,
        units: Dict = None,
        price: str = None,
        source: str = None,
        tech_assumption: str | None = None,
        **kwargs,
    ):
        """Initialize a MARIO database object.

        Parameters
        ----------
        name:
            Human-readable database name stored in metadata.
        table:
            Table kind, usually ``"IOT"`` or ``"SUT"``.
        Z, E, V, Y, EY, VY:
            Baseline matrices used when building the object directly from
            pandas objects. ``VY`` is optional.
        units:
            Units mapping consistent with the database structure.
        price:
            Price system label stored in metadata.
        source:
            Source label stored in metadata.
        tech_assumption:
            Optional SUT technology assumption stored on the database
            metadata. Accepted values are ``"industry-based"``,
            ``"product-based"``, ``"IT"`` and ``"PT"``.
        **kwargs:
            Extra options forwarded to ``CoreModel``. Parsers typically use
            these to bootstrap the instance from parsed matrices.
        """

        super().__init__(
            name=name,
            table=table,
            Z=Z,
            E=E,
            V=V,
            Y=Y,
            EY=EY,
            VY=VY,
            units=units,
            price=price,
            source=source,
            tech_assumption=tech_assumption,
            **kwargs,
        )

        if __cvxpy__:
            self.__solver = cp.ECOS

        # A counter for saving the results in a dictionary
        self.__counter = 1  # Shock Counter
        self._clusters = {}

    @property
    def clusters(self):
        """Return the currently stored user-defined shock clusters."""
        return copy.deepcopy(self._clusters)

    @property
    def default_clusters(self):
        """Return the automatically generated default shock clusters."""
        return build_default_clusters(self)

    @property
    def available_clusters(self):
        """Return the effective clusters available to shock helpers."""
        return self._resolved_clusters()

    def _normalize_cluster_mapping(self, clusters=None, *, raise_on_missing=True):
        """Normalize a cluster payload to canonical MARIO set labels."""
        normalized = {}
        if clusters is None:
            return normalized

        if not isinstance(clusters, dict):
            raise WrongInput("clusters should be a mapping of set -> cluster definitions.")

        for level, level_clusters in clusters.items():
            resolved_level = self._resolve_set_name(
                level,
                allow_codes=True,
                raise_on_missing=raise_on_missing,
            )
            if resolved_level is None:
                continue

            if not isinstance(level_clusters, dict):
                raise WrongInput(
                    f"clusters[{level!r}] should be a mapping of cluster name -> items."
                )

            target = normalized.setdefault(resolved_level, {})
            for cluster_name, members in level_clusters.items():
                if isinstance(members, str):
                    members = [members]
                else:
                    members = list(members)
                target[str(cluster_name)] = members

        return normalized

    def _resolved_clusters(self, clusters=None, legacy_clusters=None):
        """Merge stored, legacy and explicit cluster payloads with clear precedence."""
        resolved = copy.deepcopy(self.default_clusters)

        for payload in (self._clusters, legacy_clusters or {}, clusters or {}):
            normalized = self._normalize_cluster_mapping(payload)
            for level, level_clusters in normalized.items():
                resolved.setdefault(level, {}).update(level_clusters)

        return resolved

    def set_clusters(self, clusters=None, **legacy_clusters):
        """Persist reusable shock clusters on the database.

        Parameters
        ----------
        clusters:
            Preferred cluster payload using any supported set aliases.
        **legacy_clusters:
            Backward-compatible cluster payload passed as keyword arguments.
        """
        resolved = {}
        for payload in (legacy_clusters or {}, clusters or {}):
            normalized = self._normalize_cluster_mapping(payload)
            for level, level_clusters in normalized.items():
                resolved.setdefault(level, {}).update(level_clusters)
        check_clusters(index_dict=self.get_index("all"), table=self.table_type, clusters=resolved)
        self._clusters = resolved
        self.meta._add_history("Database: shock clusters updated.")

    def add_cluster(self, level, name, members):
        """Add or replace one stored shock cluster."""
        updated = self.clusters
        resolved_level = self._resolve_set_name(level, allow_codes=True)
        updated.setdefault(resolved_level, {})[str(name)] = (
            [members] if isinstance(members, str) else list(members)
        )
        self.set_clusters(clusters=updated)

    def clear_clusters(self):
        """Remove all stored shock clusters from the database."""
        self._clusters = {}
        self.meta._add_history("Database: shock clusters cleared.")

    def _normalize_aggregation_levels(self, levels):
        """Normalize requested aggregation levels to public set names."""
        if levels == "all":
            return [*TABLE_LEVELS[self.meta.table]]

        if isinstance(levels, str):
            levels = [levels]

        difference = set(levels).difference(set(self.sets))
        if difference:
            raise WrongInput(
                "{} is/are not an acceptable level/s for the database.\n"
                "Acceptable items are \n{}".format(
                    difference,
                    self.sets,
                )
            )

        return list(levels)

    def _prepare_aggregation_inputs(self, io, levels, region_aggregation):
        """Merge optional Region aggregation presets with workbook or dict inputs."""
        resolved_levels = self._normalize_aggregation_levels(levels)
        region_index = build_region_aggregation_index(self, region_aggregation)

        if region_index is None:
            return io, resolved_levels

        if _MASTER_INDEX["r"] not in resolved_levels:
            resolved_levels = [_MASTER_INDEX["r"], *resolved_levels]

        if io is None:
            return {_MASTER_INDEX["r"]: region_index}, resolved_levels

        if isinstance(io, dict):
            merged = copy.deepcopy(io)
        else:
            workbook = pd.ExcelFile(io)
            merged = {}
            for level in resolved_levels:
                if level == _MASTER_INDEX["r"] and level not in workbook.sheet_names:
                    continue
                merged[level] = workbook.parse(sheet_name=level, index_col=0)

        merged.setdefault(_MASTER_INDEX["r"], region_index)
        return merged, resolved_levels

    def build_new_instance(self, scenario):
        """Build a new database whose baseline is the selected scenario.

        Parameters
        ----------
        scenario:
            Scenario to promote as the baseline of the returned object.

        Returns
        -------
        Database
            New database instance containing the selected scenario as baseline.
        """

        return build_new_instance_from_scenario(self, scenario)

    def ras(
        self,
        target_rows,
        target_cols,
        scenario: str = "baseline",
        inplace: bool = True,
        calc_all: bool = True,
        notes=None,
        tol: float = 1e-8,
        max_iter: int = 1000,
    ):
        """Balance the ``Z`` block of one IOT scenario with the RAS method.

        Parameters
        ----------
        target_rows:
            Desired row sums for the ``Z`` matrix.
        target_cols:
            Desired column sums for the ``Z`` matrix.
        scenario:
            Scenario whose ``Z`` block should be balanced.
        inplace:
            When ``True``, mutate the current database. When ``False``, return
            a balanced copy.
        calc_all:
            When ``True``, recompute the standard dependent matrices after
            replacing ``Z``.
        notes:
            Optional user notes appended to metadata history.
        tol:
            Absolute convergence tolerance passed to :func:`mario.ras`.
        max_iter:
            Maximum number of RAS iterations.

        Returns
        -------
        Database | None
            Balanced database when ``inplace=False``, otherwise ``None``.
        """
        if self.table_type != "IOT":
            raise WrongInput("ras is only available for IOT databases.")

        if not inplace:
            new = self.copy()
            new.ras(
                target_rows=target_rows,
                target_cols=target_cols,
                scenario=scenario,
                inplace=True,
                calc_all=calc_all,
                notes=notes,
                tol=tol,
                max_iter=max_iter,
            )
            return new

        self._validate_scenario(scenario)

        balanced_Z = ras_balance_matrix(
            self._get_matrix(_ENUM.Z, scenario=scenario, auto_calc=True),
            target_rows=target_rows,
            target_cols=target_cols,
            tol=tol,
            max_iter=max_iter,
        )

        self.reset_to_flows(scenario=scenario)
        self.set_block(_ENUM.Z, balanced_Z, scenario=scenario)

        if calc_all:
            self.calc_all(scenario=scenario)

        log_time(logger, f"Database: {scenario} balanced with RAS.")
        self.meta._add_history(
            f"Database: scenario '{scenario}' balanced with RAS on Z "
            f"(tol={tol}, max_iter={max_iter})."
        )

        if notes:
            if isinstance(notes, str):
                notes = [notes]
            for note in notes:
                self.meta._add_history(f"User note: {note}")

    def to_iot(
        self,
        method,
        inplace=True,
    ):
        """Transform a SUT database into an IOT database.

        Parameters
        ----------
        method:
            SUT-to-IOT transformation method understood by the transformation
            engine.
        inplace:
            When ``True``, mutate the current database. When ``False``, return
            a transformed copy.

        Returns
        -------
        Database | None
            Transformed database when ``inplace=False``, otherwise ``None``.
        """
        return transform_sut_to_iot(self, method, inplace=inplace)

    def to_chenery_moses(
        self,
        inplace: bool = True,
        scenarios: list = None,
    ):
        """Transform an Isard SUT into a Chenery-Moses SUT.

        Parameters
        ----------
        inplace:
            When ``True``, mutate the current database. When ``False``, return
            a transformed copy.
        scenarios:
            Optional subset of scenarios to transform. When omitted, the
            transformation applies to all available scenarios.

        Returns
        -------
        Database | None
            Transformed database when ``inplace=False``, otherwise ``None``.
        """
        return transform_to_chenery_moses(
            self,
            inplace=inplace,
            scenarios=scenarios,
        )

    def get_aggregation_excel(
        self,
        path=None,
        levels="all",
        overwrite=False,
        region_aggregation=None,
    ):
        """Write an aggregation template workbook for the selected levels.

        Parameters
        ----------
        path:
            Output path for the workbook. When omitted, MARIO writes to the
            default Excel output directory.
        levels:
            One classification level, an iterable of levels, or ``"all"`` to
            include every aggregable level for the current table type.
        overwrite:
            When ``True``, replace an existing workbook at ``path``.
        region_aggregation:
            Optional Region prefill used to aggregate regions without manually
            editing the ``Region`` sheet. Accepted values are preset strings
            such as ``"continent"``, ``"UNregion"``, ``"EU"``, ``"OECD"``,
            ``"G7"`` and ``"G20"``, or an explicit mapping/Series/DataFrame.

        Returns
        -------
        None
            The workbook is written to disk.
        """

        _, levels = self._prepare_aggregation_inputs(
            io=None,
            levels=levels,
            region_aggregation=region_aggregation,
        )
        region_index = build_region_aggregation_index(self, region_aggregation)

        output_path = self._getdir(path, "Excels", "Aggregation.xlsx")
        if os.path.exists(output_path) and not overwrite:
            raise WrongInput(
                f"Aggregation workbook '{output_path}' already exists. "
                "Pass overwrite=True to replace it."
            )
        output_dir = os.path.dirname(output_path) or "."
        temp_handle = tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            dir=output_dir,
            delete=False,
        )
        temp_path = temp_handle.name
        temp_handle.close()

        try:
            with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
                for level in levels:
                    if level == _MASTER_INDEX["r"] and region_index is not None:
                        data = region_index.copy()
                    else:
                        data = pd.DataFrame(
                            index=self.get_index(level), columns=["Aggregation"]
                        )
                    data.to_excel(writer, sheet_name=level)
            os.replace(temp_path, output_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def read_aggregated_index(
        self,
        io,
        levels="all",
        ignore_nan=False,
    ):
        """Load aggregation mappings without applying them yet.

        Parameters
        ----------
        io:
            Either the path to an aggregation workbook or a
            ``{level: dataframe}`` mapping shaped like that workbook.
        levels:
            One classification level, an iterable of levels, or ``"all"`` to
            read every aggregable level for the current table type.
        ignore_nan:
            When ``True``, missing aggregation targets are interpreted as
            identity mappings for those labels.

        Returns
        -------
        None
            Aggregation mappings are stored on ``self._indeces`` under the
            ``"aggregated"`` level.
        """

        if levels != "all":
            # To avoid any issue, in case that levels is a string, return a list instead of str
            if isinstance(levels, str):
                levels = [levels]

            for level in levels:
                if level not in [*TABLE_LEVELS[self.meta.table]]:
                    raise WrongInput(
                        "'{}' is not an acceptable label for the database.\n"
                        "Acceptable items are \n{}".format(
                            level, [*TABLE_LEVELS[self.meta.table]]
                        )
                    )

        if levels == "all":
            levels = [*TABLE_LEVELS[self.meta.table]]

        indeces = {}
        for level in levels:
            if isinstance(io, dict):
                # Reading the aggregation data from a dict of pd.DataFrames similar to the Excel file
                index = io[level]
            else:
                # Reading the aggregation data from a single Excel file with differetn sheets '''

                index = pd.read_excel(io, sheet_name=level, index_col=0)
                index.index = index.index.fillna("None")

            if index.shape[1] > 1:
                index = index.iloc[:, 0].to_frame()

            difference = set(index.index).difference(set(self.get_index(level)))

            if difference:
                raise WrongInput(
                    f"Following item are not acceptable for level {level} \n {difference}"
                )

            index.columns = ["Aggregation"]

            if index.isnull().values.any():
                index = index.astype({"Aggregation": object})
                isna = index.isna()
                nans = isna.loc[isna["Aggregation"] == True].index
                if ignore_nan:
                    log_time(
                        logger,
                        "nan values for the aggregation of {} for following items ignored\n{}".format(
                            level, list(nans)
                        ),
                        "warning",
                    )

                    index.loc[nans, "Aggregation"] = list(nans)
                else:
                    raise DataMissing(
                        "nan values found for the aggregation of {} for following items."
                        " if ignore_nan = True, nan items will be ignored and no aggregation on the items will be considered\n {}".format(
                            level, list(nans)
                        )
                    )

            indeces[level] = index

        for level in levels:
            self._indeces[TABLE_LEVELS[self.meta.table][level]]["aggregated"] = indeces[
                level
            ]

    def aggregate(
        self,
        io,
        drop=["unused"],
        levels="all",
        calc_all=True,
        ignore_nan=False,
        zero_output_epsilon: float | None = 1e-30,
        inplace=True,
        region_aggregation=None,
    ):
        """Aggregate one or more classification levels in the database.

        Parameters
        ----------
        io:
            Aggregation definition, either as workbook path or as an in-memory
            mapping shaped like ``get_aggregation_excel(...)`` output.
        drop:
            Labels to drop after aggregation. The historical default
            ``["unused"]`` removes placeholder groups created during workbook
            editing.
        levels:
            One classification level, an iterable of levels, or ``"all"``.
        calc_all:
            When ``True``, recompute the standard dependent matrices after
            aggregation.
        ignore_nan:
            When ``True``, missing aggregation targets are treated as
            no-aggregation identity mappings.
        zero_output_epsilon:
            Positive fallback used to preserve non-zero coefficients for
            zero-output columns during aggregation. Pass ``None`` to disable
            the fallback.
        inplace:
            When ``True``, mutate the current database. When ``False``, return
            an aggregated copy.
        region_aggregation:
            Optional Region aggregation preset or explicit mapping applied even
            when ``io`` is ``None``. When a workbook or dict is also provided,
            MARIO uses the explicit ``Region`` sheet if present and otherwise
            injects the generated Region mapping.

        Returns
        -------
        Database | None
            Aggregated database when ``inplace=False``, otherwise ``None``.
        """

        io, levels = self._prepare_aggregation_inputs(
            io=io,
            levels=levels,
            region_aggregation=region_aggregation,
        )

        return aggregate_database(
            self,
            io=io,
            drop=drop,
            levels=levels,
            calc_all=calc_all,
            ignore_nan=ignore_nan,
            zero_output_epsilon=zero_output_epsilon,
            inplace=inplace,
        )

    def get_extensions_excel(
        self,
        matrix,
        path=None,
    ):
        """Write an Excel template for adding extensions to ``E`` or ``V``.

        Parameters
        ----------
        matrix:
            Target extension matrix. Accepted values are ``"E"`` and ``"V"``.
        path:
            Output path for the workbook. When omitted, MARIO writes to the
            default Excel output directory.

        Returns
        -------
        None
            The template workbook is written to disk.
        """

        aceptables = [_ENUM.E, _ENUM.V]

        if matrix.upper() not in aceptables:
            raise WrongInput(f"Acceptable matrix are: \n {[*aceptables]}")

        data = self.get_data(
            matrices=[matrix], units=False, indeces=False, format="dict"
        )["baseline"][matrix]

        extensions = pd.DataFrame(index=[""], columns=data.columns)

        with pd.ExcelWriter(self._getdir(path, "Excels", "Extensions.xlsx")) as writer:
            extensions.to_excel(writer)

    def add_extensions(
        self,
        io,
        matrix,
        units,
        inplace=True,
        calc_all=True,
        notes=None,
        EY=None,
    ):
        """Add new extensions to value added or satellite accounts.

        Parameters
        ----------
        io:
            Extension data as either a dataframe or a path to the Excel
            template generated by ``get_extensions_excel(...)``.
        matrix:
            Target matrix to extend. Accepted values are ``v``, ``V``, ``e``
            and ``E``.
        units:
            Unit table for the newly added rows.
        inplace:
            When ``True``, mutate the current database. When ``False``, return
            a modified copy.
        calc_all:
            When ``True``, recompute dependent matrices after inserting the new
            rows.
        notes:
            Optional user notes appended to metadata history.
        EY:
            Optional final-demand satellite account rows used when extending the
            environmental account side.

        Returns
        -------
        Database | None
            Modified database when ``inplace=False``, otherwise ``None``.
        """

        if not inplace:
            new = self.copy()
            new.add_extensions(
                io=io,
                matrix=matrix,
                inplace=True,
                units=units,
                calc_all=calc_all,
                notes=notes,
                EY=EY,
            )

            return new

        # This function can be implemented only in the following matrices
        if matrix not in [_ENUM.v, _ENUM.V, _ENUM.e, _ENUM.E]:
            raise WrongInput(
                "Acceptable items for matrix are:\n{}".format(
                    [_ENUM.v, _ENUM.V, _ENUM.e, _ENUM.E]
                )
            )

        all_matrices = [_ENUM.v, _ENUM.V, _ENUM.e, _ENUM.E, _ENUM.EY, _ENUM.Z, _ENUM.Y]

        if matrix.upper() == matrix:
            all_matrices.remove(matrix.lower())
        else:
            all_matrices.remove(matrix.upper())

        matrix_id = "f" if matrix.upper() == _ENUM.V else "k"

        info = self.query(
            matrices=all_matrices,
        )
        info["units"] = copy.deepcopy(self.units)

        if isinstance(io, pd.DataFrame):
            data = io
        elif isinstance(io, str):
            # read the Excel file form the user input
            data = pd.read_excel(io, index_col=0, header=[0, 1, 2]).fillna(0)
        else:
            raise WrongInput("data can be an Excel file or a DataFrame.")

        # # check if the format of the file is correct
        if not data.columns.equals(info[matrix].columns):
            raise WrongExcelFormat(
                "The data has not a correct format. To take the right format, get_extensions_excel function can be used."
            )

        log_time(
            logger,
            "Using add extensions will rewrite the new results on the baseline and delete other scenarios",
            "warning",
        )

        data = data.sort_index()
        units = units.sort_index()
        # check the consistency of units with items
        if not data.index.equals(units.index):
            raise WrongInput(
                "units dataframe should has exactly the same index levels of io"
            )

        if EY is not None and matrix_id == "k":
            EY = EY.sort_index()

            if not data.index.equals(EY.index):
                raise WrongInput(
                    "EY dataframe should has exactly the same index levels of io"
                )

            # # check if the format of the file is correct
            if not EY.columns.equals(info["EY"].columns):
                raise WrongInput("The EY has not correct columns.")

        try:
            units.columns = ["unit"]
        except ValueError:
            raise WrongInput("units dataframe columns does not have correct format.")

        to_add = data.index.difference(info[matrix].index)

        info[matrix] = pd.concat([info[matrix], data.loc[to_add, :]])

        if matrix_id == "k":
            if EY is None:
                info["EY"] = pd.concat(
                    [
                        info["EY"],
                        pd.DataFrame(0, index=to_add, columns=info["EY"].columns),
                    ]
                )
            else:
                info["EY"] = pd.concat([info["EY"], EY.loc[to_add, :]])

        unit_item = _MASTER_INDEX[matrix_id]
        info["units"][unit_item] = pd.concat(
            [info["units"][unit_item], units.loc[to_add]]
        )

        units = info["units"]
        del info["units"]

        matrices = {"baseline": {**info}}

        for scenario in self.scenarios:
            log_time(logger, f"{scenario} deleted from the database", "warning")
            self.meta._add_history(f"{scenario} deleted from the database")

        self.matrices = matrices

        self.meta._add_history(
            f"Modification: new '{_MASTER_INDEX[matrix_id]}' added to the database as follow:\n"
            f"{to_add.tolist()}"
        )
        self.units = units
        self._indeces[matrix_id]["main"].extend(to_add.tolist())

        if calc_all:
            self.calc_all()

        if notes:
            for note in notes:
                self.meta._add_history(f"User note: {note}")

    def to_region_subset(self, regions, inplace=True, trade_mode="aggregate"):
        """Keep one explicit region subset and externalize the remaining regions.

        Parameters
        ----------
        regions:
            One region label or an iterable of region labels to keep explicit.
        inplace:
            When ``True``, mutate the current database. When ``False``, return
            a transformed copy.
        trade_mode:
            ``"aggregate"`` collapses the excluded regions into one aggregated
            imports row plus export categories. ``"by_region"`` keeps one
            explicit import row and one explicit export category per excluded
            region.

        Returns
        -------
        Database | None
            Transformed database when ``inplace=False``, otherwise ``None``.

        Notes
        -----
        The selected regions keep their endogenous transactions with each other.
        All excluded regions are moved outside the endogenous system and are
        represented as exogenous imports and exports.

        Use ``trade_mode="aggregate"`` to collapse the excluded regions into a
        single ``imports`` row plus aggregate export categories, or
        ``trade_mode="by_region"`` to preserve one import row and one export
        category per excluded region.

        Examples
        --------
        Keep ``IT`` and ``FR`` explicit while treating the remaining regions as
        exogenous trade::

            subset = db.to_region_subset(["IT", "FR"], inplace=False)

        Keep the same subset but preserve exogenous trade partner detail::

            subset = db.to_region_subset(
                ["IT", "FR"],
                inplace=False,
                trade_mode="by_region",
            )
        """
        if not inplace:
            new = self.copy()
            new.to_region_subset(
                regions=regions,
                inplace=True,
                trade_mode=trade_mode,
            )

            return new

        if self.is_hybrid:
            raise NotImplementable("Hybrid tables are not supported.")

        if not self.is_multi_region:
            raise NotImplementable("Database is already a single region database.")

        if isinstance(regions, str):
            requested_regions = [regions]
        else:
            requested_regions = list(regions)

        if not requested_regions:
            raise WrongInput("At least one region should be selected.")

        if len(set(requested_regions)) != len(requested_regions):
            raise WrongInput("Repeated regions are not allowed in the selected subset.")

        available_regions = self.get_index(_MASTER_INDEX["r"])
        selected_regions = [
            region for region in available_regions if region in set(requested_regions)
        ]
        missing_regions = set(requested_regions).difference(set(available_regions))

        if missing_regions:
            raise WrongInput(
                "{} does/do not exist in regions".format(sorted(missing_regions))
            )

        if len(selected_regions) == len(available_regions):
            raise WrongInput(
                "Selected regions already cover the full database; choose a strict subset."
            )

        if trade_mode not in {"aggregate", "by_region"}:
            raise WrongInput(
                "trade_mode should be either 'aggregate' or 'by_region'."
            )

        excluded_regions = [
            region for region in available_regions if region not in set(selected_regions)
        ]

        log_time(
            logger,
            "All the scenarios will be deleted to build up the new baseline.",
            "warning",
        )

        data = self.query(
            matrices=[_ENUM.Y, _ENUM.X, _ENUM.Z, _ENUM.V, _ENUM.E, _ENUM.EY, _ENUM.VY],
        )

        Z = data[_ENUM.Z]
        V = data[_ENUM.V]
        Y = data[_ENUM.Y]
        E = data[_ENUM.E]
        EY = data[_ENUM.EY]
        VY = data[_ENUM.VY]

        selected_axis = (selected_regions, slice(None), slice(None))
        excluded_axis = (excluded_regions, slice(None), slice(None))

        imports_from_excluded = Z.loc[excluded_axis, selected_axis]
        exports_to_excluded = Z.loc[selected_axis, excluded_axis]
        Z = Z.loc[selected_axis, selected_axis]

        V = V.loc[:, selected_axis]
        if trade_mode == "aggregate":
            import_rows = imports_from_excluded.sum(axis=0).to_frame().T
            import_labels = ["imports"]
            import_rows.index = import_labels
        else:
            import_rows = (
                imports_from_excluded.groupby(level=0, sort=False).sum().reindex(excluded_regions)
            )
            import_labels = [f"imports from {region}" for region in excluded_regions]
            import_rows.index = import_labels
        V = pd.concat([V, import_rows])

        Y_local = Y.loc[selected_axis, selected_axis]
        Y_exports_to_excluded = Y.loc[selected_axis, excluded_axis]

        def _build_export_frame(source, item_label_template):
            if trade_mode == "aggregate":
                export_item_labels = [item_label_template]
            else:
                export_item_labels = [
                    f"{item_label_template} to {region}" for region in excluded_regions
                ]

            export_columns = pd.MultiIndex.from_tuples(
                [
                    (region, _MASTER_INDEX["n"], item_label)
                    for region in selected_regions
                    for item_label in export_item_labels
                ],
                names=Y.columns.names,
            )
            export_frame = pd.DataFrame(0.0, index=source.index, columns=export_columns)

            for region in selected_regions:
                row_mask = source.index.get_level_values(0) == region
                if not row_mask.any():
                    continue

                region_rows = source.loc[row_mask]
                if trade_mode == "aggregate":
                    export_frame.loc[
                        row_mask,
                        (region, _MASTER_INDEX["n"], item_label_template),
                    ] = region_rows.sum(axis=1).to_numpy(dtype=float)
                    continue

                for excluded_region in excluded_regions:
                    export_frame.loc[
                        row_mask,
                        (
                            region,
                            _MASTER_INDEX["n"],
                            f"{item_label_template} to {excluded_region}",
                        ),
                    ] = region_rows.loc[
                        :, (excluded_region, slice(None), slice(None))
                    ].sum(axis=1).to_numpy(dtype=float)

            return export_frame, export_item_labels

        Y_final_demand_exports, fd_export_labels = _build_export_frame(
            Y_exports_to_excluded,
            "Final Demand exports",
        )
        Y_intermediate_exports, intermediate_export_labels = _build_export_frame(
            exports_to_excluded,
            "Intermediate exports",
        )

        Y = pd.concat([Y_local, Y_final_demand_exports, Y_intermediate_exports], axis=1)

        export_columns = Y_final_demand_exports.columns.append(Y_intermediate_exports.columns)
        EY = EY.loc[:, selected_axis]
        EY = pd.concat(
            [
                EY,
                pd.DataFrame(0.0, index=EY.index, columns=export_columns),
            ],
            axis=1,
        )

        VY = VY.loc[:, selected_axis]
        VY = pd.concat(
            [
                VY,
                pd.DataFrame(0.0, index=VY.index, columns=export_columns),
            ],
            axis=1,
        )

        E = E.loc[:, selected_axis]
        X = calc_X(Z=Z, Y=Y)

        all_indeces = self.get_index("all")

        new_indeces = {
            "r": selected_regions,
            "f": all_indeces[_MASTER_INDEX["f"]] + import_labels,
            "n": all_indeces[_MASTER_INDEX["n"]]
            + fd_export_labels
            + intermediate_export_labels,
        }

        _manage_indeces(self, "single_region", **new_indeces)

        for scenario in self.scenarios:
            log_time(logger, f"Transformation: {scenario} deleted from the database.")

        self.matrices = {"baseline": {}}
        for matrix in ["Y", "Z", "E", "EY", "VY", "V", "X"]:
            self.matrices["baseline"][_ENUM[matrix]] = eval(matrix)
        log_time(logger, "Transformation: New baseline added to the database")

        slicer = _MASTER_INDEX["a"] if self.table_type == "SUT" else _MASTER_INDEX["s"]
        for import_label in import_labels:
            self.units[_MASTER_INDEX["f"]].loc[import_label, "unit"] = self.units[
                slicer
            ].iloc[0, 0]

        region_note = ", ".join(selected_regions)
        self.meta._add_history(
            "Transformation: Database transformed into a region subset database keeping "
            f"{region_note}."
        )
        if trade_mode == "aggregate":
            self.meta._add_history(
                "Transformation: Excluded regions are aggregated into one 'imports' row in "
                "the Value Added Matrix and two export categories in the Final Demand Matrix."
            )
        else:
            self.meta._add_history(
                "Transformation: Excluded regions are kept separate as one import row and one "
                "pair of export categories per excluded region."
            )
        self.meta._add_history(
            "Transformation: The Final Demand emissions are considered only for endogenous "
            "final demand columns."
        )

    def to_single_region(self, region, inplace=True, trade_mode="aggregate"):
        """Extract one region from a multi-regional database.

        Parameters
        ----------
        region:
            Region label to keep.
        inplace:
            When ``True``, mutate the current database. When ``False``, return
            a transformed copy.
        trade_mode:
            ``"aggregate"`` collapses all excluded regions into aggregated
            imports and export categories. ``"by_region"`` keeps one explicit
            import row and one explicit export category per excluded region.

        Returns
        -------
        Database | None
            Single-region database when ``inplace=False``, otherwise ``None``.

        Notes
        -----
        This is a convenience wrapper around ``to_region_subset([region], ...)``.
        Use ``to_region_subset(...)`` when you need to keep more than one region
        explicit while externalizing the rest of the world.
        """
        return self.to_region_subset(
            regions=[region],
            inplace=inplace,
            trade_mode=trade_mode,
        )

    def calc_linkages(
        self,
        scenario="baseline",
        normalized=True,
        cut_diag=True,
        multi_mode=True,
    ):
        r"""Calculate backward and forward linkages for one scenario.

        Parameters
        ----------
        scenario:
            Scenario to analyse.
        normalized:
            When ``True``, normalize linkage indicators using the standard
            linkages convention.
        cut_diag:
            When ``True``, exclude diagonal terms from the calculation.
        multi_mode:
            When ``True``, preserve the multi-regional interpretation of the
            linkages. This is valid only for multi-regional databases.

        Returns
        -------
        object
            Linkages payload returned by ``linkages_calculation(...)``.
        """

        if not self.is_multi_region and multi_mode:
            raise NotImplementable(
                "multi_mode option is valid only for mult-regional data"
            )

        if self.meta.table == "SUT":
            blocks = self.query(
                matrices=[_ENUM.w, _ENUM.z, "bu", "bs", "gcc", "gca", "gac", "gaa"],
                scenarios=scenario,
            )
            ordering = SUTUnifiedOrderingPolicy.from_blocks(
                z=blocks[_ENUM.z],
                w=blocks[_ENUM.w],
                bu=blocks["bu"],
                bs=blocks["bs"],
                gcc=blocks["gcc"],
                gca=blocks["gca"],
                gac=blocks["gac"],
                gaa=blocks["gaa"],
            )
            _matrices = {
                _ENUM.w: blocks[_ENUM.w].copy(),
                _ENUM.z: blocks[_ENUM.z].copy(),
                _ENUM.b: concat_sut_b(blocks["bu"], blocks["bs"], ordering),
                _ENUM.g: concat_sut_g(
                    blocks["gcc"],
                    blocks["gca"],
                    blocks["gac"],
                    blocks["gaa"],
                    ordering,
                ),
            }
        else:
            _matrices = {
                name: value.copy()
                for name, value in self.query(
                    matrices=[_ENUM.w, _ENUM.b, _ENUM.z, _ENUM.g],
                    scenarios=scenario,
                ).items()
            }

        return linkages_calculation(
            cut_diag=cut_diag,
            matrices=_matrices,
            multi_mode=multi_mode,
            normalized=normalized,
        )

    @staticmethod
    def _warn_deprecated_plot_method(name: str, replacement: str) -> None:
        warnings.warn(
            f"'{name}' is deprecated and will be removed in a future MARIO release. Use '{replacement}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    @staticmethod
    def _normalize_plot_dimension_name(value, columns):
        if value is None:
            return None
        normalized = "".join(ch for ch in str(value).lower() if ch.isalnum())
        for column in columns:
            candidate = "".join(ch for ch in str(column).lower() if ch.isalnum())
            if candidate == normalized:
                return column
        return value

    def _normalize_legacy_plot_filters(self, filters: dict, columns) -> dict:
        normalized = {}
        for key, value in filters.items():
            if not key.startswith("filter_"):
                normalized[key] = value
                continue

            candidate = key[len("filter_") :]
            candidate = self._normalize_plot_dimension_name(candidate, columns)
            normalized[candidate] = value
        return normalized

    def _resolve_plot_output_path(self, path, default_name):
        if path is False:
            return None
        return self._getdir(path, "Plots", default_name)

    def plot(
        self,
        matrix=None,
        data=None,
        scenarios="baseline",
        base_scenario=None,
        difference="absolute",
        preset="overview",
        kind=None,
        x=None,
        y="Value",
        color=None,
        size=None,
        facet_row=None,
        facet_col=None,
        animation_frame=None,
        hover_name=None,
        hover_data=None,
        line_group=None,
        text=None,
        path_columns=None,
        filters=None,
        item=None,
        agg="sum",
        top_n=None,
        path=None,
        auto_open=True,
        layout=None,
        barmode="relative",
        log_x=False,
        log_y=False,
        title=None,
        return_data=False,
        **kwargs,
    ):
        """Build one interactive plot from a matrix or a prepared dataframe.

        Parameters
        ----------
        matrix:
            Matrix name to resolve, flatten and plot.
        data:
            Optional already-flat dataframe. Use this for custom derived views.
        scenarios:
            Scenario name or iterable of scenario names. Used only with
            ``matrix=...``.
        base_scenario:
            Optional reference scenario used to plot scenario differences.
        difference:
            Difference mode used with ``base_scenario``. Accepted values are
            ``"absolute"`` and ``"relative"``.
        preset:
            Convenience preset for the non-expert workflow. Accepted values are
            ``"overview"``, ``"composition"``, ``"trend"``,
            ``"heatmap"``, ``"treemap"`` and ``"sunburst"``.
        kind:
            Plotly Express chart type. When omitted, MARIO infers a sensible
            default from ``preset``.
        mappings:
            Standard Plotly Express mappings used in the advanced workflow.
            This includes ``x``, ``y``, ``color``, ``size``, ``facet_row``,
            ``facet_col``, ``animation_frame``, ``hover_name``,
            ``hover_data``, ``line_group`` and ``text``.
        path_columns:
            Hierarchy columns for ``treemap`` and ``sunburst`` plots.
        filters:
            Column filters applied after flattening. Example:
            ``{"Region_from": ["IT"], "Sector_to": ["Food"]}``.
        item:
            Optional shorthand filter applied on ``Level_from`` and
            ``Level_to`` when the selected matrix carries activity/commodity or
            sector semantics.
        agg:
            Aggregation applied before plotting.
        top_n:
            Optional cap on the number of ``x`` categories kept in the plot.
        path:
            Output HTML path. Pass ``False`` to skip HTML export.
        auto_open:
            When ``True``, open the generated HTML plot automatically.
        layout:
            Optional Plotly layout overrides.
        barmode:
            Bar stacking mode used for bar plots.
        log_x, log_y:
            Whether to use logarithmic scaling.
        title:
            Optional plot title.
        return_data:
            When ``True``, return ``(figure, plotted_dataframe)``.
        **kwargs:
            Additional keyword arguments forwarded to Plotly Express.

        Returns
        -------
        plotly.graph_objects.Figure | tuple
            The generated figure, or ``(figure, plotted_dataframe)`` when
            ``return_data=True``.
        """
        if matrix is None and data is None:
            raise WrongInput("Pass either 'matrix' or 'data' to plot(...).")
        if matrix is not None and data is not None:
            raise WrongInput("Pass either 'matrix' or 'data', not both.")

        if matrix is not None:
            plot_data = plt.build_matrix_plot_frame(
                self,
                matrix,
                scenarios=scenarios,
                base_scenario=base_scenario,
                difference=difference,
                filters=filters,
                item=item,
            )
            scenarios_list = [scenarios] if isinstance(scenarios, str) else list(scenarios)
            suffix = scenarios_list[0] if len(scenarios_list) == 1 else "multi"
            output_path = self._resolve_plot_output_path(
                path,
                f"{matrix}_{preset or kind or 'plot'}_{suffix}.html",
            )
            resolved_title = title or plt.matrix_title(matrix)
            if base_scenario is not None:
                resolved_title = f"{resolved_title} vs {base_scenario} ({difference})"
        else:
            if not isinstance(data, pd.DataFrame):
                raise WrongInput("'data' should be a pandas DataFrame.")
            plot_data = plt._apply_filters(data.copy(), filters)
            output_path = self._resolve_plot_output_path(path, f"{preset or kind or 'plot'}.html")
            resolved_title = title

        return plt.plot_frame(
            plot_data,
            kind=kind,
            preset=preset,
            x=x,
            y=y,
            color=color,
            size=size,
            facet_row=facet_row,
            facet_col=facet_col,
            animation_frame=animation_frame,
            hover_name=hover_name,
            hover_data=hover_data,
            line_group=line_group,
            text=text,
            path_columns=path_columns,
            path=output_path,
            auto_open=auto_open,
            layout=layout,
            top_n=top_n,
            agg=agg,
            barmode=barmode,
            log_x=log_x,
            log_y=log_y,
            title=resolved_title,
            return_data=return_data,
            **kwargs,
        )

    def plot_linkages(
        self,
        scenarios="baseline",
        normalized=True,
        cut_diag=True,
        multi_mode=False,
        path=None,
        plot="Total",
        auto_open=True,
        **config,
    ):
        """Deprecated wrapper for plotting linkage indicators.

        Parameters
        ----------
        scenarios:
            Scenario name or iterable of scenario names to plot.
        normalized:
            Forwarded to ``calc_linkages(...)``.
        cut_diag:
            Forwarded to ``calc_linkages(...)``.
        multi_mode:
            Forwarded to ``calc_linkages(...)``.
        path:
            Output HTML path. When omitted, MARIO writes to the default plots
            directory.
        plot:
            Linkage flavor to visualize. Accepted values are ``"Total"`` and
            ``"Direct"``.
        auto_open:
            When ``True``, open the generated HTML plot automatically.
        **config:
            Extra plotting options forwarded to the plotting backend.

        Returns
        -------
        None
            The plot is written to disk.
        """
        self._warn_deprecated_plot_method(
            "plot_linkages",
            "plot(data=..., kind=..., ...) after calling calc_linkages(...)",
        )
        if plot not in ["Total", "Direct"]:
            raise WrongInput(
                "{} is not an acceptable value. Acceptable values are:\n{}".format(
                    plot, ["Total", "Direct"]
                )
            )
        if isinstance(scenarios, str):
            scenarios = [scenarios]

        difference = set(scenarios).difference(self.scenarios)

        if difference:
            raise WrongInput(
                "Scenarios: {} do not exist in the database. Existing scenarios are:\n{}".format(
                    difference,
                    self.scenarios,
                )
            )

        data = {
            scenario: self.calc_linkages(
                scenario=scenario,
                normalized=normalized,
                cut_diag=cut_diag,
                multi_mode=multi_mode,
            )
            for scenario in scenarios
        }

        frame = plt.build_linkages_plot_frame(data, plot=plot)
        output_path = self._resolve_plot_output_path(path, "linkages.html")

        if multi_mode:
            return self.plot(
                data=frame,
                kind="bar",
                x=self._normalize_plot_dimension_name("Item", frame.columns),
                y="Value",
                color=self._normalize_plot_dimension_name("Region", frame.columns),
                facet_col="Measure",
                facet_row="Component",
                animation_frame="Scenario" if "Scenario" in frame.columns and frame["Scenario"].nunique() > 1 else None,
                preset=None,
                path=output_path,
                auto_open=auto_open,
                title=f"{plot} linkages",
                barmode=config.get("barmode", "relative"),
            )

        return self.plot(
            data=frame,
            kind="scatter",
            x=f"{plot} Forward",
            y=f"{plot} Backward",
            color=self._normalize_plot_dimension_name("Item", frame.columns),
            hover_name=self._normalize_plot_dimension_name("Region", frame.columns),
            animation_frame="Scenario" if "Scenario" in frame.columns and frame["Scenario"].nunique() > 1 else None,
            preset=None,
            path=output_path,
            auto_open=auto_open,
            title=f"{plot} linkages",
        )

    def to_excel(
        self,
        path=None,
        flows=True,
        coefficients=False,
        scenario="baseline",
        include_meta=False,
    ):
        """Export one scenario to the historical MARIO Excel format.

        Parameters
        ----------
        path:
            Output path or directory, depending on the exporter backend.
        flows:
            When ``True``, include flow matrices.
        coefficients:
            When ``True``, include coefficient matrices.
        scenario:
            Scenario to export.
        include_meta:
            When ``True``, export metadata together with matrices.

        Returns
        -------
        None
            Export files are written to disk.
        """

        return export_database_to_excel(
            self,
            path=path,
            flows=flows,
            coefficients=coefficients,
            scenario=scenario,
            include_meta=include_meta,
        )

    def to_txt(
        self,
        path=None,
        flows=True,
        coefficients=False,
        scenario="baseline",
        _format="txt",
        include_meta=False,
        sep=",",
        flat=False,
        separate_files=False,
    ):
        """Export one scenario as multiple text or CSV files.

        Parameters
        ----------
        path:
            Output path or directory.
        flows:
            When ``True``, include flow matrices.
        coefficients:
            When ``True``, include coefficient matrices.
        scenario:
            Scenario to export.
        _format:
            File format label accepted by the text exporter, typically
            ``"txt"`` or ``"csv"``.
        include_meta:
            When ``True``, export metadata together with matrices.
        sep:
            Column separator used by delimited exports.
        flat:
            ``False`` keeps the historical matrix-per-file layout.
            ``True`` writes one long-format data file plus a units file.
        separate_files:
            when ``flat=True``, also write one trimmed long-format file per
            matrix in the same export directory.

        Returns
        -------
        None
            Export files are written to disk.
        """

        return export_database_to_txt(
            self,
            path=path,
            flows=flows,
            coefficients=coefficients,
            scenario=scenario,
            _format=_format,
            include_meta=include_meta,
            sep=sep,
            flat=flat,
            separate_files=separate_files,
        )

    def to_parquet(
        self,
        path=None,
        flows=True,
        coefficients=False,
        scenario="baseline",
        include_meta=False,
        flat=False,
        separate_files=False,
    ):
        """Export one scenario as parquet files.

        Parameters
        ----------
        path:
            Output path or directory.
        flows:
            When ``True``, include flow matrices.
        coefficients:
            When ``True``, include coefficient matrices.
        scenario:
            Scenario to export.
        include_meta:
            When ``True``, export metadata together with matrices.
        flat:
            ``False`` writes one parquet file per matrix.
            ``True`` writes one long-format ``data.parquet`` plus
            ``units.parquet``.
        separate_files:
            when ``flat=True``, also write one trimmed long-format parquet file
            per matrix in the same export directory.

        Returns
        -------
        None
            Export files are written to disk.
        """

        return export_database_to_parquet(
            self,
            path=path,
            flows=flows,
            coefficients=coefficients,
            scenario=scenario,
            include_meta=include_meta,
            flat=flat,
            separate_files=separate_files,
        )

    def to_pymrio(
        self,
        satellite_account="satellite_account",
        factor_of_production="factor_of_production",
        include_meta=True,
        scenario="baseline",
        **kwargs,
    ):
        """Export an IOT database as a ``pymrio.IOSystem``.

        Parameters
        ----------
        satellite_account:
            Label used for the exported environmental extension account.
        factor_of_production:
            Label used for the exported value-added account.
        include_meta:
            When ``True``, attach MARIO metadata to the exported object.
        scenario:
            Scenario to export.
        **kwargs:
            Additional keyword arguments forwarded to the pymrio exporter.

        Returns
        -------
        object
            ``pymrio.IOSystem`` instance created from the selected scenario.
        """

        return export_database_to_pymrio(
            self,
            satellite_account=satellite_account,
            factor_of_production=factor_of_production,
            include_meta=include_meta,
            scenario=scenario,
            **kwargs,
        )

    def get_add_sectors_excel(
        self,
        path=None,
        items=None,
        regions=None,
        item=None,
        redefine_uncertainties=False,
        overwrite=False,
    ):
        """Write the add-sectors workbook template.

        Parameters
        ----------
        path:
            Output path for the workbook. When omitted, MARIO writes to the
            default Excel output folder.
        items:
            Optional item names to pre-populate in the master sheet. For IOT the
            items are sectors. For SUT they are interpreted according to
            ``item``. When omitted, an empty workbook skeleton is written.
        regions:
            Optional regions to pre-populate in the master sheet. When omitted
            and ``items`` are provided, all database regions are used.
        item:
            SUT-only selector that controls whether ``items`` should be written
            as activities, commodities, or both. ``None`` means both.
        redefine_uncertainties:
            When ``True``, include the editable uncertainties sheet in the
            workbook.

        Notes
        -----
        The old simple workbook is deprecated. This method now always writes the
        single workbook format consumed by ``read_add_sectors_excel(...)`` and
        ``add_sectors(...)``.
        """

        if items is None:
            items = []
        elif isinstance(items, str):
            items = [items]
        elif isinstance(items, tuple):
            items = list(items)

        if regions is None:
            regions = self.get_index(_MASTER_INDEX["r"]) if items else []
        elif isinstance(regions, str):
            regions = [regions]
        elif isinstance(regions, tuple):
            regions = list(regions)

        if not isinstance(items, list) or not isinstance(regions, list):
            raise WrongInput("'items' and 'regions' should be a list.")

        difference = set(regions).difference(self.get_index(_MASTER_INDEX["r"]))

        if difference:
            raise WrongInput(
                "Regions: {} do not exist in the database. Existing regions are:\n{}".format(
                    difference,
                    self.get_index(_MASTER_INDEX["r"]),
                )
            )

        if self.meta.table == "SUT" and item not in [
            _MASTER_INDEX["c"],
            _MASTER_INDEX["a"],
            None,
        ]:
            raise WrongInput(
                "For SUT, item should be {}, {} or None".format(
                    _MASTER_INDEX["c"], _MASTER_INDEX["a"]
                )
            )

        target = self._getdir(path, "Excels", "add_sectors.xlsx")
        if os.path.exists(target) and not overwrite:
            raise WrongInput(
                f"Add-sectors workbook '{target}' already exists. "
                "Pass overwrite=True to replace it."
            )
        write_add_sector_workbook(
            self,
            target,
            new_items=items,
            regions=regions,
            item=item,
            redefine_uncertainties=redefine_uncertainties,
        )

    def read_add_sectors_excel(self, path, get_inventories=False, read_inventories=False):
        """Read one add-sectors workbook and attach its metadata to the database.

        Parameters
        ----------
        path:
            Path to the add-sectors workbook.
        get_inventories:
            When ``True``, create any missing inventory-sheet templates in the
            workbook after reading the master sheet.
        read_inventories:
            When ``True``, also read and group the inventory sheets referenced
            by the workbook.

        Returns
        -------
        None
            Workbook metadata is stored on the current instance.

        Notes
        -----
        The method always stores the normalized master sheet, cluster maps and
        derived item sets on the database instance. When
        ``read_inventories=True`` it also groups the inventory sheets by target
        item and stores them on ``self.inventories``.
        """

        workbook = read_add_sector_workbook(
            path,
            table=self.meta.table,
            require_inventory_sheets=read_inventories,
        )
        self.add_sectors_workbook = workbook
        self.add_sectors_workbook_path = str(path)
        self.add_sectors_master = workbook.master_sheet
        self.regions_clusters = workbook.regions_clusters
        self.factors_clusters = workbook.factors_clusters
        self.uncertainty_values = workbook.uncertainty_values

        if self.meta.table == "IOT":
            self.sectors_clusters = workbook.item_clusters
            self.split_info = workbook.split_info or {}
            derived = derive_add_sector_sets(
                workbook,
                existing_sectors=self.get_index(_MASTER_INDEX["s"]),
            )
        else:
            self.commodities_clusters = workbook.item_clusters
            self.split_info = {}
            derived = derive_add_sector_sets(
                workbook,
                existing_activities=self.get_index(_MASTER_INDEX["a"]),
                existing_commodities=self.get_index(_MASTER_INDEX["c"]),
            )

        for key, value in derived.items():
            setattr(self, key, value)

        if get_inventories:
            self.get_inventory_sheets(path)
            workbook = read_add_sector_workbook(
                path,
                table=self.meta.table,
                require_inventory_sheets=False,
            )
            self.add_sectors_workbook = workbook

        if read_inventories:
            self.inventories = group_inventories_by_target(workbook)

    def get_inventory_sheets(self, path, overwrite=False):
        """Create inventory-sheet templates referenced by an add-sectors workbook.

        Parameters
        ----------
        path:
            Path to the add-sectors workbook.
        overwrite:
            When ``True``, replace inventory sheets that already exist in the
            workbook.

        Returns
        -------
        None
            Inventory templates are written into the workbook in place.
        """

        workbook = getattr(self, "add_sectors_workbook", None)
        workbook_path = getattr(self, "add_sectors_workbook_path", None)

        if workbook is None or workbook_path != str(path):
            self.read_add_sectors_excel(path, read_inventories=False)
            workbook = self.add_sectors_workbook

        write_inventory_templates_to_workbook(
            self,
            workbook,
            path,
            overwrite=overwrite,
        )
        workbook = read_add_sector_workbook(
            path,
            table=self.meta.table,
            require_inventory_sheets=False,
        )
        self.add_sectors_workbook = workbook
        self.add_sectors_workbook_path = str(path)

    def read_inventory_sheets(self, path):
        """Read and group inventory sheets from an add-sectors workbook.

        Parameters
        ----------
        path:
            Path to the add-sectors workbook.

        Returns
        -------
        dict
            Mapping keyed by target item name. Each value is a
            ``{sheet_name: dataframe}`` dictionary ready for the add-sectors
            engine.
        """

        workbook = getattr(self, "add_sectors_workbook", None)
        workbook_path = getattr(self, "add_sectors_workbook_path", None)

        if workbook is None or workbook_path != str(path):
            self.read_add_sectors_excel(path, read_inventories=False)
            workbook = self.add_sectors_workbook

        if not workbook.inventories_by_sheet:
            workbook = read_add_sector_workbook(
                path,
                table=self.meta.table,
                require_inventory_sheets=True,
            )
            self.add_sectors_workbook = workbook

        self.add_sectors_workbook_path = str(path)
        self.inventories = group_inventories_by_target(workbook)
        return self.inventories

    def add_sectors(
        self,
        io="inventories",
        scenario="baseline",
        inplace=True,
        split=False,
        keep_all_split_steps=False,
        notes=None,
        ignore_warnings=True,
        cvxlab_path=None,
        input_data_files_type="xlsx",
        only_input_data_gen=False,
        solver=None,
        solver_parameters=None,
        parent_name=None,
        parent_names=None,
        residue=None,
    ):
        """Apply the add-sectors workbook to the selected scenario.

        Parameters
        ----------
        io:
            Either a workbook path or the special value ``"inventories"``.
            When a path is provided, MARIO reads workbook metadata and grouped
            inventory sheets from that file first. When ``"inventories"`` is
            used, the caller is expected to have already loaded workbook state
            with ``read_add_sectors_excel(...)`` / ``read_inventory_sheets(...)``.
        scenario:
            Scenario to read the source coefficient blocks from.
        inplace:
            When ``False``, return a modified copy. When ``True``, the method
            mutates the current database and returns ``None``.
        notes:
            Optional metadata notes appended to the database history.
        ignore_warnings:
            Passed through to the engine for the handful of cases where the
            historical workflow intentionally muted warnings.
        split:
            When ``True`` and the table is an IOT, run the split workflow after
            the standard coefficient-side insertion.
        keep_all_split_steps:
            When ``False`` and ``split=True``, keep only the final available
            split result as ``baseline`` and discard intermediate scenarios such
            as ``original``, ``split_<scenario>``, and ``split_cvxlab``.
            When ``True``, preserve all intermediate split scenarios.
        cvxlab_path:
            Directory where MARIO should generate the CVXLab model directory.
        input_data_files_type:
            Format for the generated CVXLab input files. ``"xlsx"`` is fully
            supported. ``"csv"`` is available only for input-data generation.
        only_input_data_gen:
            When ``True``, stop after generating the CVXLab model directory and
            input data. No optimization run is executed.
        solver:
            Optional solver passed through to CVXLab.
        solver_parameters:
            Optional solver keyword arguments passed to CVXLab. When provided,
            they are forwarded as ``mosek_params`` to preserve the historical
            MARIO split workflow.
        parent_name:
            Optional new label for the residual parent sector when exactly one
            parent sector is being split.
        parent_names:
            Optional mapping of split child sector or parent sector -> new
            parent label. This is useful when you want the residual parent
            sector to be renamed after the split, for example
            ``{"Non metallic minerals": "Other non metallic minerals"}``.
        residue:
            Threshold for zeroing out small positive values in the CVXLab
            input data. Values strictly below this threshold are set to zero
            before writing the input files. When ``None`` (default), no
            correction is applied.

        Notes
        -----
        The workbook-driven non-split insertion always runs first. If
        ``split=True`` for an IOT, MARIO then builds a deterministic
        ``split_<scenario>`` flow scenario and optionally hands it to CVXLab.
        By default, the final available split scenario is then promoted back to
        ``baseline``.
        """
        if not inplace:
            new = self.copy()
            new.add_sectors(
                io=io,
                scenario=scenario,
                inplace=True,
                split=split,
                keep_all_split_steps=keep_all_split_steps,
                notes=notes,
                ignore_warnings=ignore_warnings,
                cvxlab_path=cvxlab_path,
                input_data_files_type=input_data_files_type,
                only_input_data_gen=only_input_data_gen,
                solver=solver,
                solver_parameters=solver_parameters,
                parent_name=parent_name,
                parent_names=parent_names,
                residue=residue,
            )
            return new

        self._validate_scenario(scenario)
        source_label = "loaded inventories" if io == "inventories" else os.fspath(io)
        workflow_context = (
            f"table {self.meta.table}, scenario {scenario!r}, split={split}, source {source_label!r}"
        )
        log_time(logger, f"Database: add_sectors started ({workflow_context}).")
        stage = "initialization"

        try:
            stage = "loading add-sectors inputs"
            if io != "inventories":
                self.read_add_sectors_excel(io, read_inventories=True)
            elif not hasattr(self, "inventories"):
                raise LackOfInput(
                    "Inventory sheets are not loaded. Pass an add-sectors workbook path "
                    "or call read_inventory_sheets(...) first."
                )

            stage = "validating split parameters"
            if split:
                validate_split_parameters(
                    self,
                    cvxlab_path=cvxlab_path,
                    input_data_files_type=input_data_files_type,
                    only_input_data_gen=only_input_data_gen,
                )
                prepare_split_support(self)
                resolved_parent_renames = normalize_split_parent_renames(
                    self,
                    parent_name=parent_name,
                    parent_names=parent_names,
                )
            else:
                if parent_name is not None or parent_names is not None:
                    raise WrongInput("parent_name and parent_names are supported only when split=True.")
                resolved_parent_renames = {}

            stage = "checking duplicate target items"
            item_to_query = _MASTER_INDEX["a"] if self.meta.table == "SUT" else _MASTER_INDEX["s"]
            duplicates = sorted(set(name for name in self.inventories if name in self.get_index(item_to_query)))
            if duplicates:
                raise WrongInput(f"Some items already exist in the table: {duplicates}")

            log_time(
                logger,
                "Database: All scenarios will be deleted from the database after add_sectors.",
                "warning",
            )

            stage = "collecting add-sectors reference matrices"
            original_reference = collect_add_sector_matrices(self, scenario=scenario) if split else None

            stage = "running add-sectors engine"
            result = run_add_sector_engine(
                self,
                scenario=scenario,
                ignore_warnings=ignore_warnings,
            )

            stage = "collecting baseline VY"
            baseline_vy = (
                self.get_block_as_pandas(_ENUM["VY"], scenario=scenario)
                if self.has_matrix(_ENUM["VY"], scenario=scenario)
                else self.resolve(_ENUM["VY"], scenario=scenario)
            )
        except (WrongInput, WrongExcelFormat, LackOfInput, NotImplementable, DataMissing) as exc:
            log_time(logger, f"Database: add_sectors failed during {stage} ({workflow_context}). {exc}", "error")
            raise
        except ValueError as exc:
            message = f"Database.add_sectors failed during {stage} ({workflow_context}). {exc}"
            log_time(logger, f"Database: add_sectors failed during {stage} ({workflow_context}). {exc}", "error")
            raise WrongInput(message) from exc

        if self.meta.table == "IOT":
            new_matrices, new_units, new_indeces, uncertainty_matrix = result
            baseline = {
                _ENUM["z"]: new_matrices[_ENUM["z"]],
                _ENUM["e"]: new_matrices[_ENUM["e"]],
                _ENUM["v"]: new_matrices[_ENUM["v"]],
                _ENUM["Y"]: new_matrices[_ENUM["Y"]],
                _ENUM["EY"]: new_matrices[_ENUM["EY"]],
                _ENUM["VY"]: baseline_vy,
            }
            self.uncertainty_matrix = uncertainty_matrix
            added_items = getattr(self, "new_sectors", [])
            added_label = _MASTER_INDEX["s"]
        else:
            new_matrices, new_units, new_indeces = result
            baseline = {
                _ENUM["z"]: new_matrices[_ENUM["z"]],
                _ENUM["u"]: new_matrices[_ENUM["u"]],
                _ENUM["s"]: new_matrices[_ENUM["s"]],
                _ENUM["e"]: new_matrices[_ENUM["e"]],
                _ENUM["v"]: new_matrices[_ENUM["v"]],
                _ENUM["Y"]: new_matrices[_ENUM["Y"]],
                _ENUM["EY"]: self.EY,
                _ENUM["VY"]: baseline_vy,
            }
            self.uncertainty_matrix = None
            added_items = {
                _MASTER_INDEX["a"]: getattr(self, "new_activities", []),
                _MASTER_INDEX["c"]: getattr(self, "new_commodities", []),
            }
            added_label = None

        if split and self.meta.table == "IOT":
            self.matrices = {
                "baseline": baseline,
                "original": {
                    _ENUM["Z"]: original_reference[_ENUM["Z"]],
                    _ENUM["E"]: original_reference[_ENUM["E"]],
                    _ENUM["V"]: original_reference[_ENUM["V"]],
                    _ENUM["Y"]: original_reference[_ENUM["Y"]],
                    _ENUM["EY"]: original_reference[_ENUM["EY"]],
                    _ENUM["VY"]: original_reference[_ENUM["VY"]],
                },
            }
        else:
            self.matrices = {"baseline": baseline}
        self.units = new_units
        self._indeces = new_indeces

        self.meta._add_history("Scenarios: all scenarios deleted from the database.")
        if self.meta.table == "IOT":
            self.meta._add_history(
                f"Database: new {added_label}: {added_items} added to the database"
            )
            log_time(logger, f"New {added_label}: {added_items} added to the database")
        else:
            self.meta._add_history(
                f"Database: new {_MASTER_INDEX['a']}: {added_items[_MASTER_INDEX['a']]} added to the database"
            )
            self.meta._add_history(
                f"Database: new {_MASTER_INDEX['c']}: {added_items[_MASTER_INDEX['c']]} added to the database"
            )
            log_time(logger, f"New {_MASTER_INDEX['a']}: {added_items[_MASTER_INDEX['a']]} added to the database")
            log_time(logger, f"New {_MASTER_INDEX['c']}: {added_items[_MASTER_INDEX['c']]} added to the database")

        if notes:
            for note in notes if isinstance(notes, list) else [notes]:
                self.meta._add_history(f"User note: {note}")

        if split:
            split_scenario = build_split_flow_scenario(
                self,
                base_scenario="baseline",
                scenario_label=scenario,
            )
            log_split_scenario(logger, split_scenario, getattr(self, "to_split_sectors", []))
            self.meta._add_history(
                f"Database: split flow scenario '{split_scenario}' generated for sectors {getattr(self, 'to_split_sectors', [])}"
            )

            if only_input_data_gen:
                dest_dir = create_split_input_data(
                    self,
                    main_dir_path=cvxlab_path,
                    scenario_label=scenario,
                    input_data_files_type=input_data_files_type,
                    residue=residue,
                )
                self.meta._add_history(
                    f"Database: CVXLab split input data generated in '{dest_dir}'."
                )
            else:
                optimized = optimize_split_in_cvxlab(
                    self,
                    main_dir_path=cvxlab_path,
                    scenario_label=scenario,
                    input_data_files_type=input_data_files_type,
                    solver=solver,
                    solver_parameters=solver_parameters,
                    residue=residue,
                )
                split_cvxlab = {
                    _ENUM["Z"]: optimized.get(_ENUM["Z"], self.matrices[split_scenario][_ENUM["Z"]]),
                    _ENUM["E"]: self.matrices[split_scenario][_ENUM["E"]],
                    _ENUM["V"]: optimized.get(_ENUM["V"], self.matrices[split_scenario][_ENUM["V"]]),
                    _ENUM["Y"]: optimized.get(_ENUM["Y"], self.matrices[split_scenario][_ENUM["Y"]]),
                    _ENUM["EY"]: self.matrices[split_scenario][_ENUM["EY"]],
                    _ENUM["VY"]: self.matrices[split_scenario][_ENUM["VY"]],
                }
                split_cvxlab[_ENUM["X"]] = calc_X(
                    split_cvxlab[_ENUM["Z"]],
                    split_cvxlab[_ENUM["Y"]],
                )
                self.matrices["split_cvxlab"] = split_cvxlab
                self.meta._add_history(
                    "Database: new scenario 'split_cvxlab' defined with optimized split-sector flows."
                )

            if resolved_parent_renames:
                rename_scenarios = ["baseline", split_scenario]
                if "split_cvxlab" in self.matrices:
                    rename_scenarios.append("split_cvxlab")
                apply_split_parent_renames(
                    self,
                    resolved_parent_renames,
                    scenarios=rename_scenarios,
                )
                self.meta._add_history(
                    f"Database: renamed split parent sectors {resolved_parent_renames}."
                )

            if not keep_all_split_steps:
                final_split_scenario = "split_cvxlab" if "split_cvxlab" in self.matrices else split_scenario
                self.matrices = {"baseline": self.matrices[final_split_scenario]}
                self.meta._add_history(
                    f"Database: scenario '{final_split_scenario}' promoted to 'baseline' and intermediate split scenarios removed."
                )

        return None

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
            Same compact payload shape as ``CoreModel.query(...)``.
        """
        return super().query(
            matrices=matrices,
            scenarios=scenarios,
            base_scenario=base_scenario,
            type=type,
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
            When ``True``, include unit tables in the returned payload.
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
            Optional reference scenario used to return scenario differences.
        type:
            Difference type used with ``base_scenario``. Accepted values are
            ``"absolute"`` and ``"relative"``.

        Returns
        -------
        object | dict
            Same payload shape as ``CoreModel.get_data(...)``.
        """
        return super().get_data(
            matrices=matrices,
            units=units,
            indeces=indeces,
            auto_calc=auto_calc,
            format=format,
            scenarios=scenarios,
            base_scenario=base_scenario,
            type=type,
        )

    def DataFrame(
        self,
        scenario="baseline",
    ):
        """Return a single dataframe view of one scenario.

        Parameters
        ----------
        scenario:
            Scenario to flatten into a dataframe.

        Returns
        -------
        pandas.DataFrame
            Long-form dataframe view built by ``build_database_frame(...)``.
        """

        return build_database_frame(self, scenario=scenario)

    def shock_calc(
        self,
        io,
        z=False,
        e=False,
        v=False,
        Y=False,
        clusters=None,
        notes=[],
        scenario=None,
        force_rewrite=False,
        **legacy_clusters,
    ):
        """Apply shocks to coefficients or demand and store the result as a scenario.

        Parameters
        ----------
        io:
            Shock definition source understood by the shock readers, typically
            an Excel workbook path.
        z, e, v, Y:
            Select which shock blocks should be read and applied from ``io``.
            For SUT databases, MARIO first looks for split-native worksheets:
            ``u``/``s`` for ``z``, ``va``/``vc`` for ``v``, ``ea``/``ec`` for
            ``e`` and ``Ya``/``Yc`` for ``Y``. When they are not present it
            falls back to the legacy unified worksheets ``z``, ``v``, ``e``
            and ``Y``.
        clusters:
            Preferred cluster payload. When omitted, MARIO uses clusters
            already stored on the database, optionally merged with any legacy
            keyword clusters.
        notes:
            Optional metadata notes attached to the created scenario.
        scenario:
            Name of the output scenario. When omitted, MARIO creates
            ``shock <n>`` automatically.
        force_rewrite:
            When ``True``, allow overwriting an existing non-baseline scenario.
        **legacy_clusters:
            Backward-compatible cluster mappings passed as keyword arguments.

        Returns
        -------
        None
            The shocked scenario is materialized on the current database.
        """

        # be sure that all the data exist

        if (scenario in self.matrices) and (not force_rewrite):
            raise WrongInput(
                f"Scenario {scenario} already exist. In order to re-write the scenario, you can use force_rewrite = True."
            )

        if scenario == "baseline":
            raise WrongInput("baseline scenario can not be overwritten.")

        clusters = self._resolved_clusters(clusters=clusters, legacy_clusters=legacy_clusters)
        check_clusters(
            index_dict=self.get_index("all"), table=self.table_type, clusters=clusters
        )

        # have the test for the existence of the database

        note_u = []
        note_s = []
        note_z = []
        note_va = []
        note_vc = []
        note_v = []
        note_ea = []
        note_ec = []
        note_e = []
        note_Ya = []
        note_Yc = []
        note_y = []

        if self.table_type == "SUT":
            ordering = SUTUnifiedOrderingPolicy.from_blocks(
                U=self.query(_ENUM.U),
                S=self.query(_ENUM.S),
                Y=self.query(_ENUM.Y),
            )

            if z:
                has_u_sheet = has_shock_sheet(io, _ENUM.u, str(_ENUM.u).lower())
                has_s_sheet = has_shock_sheet(io, _ENUM.s, str(_ENUM.s).lower())
                has_legacy_z_sheet = has_shock_sheet(
                    io,
                    _ENUM.z,
                    _ENUM.Z,
                    str(_ENUM.z).lower(),
                    str(_ENUM.Z).upper(),
                )

                if has_u_sheet or has_s_sheet:
                    if has_legacy_z_sheet:
                        log_time(
                            logger,
                            "Shock: SUT shock workbook contains both split 'u'/'s' sheets and legacy 'z'. The split sheets are used and the legacy 'z' sheet is ignored.",
                            "warning",
                        )
                    u_c, note_u = U_shock(self, io, z, clusters, 1)
                    s_c, note_s = S_shock(self, io, z, clusters, 1)
                    z_c = concat_sut_z(u_c, s_c, ordering)
                else:
                    z_c, note_z = Z_shock(self, io, z, clusters, 1)
            else:
                z_c, note_z = Z_shock(self, io, z, clusters, 1)

            if v:
                has_va_sheet = has_shock_sheet(io, "va")
                has_vc_sheet = has_shock_sheet(io, "vc")
                has_legacy_v_sheet = has_shock_sheet(io, _ENUM.v, str(_ENUM.v).lower(), str(_ENUM.v).upper())

                if has_va_sheet or has_vc_sheet:
                    if has_legacy_v_sheet:
                        log_time(
                            logger,
                            "Shock: SUT shock workbook contains both split 'va'/'vc' sheets and legacy 'v'. The split sheets are used and the legacy 'v' sheet is ignored.",
                            "warning",
                        )
                    va_c, note_va = va_shock(self, io, v, clusters, 1)
                    vc_c, note_vc = vc_shock(self, io, v, clusters, 1)
                    v_c = concat_sut_v(va_c, vc_c, ordering)
                else:
                    v_c, note_v = V_shock(self, io, "V", v, clusters, 1)
            else:
                v_c, note_v = V_shock(self, io, "V", v, clusters, 1)

            if e:
                has_ea_sheet = has_shock_sheet(io, "ea")
                has_ec_sheet = has_shock_sheet(io, "ec")
                has_legacy_e_sheet = has_shock_sheet(io, _ENUM.e, str(_ENUM.e).lower(), str(_ENUM.e).upper())

                if has_ea_sheet or has_ec_sheet:
                    if has_legacy_e_sheet:
                        log_time(
                            logger,
                            "Shock: SUT shock workbook contains both split 'ea'/'ec' sheets and legacy 'e'. The split sheets are used and the legacy 'e' sheet is ignored.",
                            "warning",
                        )
                    ea_c, note_ea = ea_shock(self, io, e, clusters, 1)
                    ec_c, note_ec = ec_shock(self, io, e, clusters, 1)
                    e_c = concat_sut_e(ea_c, ec_c, ordering)
                else:
                    e_c, note_e = V_shock(self, io, "E", e, clusters, 1)
            else:
                e_c, note_e = V_shock(self, io, "E", e, clusters, 1)

            if Y:
                has_Ya_sheet = has_shock_sheet(io, "Ya")
                has_Yc_sheet = has_shock_sheet(io, "Yc")
                has_legacy_Y_sheet = has_shock_sheet(io, _ENUM.Y, str(_ENUM.Y).lower(), str(_ENUM.Y).upper())

                if has_Ya_sheet or has_Yc_sheet:
                    if has_legacy_Y_sheet:
                        log_time(
                            logger,
                            "Shock: SUT shock workbook contains both split 'Ya'/'Yc' sheets and legacy 'Y'. The split sheets are used and the legacy 'Y' sheet is ignored.",
                            "warning",
                        )
                    Ya_c, note_Ya = Ya_shock(self, io, Y, clusters, 1)
                    Yc_c, note_Yc = Yc_shock(self, io, Y, clusters, 1)
                    Y_c = concat_sut_Y(Ya_c, Yc_c, ordering)
                else:
                    Y_c, note_y = Y_shock(self, io, Y, clusters, 1)
            else:
                Y_c, note_y = Y_shock(self, io, Y, clusters, 1)
        else:
            z_c, note_z = Z_shock(self, io, z, clusters, 1)
            e_c, note_e = V_shock(self, io, "E", e, clusters, 1)
            v_c, note_v = V_shock(self, io, "V", v, clusters, 1)
            Y_c, note_y = Y_shock(self, io, Y, clusters, 1)

        EY_c = self.query([_ENUM.EY])
        VY_c = self.query([_ENUM.VY])

        _results = calc_all_shock(z_c, e_c, v_c, Y_c)
        _results["EY"] = EY_c
        _results["VY"] = VY_c

        if scenario is None:
            scenario = f"shock {self.__counter}"
            self.__counter += 1

        self.matrices[scenario] = _results

        self.meta._add_history(f"Shocks implemented from {io} as follow:")

        try:
            for note in notes:
                self.meta._add_history(f"Shock (Notes): {note}")
        except:
            pass

        for note in (
            note_u
            + note_s
            + note_z
            + note_va
            + note_vc
            + note_v
            + note_ea
            + note_ec
            + note_e
            + note_Ya
            + note_Yc
            + note_y
        ):
            self.meta._add_history(note)

        log_time(logger, "Shock: Shock implemented successfully.")

    def get_shock_excel(
        self,
        path=None,
        num_shock=10,
        clusters=None,
        **legacy_clusters,
    ):
        """Write an Excel template for defining shocks.

        Parameters
        ----------
        path:
            Output path for the workbook. When omitted, MARIO writes to the
            default Excel output directory.
        num_shock:
            Number of shock rows to pre-create in the workbook template.
        clusters:
            Preferred cluster payload. When omitted, MARIO uses clusters
            already stored on the database, optionally merged with any legacy
            keyword clusters.
        **legacy_clusters:
            Backward-compatible cluster mappings passed as keyword arguments.

        Returns
        -------
        None
            The template workbook is written to disk.

        Notes
        -----
        For SUT databases, the template exposes split block sheets such as
        ``u``, ``s``, ``Ya``, ``Yc``, ``va``, ``vc``, ``ea`` and ``ec``.
        Sheets whose current block is entirely zero are omitted to keep the
        workbook compact. ``shock_calc(...)`` still accepts the old unified
        workbook format (``z``, ``v``, ``e``, ``Y``) for backward
        compatibility. For both IOT and SUT, the new template uses flat-style
        column names such as ``Region_from`` and ``Sector_to`` instead of the
        legacy explicit level columns.
        """

        clusters = self._resolved_clusters(clusters=clusters, legacy_clusters=legacy_clusters)
        check_clusters(
            index_dict=self.get_index("all"), table=self.table_type, clusters=clusters
        )

        _sh_excel(self, num_shock, self._getdir(path, "Excels", "shock.xlsx"), clusters)

    def replace_units_name(self, level, names):
        """Rename unit labels inside one unit table without touching matrix data.

        Parameters
        ----------
        level:
            Classification level whose unit table should be updated.
        names:
            Mapping ``old_unit -> new_unit`` applied to the selected unit table.

        Returns
        -------
        None
            The unit labels are updated in place.
        """
        if level not in [*TABLE_LEVELS[self.meta.table]]:
            raise WrongInput(
                "'{}' is not a valid index. Valid indeces are: \n{}".format(
                    level, [*TABLE_LEVELS[self.meta.table]]
                )
            )
        if len(list(dict.fromkeys(self.units[level].iloc[:, 0]))) > 1:
            for item, value in names.items():
                if True in set((self.units[level]["unit"] == item).values):
                    self.units[level][self.units[level]["unit"] == item] = value
                else:
                    log_time(
                        logger,
                        comment="No units named {} found".format(item),
                        level="warning",
                    )

    def plot_bubble(
        self,
        x,
        y,
        size,
        path=None,
        auto_open=True,
        scenario="baseline",
        log_x=False,
        log_y=False,
    ):
        """Deprecated wrapper for a GDP or extension bubble chart.

        Parameters
        ----------
        x, y, size:
            Variables mapped to the chart axes and bubble size. Each value can
            be ``"GDP"``, a satellite-account label, or a factor-of-production
            label.
        path:
            Output HTML path. When omitted, MARIO writes to the default plots
            directory.
        auto_open:
            When ``True``, open the generated HTML plot automatically.
        scenario:
            Scenario to plot.
        log_x, log_y:
            When ``True``, use logarithmic scaling on the corresponding axis.

        Returns
        -------
        None
            The plot is written to disk.
        """
        self._warn_deprecated_plot_method(
            "plot_bubble",
            "plot(data=..., kind='scatter', x=..., y=..., size=...)",
        )

        items = {"x": x, "y": y, "size": size}
        focus_level = _MASTER_INDEX["s"] if self.table_type == "IOT" else _MASTER_INDEX["a"]
        item_label = _MASTER_INDEX["s"] if self.table_type == "IOT" else _MASTER_INDEX["a"]

        focus_index = self.X.loc[(slice(None), focus_level, slice(None)), :].index
        to_plot = pd.DataFrame(index=focus_index)

        matrices = self.query(matrices=[_ENUM.E, _ENUM.V], scenarios=[scenario])
        columns = {}
        for axis_name, requested in items.items():
            if requested == "GDP":
                to_plot[requested] = self.GDP(total=False, scenario=scenario).loc[focus_index, "GDP"].values
                unit = self.units[_MASTER_INDEX["f"]].iloc[0, 0]
            elif requested in self.get_index(_MASTER_INDEX["k"]):
                to_plot[requested] = matrices[_ENUM.E].loc[requested, focus_index].values
                unit = self.units[_MASTER_INDEX["k"]].loc[requested, "unit"]
            elif requested in self.get_index(_MASTER_INDEX["f"]):
                to_plot[requested] = matrices[_ENUM.V].loc[requested, focus_index].values
                unit = self.units[_MASTER_INDEX["f"]].loc[requested, "unit"]
            else:
                raise WrongInput(
                    "Acceptable values are GDP or one of the Satellite account or Factor of production items."
                )

            columns[axis_name] = f"{requested} ({unit})"

        to_plot.columns = [columns["x"], columns["y"], columns["size"]]
        to_plot.index.names = ["Region", "Level", item_label]
        to_plot = to_plot.reset_index()

        if (to_plot[columns["size"]] <= 0).any():
            negatives = to_plot.loc[to_plot[columns["size"]] <= 0, ["Region", item_label]].values.tolist()
            raise NotImplementable(
                f"cannot plot when size have negative or null numbers. negatives: {negatives}"
            )

        return self.plot(
            data=to_plot,
            kind="scatter",
            preset=None,
            x=columns["x"],
            y=columns["y"],
            size=columns["size"],
            color="Region",
            hover_name=item_label,
            log_x=log_x,
            log_y=log_y,
            path=self._resolve_plot_output_path(path, "bubble.html"),
            auto_open=auto_open,
            size_max=60,
            title="Bubble plot",
        )

    def plot_gdp(
        self,
        path=None,
        plot="treemap",
        scenario="baseline",
        extension=None,
        extension_value="relative",
        auto_open=True,
        drop_reg=None,
        title=None,
    ):
        """Deprecated wrapper for sectoral GDP treemap and sunburst plots.

        Parameters
        ----------
        path:
            Output HTML path. When omitted, MARIO writes to the default plots
            directory.
        plot:
            Plot type. Accepted values are ``"treemap"`` and ``"sunburst"``.
        scenario:
            Scenario to plot.
        extension:
            Optional satellite-account label used to color GDP tiles by an
            extension indicator.
        extension_value:
            Extension measure used for coloring. Accepted values are
            ``"relative"``, ``"absolute"``, ``"specific footprint"`` and
            ``"absolute footprint"``.
        auto_open:
            When ``True``, open the generated HTML plot automatically.
        drop_reg:
            Optional region label to exclude from the visualization.
        title:
            Optional custom plot title.

        Returns
        -------
        None
            The plot is written to disk.
        """
        self._warn_deprecated_plot_method(
            "plot_gdp",
            "plot(data=..., kind='treemap'|'sunburst', path_columns=[...])",
        )
        plots = ["treemap", "sunburst"]
        extension_values = [
            "relative",
            "absolute",
            "specific footprint",
            "absolute footprint",
        ]

        if plot not in plots:
            raise WrongInput(f"Acceptable plots are {plots}")

        if extension_value not in extension_values:
            raise WrongInput(f"Acceptable extension_values are {extension_value}")

        if (extension is not None) and (
            extension not in self.get_index(_MASTER_INDEX["k"])
        ):
            raise WrongInput(f"{extension} is not a valid { _MASTER_INDEX['k']}")

        log_time(logger, "Plots may not work with big databases")

        data_frame = self.GDP(
            share=True if extension is None else False, total=False, scenario=scenario
        )
        color = "Share of sector by region"
        if extension is not None:
            if extension_value == "relative":
                matrix = _ENUM.e
                color = "{} [{}]/ Production"

            elif extension_value == "specific footprint":
                matrix = _ENUM.f
                color = "{} [{}]/ Production"

            elif extension_value == "absolute footprint":
                matrix = _ENUM.F
                color = "{} [{}]"

            else:
                matrix = _ENUM.E
                color = "{} [{}]"

            data = self.get_data(
                matrices=[matrix],
                scenarios=[scenario],
                units=True,
                indeces=False,
                format="dict",
            )[scenario]

            unit = data["units"][_MASTER_INDEX["k"]].loc[extension, "unit"]

            color = color.format(extension, unit)

            data_frame.loc[data_frame.index, color] = (
                data[matrix].loc[extension, data_frame.index].values
            )

        data_frame = data_frame[data_frame["GDP"] != 0].reset_index()

        if self.table_type == "IOT":
            col = "Sector"
        else:
            col = "Activity"
        _path = [
            px.Constant("<b>Gross Domestic Production</b>"),
            "Region",
            col,
        ]
        values = "GDP"

        if drop_reg == None:
            data_frame = data_frame
        else:
            data_frame = data_frame.loc[data_frame.Region != drop_reg]

        return self.plot(
            data=data_frame,
            kind=plot,
            preset=None,
            y=values,
            color=color,
            path_columns=["Region", col],
            path=self._resolve_plot_output_path(path, f"GDP_{scenario}_{plot}.html"),
            auto_open=auto_open,
            title=title,
        )

    def plot_matrix(
        self,
        matrix,
        x,
        color,
        y="Value",
        item=_MASTER_INDEX["s"],
        facet_row=None,
        facet_col=None,
        animation_frame="Scenario",
        base_scenario=None,
        path=None,
        mode="stack",
        layout=None,
        auto_open=True,
        shared_yaxes="all",
        shared_xaxes=True,
        **filters,
    ):
        """Deprecated wrapper around :meth:`plot` for matrix bar plots.

        Parameters
        ----------
        matrix:
            Matrix or block name to visualize.
        x:
            Column used on the x axis in the generated long-form plot.
        color:
            Column used to color bars.
        y:
            Column used on the y axis. The default is ``"Value"``.
        item:
            Item dimension used to interpret the matrix for plotting. For SUT
            tables this controls whether the commodity or activity side is
            shown.
        facet_row, facet_col:
            Optional columns used to facet the plot.
        animation_frame:
            Column used to animate the plot, typically ``"Scenario"``.
        base_scenario:
            Optional reference scenario used to plot differences.
        path:
            Output HTML path. When omitted, MARIO writes to the default plots
            directory.
        mode:
            Plotly bar mode, such as ``"stack"`` or ``"group"``.
        layout:
            Optional layout dictionary overriding the default plot layout.
        auto_open:
            When ``True``, open the generated HTML plot automatically.
        shared_yaxes, shared_xaxes:
            Axis-sharing options forwarded to the plotting backend.
        **filters:
            Named plot filters such as ``filter_region_from`` or
            ``filter_satellite_account``.

        Returns
        -------
        None
            The plot is written to disk.
        """
        self._warn_deprecated_plot_method("plot_matrix", "plot(matrix=..., ...)")

        item_from = item
        selected_matrix = matrix
        if self.table_type == "SUT":
            if selected_matrix == "Z" and item_from == _MASTER_INDEX["c"]:
                selected_matrix = "U"
            elif selected_matrix == "z" and item_from == _MASTER_INDEX["c"]:
                selected_matrix = "u"
            elif selected_matrix == "Z" and item_from == _MASTER_INDEX["a"]:
                selected_matrix = "S"
            elif selected_matrix == "z" and item_from == _MASTER_INDEX["a"]:
                selected_matrix = "s"

        scenarios = [scenario for scenario in self.scenarios if scenario != base_scenario]
        if not scenarios:
            scenarios = ["baseline"]

        plot_data = plt.build_matrix_plot_frame(
            self,
            selected_matrix,
            scenarios=scenarios,
            base_scenario=base_scenario,
            difference="absolute",
            filters=None,
            item=item_from,
        )
        normalized_filters = self._normalize_legacy_plot_filters(filters, plot_data.columns)
        plot_data = plt._apply_filters(plot_data, normalized_filters)

        resolved_columns = plot_data.columns
        resolved_x = self._normalize_plot_dimension_name(x, resolved_columns)
        resolved_y = self._normalize_plot_dimension_name(y, resolved_columns)
        resolved_color = self._normalize_plot_dimension_name(color, resolved_columns)
        resolved_facet_row = self._normalize_plot_dimension_name(facet_row, resolved_columns)
        resolved_facet_col = self._normalize_plot_dimension_name(facet_col, resolved_columns)
        resolved_animation = self._normalize_plot_dimension_name(animation_frame, resolved_columns)

        resolved_layout = {} if layout is None else dict(layout)
        if base_scenario is None:
            resolved_layout.setdefault("title", f"{MATRIX_TITLES.get(selected_matrix, selected_matrix)}")
        else:
            resolved_layout.setdefault(
                "title",
                f"{MATRIX_TITLES.get(selected_matrix, selected_matrix)} - Variation with respect to '{base_scenario}' scenario",
            )

        return self.plot(
            data=plot_data,
            kind="bar",
            preset=None,
            x=resolved_x,
            y=resolved_y,
            color=resolved_color,
            facet_row=resolved_facet_row,
            facet_col=resolved_facet_col,
            animation_frame=resolved_animation,
            path=self._resolve_plot_output_path(path, f"{selected_matrix}.html"),
            auto_open=auto_open,
            layout=resolved_layout,
            barmode=mode,
        )
