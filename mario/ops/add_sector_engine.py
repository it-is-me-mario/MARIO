"""Add-sectors engine for inventory-driven structural insertion."""

from __future__ import annotations

import copy
import warnings
from copy import deepcopy

import pandas as pd
import pint

from mario.log_exc.exceptions import LackOfInput
from mario.model.conventions import IOT, SUT, _ENUM, _MASTER_INDEX as MI
from mario.ops.add_sector_specs import (
    ADVANCED_ADD_SECTOR_INVENTORY_SHEET_COLUMNS as INC,
    ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS as MSC,
)


sn = slice(None)


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

        if ignore_warnings:
            warnings.filterwarnings("ignore")

    def to_iot(self):
        """Return an IOT with the new sectors inserted in coefficient form."""

        if self.table != IOT:
            raise ValueError("This method can only be used for IOT matrices.")

        self.add_new_units(MI["s"])
        empty_slices = self.get_empty_table_slices()

        self.filled_slices = deepcopy(empty_slices)
        self.filled_uncertainty_slices = empty_slices["z"] * 0 + 1
        self.uncertainty_matrix = deepcopy(self.matrices[_ENUM["z"]]) * 0 + 1

        for sector in self.new_sectors:
            self.fill_slices(sector)

        self.add_slices()
        self.reindex_matrices()
        self.get_mario_indices()

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

    def fill_slices(self, activity: str) -> None:
        """Fill all coefficient slices for one target item from its inventories."""

        slices = self.get_empty_table_slices()
        if self.table == IOT:
            slices_uncertainty = slices["z"] * 0

        inventories = self.db.inventories[activity]

        for sheet_name, inventory in inventories.items():
            if self.leave_empty(sheet_name):
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

            if self.table == SUT:
                parent_activity = self.db.add_sectors_master.query(
                    f"`{MSC[self.table]['inventory_sheet']}`==@sheet_name"
                )[MSC[self.table]["parent_activity"]].values[0]
            else:
                parent_activity = self.db.add_sectors_master.query(
                    f"`{MSC[self.table]['inventory_sheet']}`==@sheet_name"
                )[MSC[self.table]["parent_sector"]].values[0]

            if pd.isna(parent_activity) is False:
                slices = self.copy_from_parent(
                    activity, parent_activity, target_regions, slices, inventory
                )

            inventory = self.make_units_consistent_to_database(inventory.copy(), sheet_name)

            for region_to in target_regions:
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

    def reindex_matrices(self) -> None:
        """Sort index and columns after concatenating the new slices."""

        matrices_levels = {
            "z": {0: 3, 1: 3},
            "e": {0: 1, 1: 3},
            "v": {0: 1, 1: 3},
            "Y": {0: 3, 1: 3},
        }

        for matrix, axes in matrices_levels.items():
            for axis, nlevels in axes.items():
                levels = list(range(nlevels))
                self.matrices[matrix].sort_index(axis=axis, level=levels, inplace=True)

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
        inventory[cqc] = ""
        ureg = pint.UnitRegistry()

        for i in inventory.index:
            item = inventory.loc[i, INC["item_type"]]
            if item in (MI["c"], MI["s"]):
                if self.table == SUT:
                    if inventory.loc[i, INC["db_item"]] in self.commodities:
                        db_unit = self.units[item].loc[inventory.loc[i, INC["db_item"]], "unit"]
                    elif inventory.loc[i, INC["db_item"]] in self.new_commodities:
                        dummy = inventory.loc[i, INC["db_item"]]
                        db_unit = self.db.add_sectors_master.query(f"{MI['c']}==@dummy")[
                            MSC[self.table]["unit"]
                        ].values[0]
                    elif inventory.loc[i, INC["db_item"]] in self.db.commodities_clusters:
                        db_units = [
                            self.units[item].loc[c, "unit"]
                            for c in self.db.commodities_clusters[inventory.loc[i, INC["db_item"]]]
                        ]
                        if len(set(db_units)) != 1:
                            raise ValueError(
                                f"Commodities in cluster {inventory.loc[i, INC['db_item']]} have different units."
                            )
                        db_unit = db_units[0]
                    else:
                        raise ValueError(
                            f"Issues in converting unit of commodity {inventory.loc[i, INC['db_item']]} "
                            f"in sheet {sheet_name}."
                        )
                else:
                    if inventory.loc[i, INC["db_item"]] in self.sectors:
                        db_unit = self.units[item].loc[inventory.loc[i, INC["db_item"]], "unit"]
                    elif inventory.loc[i, INC["db_item"]] in self.new_sectors:
                        dummy = inventory.loc[i, INC["db_item"]]
                        db_unit = self.db.add_sectors_master.query(f"{MI['s']}==@dummy")[
                            MSC[self.table]["unit"]
                        ].values[0]
                    elif inventory.loc[i, INC["db_item"]] in self.db.sectors_clusters:
                        db_units = [
                            self.units[item].loc[c, "unit"]
                            for c in self.db.sectors_clusters[inventory.loc[i, INC["db_item"]]]
                        ]
                        if len(set(db_units)) != 1:
                            raise ValueError(
                                f"Sectors in cluster {inventory.loc[i, INC['db_item']]} have different units."
                            )
                        db_unit = db_units[0]
                    else:
                        raise ValueError("Issues in converting unit.")
            elif item == MI["a"]:
                raise ValueError(
                    f"{INC['item_type']} {item} is not recognized: activities cannot be supplied to other activities."
                )
            elif item == MI["k"]:
                db_unit = self.units[MI["k"]].loc[inventory.loc[i, INC["db_item"]], "unit"]
            elif item == MI["f"]:
                db_unit = self.units[MI["f"]].loc[inventory.loc[i, INC["db_item"]], "unit"]
            else:
                raise ValueError(f"{INC['item_type']} {item} is not recognized.")

            if inventory.loc[i, INC["unit"]] == db_unit:
                inventory.loc[i, cqc] = inventory.loc[i, INC["quantity"]]
            elif ureg(inventory.loc[i, INC["unit"]]).is_compatible_with(db_unit):
                inventory.loc[i, cqc] = (
                    inventory.loc[i, INC["quantity"]]
                    * ureg(inventory.loc[i, INC["unit"]]).to(db_unit).magnitude
                )
            else:
                raise NotImplementedError(
                    f"{INC['unit']} {inventory.loc[i, INC['unit']]} is not convertible to {db_unit}."
                )

        return inventory

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
            )[INC["db_item"]].values
            factors_to_nullify = inventory.query(
                f"`{INC['item_type']}`=='{MI['f']}' & `{INC['change_type']}`=='Update'"
            )[INC["db_item"]].values

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

            for k in satellites_to_nullify:
                slices[_ENUM["e"]].loc[k, (region, MI["a" if self.table == SUT else "s"], activity)] = 0

            for f in factors_to_nullify:
                slices[_ENUM["v"]].loc[f, (region, MI["a" if self.table == SUT else "s"], activity)] = 0

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
                                    com_use = self.matrices[_ENUM["U"]].loc[
                                        (self.db.regions_clusters[region_from], sn, input_item_parent),
                                        (region_to, sn, parent_activity),
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
                                    com_use = self.matrices[_ENUM["Z"]].loc[
                                        (self.db.regions_clusters[region_from], sn, input_item_parent),
                                        (region_to, sn, parent_activity),
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
            quantity = inventory.loc[i, self.converted_quantity_column]
            change_type = inventory.loc[i, INC["change_type"]]

            if change_type == "Update":
                slices[matrix].loc[input_item, (region_to, MI["a" if self.table == SUT else "s"], activity)] += quantity
            elif change_type == "Percentage":
                if self.table == SUT:
                    if activity in self.parented_activities:
                        parent = self.db.add_sectors_master.query(f"{MI['a']}==@activity")[
                            MSC[self.table]["parent_activity"]
                        ].values[0]
                        old_value = self.matrices[matrix].loc[input_item, (region_to, MI["a"], parent)]
                        slices[matrix].loc[input_item, (region_to, MI["a"], activity)] = old_value * (1 + quantity)
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
                        old_value = self.matrices[matrix].loc[input_item, (region_to, MI["s"], parent)]
                        slices[matrix].loc[input_item, (region_to, MI["s"], activity)] = old_value * (1 + quantity)
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
                mario_indices[item] = {"main": sorted(set(self.matrices[_ENUM["e"]].index))}
            elif item == "f":
                mario_indices[item] = {"main": sorted(set(self.matrices[_ENUM["v"]].index))}

        self.indeces = mario_indices


def collect_add_sector_matrices(instance, scenario: str = "baseline") -> dict[str, pd.DataFrame]:
    """Collect the coefficient and reference blocks required by the add-sectors engine."""

    matrices = {
        _ENUM["z"]: instance.get_block_as_pandas("z", scenario=scenario) if instance.has_block("z", scenario=scenario) else instance.resolve("z", scenario=scenario),
        _ENUM["e"]: instance.get_block_as_pandas("e", scenario=scenario) if instance.has_block("e", scenario=scenario) else instance.resolve("e", scenario=scenario),
        _ENUM["v"]: instance.get_block_as_pandas("v", scenario=scenario) if instance.has_block("v", scenario=scenario) else instance.resolve("v", scenario=scenario),
        _ENUM["Y"]: instance.get_block_as_pandas("Y", scenario=scenario) if instance.has_block("Y", scenario=scenario) else instance.resolve("Y", scenario=scenario),
        _ENUM["EY"]: instance.get_block_as_pandas("EY", scenario=scenario) if instance.has_block("EY", scenario=scenario) else instance.resolve("EY", scenario=scenario),
        _ENUM["VY"]: instance.get_block_as_pandas("VY", scenario=scenario) if instance.has_block("VY", scenario=scenario) else instance.resolve("VY", scenario=scenario),
        _ENUM["Z"]: instance.get_block_as_pandas("Z", scenario=scenario) if instance.has_block("Z", scenario=scenario) else instance.resolve("Z", scenario=scenario),
        _ENUM["E"]: instance.get_block_as_pandas("E", scenario=scenario) if instance.has_block("E", scenario=scenario) else instance.resolve("E", scenario=scenario),
        _ENUM["V"]: instance.get_block_as_pandas("V", scenario=scenario) if instance.has_block("V", scenario=scenario) else instance.resolve("V", scenario=scenario),
    }
    if instance.table_type == SUT:
        matrices[_ENUM["u"]] = instance.get_block_as_pandas("u", scenario=scenario) if instance.has_block("u", scenario=scenario) else instance.resolve("u", scenario=scenario)
        matrices[_ENUM["s"]] = instance.get_block_as_pandas("s", scenario=scenario) if instance.has_block("s", scenario=scenario) else instance.resolve("s", scenario=scenario)
        matrices[_ENUM["U"]] = instance.get_block_as_pandas("U", scenario=scenario) if instance.has_block("U", scenario=scenario) else instance.resolve("U", scenario=scenario)
        matrices[_ENUM["S"]] = instance.get_block_as_pandas("S", scenario=scenario) if instance.has_block("S", scenario=scenario) else instance.resolve("S", scenario=scenario)
    return matrices


def run_add_sector_engine(instance, scenario: str = "baseline", ignore_warnings: bool = True):
    """Run the add-sectors engine and return updated coefficient matrices."""

    if not hasattr(instance, "inventories"):
        raise LackOfInput("Inventory sheets are not loaded. Use read_inventory_sheets(...) first.")

    matrices = collect_add_sector_matrices(instance, scenario=scenario)
    engine = AddSectorEngine(instance, matrices, ignore_warnings=ignore_warnings)
    if instance.table_type == IOT:
        return engine.to_iot()
    return engine.to_sut()


# Backward-compatible aliases for the first port of the workflow.
AdvancedAddSectorEngine = AddSectorEngine
collect_advanced_add_sector_matrices = collect_add_sector_matrices
run_advanced_add_sector_engine = run_add_sector_engine
