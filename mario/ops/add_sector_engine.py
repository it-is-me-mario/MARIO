"""Add-sectors engine for inventory-driven structural insertion."""

from __future__ import annotations

import copy
import logging
import warnings
from copy import deepcopy

import pandas as pd
import pint

from mario.log_exc.exceptions import LackOfInput, NotImplementable
from mario.log_exc.logger import log_time
from mario.model.conventions import IOT, SUT, _ENUM, _MASTER_INDEX as MI
from mario.ops.add_sector_specs import (
    ADVANCED_ADD_SECTOR_INVENTORY_SHEET_COLUMNS as INC,
    ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS as MSC,
)


sn = slice(None)
logger = logging.getLogger(__name__)


_MATRIX_SLICES_MAP = {
    SUT: {
        "u": {0: MI["c"], 1: MI["a"], "concat": 1},
        "s": {0: MI["a"], 1: MI["c"], "concat": 0},
        "e": {0: MI["k"], 1: MI["a"], "concat": 1},
        "v": {0: MI["f"], 1: MI["a"], "concat": 1},
        "Y": {0: MI["c"], 1: MI["n"], "concat": 0},
    },
    IOT: {
        "z": {0: MI["s"], 1: MI["s"], "concat": 1},
        "e": {0: MI["k"], 1: MI["s"], "concat": 1},
        "v": {0: MI["f"], 1: MI["s"], "concat": 1},
        "Y": {0: MI["s"], 1: MI["n"], "concat": 0},
    },
}


class InventoryRowValidationError(ValueError):
    """Row-level inventory validation issue collected before failing one sheet."""

    def __init__(self, reason: str, details: str):
        super().__init__(details)
        self.reason = reason
        self.details = details


class AddSectorEngine:
    """Apply the workbook-driven add-sectors workflow to one database.

    The engine assumes that the database already exposes the parsed workbook
    state through attributes such as ``add_sectors_master``,
    ``regions_clusters`` and ``inventories``. It then extends the coefficient
    matrices in-place and returns the updated blocks needed to rebuild the
    public ``Database`` object.
    """

    def __init__(self, instance, matrices: dict[str, pd.DataFrame], ignore_warnings: bool = True):
        """Cache the database state and the coefficient matrices to be extended."""
        self.db = instance
        self.matrices = matrices
        self._iot_public_axis_names: dict[tuple[str, str], tuple[object, ...]] = {}
        self.missing_factors_of_production = getattr(instance, "missing_factors_of_production", {})
        self.regions = instance.get_index(MI["r"])
        self.units = copy.deepcopy(instance.units)
        self.table = self.db.meta.table
        self.uncertainty_values = getattr(instance, "uncertainty_values", {})

        if self.table == SUT:
            self.new_activities = getattr(instance, "new_activities", [])
            self.new_commodities = getattr(instance, "new_commodities", [])
            self.parented_activities = getattr(instance, "parented_activities", [])
            self.commodities = instance.get_index(MI["c"])
            self.commodities_clusters = getattr(instance, "commodities_clusters", {})
        else:
            self.new_sectors = getattr(instance, "new_sectors", [])
            self.parented_sectors = getattr(instance, "parented_sectors", [])
            self.sectors = instance.get_index(MI["s"])
            self.sectors_clusters = getattr(instance, "sectors_clusters", {})

        self.regions_clusters = getattr(instance, "regions_clusters", {})
        self.factors_clusters = getattr(instance, "factors_clusters", {})

        if ignore_warnings:
            warnings.filterwarnings("ignore")

        if self.table == IOT:
            self._prepare_iot_working_layout()

    @staticmethod
    def _axis_names(axis) -> tuple[object, ...]:
        """Return the public level names exposed by one pandas axis."""
        if isinstance(axis, pd.MultiIndex):
            return tuple(axis.names)
        return (axis.name,)

    def _coerce_iot_axis_to_working(
        self,
        axis,
        *,
        matrix: str,
        side: str,
        marker: str,
    ):
        """Convert explicit IOT public axes to the legacy working layout used by add-sectors.

        The historical engine assumes productive and final-demand axes always use
        ``Region / Level / Item``. For explicit parser layouts we normalize those
        axes internally before running the engine, then restore the original
        public layout on return.
        """
        names = self._axis_names(axis)
        self._iot_public_axis_names[(matrix, side)] = names

        if isinstance(axis, pd.MultiIndex) and names == ("Region", "Level", "Item"):
            return axis

        if isinstance(axis, pd.MultiIndex) and names == ("Region", marker):
            return pd.MultiIndex.from_tuples(
                [(region, marker, item) for region, item in axis.tolist()],
                names=["Region", "Level", "Item"],
            )

        if side == "index" and isinstance(axis, pd.MultiIndex):
            return axis
        if side == "index" and not isinstance(axis, pd.MultiIndex):
            return axis

        raise NotImplementable(
            "add_sectors currently supports only IOT productive/final-demand public axes "
            "with regions, either in legacy form ('Region', 'Level', 'Item') or in "
            f"explicit form ('Region', '{marker}')."
        )

    def _restore_iot_public_axis(
        self,
        axis,
        *,
        matrix: str,
        side: str,
        marker: str,
    ):
        """Restore one working IOT axis to the public layout originally exposed by the database."""
        original_names = self._iot_public_axis_names.get((matrix, side))
        if not original_names:
            return axis

        if isinstance(axis, pd.MultiIndex) and original_names == ("Region", "Level", "Item") and axis.nlevels == 3:
            return pd.MultiIndex.from_tuples(axis.tolist(), names=["Region", "Level", "Item"])

        if original_names == ("Region", marker) and isinstance(axis, pd.MultiIndex) and axis.nlevels == 3:
            return pd.MultiIndex.from_tuples(
                [(region, item) for region, _level, item in axis.tolist()],
                names=["Region", marker],
            )

        if isinstance(axis, pd.MultiIndex) and len(original_names) == axis.nlevels:
            return pd.MultiIndex.from_tuples(axis.tolist(), names=list(original_names))

        if not isinstance(axis, pd.MultiIndex) and len(original_names) == 1:
            return pd.Index(axis.tolist(), name=original_names[0])

        return axis

    def _prepare_iot_working_layout(self) -> None:
        """Normalize explicit IOT axes to the legacy working layout expected by add-sectors."""
        productive_matrices = (_ENUM["z"], _ENUM["Z"], _ENUM["e"], _ENUM["E"], _ENUM["v"], _ENUM["V"])
        for matrix in productive_matrices:
            if matrix not in self.matrices:
                continue
            frame = self.matrices[matrix]
            if matrix in {_ENUM["z"], _ENUM["Z"]}:
                frame.index = self._coerce_iot_axis_to_working(
                    frame.index,
                    matrix=matrix,
                    side="index",
                    marker=MI["s"],
                )
            frame.columns = self._coerce_iot_axis_to_working(
                frame.columns,
                matrix=matrix,
                side="columns",
                marker=MI["s"],
            )

        demand_matrices = (_ENUM["Y"], _ENUM["EY"], _ENUM["VY"])
        for matrix in demand_matrices:
            if matrix not in self.matrices:
                continue
            frame = self.matrices[matrix]
            if matrix == _ENUM["Y"]:
                frame.index = self._coerce_iot_axis_to_working(
                    frame.index,
                    matrix=matrix,
                    side="index",
                    marker=MI["s"],
                )
            frame.columns = self._coerce_iot_axis_to_working(
                frame.columns,
                matrix=matrix,
                side="columns",
                marker=MI["n"],
            )

    def _restore_iot_public_layout(self) -> None:
        """Restore the original IOT public axes after the legacy working pass."""
        productive_matrices = (_ENUM["z"], _ENUM["Z"], _ENUM["e"], _ENUM["E"], _ENUM["v"], _ENUM["V"])
        for matrix in productive_matrices:
            if matrix not in self.matrices:
                continue
            frame = self.matrices[matrix]
            if matrix in {_ENUM["z"], _ENUM["Z"]}:
                frame.index = self._restore_iot_public_axis(
                    frame.index,
                    matrix=matrix,
                    side="index",
                    marker=MI["s"],
                )
            frame.columns = self._restore_iot_public_axis(
                frame.columns,
                matrix=matrix,
                side="columns",
                marker=MI["s"],
            )

        demand_matrices = (_ENUM["Y"], _ENUM["EY"], _ENUM["VY"])
        for matrix in demand_matrices:
            if matrix not in self.matrices:
                continue
            frame = self.matrices[matrix]
            if matrix == _ENUM["Y"]:
                frame.index = self._restore_iot_public_axis(
                    frame.index,
                    matrix=matrix,
                    side="index",
                    marker=MI["s"],
                )
            frame.columns = self._restore_iot_public_axis(
                frame.columns,
                matrix=matrix,
                side="columns",
                marker=MI["n"],
            )

        if hasattr(self, "uncertainty_matrix") and self.uncertainty_matrix is not None:
            self.uncertainty_matrix.index = self._restore_iot_public_axis(
                self.uncertainty_matrix.index,
                matrix=_ENUM["z"],
                side="index",
                marker=MI["s"],
            )
            self.uncertainty_matrix.columns = self._restore_iot_public_axis(
                self.uncertainty_matrix.columns,
                matrix=_ENUM["z"],
                side="columns",
                marker=MI["s"],
            )

    def _matrix_row_semantic_axes(self, matrix: str) -> tuple[str, ...]:
        """Return semantic row-axis ids for one matrix, even with legacy public axes."""
        try:
            spec = self.db.get_block_spec(matrix)
            return tuple(axis.id for axis in spec.row_axes)
        except Exception:
            labels = self.matrices[matrix].index
            if isinstance(labels, pd.MultiIndex):
                names = tuple(name for name in labels.names if name is not None)
                if "Level" in names and "Item" in names:
                    extras = tuple(name for name in names if name not in {"Level", "Item"})
                    natural = MI["f"] if matrix == _ENUM["v"] else MI["k"]
                    return extras + (natural,)
                return names
            natural = MI["f"] if matrix == _ENUM["v"] else MI["k"]
            return (getattr(labels, "name", None) or natural,)

    def _matrix_row_terminal_position(self, matrix: str) -> int:
        """Return the positional level that stores the natural factor/satellite item."""
        labels = self.matrices[matrix].index
        if isinstance(labels, pd.MultiIndex):
            return labels.nlevels - 1
        return 0

    def _matrix_row_region_position(self, matrix: str) -> int | None:
        """Return the positional level that stores the row-region, if any."""
        semantic_axes = self._matrix_row_semantic_axes(matrix)
        if MI["r"] not in semantic_axes:
            return None
        return semantic_axes.index(MI["r"])

    def _matching_factor_sat_rows(
        self,
        matrix: str,
        input_item: str,
        row_region: str | None,
    ):
        """Return row labels matching one factor/satellite item and optional row-region."""
        labels = self.matrices[matrix].index
        terminal_position = self._matrix_row_terminal_position(matrix)
        region_position = self._matrix_row_region_position(matrix)

        if isinstance(labels, pd.MultiIndex):
            # Resolve item clusters (factors)
            item_values = {input_item}
            col_id = MI["f"] if matrix == _ENUM["v"] else MI["k"]
            if col_id == MI["f"] and input_item in self.factors_clusters:
                item_values = set(self.factors_clusters[input_item])

            mask = labels.get_level_values(terminal_position).isin(item_values)

            if region_position is not None and not (row_region in (None, "") or pd.isna(row_region)):
                if row_region in self.regions:
                    region_values = {row_region}
                elif row_region in self.db.regions_clusters:
                    region_values = set(self.db.regions_clusters[row_region])
                else:
                    raise ValueError(f"Unknown DB region {row_region}.")
                mask &= labels.get_level_values(region_position).isin(region_values)
            return labels[mask]

        if not (row_region in (None, "") or pd.isna(row_region)) and self._matrix_row_region_position(matrix) is not None:
            raise ValueError(f"Unknown DB region {row_region}.")
        if matrix == _ENUM["v"] and input_item in self.factors_clusters:
            item_values = [v for v in self.factors_clusters[input_item] if v in labels]
            return pd.Index(item_values, name=labels.name)
        if input_item not in labels:
            return pd.Index([], name=labels.name)
        return pd.Index([input_item], name=labels.name)

    def _target_output_column(self, region_to: str, activity: str):
        """Return the target productive column key for the new item."""
        return (region_to, MI["a" if self.table == SUT else "s"], activity)

    def _parent_output_column(self, region_to: str, activity: str):
        """Return the parent productive column key for one new target item."""
        if self.table == SUT:
            if activity not in self.parented_activities:
                return None
            parent = self.db.add_sectors_master.query(f"{MI['a']}==@activity")[
                MSC[self.table]["parent_activity"]
            ].values[0]
            if pd.isna(parent):
                return None
            return (region_to, MI["a"], parent)

        if activity not in self.parented_sectors:
            return None
        parent = self.db.add_sectors_master.query(f"{MI['s']}==@activity")[
            MSC[self.table]["parent_sector"]
        ].values[0]
        if pd.isna(parent):
            return None
        return (region_to, MI["s"], parent)

    def _factor_sat_allocation_weights(
        self,
        matrix: str,
        row_labels,
        region_to: str,
        activity: str,
    ) -> pd.Series:
        """Return allocation weights for one factor/satellite update across matching rows."""
        if len(row_labels) == 0:
            return pd.Series(dtype=float)

        parent_column = self._parent_output_column(region_to, activity)
        if parent_column is not None:
            reference = self.matrices[matrix].loc[row_labels, parent_column]
            if isinstance(reference, pd.DataFrame):
                reference = reference.iloc[:, 0]
            reference = reference.astype(float)
            total = reference.sum()
            if total > 0:
                return reference / total

        weight = 1 / len(row_labels)
        return pd.Series(weight, index=row_labels, dtype=float)

    def to_iot(self, VA_fix: bool = False, accept_non_unitary_sum: bool = False):
        """Return an IOT with the new sectors inserted in coefficient form."""

        if self.table != IOT:
            raise ValueError("This method can only be used for IOT matrices.")

        self.add_new_units(MI["s"])
        empty_slices = self.get_empty_table_slices()

        self.filled_slices = deepcopy(empty_slices)
        self.filled_uncertainty_slices = empty_slices["z"] * 0 + 1
        self.uncertainty_matrix = deepcopy(self.matrices[_ENUM["z"]]) * 0 + 1

        for sector in self.new_sectors:
            log_time(logger, f"Add-sectors engine: filling IOT slices for sector {sector!r}.", "info")
            self.fill_slices(sector, VA_fix, accept_non_unitary_sum)

        self.add_slices()
        self.reindex_matrices()
        self.get_mario_indices()
        self._restore_iot_public_layout()

        return self.matrices, self.units, self.indeces, self.uncertainty_matrix

    def to_sut(self):
        """Return a SUT with the new activities and commodities inserted."""

        if self.table != SUT:
            raise ValueError("This method can only be used for SUT matrices.")

        self.add_new_units(MI["c"])
        self.add_new_units(MI["a"])

        self.matrices[_ENUM["u"]] = self.matrices[_ENUM["z"]].loc[
            (sn, MI["c"], sn), (sn, MI["a"], sn)
        ]
        self.matrices[_ENUM["s"]] = self.matrices[_ENUM["z"]].loc[
            (sn, MI["a"], sn), (sn, MI["c"], sn)
        ]

        empty_slices = self.get_empty_table_slices()
        self.filled_slices = deepcopy(empty_slices)
        for activity in self.new_activities:
            log_time(logger, f"Add-sectors engine: filling SUT slices for activity {activity!r}.", "info")
            self.fill_slices(activity)

        self.add_slices()

        if self.new_activities:
            new_act_indices = self.matrices[_ENUM["s"]].loc[
                (sn, MI["a"], self.new_activities), :
            ].index
            self.matrices[_ENUM["Y"]] = pd.concat(
                [
                    self.matrices[_ENUM["Y"]],
                    pd.DataFrame(0.0, index=new_act_indices, columns=self.matrices[_ENUM["Y"]].columns),
                ],
                axis=0,
            )

        if self.new_commodities:
            new_com_indices = self.matrices[_ENUM["u"]].loc[
                (sn, MI["c"], self.new_commodities), :
            ].index
            self.matrices[_ENUM["v"]] = pd.concat(
                [
                    self.matrices[_ENUM["v"]],
                    pd.DataFrame(0.0, index=self.matrices[_ENUM["v"]].index, columns=new_com_indices),
                ],
                axis=1,
            )
            self.matrices[_ENUM["e"]] = pd.concat(
                [
                    self.matrices[_ENUM["e"]],
                    pd.DataFrame(0.0, index=self.matrices[_ENUM["e"]].index, columns=new_com_indices),
                ],
                axis=1,
            )

        self.matrices[_ENUM["z"]] = pd.concat(
            [self.matrices[_ENUM["u"]], self.matrices[_ENUM["s"]]], axis=1
        ).fillna(0)
        self.reindex_matrices()
        self.get_mario_indices()
        return self.matrices, self.units, self.indeces

    def add_new_units(self, item: str) -> None:
        """Append unit rows for newly added sectors, activities or commodities."""

        if item == MI["c"]:
            new_items = self.new_commodities
            df = (
                self.db.add_sectors_master.query(f"{MI['c']}==@new_items")
                .loc[:, [item, MSC[self.table]["unit"]]]
                .set_index(item)
            )
            df.columns = ["unit"]
            df = df.reset_index().drop_duplicates().set_index(item)

        elif item == MI["a"]:
            new_items = self.new_activities
            if self.db.is_hybrid:
                act_unit = self.units[MI["a"]]["unit"].unique()[0]
                df = pd.DataFrame(act_unit, index=new_items, columns=["unit"])
            else:
                df = (
                    self.db.add_sectors_master.query(f"{MI['a']}==@new_items")
                    .loc[:, [item, MSC[self.table]["unit"]]]
                    .set_index(item)
                )
                df.columns = ["unit"]
                df = df.drop_duplicates()

        elif item == MI["s"]:
            new_items = self.new_sectors
            df = (
                self.db.add_sectors_master.query(f"{MI['s']}==@new_items")
                .loc[:, [item, MSC[self.table]["unit"]]]
                .set_index(item)
            )
            df.columns = ["unit"]
            df = df.reset_index().drop_duplicates().set_index(item)
        else:
            raise ValueError(f"Unsupported item {item} for add_new_units.")

        self.units[item] = pd.concat([self.units[item], df], axis=0)

    def get_empty_table_slices(self) -> dict[str, pd.DataFrame]:
        """Build empty coefficient slices matching the items declared in the workbook."""

        empty_slices = {}
        for matrix in _MATRIX_SLICES_MAP[self.table]:
            new_index, new_columns = self.get_slice_indices(matrix)
            empty_slices[matrix] = pd.DataFrame(0.0, index=new_index, columns=new_columns)
        return empty_slices

    def get_slice_indices(self, matrix: str):
        """Return row and column labels for one empty slice matrix."""

        concat = _MATRIX_SLICES_MAP[self.table][matrix]["concat"]
        item_row = _MATRIX_SLICES_MAP[self.table][matrix][0]
        item_col = _MATRIX_SLICES_MAP[self.table][matrix][1]

        if concat == 0:
            empty_index = [[], [], []]
            if self.table == SUT:
                items_to_add_on_rows = self.new_commodities if item_row == MI["c"] else self.new_activities
            else:
                items_to_add_on_rows = self.new_sectors
            for region in self.regions:
                for item in items_to_add_on_rows:
                    empty_index[0].append(region)
                    empty_index[1].append(item_row)
                    empty_index[2].append(item)

            if matrix == _ENUM["Y"]:
                new_index = pd.MultiIndex.from_arrays(
                    [
                        self.matrices[matrix].index.get_level_values(0).tolist() + empty_index[0],
                        self.matrices[matrix].index.get_level_values(1).tolist() + empty_index[1],
                        self.matrices[matrix].index.get_level_values(2).tolist() + empty_index[2],
                    ]
                )
            else:
                new_index = pd.MultiIndex.from_arrays(empty_index)

            empty_extra_columns = [[], [], []]
            if self.table == SUT:
                items_to_add_on_cols = self.new_activities if item_col == MI["a"] else self.new_commodities
            else:
                items_to_add_on_cols = self.new_sectors
            for region in self.regions:
                for item in items_to_add_on_cols:
                    empty_extra_columns[0].append(region)
                    empty_extra_columns[1].append(item_col)
                    empty_extra_columns[2].append(item)

            new_columns = pd.MultiIndex.from_arrays(
                [
                    self.matrices[matrix].columns.get_level_values(0).tolist() + empty_extra_columns[0],
                    self.matrices[matrix].columns.get_level_values(1).tolist() + empty_extra_columns[1],
                    self.matrices[matrix].columns.get_level_values(2).tolist() + empty_extra_columns[2],
                ]
            )
            if matrix == _ENUM["Y"]:
                new_columns = self.matrices[matrix].columns

        else:
            if matrix in [_ENUM["v"], _ENUM["e"]]:
                new_index = self.matrices[matrix].index
            else:
                empty_extra_index = [[], [], []]
                if self.table == SUT:
                    items_to_add_on_rows = self.new_activities if item_row == MI["a"] else self.new_commodities
                else:
                    items_to_add_on_rows = self.new_sectors

                for region in self.regions:
                    for item in items_to_add_on_rows:
                        empty_extra_index[0].append(region)
                        empty_extra_index[1].append(item_row)
                        empty_extra_index[2].append(item)
                new_index = pd.MultiIndex.from_arrays(
                    [
                        self.matrices[matrix].index.get_level_values(0).tolist() + empty_extra_index[0],
                        self.matrices[matrix].index.get_level_values(1).tolist() + empty_extra_index[1],
                        self.matrices[matrix].index.get_level_values(2).tolist() + empty_extra_index[2],
                    ]
                )

            empty_columns = [[], [], []]
            if self.table == SUT:
                items_to_add_on_cols = self.new_activities if item_col == MI["a"] else self.new_commodities
            else:
                items_to_add_on_cols = self.new_sectors
            for region in self.regions:
                for item in items_to_add_on_cols:
                    empty_columns[0].append(region)
                    empty_columns[1].append(item_col)
                    empty_columns[2].append(item)
            new_columns = pd.MultiIndex.from_arrays(empty_columns)

        return new_index, new_columns

    @staticmethod
    def _inventory_factor_or_sector_total(inventory: pd.DataFrame) -> float:
        """Return the total quantity across sector and factor rows for one inventory."""

        if INC["item_type"] not in inventory.columns or INC["quantity"] not in inventory.columns:
            return float("nan")

        mask = inventory[INC["item_type"]].fillna("").astype(str).isin([MI["f"], MI["s"]])
        if not mask.any():
            return 0.0

        return float(pd.to_numeric(inventory.loc[mask, INC["quantity"]], errors="coerce").fillna(0.0).sum())

    def fill_slices(
        self,
        activity: str,
        VA_fix: bool = False,
        accept_non_unitary_sum: bool = False,
    ) -> None:
        """Fill all coefficient slices for one target item from its inventories."""

        slices = self.get_empty_table_slices()
        if self.table == IOT:
            slices_uncertainty = slices["z"] * 0

        inventories = self.db.inventories[activity]

        for sheet_name, inventory in inventories.items():
            if self.leave_empty(sheet_name):
                log_time(
                    logger,
                    f"Add-sectors engine: skipping inventory {sheet_name!r} for {activity!r} because it is marked leave-empty.",
                    "debug",
                )
                continue

            regions = self.db.add_sectors_master.query(
                f"`{MSC[self.table]['inventory_sheet']}`==@sheet_name"
            )[MI["r"]].values
            target_regions = []
            for region in regions:
                if region in self.regions:
                    target_regions.append(region)
                elif region in self.db.regions_clusters:
                    target_regions.extend(self.db.regions_clusters[region])
                else:
                    raise ValueError(
                        f"{activity} is added in region {region} which is not in the database "
                        "nor in the regions cluster map."
                    )
            target_regions = list(dict.fromkeys(target_regions))
            log_time(
                logger,
                f"Add-sectors engine: processing inventory {sheet_name!r} for {activity!r} "
                f"across {len(target_regions)} target region(s): {target_regions}.",
                "debug",
            )

            if self.table == SUT:
                parent_activity = self.db.add_sectors_master.query(
                    f"`{MSC[self.table]['inventory_sheet']}`==@sheet_name"
                )[MSC[self.table]["parent_activity"]].values[0]
            else:
                parent_activity = self.db.add_sectors_master.query(
                    f"`{MSC[self.table]['inventory_sheet']}`==@sheet_name"
                )[MSC[self.table]["parent_sector"]].values[0]

            inventory = self.make_units_consistent_to_database(inventory.copy(), sheet_name)
            inventory_total = self._inventory_factor_or_sector_total(inventory)
            if accept_non_unitary_sum and pd.notna(inventory_total):
                if abs(inventory_total) <= 1e-12:
                    warnings.warn(
                        f"Inventory {sheet_name} for activity {activity!r} sums to 0 across sectors/factors "
                        "and will be skipped because accept_non_unitary_sum=True.",
                        stacklevel=2,
                    )
                    continue
                if abs(inventory_total - 1.0) > 1e-4:
                    warnings.warn(
                        f"Inventory {sheet_name} for activity {activity!r} sums to {inventory_total} across "
                        "sectors/factors and will be accepted because accept_non_unitary_sum=True.",
                        stacklevel=2,
                    )

            if pd.isna(parent_activity) is False:
                log_time(
                    logger,
                    f"Add-sectors engine: bootstrapping {activity!r} from parent {parent_activity!r} "
                    f"for inventory {sheet_name!r}.",
                    "debug",
                )
                slices = self.copy_from_parent(
                    activity, parent_activity, target_regions, slices, inventory
                )

            for region_to in target_regions:
                log_time(
                    logger,
                    f"Add-sectors engine: applying inventory {sheet_name!r} for {activity!r} in region {region_to!r}.",
                    "debug",
                )
                if VA_fix:
                    inventory, slices = self._augment_inventory_with_missing_factors(
                        inventory,
                        sheet_name=sheet_name,
                        region_to=region_to,
                        activity=activity,
                        slices=slices,
                        parent_activity=parent_activity,
                        accept_non_unitary_sum=accept_non_unitary_sum,
                    )

                if self.table == SUT:
                    slices = self.fill_commodities_inputs(
                        inventory, region_to, activity, slices, parent_activity
                    )
                else:
                    slices, slices_uncertainty = self.fill_commodities_inputs(
                        inventory, region_to, activity, slices, parent_activity, slices_uncertainty
                    )

                slices = self.fill_fact_sats_inputs(inventory, region_to, activity, "v", slices)
                slices = self.fill_fact_sats_inputs(inventory, region_to, activity, "e", slices)
                if self.table == SUT:
                    slices = self.fill_market_shares(activity, region_to, region, slices)
                slices = self.fill_final_demand(activity, region_to, region, slices)

        for matrix in slices:
            self.filled_slices[matrix] += slices[matrix]

        if self.table == IOT:
            self.filled_uncertainty_slices += slices_uncertainty

    def _augment_inventory_with_missing_factors(
        self,
        inventory: pd.DataFrame,
        *,
        sheet_name: str,
        region_to: str,
        activity: str,
        slices: dict,
        parent_activity: str | None,
        accept_non_unitary_sum: bool = False,
    ):
        """Add missing factor rows from the parent V block and rescale existing factor rows."""

        if parent_activity is None:
            return inventory, slices

        parent_column = self._parent_output_column(region_to, activity)
        if parent_column is None:
            return inventory, slices

        factor_missing = self.missing_factors_of_production.get(activity, {}).get(sheet_name, {})
        if not factor_missing:
            return inventory, slices

        factor_type_column = INC["item_type"]
        factor_item_column = INC["db_item"]
        factor_region_column = INC["db_region"]
        quantity_column = INC["quantity"]

        if factor_type_column not in inventory.columns or factor_item_column not in inventory.columns:
            return inventory, slices

        augmented_inventory = inventory.copy()
        added_rows = []
        factor_or_sector_mask = augmented_inventory[factor_type_column].fillna("").astype(str).isin(
            [MI["f"], MI["s"]]
        )

        missing_total = 0.0

        for factor in factor_missing:          
            row_labels = self._matching_factor_sat_rows(_ENUM["v"], factor,None)
            if len(row_labels) == 0:
                continue

            parent_value = self.matrices[_ENUM["v"]].loc[row_labels, parent_column]
            if isinstance(parent_value, pd.DataFrame):
                parent_value = parent_value.iloc[:, 0]
            parent_value = float(parent_value.sum())
            if parent_value == 0:
                continue
            
            #Set parent to null
            slices['v'].loc[factor,(region_to,'Sector',activity)] = 0 

            missing_total += parent_value

            new_row = inventory.iloc[0].copy()
            new_row[factor_type_column] = MI["f"]
            new_row[factor_item_column] = factor
            new_row[factor_region_column] = None
            new_row[INC["input"]] = f"Parent {factor}"
            new_row[INC["change_type"]] = inventory[INC["change_type"]].iloc[0] if INC["change_type"] in inventory.columns else "Update"
            new_row[INC["quantity"]] = parent_value
            if hasattr(self, "converted_quantity_column") and self.converted_quantity_column in new_row.index:
                new_row[self.converted_quantity_column] = parent_value
            added_rows.append(new_row)

        if missing_total != 0.0:
            scale = 1 - missing_total
            augmented_inventory.loc[factor_or_sector_mask, INC["quantity"]] = (
                augmented_inventory.loc[factor_or_sector_mask, INC["quantity"]].astype(float) * scale
            )
            if hasattr(self, "converted_quantity_column") and self.converted_quantity_column in augmented_inventory.columns:
                augmented_inventory.loc[factor_or_sector_mask, self.converted_quantity_column] = (
                    augmented_inventory.loc[factor_or_sector_mask, self.converted_quantity_column].astype(float) * scale
                )

        factor_total = augmented_inventory.loc[factor_or_sector_mask, INC["quantity"]].sum() + missing_total
        if abs(factor_total - 1.0) > 1e-4:
            if accept_non_unitary_sum:
                warnings.warn(
                    f"Augmented inventory {sheet_name} for {region_to} and activity {activity!r} sums to "
                    f"{factor_total}; continuing because accept_non_unitary_sum=True.",
                    stacklevel=2,
                )
                return (
                    pd.concat(
                        [augmented_inventory, pd.DataFrame(added_rows, columns=augmented_inventory.columns)],
                        ignore_index=True,
                    ),
                    slices,
                )
            raise InventoryRowValidationError(
                "Augmented factor inventory does not sum to 1",
                f"Inventory {sheet_name} for {region_to} and activity {activity!r} sums to {factor_total}, expected 1.0.",
            )

        return pd.concat([augmented_inventory, pd.DataFrame(added_rows, columns=augmented_inventory.columns)], ignore_index=True), slices

    def reindex_matrices(self) -> None:
        """Sort index and columns after concatenating the new slices."""
        for matrix in ("z", "e", "v", "Y"):
            for axis, labels in ((0, self.matrices[matrix].index), (1, self.matrices[matrix].columns)):
                if isinstance(labels, pd.MultiIndex):
                    self.matrices[matrix].sort_index(
                        axis=axis,
                        level=list(range(labels.nlevels)),
                        inplace=True,
                    )
                else:
                    self.matrices[matrix].sort_index(axis=axis, inplace=True)

        if self.table == IOT:
            for axis in [0, 1]:
                self.uncertainty_matrix.sort_index(axis=axis, level=list(range(3)), inplace=True)

    def make_units_consistent_to_database(
        self,
        inventory: pd.DataFrame,
        sheet_name: str,
        cqc: str = "Converted quantity",
    ) -> pd.DataFrame:
        """Convert inventory quantities to the database units using pint."""

        self.converted_quantity_column = cqc
        inventory[cqc] = 0.0
        ureg = pint.UnitRegistry()
        grouped_errors: dict[str, list[str]] = {}

        for excel_row, i in enumerate(inventory.index, start=2):
            row = inventory.loc[i]
            try:
                db_unit = self._resolve_inventory_db_unit(row)
                inventory.loc[i, cqc] = self._convert_inventory_quantity(row, db_unit, ureg)
            except InventoryRowValidationError as exc:
                grouped_errors.setdefault(exc.reason, []).append(
                    f"{self._format_inventory_row_context(row, excel_row)}. {exc.details}"
                )

        if grouped_errors:
            raise ValueError(self._format_inventory_validation_errors(sheet_name, grouped_errors))

        return inventory

    @staticmethod
    def _format_inventory_row_context(row: pd.Series, excel_row: int) -> str:
        """Render one inventory row with the fields most useful for troubleshooting."""

        details = [f"Excel row {excel_row}"]
        for key in ("input", "item_type", "db_item", "db_region", "unit"):
            value = row.get(INC[key], "")
            if pd.isna(value) or value == "":
                continue
            details.append(f"{INC[key]}={value!r}")

        return ", ".join(details)

    @staticmethod
    def _format_inventory_validation_errors(
        sheet_name: str, grouped_errors: dict[str, list[str]]
    ) -> str:
        """Collapse per-row issues into one message grouped by problem type."""

        lines = [f"Issues found while validating inventory sheet {sheet_name}:"]
        for reason, details in grouped_errors.items():
            lines.append(f"- {reason}")
            for detail in details:
                lines.append(f"  - {detail}")

        return "\n".join(lines)

    def _resolve_inventory_db_unit(self, row: pd.Series) -> str:
        """Resolve the database unit used by one inventory row."""

        item = row[INC["item_type"]]
        db_item = row[INC["db_item"]]

        if item in (MI["c"], MI["s"]):
            if self.table == SUT:
                if db_item in self.commodities:
                    return self.units[item].loc[db_item, "unit"]
                if db_item in self.new_commodities:
                    return self.db.add_sectors_master.query(f"{MI['c']}==@db_item")[
                        MSC[self.table]["unit"]
                    ].values[0]
                if db_item in self.db.commodities_clusters:
                    db_units = [
                        self.units[item].loc[commodity, "unit"]
                        for commodity in self.db.commodities_clusters[db_item]
                    ]
                    if len(set(db_units)) != 1:
                        raise InventoryRowValidationError(
                            "Cluster members use inconsistent database units",
                            f"Commodities in cluster {db_item!r} have different units.",
                        )
                    return db_units[0]
                raise InventoryRowValidationError(
                    "Database item could not be resolved",
                    f"{INC['db_item']} {db_item!r} is not an existing commodity, a new commodity, or a commodity cluster.",
                )

            if db_item in self.sectors:
                return self.units[item].loc[db_item, "unit"]
            if db_item in self.new_sectors:
                return self.db.add_sectors_master.query(f"{MI['s']}==@db_item")[MSC[self.table]["unit"]].values[0]
            if db_item in self.db.sectors_clusters:
                db_units = [self.units[item].loc[sector, "unit"] for sector in self.db.sectors_clusters[db_item]]
                if len(set(db_units)) != 1:
                    raise InventoryRowValidationError(
                        "Cluster members use inconsistent database units",
                        f"Sectors in cluster {db_item!r} have different units.",
                    )
                return db_units[0]
            raise InventoryRowValidationError(
                "Database item could not be resolved",
                f"{INC['db_item']} {db_item!r} is not an existing sector, a new sector, or a sector cluster.",
            )

        if item == MI["a"]:
            raise InventoryRowValidationError(
                "Unsupported inventory item type",
                f"{INC['item_type']} {item!r} is not supported here: activities cannot be supplied to other activities.",
            )

        if item == MI["k"]:
            if db_item not in self.units[MI["k"]].index:
                raise InventoryRowValidationError(
                    "Database item could not be resolved",
                    f"Unknown satellite account {db_item!r}.",
                )
            return self.units[MI["k"]].loc[db_item, "unit"]

        if item == MI["f"]:
            if db_item in self.units[MI["f"]].index:
                return self.units[MI["f"]].loc[db_item, "unit"]
            if db_item in self.factors_clusters:
                db_units = [self.units[MI["f"]].loc[factor, "unit"] for factor in self.factors_clusters[db_item]]
                if len(set(db_units)) != 1:
                    raise InventoryRowValidationError(
                        "Cluster members use inconsistent database units",
                        f"Factors in cluster {db_item!r} have different units.",
                    )
                return db_units[0]
            raise InventoryRowValidationError(
                "Database item could not be resolved",
                f"Unknown factor {db_item!r}.",
            )

        raise InventoryRowValidationError(
            "Unsupported inventory item type",
            f"{INC['item_type']} {item!r} is not recognized.",
        )

    def _convert_inventory_quantity(
        self, row: pd.Series, db_unit: str, ureg: pint.UnitRegistry
    ) -> float:
        """Convert one inventory quantity to the resolved database unit."""

        input_unit = row[INC["unit"]]
        quantity = row[INC["quantity"]]

        if input_unit == db_unit:
            return quantity

        try:
            source_quantity = ureg(input_unit)
            if source_quantity.is_compatible_with(db_unit):
                return quantity * source_quantity.to(db_unit).magnitude
        except pint.errors.PintError as exc:
            raise InventoryRowValidationError(
                "Unit conversion could not be evaluated",
                f"{INC['unit']} {input_unit!r} could not be converted to database unit {db_unit!r}: {exc}.",
            ) from exc

        raise InventoryRowValidationError(
            "Provided unit is not compatible with the database unit",
            f"{INC['unit']} {input_unit!r} is not convertible to database unit {db_unit!r}.",
        )

    def copy_from_parent(
        self,
        activity: str,
        parent_activity: str,
        target_regions: list[str],
        slices: dict[str, pd.DataFrame],
        inventory: pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        """Bootstrap a new item from its parent column before inventory overrides."""

        for region in target_regions:
            if self.table == SUT:
                slices[_ENUM["u"]].loc[self.matrices[_ENUM["u"]].index, (region, MI["a"], activity)] = (
                    self.matrices[_ENUM["u"]].loc[:, (region, MI["a"], parent_activity)].values
                )
                slices[_ENUM["v"]].loc[:, (region, MI["a"], activity)] = (
                    self.matrices[_ENUM["v"]].loc[:, (region, MI["a"], parent_activity)].values
                )
                slices[_ENUM["e"]].loc[:, (region, MI["a"], activity)] = (
                    self.matrices[_ENUM["e"]].loc[:, (region, MI["a"], parent_activity)].values
                )
            else:
                slices[_ENUM["z"]].loc[self.matrices[_ENUM["z"]].index, (region, MI["s"], activity)] = (
                    self.matrices[_ENUM["z"]].loc[:, (region, MI["s"], parent_activity)].values
                )
                slices[_ENUM["v"]].loc[:, (region, MI["s"], activity)] = (
                    self.matrices[_ENUM["v"]].loc[:, (region, MI["s"], parent_activity)].values
                )
                slices[_ENUM["e"]].loc[:, (region, MI["s"], activity)] = (
                    self.matrices[_ENUM["e"]].loc[:, (region, MI["s"], parent_activity)].values
                )

            item_to_query = MI["c"] if self.table == SUT else MI["s"]
            commodities_to_nullify = [
                (c, r)
                for c, r in zip(
                    inventory.query(
                        f"`{INC['item_type']}`=='{item_to_query}' & `{INC['change_type']}`=='Update'"
                    )[INC["db_item"]].values,
                    inventory.query(
                        f"`{INC['item_type']}`=='{item_to_query}' & `{INC['change_type']}`=='Update'"
                    )[INC["db_region"]].values,
                )
            ]
            satellites_to_nullify = inventory.query(
                f"`{INC['item_type']}`=='{MI['k']}' & `{INC['change_type']}`=='Update'"
            )[[INC["db_item"], INC["db_region"]]].itertuples(index=False, name=None)
            factors_to_nullify = inventory.query(
                f"`{INC['item_type']}`=='{MI['f']}' & `{INC['change_type']}`=='Update'"
            )[[INC["db_item"], INC["db_region"]]].itertuples(index=False, name=None)

            for c, r in commodities_to_nullify:
                if r in self.regions:
                    if self.table == SUT:
                        if c in self.commodities:
                            slices[_ENUM["u"]].loc[(r, MI["c"], c), (region, MI["a"], activity)] = 0
                        if c in self.db.commodities_clusters:
                            slices[_ENUM["u"]].loc[
                                (r, MI["c"], self.db.commodities_clusters[c]), (region, MI["a"], activity)
                            ] = 0
                    else:
                        if c in self.sectors:
                            slices[_ENUM["z"]].loc[(r, MI["s"], c), (region, MI["s"], activity)] = 0
                        if c in self.db.sectors_clusters:
                            slices[_ENUM["z"]].loc[
                                (r, MI["s"], self.db.sectors_clusters[c]), (region, MI["s"], activity)
                            ] = 0
                elif r in self.db.regions_clusters:
                    if self.table == SUT:
                        if c in self.commodities:
                            slices[_ENUM["u"]].loc[
                                (self.db.regions_clusters[r], MI["c"], c), (region, MI["a"], activity)
                            ] = 0
                        if c in self.db.commodities_clusters:
                            slices[_ENUM["u"]].loc[
                                (
                                    self.db.regions_clusters[r],
                                    MI["c"],
                                    self.db.commodities_clusters[c],
                                ),
                                (region, MI["a"], activity),
                            ] = 0
                    else:
                        if c in self.sectors:
                            slices[_ENUM["z"]].loc[
                                (self.db.regions_clusters[r], MI["s"], c), (region, MI["s"], activity)
                            ] = 0
                        if c in self.db.sectors_clusters:
                            slices[_ENUM["z"]].loc[
                                (
                                    self.db.regions_clusters[r],
                                    MI["s"],
                                    self.db.sectors_clusters[c],
                                ),
                                (region, MI["s"], activity),
                            ] = 0

            for k, row_region in satellites_to_nullify:
                row_labels = self._matching_factor_sat_rows(_ENUM["e"], k, row_region)
                if len(row_labels):
                    slices[_ENUM["e"]].loc[row_labels, (region, MI["a" if self.table == SUT else "s"], activity)] = 0

            for f, row_region in factors_to_nullify:
                row_labels = self._matching_factor_sat_rows(_ENUM["v"], f, row_region)
                if len(row_labels):
                    slices[_ENUM["v"]].loc[row_labels, (region, MI["a" if self.table == SUT else "s"], activity)] = 0

        return slices

    def fill_commodities_inputs(
        self,
        full_inventory: pd.DataFrame,
        region_to: str,
        activity: str,
        slices: dict[str, pd.DataFrame],
        parent_activity: str,
        slices_uncertainty: pd.DataFrame | None = None,
    ):
        """Fill commodity or sector inputs for one new target item."""

        item_to_query = MI["c"] if self.table == SUT else MI["s"]
        inventory = full_inventory.query(f"`{INC['item_type']}`=='{item_to_query}'")

        for i in inventory.index:
            input_item = inventory.loc[i, INC["db_item"]]
            sec_com_clusters = (
                self.db.commodities_clusters.keys() if self.table == SUT else self.db.sectors_clusters.keys()
            )
            is_cluster = input_item in sec_com_clusters
            is_new = input_item not in self.db.get_index(item_to_query) and not is_cluster

            quantity = inventory.loc[i, self.converted_quantity_column]
            region_from = inventory.loc[i, INC["db_region"]]
            change_type = inventory.loc[i, INC["change_type"]]

            if change_type == "Update":
                if region_from in self.regions:
                    if self.table == SUT:
                        if is_cluster:
                            com_use = self.matrices[_ENUM["Z"]].loc[
                                (region_from, MI["c"], self.db.commodities_clusters[input_item]),
                                (region_to, MI["a"], sn),
                            ]
                            if isinstance(com_use, pd.Series):
                                com_use = com_use.to_frame()
                            u_share = com_use.sum(1) / com_use.sum().sum() * quantity
                            if isinstance(u_share, pd.Series):
                                u_share = u_share.to_frame()
                            u_share.columns = pd.MultiIndex.from_arrays([[region_to], [MI["a"]], [activity]])
                            slices[_ENUM["u"]].loc[u_share.index, u_share.columns] += u_share.values
                        else:
                            slices[_ENUM["u"]].loc[(region_from, MI["c"], input_item), (region_to, MI["a"], activity)] += quantity
                    else:
                        if is_cluster:
                            com_use = self.matrices[_ENUM["Z"]].loc[
                                (region_from, sn, self.db.sectors_clusters[input_item]),
                                (region_to, sn, sn),
                            ]
                            if isinstance(com_use, pd.Series):
                                com_use = com_use.to_frame()
                            z_share = com_use.sum(1) / com_use.sum().sum() * quantity
                            if isinstance(z_share, pd.Series):
                                z_share = z_share.to_frame()
                            z_share.columns = pd.MultiIndex.from_arrays([[region_to], [MI["s"]], [activity]])
                            slices[_ENUM["z"]].loc[z_share.index, z_share.columns] += z_share.values
                        else:
                            slices[_ENUM["z"]].loc[(region_from, sn, input_item), (region_to, sn, activity)] += quantity

                elif region_from in self.db.regions_clusters:
                    if not is_new:
                        if self.table == SUT:
                            if input_item in self.commodities:
                                if pd.isna(parent_activity) is False:
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (self.db.regions_clusters[region_from], MI["c"], input_item),
                                        (region_to, MI["a"], parent_activity),
                                    ]
                                else:
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (self.db.regions_clusters[region_from], MI["c"], input_item),
                                        (region_to, MI["a"], sn),
                                    ]
                                if isinstance(com_use, pd.Series):
                                    com_use = com_use.to_frame()
                                u_share = com_use.sum(1) / com_use.sum().sum() * quantity
                                if isinstance(u_share, pd.Series):
                                    u_share = u_share.to_frame()
                                u_share.columns = pd.MultiIndex.from_arrays([[region_to], [MI["a"]], [activity]])
                                slices[_ENUM["u"]].loc[u_share.index, u_share.columns] += u_share.values
                            elif is_cluster:
                                if pd.isna(parent_activity) is False:
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (
                                            self.db.regions_clusters[region_from],
                                            MI["c"],
                                            self.db.commodities_clusters[input_item],
                                        ),
                                        (region_to, MI["a"], parent_activity),
                                    ]
                                else:
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (
                                            self.db.regions_clusters[region_from],
                                            MI["c"],
                                            self.db.commodities_clusters[input_item],
                                        ),
                                        (region_to, MI["a"], sn),
                                    ]
                                if isinstance(com_use, pd.Series):
                                    com_use = com_use.to_frame()
                                u_share = com_use.sum(1) / com_use.sum().sum() * quantity
                                if isinstance(u_share, pd.Series):
                                    u_share = u_share.to_frame()
                                u_share.columns = pd.MultiIndex.from_arrays([[region_to], [MI["a"]], [activity]])
                                slices[_ENUM["u"]].loc[u_share.index, u_share.columns] += u_share.values
                        else:
                            if input_item in self.sectors:
                                if pd.isna(parent_activity) is False:
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (self.db.regions_clusters[region_from], sn, input_item),
                                        (region_to, sn, parent_activity),
                                    ]
                                    slices_uncertainty.loc[
                                        (self.db.regions_clusters[region_from], sn, input_item),
                                        (region_to, sn, activity),
                                    ] = -1 + self.uncertainty_values["original s specific, r cluster"]
                                    self.uncertainty_matrix.loc[
                                        (self.db.regions_clusters[region_from], sn, input_item),
                                        (region_to, sn, parent_activity),
                                    ] = self.uncertainty_values["original s specific, r cluster"]
                                else:
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (self.db.regions_clusters[region_from], sn, input_item),
                                        (region_to, sn, sn),
                                    ]
                                    slices_uncertainty.loc[
                                        (self.db.regions_clusters[region_from], sn, input_item),
                                        (region_to, sn, activity),
                                    ] = -1 + self.uncertainty_values["original s specific_no parent, r cluster"]
                                if isinstance(com_use, pd.Series):
                                    com_use = com_use.to_frame()
                                z_share = com_use.sum(1) / com_use.sum().sum() * quantity
                                if isinstance(z_share, pd.Series):
                                    z_share = z_share.to_frame()
                                z_share.columns = pd.MultiIndex.from_arrays([[region_to], [MI["s"]], [activity]])
                                slices[_ENUM["z"]].loc[z_share.index, z_share.columns] += z_share.values

                            elif is_cluster:
                                if pd.isna(parent_activity) is False:
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (
                                            self.db.regions_clusters[region_from],
                                            sn,
                                            self.db.sectors_clusters[input_item],
                                        ),
                                        (region_to, sn, parent_activity),
                                    ]
                                    slices_uncertainty.loc[
                                        (
                                            self.db.regions_clusters[region_from],
                                            sn,
                                            self.db.sectors_clusters[input_item],
                                        ),
                                        (region_to, sn, activity),
                                    ] = -1 + self.uncertainty_values["original s cluster, r cluster"]
                                    self.uncertainty_matrix.loc[
                                        (
                                            self.db.regions_clusters[region_from],
                                            sn,
                                            self.db.sectors_clusters[input_item],
                                        ),
                                        (region_to, sn, parent_activity),
                                    ] = self.uncertainty_values["original s cluster, r cluster"]
                                else:
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (
                                            self.db.regions_clusters[region_from],
                                            sn,
                                            self.db.sectors_clusters[input_item],
                                        ),
                                        (region_to, sn, sn),
                                    ]
                                    slices_uncertainty.loc[
                                        (
                                            self.db.regions_clusters[region_from],
                                            sn,
                                            self.db.sectors_clusters[input_item],
                                        ),
                                        (region_to, sn, activity),
                                    ] = -1 + self.uncertainty_values["original s cluster_no parent, r cluster"]
                                if isinstance(com_use, pd.Series):
                                    com_use = com_use.to_frame()
                                z_share = com_use.sum(1) / com_use.sum().sum() * quantity
                                if isinstance(z_share, pd.Series):
                                    z_share = z_share.to_frame()
                                z_share.columns = pd.MultiIndex.from_arrays([[region_to], [MI["s"]], [activity]])
                                slices[_ENUM["z"]].loc[z_share.index, z_share.columns] += z_share.values

                    else:
                        if self.table == SUT:
                            if input_item in self.commodities or input_item in self.new_commodities:
                                input_item_parent = self.db.add_sectors_master.query(f"{MI['c']}==@input_item")[
                                    MSC[self.table]["parent_activity"]
                                ].values[0]
                                if pd.isna(input_item_parent):
                                    slices[_ENUM["u"]].loc[(region_to, MI["c"], input_item), (region_to, MI["a"], activity)] += quantity
                                    warnings.warn(
                                        f"In region {region_to} for activity {activity} and input commodity {input_item}, "
                                        "no parent activity is defined. Therefore, only domestic consumption is assumed."
                                    )
                                else:
                                    parent_selector = parent_activity if pd.isna(parent_activity) is False else sn
                                    com_use = self.matrices[_ENUM["U"]].loc[
                                        (self.db.regions_clusters[region_from], sn, input_item_parent),
                                        (region_to, sn, parent_selector),
                                    ]
                                    if isinstance(com_use, pd.Series):
                                        com_use = com_use.to_frame()
                                    u_share = com_use.sum(1) / com_use.sum().sum() * quantity
                                    if isinstance(u_share, pd.Series):
                                        u_share = u_share.to_frame()
                                    u_share.columns = pd.MultiIndex.from_arrays([[region_to], [MI["a"]], [activity]])
                                    u_share.index = pd.MultiIndex.from_arrays(
                                        [
                                            u_share.index.get_level_values(0),
                                            u_share.index.get_level_values(1),
                                            [input_item] * len(u_share.index),
                                        ]
                                    )
                                    slices[_ENUM["u"]].loc[u_share.index, u_share.columns] += u_share.values
                        else:
                            if input_item in self.sectors or input_item in self.new_sectors:
                                input_item_parent = self.db.add_sectors_master.query(f"{MI['s']}==@input_item")[
                                    MSC[self.table]["parent_sector"]
                                ].values[0]
                                if pd.isna(input_item_parent):
                                    slices[_ENUM["z"]].loc[(region_to, MI["s"], input_item), (region_to, MI["s"], activity)] += quantity
                                    slices_uncertainty.loc[
                                        (self.db.regions_clusters[region_from], sn, input_item),
                                        (region_to, sn, activity),
                                    ] = -1 + self.uncertainty_values["disag s specific_no parent, r cluster"]
                                    warnings.warn(
                                        f"In region {region_to} for sector {activity} and input sector {input_item}, "
                                        "no parent sector is defined. Therefore, only domestic consumption is assumed."
                                    )
                                else:
                                    parent_selector = parent_activity if pd.isna(parent_activity) is False else sn
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (self.db.regions_clusters[region_from], sn, input_item_parent),
                                        (region_to, sn, parent_selector),
                                    ]
                                    slices_uncertainty.loc[
                                        (self.db.regions_clusters[region_from], sn, input_item),
                                        (region_to, sn, activity),
                                    ] = -1 + self.uncertainty_values["disag s specific, r cluster"]
                                    if isinstance(com_use, pd.Series):
                                        com_use = com_use.to_frame()
                                    z_share = com_use.sum(1) / com_use.sum().sum() * quantity
                                    if isinstance(z_share, pd.Series):
                                        z_share = z_share.to_frame()
                                    z_share.columns = pd.MultiIndex.from_arrays([[region_to], [MI["s"]], [activity]])
                                    z_share.index = pd.MultiIndex.from_arrays(
                                        [
                                            z_share.index.get_level_values(0),
                                            z_share.index.get_level_values(1),
                                            [input_item] * len(z_share.index),
                                        ]
                                    )
                                    slices[_ENUM["z"]].loc[z_share.index, z_share.columns] += z_share.values

            elif change_type == "Percentage":
                r_cluster = 0
                s_cluster = 0
                if region_from in self.regions:
                    regs = [region_from]
                elif region_from in self.db.regions_clusters:
                    r_cluster = 1
                    regs = self.db.regions_clusters[region_from]
                else:
                    raise ValueError(f"Unknown DB region {region_from}.")

                if self.table == SUT:
                    if input_item in self.commodities or input_item in self.new_commodities:
                        inputs = [input_item]
                    elif input_item in self.db.commodities_clusters:
                        inputs = self.db.commodities_clusters[input_item]
                    else:
                        raise ValueError(f"Unknown commodity {input_item}.")

                    if activity in self.parented_activities:
                        parent = self.db.add_sectors_master.query(f"{MI['a']}==@activity")[
                            MSC[self.table]["parent_activity"]
                        ].values[0]
                        old_values = self.matrices[_ENUM["u"]].loc[(regs, MI["c"], inputs), (region_to, MI["a"], parent)]
                        if isinstance(old_values, pd.Series):
                            old_values = old_values.to_frame()
                        old_values *= 1 + quantity
                        old_values.columns = pd.MultiIndex.from_arrays([[region_to], [MI["a"]], [activity]])
                        slices[_ENUM["u"]].update(old_values)
                    else:
                        raise ValueError(
                            f"It's not possible to apply a percentage change to activity {activity} "
                            "because it has no parent activity."
                        )

                else:
                    if input_item in self.sectors or input_item in self.new_sectors:
                        inputs = [input_item]
                    elif input_item in self.db.sectors_clusters:
                        s_cluster = 1
                        inputs = self.db.sectors_clusters[input_item]
                    else:
                        raise ValueError(f"Unknown sector {input_item}.")

                    if activity in self.parented_sectors:
                        parent_sector = self.db.add_sectors_master.query(f"{MI['s']}==@activity")[
                            MSC[self.table]["parent_sector"]
                        ].values[0]
                        old_values = self.matrices[_ENUM["z"]].loc[(regs, MI["s"], inputs), (region_to, MI["s"], parent_sector)]
                        if isinstance(old_values, pd.Series):
                            old_values = old_values.to_frame()
                        old_values *= 1 + quantity
                        old_values.columns = pd.MultiIndex.from_arrays([[region_to], [MI["s"]], [activity]])
                        slices[_ENUM["z"]].update(old_values)
                        if r_cluster == 1:
                            if s_cluster == 1:
                                value = self.uncertainty_values["original s cluster, r cluster"]
                            else:
                                value = self.uncertainty_values["original s specific, r cluster"]
                        else:
                            if s_cluster == 1:
                                value = self.uncertainty_values["original s cluster, r specific"]
                            else:
                                value = None
                        if value is not None:
                            slices_uncertainty.loc[(regs, MI["s"], inputs), (region_to, MI["s"], activity)] = -1 + value
                            self.uncertainty_matrix.loc[(regs, MI["s"], inputs), (region_to, MI["s"], parent_sector)] = value
                    else:
                        raise ValueError(
                            f"It's not possible to apply a percentage change to sector {activity} "
                            "because it has no parent sector."
                        )

        if self.table == IOT:
            return slices, slices_uncertainty
        return slices

    def fill_fact_sats_inputs(
        self,
        full_inventory: pd.DataFrame,
        region_to: str,
        activity: str,
        matrix: str,
        slices: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        """Fill factor or satellite inputs for one new target item."""

        if matrix == _ENUM["v"]:
            inventory = full_inventory.query(f"`{INC['item_type']}`=='{MI['f']}'")
        else:
            inventory = full_inventory.query(f"`{INC['item_type']}`=='{MI['k']}'")

        for i in inventory.index:
            input_item = inventory.loc[i, INC["db_item"]]
            row_region = inventory.loc[i, INC["db_region"]]
            quantity = inventory.loc[i, self.converted_quantity_column]
            change_type = inventory.loc[i, INC["change_type"]]
            row_labels = self._matching_factor_sat_rows(matrix, input_item, row_region)
            target_column = self._target_output_column(region_to, activity)

            if change_type == "Update":
                if len(row_labels) == 0:
                    continue
                
                if matrix == _ENUM["e"]:
                    weights = self._factor_sat_allocation_weights(matrix, row_labels, region_to, activity)
                else:
                    #Check if it's a factor in a cluster
                    if input_item in self.factors_clusters:
                        # Allocate based on existing structure of the cluster for sn columns
                        # If it's a SUT, we use activities as marker
                        marker = MI["a"] if self.table == SUT else MI["s"]
                        cluster_data = self.matrices[matrix].loc[row_labels, (sn, marker, sn)]
                        if isinstance(cluster_data, pd.Series):
                            cluster_data = cluster_data.to_frame()
                        
                        row_sums = cluster_data.sum(axis=1)
                        total_sum = row_sums.sum()
                        
                        if total_sum > 0:
                            weights = row_sums / total_sum
                        else:
                            weights = pd.Series(1 / len(row_labels), index=row_labels)
                    else:
                        weights = self._factor_sat_allocation_weights(matrix, row_labels, region_to, activity)
                    
                slices[matrix].loc[row_labels, target_column] += weights * quantity
            elif change_type == "Percentage":
                if len(row_labels) == 0:
                    continue
                if self.table == SUT:
                    if activity in self.parented_activities:
                        parent = self.db.add_sectors_master.query(f"{MI['a']}==@activity")[
                            MSC[self.table]["parent_activity"]
                        ].values[0]
                        old_value = self.matrices[matrix].loc[row_labels, (region_to, MI["a"], parent)]
                        slices[matrix].loc[row_labels, target_column] = old_value * (1 + quantity)
                    else:
                        raise ValueError(
                            f"It's not possible to apply a percentage change to activity {activity} "
                            "because it has no parent activity."
                        )
                else:
                    if activity in self.parented_sectors:
                        parent = self.db.add_sectors_master.query(f"{MI['s']}==@activity")[
                            MSC[self.table]["parent_sector"]
                        ].values[0]
                        old_value = self.matrices[matrix].loc[row_labels, (region_to, MI["s"], parent)]
                        slices[matrix].loc[row_labels, target_column] = old_value * (1 + quantity)
                    else:
                        raise ValueError(
                            f"It's not possible to apply a percentage change to sector {activity} "
                            "because it has no parent sector."
                        )

        return slices

    def fill_market_shares(
        self,
        activity: str,
        region: str,
        cluster_region: str,
        slices: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        """Fill SUT market-share rows from the master sheet."""

        market_shares = self.db.add_sectors_master.query(
            f"{MI['a']}==@activity & {MI['r']}==@cluster_region"
        )[MSC[self.table]["market_share"]].values
        market_shares = [0 if pd.isna(value) else value for value in market_shares]

        commodities = self.db.add_sectors_master.query(
            f"{MI['a']}==@activity & {MI['r']}==@cluster_region"
        )[MI["c"]].values
        for i, commodity in enumerate(commodities):
            if pd.isna(commodity) or commodity == "":
                continue
            slices[_ENUM["s"]].loc[(region, MI["a"], activity), (region, MI["c"], commodity)] = market_shares[i]

        return slices

    def fill_final_demand(
        self,
        activity: str,
        region: str,
        cluster_region: str,
        slices: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        """Fill final demand rows from the master sheet."""

        item_to_query = MI["a"] if self.table == SUT else MI["s"]
        other_item = MI["c"] if self.table == SUT else MI["s"]

        total_outputs = self.db.add_sectors_master.query(
            f"{item_to_query}==@activity & {MI['r']}==@cluster_region"
        )[MSC[self.table]["final_consumption"]].values
        total_outputs = [0 if pd.isna(value) else value for value in total_outputs]

        cons_categories = self.db.add_sectors_master.query(
            f"{item_to_query}==@activity & {MI['r']}==@cluster_region"
        )[MI["n"]].values
        new_cons_categories = []
        for value in cons_categories:
            if pd.isna(value):
                new_cons_categories.append(self.matrices[_ENUM["Y"]].columns.get_level_values(-1)[0])
            else:
                new_cons_categories.append(value)

        cons_region = region
        commodities = self.db.add_sectors_master.query(
            f"{item_to_query}==@activity & {MI['r']}==@cluster_region"
        )[other_item].values

        for i, commodity in enumerate(commodities):
            if pd.isna(commodity) or commodity == "":
                continue
            slices[_ENUM["Y"]].loc[(region, other_item, commodity), (cons_region, MI["n"], new_cons_categories[i])] += total_outputs[i]

        return slices

    def leave_empty(self, sheet_name: str) -> bool:
        """Return whether one inventory sheet should be left empty."""

        empty = self.db.add_sectors_master.query(
            f"`{MSC[self.table]['inventory_sheet']}`==@sheet_name"
        )[MSC[self.table]["leave_empty"]].values[0]
        if empty in (True, False):
            return bool(empty)
        if empty in (None, ""):
            return False
        if isinstance(empty, float):
            if empty == 1:
                return True
            if empty == 0 or pd.isna(empty):
                return False
        raise ValueError(
            f"'{MSC[self.table]['leave_empty']}' for inventory {sheet_name} must be boolean or empty, got {empty}."
        )

    def add_slices(self) -> None:
        """Concatenate the filled slices into the coefficient matrices."""

        for matrix in _MATRIX_SLICES_MAP[self.table]:
            concat = _MATRIX_SLICES_MAP[self.table][matrix]["concat"]
            self.matrices[matrix] = pd.concat([self.matrices[matrix], self.filled_slices[matrix]], axis=concat)
            self.matrices[matrix] = (
                self.matrices[matrix].groupby(level=list(range(self.matrices[matrix].index.nlevels))).sum()
            )
            self.matrices[matrix] = (
                self.matrices[matrix].T.groupby(level=list(range(self.matrices[matrix].columns.nlevels))).sum().T
            )

        if self.table == IOT:
            self.uncertainty_matrix = pd.concat(
                [self.uncertainty_matrix, self.filled_uncertainty_slices], axis=1
            )
            self.uncertainty_matrix = (
                self.uncertainty_matrix.groupby(level=list(range(self.uncertainty_matrix.index.nlevels))).sum()
            )
            self.uncertainty_matrix = (
                self.uncertainty_matrix.T.groupby(level=list(range(self.uncertainty_matrix.columns.nlevels))).sum().T
            )

    def get_mario_indices(self) -> None:
        """Rebuild the database index mapping from the updated coefficient blocks."""

        mario_indices = {}
        for item in MI.vars:
            if item == "r":
                mario_indices[item] = {"main": sorted(set(self.matrices[_ENUM["z"]].index.get_level_values(0)))}
            elif self.table == SUT and item in {"a", "s"}:
                mario_indices[item] = {
                    "main": sorted(
                        set(self.matrices[_ENUM["z"]].loc[(sn, MI["a"], sn), :].index.get_level_values(2))
                    )
                }
            elif self.table == SUT and item == "c":
                mario_indices[item] = {
                    "main": sorted(
                        set(self.matrices[_ENUM["z"]].loc[(sn, MI["c"], sn), :].index.get_level_values(2))
                    )
                }
            elif self.table == IOT and item == "s":
                mario_indices[item] = {
                    "main": sorted(
                        set(self.matrices[_ENUM["z"]].loc[(sn, MI["s"], sn), :].index.get_level_values(2))
                    )
                }
            elif item == "n":
                mario_indices[item] = {"main": sorted(set(self.matrices[_ENUM["Y"]].columns.get_level_values(2)))}
            elif item == "k":
                if isinstance(self.matrices[_ENUM["e"]].index, pd.MultiIndex):
                    mario_indices[item] = {
                        "main": sorted(set(self.matrices[_ENUM["e"]].index.get_level_values(-1)))
                    }
                else:
                    mario_indices[item] = {"main": sorted(set(self.matrices[_ENUM["e"]].index))}
            elif item == "f":
                if isinstance(self.matrices[_ENUM["v"]].index, pd.MultiIndex):
                    mario_indices[item] = {
                        "main": sorted(set(self.matrices[_ENUM["v"]].index.get_level_values(-1)))
                    }
                else:
                    mario_indices[item] = {"main": sorted(set(self.matrices[_ENUM["v"]].index))}

        self.indeces = mario_indices


def collect_add_sector_matrices(instance, scenario: str = "baseline") -> dict[str, pd.DataFrame]:
    """Collect the coefficient and reference blocks required by the add-sectors engine."""

    matrices = {
        _ENUM["z"]: instance.get_block_as_pandas("z", scenario=scenario) if instance.has_matrix("z", scenario=scenario) else instance.resolve("z", scenario=scenario),
        _ENUM["e"]: instance.get_block_as_pandas("e", scenario=scenario) if instance.has_matrix("e", scenario=scenario) else instance.resolve("e", scenario=scenario),
        _ENUM["v"]: instance.get_block_as_pandas("v", scenario=scenario) if instance.has_matrix("v", scenario=scenario) else instance.resolve("v", scenario=scenario),
        _ENUM["Y"]: instance.get_block_as_pandas("Y", scenario=scenario) if instance.has_matrix("Y", scenario=scenario) else instance.resolve("Y", scenario=scenario),
        _ENUM["EY"]: instance.get_block_as_pandas("EY", scenario=scenario) if instance.has_matrix("EY", scenario=scenario) else instance.resolve("EY", scenario=scenario),
        _ENUM["VY"]: instance.get_block_as_pandas("VY", scenario=scenario) if instance.has_matrix("VY", scenario=scenario) else instance.resolve("VY", scenario=scenario),
        _ENUM["Z"]: instance.get_block_as_pandas("Z", scenario=scenario) if instance.has_matrix("Z", scenario=scenario) else instance.resolve("Z", scenario=scenario),
        _ENUM["E"]: instance.get_block_as_pandas("E", scenario=scenario) if instance.has_matrix("E", scenario=scenario) else instance.resolve("E", scenario=scenario),
        _ENUM["V"]: instance.get_block_as_pandas("V", scenario=scenario) if instance.has_matrix("V", scenario=scenario) else instance.resolve("V", scenario=scenario),
    }
    if instance.table_type == SUT:
        matrices[_ENUM["u"]] = instance.get_block_as_pandas("u", scenario=scenario) if instance.has_matrix("u", scenario=scenario) else instance.resolve("u", scenario=scenario)
        matrices[_ENUM["s"]] = instance.get_block_as_pandas("s", scenario=scenario) if instance.has_matrix("s", scenario=scenario) else instance.resolve("s", scenario=scenario)
        matrices[_ENUM["U"]] = instance.get_block_as_pandas("U", scenario=scenario) if instance.has_matrix("U", scenario=scenario) else instance.resolve("U", scenario=scenario)
        matrices[_ENUM["S"]] = instance.get_block_as_pandas("S", scenario=scenario) if instance.has_matrix("S", scenario=scenario) else instance.resolve("S", scenario=scenario)
    return matrices


def collect_missing_factor_of_production_inputs(instance) -> dict[str, dict[str, dict[object, list[str]]]]:
    """Collect missing factor-of-production rows for every inventory sheet."""

    if not hasattr(instance, "inventories"):
        instance.missing_factors_of_production = {}
        return {}

    factor_units = instance.units.get(MI["f"])
    if factor_units is None or factor_units.empty:
        warnings.warn("No factors of production in the database.", stacklevel=2)
        instance.missing_factors_of_production = {}
        return {}

    item_type_column = INC["item_type"]
    db_item_column = INC["db_item"]
    db_region_column = INC["db_region"]
    expected_factors = [
        str(factor).strip() for factor in factor_units.index.tolist() if str(factor).strip()
    ]
    factor_clusters = getattr(instance, "factors_clusters", {}) or {}

    missing_factors: dict[str, dict[str, dict[object, list[str]]]] = {}

    for activity, inventories in instance.inventories.items():
        activity_missing: dict[str, dict[object, list[str]]] = {}
        for sheet_name, inventory in inventories.items():
            if item_type_column not in inventory.columns or db_item_column not in inventory.columns:
                continue

            factor_rows = inventory.loc[
                inventory[item_type_column].fillna("").astype(str).eq(MI["f"]),
                [db_item_column] + ([db_region_column] if db_region_column in inventory.columns else []),
            ]

            present_factors: set[str] = set()
            for raw_factor in factor_rows[db_item_column].dropna().tolist():
                factor_name = str(raw_factor).strip()
                if not factor_name:
                    continue
                present_factors.add(factor_name)
                present_factors.update(
                    str(member).strip()
                    for member in factor_clusters.get(factor_name, [])
                    if str(member).strip()
                )

            missing = [factor for factor in expected_factors if factor not in present_factors]

            if missing:
                activity_missing[sheet_name] = missing

        if activity_missing:
            missing_factors[activity] = activity_missing

    instance.missing_factors_of_production = missing_factors
    return missing_factors


def warn_missing_factor_of_production_inputs(instance) -> None:
    """Warn when workbook inventories omit database factor-of-production rows."""

    missing_factors = collect_missing_factor_of_production_inputs(instance)
    if not missing_factors:
        return

    warning_lines = ["Factors of production missing in add-sectors inventories:"]

    for activity, sheets in sorted(missing_factors.items()):
        for sheet_name, factors in sorted(sheets.items()):
            factor_list = ", ".join(sorted(dict.fromkeys(factor.capitalize() for factor in factors)))
            warning_lines.append(f"- {sheet_name} [{activity}]: {factor_list}")

    warnings.warn("\n".join(warning_lines), stacklevel=2)


def run_add_sector_engine(
    instance,
    scenario: str = "baseline",
    ignore_warnings: bool = True,
    VA_fix: bool = False,
    accept_non_unitary_sum: bool = False,
) -> dict[str, pd.DataFrame]:
    """Run the add-sectors engine and return updated coefficient matrices."""

    if not hasattr(instance, "inventories"):
        raise LackOfInput("Inventory sheets are not loaded. Use read_inventory_sheets(...) first.")

    matrices = collect_add_sector_matrices(instance, scenario=scenario)
    engine = AddSectorEngine(instance, matrices, ignore_warnings=ignore_warnings)
    engine.missing_factors_of_production = getattr(instance, "missing_factors_of_production", {})
    if instance.table_type == IOT:
        return engine.to_iot(VA_fix=VA_fix, accept_non_unitary_sum=accept_non_unitary_sum)
    return engine.to_sut()


# Backward-compatible aliases for the first port of the workflow.
AdvancedAddSectorEngine = AddSectorEngine
collect_advanced_add_sector_matrices = collect_add_sector_matrices
run_advanced_add_sector_engine = run_add_sector_engine
