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

from mario.ops.shocks import Y_shock, V_shock, Z_shock
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
    build_split_flow_scenario,
    log_split_scenario,
    prepare_split_support,
    validate_split_parameters,
)
from mario.ops.cvxlab_bridge import (
    create_split_input_data,
    optimize_split_in_cvxlab,
)
from mario.utils import (
    _manage_indeces,
    check_clusters,
    filtering,
)

from mario.ops.excel import _sh_excel

from mario.views import plots as plt
from mario.views.plots import _plotter
from mario.views.plot_specs import (
    _NON_ACCEPTABLE_FILTERS,
    _PLOTS_LAYOUT,
    Color,
)

from mario.compute.primitives import (
    calc_all_shock,
    calc_X,
    linkages_calculation,
)

import numpy as np
import pandas as pd
import logging
import copy
import os
import tempfile
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
        **kwargs,
    ):
        """Initialize a MARIO database object."""

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
            **kwargs,
        )

        if __cvxpy__:
            self.__solver = cp.ECOS

        # A counter for saving the results in a dictionary
        self.__counter = 1  # Shock Counter

    def build_new_instance(self, scenario):
        """Return a new database whose baseline is the selected scenario."""

        return build_new_instance_from_scenario(self, scenario)

    def to_iot(
        self,
        method,
        inplace=True,
    ):
        """Transform a SUT database into an IOT database."""
        return transform_sut_to_iot(self, method, inplace=inplace)

    def to_chenery_moses(
        self,
        inplace: bool = True,
        scenarios: list = None,
    ):
        """Transform an Isard SUT into a Chenery-Moses SUT."""
        return transform_to_chenery_moses(
            self,
            inplace=inplace,
            scenarios=scenarios,
        )

    def get_aggregation_excel(
        self,
        path=None,
        levels="all",
    ):
        """Write an aggregation template workbook for the selected levels."""

        if levels != "all":
            # To avoid any issue, in case that levels is a string, return a list instead of str
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
        elif levels == "all":
            levels = [*TABLE_LEVELS[self.meta.table]]

        output_path = self._getdir(path, "Excels", "Aggregation.xlsx")
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
        """Load aggregation mappings without applying them yet."""

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
        inplace=True,
    ):
        """Aggregate one or more classification levels in the database."""

        return aggregate_database(
            self,
            io=io,
            drop=drop,
            levels=levels,
            calc_all=calc_all,
            ignore_nan=ignore_nan,
            inplace=inplace,
        )

    def get_extensions_excel(
        self,
        matrix,
        path=None,
    ):
        """Write an Excel template for adding extensions to ``E`` or ``V``."""

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
        """Add new extensions to value added or satellite accounts."""

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

    def to_single_region(self, region, inplace=True):
        """Extract a single region from a multi-regional database."""
        if not inplace:
            new = self.copy()
            new.to_single_region(region=region, inplace=True)

            return new

        if self.is_hybrid:
            raise NotImplementable("Hybrid tables are not supported.")

        if not self.is_multi_region:
            raise NotImplementable("Database is already a single region database.")

        if region not in self.get_index(_MASTER_INDEX["r"]):
            raise WrongInput("{} does not exist in regions".format(region))

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

        # Take the regions!=region
        rest_reg = self.get_index(_MASTER_INDEX["r"])
        rest_reg.remove(region)

        # Take the imports from the Z matrix
        IM = Z.loc[
            (rest_reg, slice(None), slice(None)),
            (region, slice(None), slice(None)),
        ]

        # Taking the intermediate export
        EX = Z.loc[
            (region, slice(None), slice(None)),
            (rest_reg, slice(None), slice(None)),
        ]

        # Take the Z for the region
        Z = Z.loc[
            (region, slice(None), slice(None)),
            (region, slice(None), slice(None)),
        ]

        IM = IM.sum(axis=0).to_frame().T
        IM.index = ["imports"]

        # Adding the imports to the V matrix
        V = V.loc[:, (region, slice(None), slice(None))]
        V = pd.concat([V, IM])

        # Taking the Y_local matrix
        Y_local = Y.loc[
            (region, slice(None), slice(None)),
            (region, slice(None), slice(None)),
        ]

        YEX = Y.loc[
            (region, slice(None), slice(None)),
            (rest_reg, slice(None), slice(None)),
        ]

        YEX = YEX.sum(axis=1).to_frame()

        YEX.columns = [[region], [_MASTER_INDEX["n"]], ["Final Demand exports"]]

        EX = EX.sum(axis=1).to_frame()
        EX.columns = [[region], [_MASTER_INDEX["n"]], ["Intermediate exports"]]

        # Adding the exports as a category of the
        Y = pd.concat([Y_local, YEX, EX], axis=1)

        # Taking the exposts
        EYX = pd.DataFrame(
            0,
            index=EY.index,
            columns=[
                [region] * 2,
                [_MASTER_INDEX["n"]] * 2,
                ["Final Demand exports", "Intermediate exports"],
            ],
        )

        # fixing the EY export emissions
        # Taking the Y matrix
        EY = EY.loc[:, (region, slice(None), slice(None))]
        EY = pd.concat([EY, EYX], axis=1)

        VYX = pd.DataFrame(
            0,
            index=VY.index,
            columns=[
                [region] * 2,
                [_MASTER_INDEX["n"]] * 2,
                ["Final Demand exports", "Intermediate exports"],
            ],
        )
        VY = VY.loc[:, (region, slice(None), slice(None))]
        VY = pd.concat([VY, VYX], axis=1)

        # Taking the E matrix
        E = E.loc[:, (region, slice(None), slice(None))]

        X = calc_X(Z=Z, Y=Y)

        all_indeces = self.get_index("all")

        new_indeces = {
            "r": [region],
            "f": all_indeces[_MASTER_INDEX["f"]] + ["imports"],
            "n": all_indeces[_MASTER_INDEX["n"]]
            + ["Final Demand exports", "Intermediate exports"],
        }

        _manage_indeces(self, "single_region", **new_indeces)

        for scenario in self.scenarios:
            log_time(logger, f"Transformation: {scenario} deleted from the database.")

        self.matrices = {"baseline": {}}
        for matrix in ["Y", "Z", "E", "EY", "VY", "V", "X"]:
            self.matrices["baseline"][_ENUM[matrix]] = eval(matrix)
        log_time(logger, "Transformation: New baseline added to the database")

        slicer = _MASTER_INDEX["a"] if self.table_type == "SUT" else _MASTER_INDEX["s"]

        self.units[_MASTER_INDEX["f"]].loc["imports", "unit"] = self.units[slicer].iloc[
            0, 0
        ]

        self.meta._add_history(
            f"Transformation: Database transformed into a single region database for {region}. Following assumptions are considered: "
        )
        self.meta._add_history(
            "Transformation: The intermediate imports are accounted as 'imports' in the Value Added Matrix."
        )
        self.meta._add_history(
            "Transformation: The intermediate Exports are accounted as 'Intermediate exports' in the Final Demand Matrix."
        )
        self.meta._add_history(
            "Transformation: The Final Demand Exports are accounted as 'Final Demand exports' in the Final Demand Matrix."
        )
        self.meta._add_history(
            "Transformation: The Final Demand emissions are considered only for 'Local Final Demand.'"
        )

    def calc_linkages(
        self,
        scenario="baseline",
        normalized=True,
        cut_diag=True,
        multi_mode=True,
    ):
        r"""Calculate backward and forward linkages for an IOT scenario."""

        if not self.is_multi_region and multi_mode:
            raise NotImplementable(
                "multi_mode option is valid only for mult-regional data"
            )

        if self.meta.table == "SUT":
            raise NotImplementable("Linkages can not be calculated for SUT.")

        _matrices = {
            **self.query(
                matrices=[_ENUM.w, _ENUM.b, _ENUM.z, _ENUM.g],
            )
        }

        return linkages_calculation(
            cut_diag=cut_diag,
            matrices=_matrices,
            multi_mode=multi_mode,
            normalized=normalized,
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
        """Plot linkage indicators for one or more scenarios."""
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

        plt._plot_linkages(
            data=data,
            path=self._getdir(path, "Plots", "linkages.html"),
            multi_mode=multi_mode,
            plot=plot,
            auto_open=auto_open,
            **config,
        )

    def to_excel(
        self,
        path=None,
        flows=True,
        coefficients=False,
        scenario="baseline",
        include_meta=False,
    ):
        """Export one scenario to the historical MARIO Excel format."""

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
    ):
        """Export one scenario as multiple text or CSV files.

        ``flat=False`` keeps the historical matrix-per-file layout.
        ``flat=True`` writes one long-format data file plus a units file.
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
        )

    def to_parquet(
        self,
        path=None,
        flows=True,
        coefficients=False,
        scenario="baseline",
        include_meta=False,
        flat=False,
    ):
        """Export one scenario as parquet files.

        ``flat=False`` writes one parquet file per matrix.
        ``flat=True`` writes one long-format ``data.parquet`` plus ``units.parquet``.
        """

        return export_database_to_parquet(
            self,
            path=path,
            flows=flows,
            coefficients=coefficients,
            scenario=scenario,
            include_meta=include_meta,
            flat=flat,
        )

    def to_pymrio(
        self,
        satellite_account="satellite_account",
        factor_of_production="factor_of_production",
        include_meta=True,
        scenario="baseline",
        **kwargs,
    ):
        """Export an IOT database as a ``pymrio.IOSystem``."""

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

        This method always stores the normalized master sheet, cluster maps and
        derived item sets on the database instance. When ``read_inventories`` is
        true it also groups the referenced inventory sheets by target item and
        stores them on ``self.inventories``.
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

    def get_inventory_sheets(self, path, overwrite=True):
        """Create inventory-sheet templates referenced by one add-sectors workbook."""

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

        The returned mapping is keyed by target item name and each value is a
        ``{sheet_name: dataframe}`` dictionary ready for the add-sectors engine.
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
        notes=None,
        ignore_warnings=True,
        cvxlab_path=None,
        input_data_files_type="xlsx",
        only_input_data_gen=False,
        solver=None,
        solver_parameters=None,
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

        Notes
        -----
        The workbook-driven non-split insertion always runs first. If
        ``split=True`` for an IOT, MARIO then builds a deterministic
        ``split_<scenario>`` flow scenario and optionally hands it to CVXLab.
        """
        if not inplace:
            new = self.copy()
            new.add_sectors(
                io=io,
                scenario=scenario,
                inplace=True,
                split=split,
                notes=notes,
                ignore_warnings=ignore_warnings,
                cvxlab_path=cvxlab_path,
                input_data_files_type=input_data_files_type,
                only_input_data_gen=only_input_data_gen,
                solver=solver,
                solver_parameters=solver_parameters,
            )
            return new

        self._validate_scenario(scenario)

        if io != "inventories":
            self.read_add_sectors_excel(io, read_inventories=True)
        elif not hasattr(self, "inventories"):
            raise LackOfInput(
                "Inventory sheets are not loaded. Pass an add-sectors workbook path "
                "or call read_inventory_sheets(...) first."
            )

        if split:
            validate_split_parameters(
                self,
                cvxlab_path=cvxlab_path,
                input_data_files_type=input_data_files_type,
                only_input_data_gen=only_input_data_gen,
            )
            prepare_split_support(self)

        item_to_query = _MASTER_INDEX["a"] if self.meta.table == "SUT" else _MASTER_INDEX["s"]
        duplicates = sorted(set(name for name in self.inventories if name in self.get_index(item_to_query)))
        if duplicates:
            raise WrongInput(f"Some items already exist in the table: {duplicates}")

        log_time(
            logger,
            "Database: All scenarios will be deleted from the database after add_sectors.",
            "warning",
        )

        original_reference = collect_add_sector_matrices(self, scenario=scenario) if split else None

        result = run_add_sector_engine(
            self,
            scenario=scenario,
            ignore_warnings=ignore_warnings,
        )

        baseline_vy = (
            self.get_block_as_pandas(_ENUM["VY"], scenario=scenario)
            if self.has_block(_ENUM["VY"], scenario=scenario)
            else self.resolve(_ENUM["VY"], scenario=scenario)
        )

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

        return None

    def query(
        self,
        matrices,
        scenarios=["baseline"],
        base_scenario=None,
        type="absolute",
    ):
        """Query matrices from one or more scenarios."""
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
        """Return matrices, units and indexes in a structured payload."""
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
        """Return a single dataframe view of the selected scenario."""

        return build_database_frame(self, scenario=scenario)

    def shock_calc(
        self,
        io,
        z=False,
        e=False,
        v=False,
        Y=False,
        notes=[],
        scenario=None,
        force_rewrite=False,
        **clusters,
    ):
        """Apply shocks to coefficients or demand and store the result as a scenario."""

        # be sure that all the data exist

        if (scenario in self.matrices) and (not force_rewrite):
            raise WrongInput(
                f"Scenario {scenario} already exist. In order to re-write the scenario, you can use force_rewrite = True."
            )

        if scenario == "baseline":
            raise WrongInput("baseline scenario can not be overwritten.")

        check_clusters(
            index_dict=self.get_index("all"), table=self.table_type, clusters=clusters
        )

        # have the test for the existence of the database

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

        for note in note_z + note_e + note_v + note_y:
            self.meta._add_history(note)

        log_time(logger, "Shock: Shock implemented successfully.")

    def get_shock_excel(
        self,
        path=None,
        num_shock=10,
        **clusters,
    ):
        """Write an Excel template for defining shocks."""

        check_clusters(
            index_dict=self.get_index("all"), table=self.table_type, clusters=clusters
        )

        _sh_excel(self, num_shock, self._getdir(path, "Excels", "shock.xlsx"), clusters)

    def replace_units_name(self, level, names):
        """Rename unit labels inside one unit table without touching matrix data."""
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
        """Create a bubble chart from GDP or extension indicators."""

        items = ["x", "y", "size"]

        slicer = _MASTER_INDEX["s"] if self.table_type == "IOT" else _MASTER_INDEX["a"]

        to_plot = pd.DataFrame(
            0,
            index=self.X.loc[(slice(None), slicer, slice(None)), :].index,
            columns=[x, y, size],
        )

        cols = {}
        matrices = self.query(matrices=[_ENUM.E, _ENUM.V])
        for item in items:
            if eval(item) == "GDP":
                to_plot["GDP"] = (
                    self.GDP(total=False, scenario=scenario)
                    .loc[to_plot.index, "GDP"]
                    .values
                )
                unit = self.units[_MASTER_INDEX["f"]].iloc[0, 0]

            elif eval(item) in self.get_index(_MASTER_INDEX["k"]):
                to_plot[eval(item)] = (
                    matrices[_ENUM.E].loc[eval(item), to_plot.index].values
                )
                unit = self.units[_MASTER_INDEX["k"]].loc[eval(item), "unit"]

            elif eval(item) in self.get_index(_MASTER_INDEX["f"]):
                to_plot[eval(item)] = (
                    matrices[_ENUM.V].loc[eval(item), to_plot.index].values
                )
                unit = self.units[_MASTER_INDEX["f"]].loc[eval(item), "unit"]
            else:
                raise WrongInput(
                    "Acceptable values are GDP or one of the Satellite account or "
                    "Factor of production items."
                )

            cols[item] = eval(item) + f"({unit})"

        to_plot.index.names = ["Region", "Level", "Sector"]
        to_plot.columns = [cols[item] for item in items]

        colors = Color()
        colors.has_enough_colors(self.get_index(_MASTER_INDEX["r"]))
        try:
            fig = px.scatter(
                to_plot.reset_index(),
                x=cols["x"],
                y=cols["y"],
                size=cols["size"],
                color="Region",
                color_discrete_sequence=Color(),
                hover_name="Sector",
                log_x=log_x,
                log_y=log_y,
                size_max=60,
            )
        except ValueError:
            negatives = to_plot.loc[to_plot[size] <= 0].index.tolist()
            raise NotImplementable(
                f"cannot plot when size have negative numbers.\n negatives: {negatives}"
            )

        path = self._getdir(path, "Plots", "bubble.html")
        fig.update_layout(
            {i: _PLOTS_LAYOUT[i] for i in ["template", "font_family", "font_size"]}
        )
        _plotter(fig=fig, directory=path, auto_open=auto_open)

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
        """Plot sectoral GDP as a treemap or sunburst chart."""

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

        fig = getattr(px, plot)(
            data_frame=data_frame,
            path=_path,
            values=values,
            color=color,
            color_continuous_scale=px.colors.diverging.RdBu[::-1],
            title=title,
        )

        path = r"{}".format(self._getdir(path, "Plots", f"GDP_{scenario}_{plot}.html"))
        fig.update_layout(
            {i: _PLOTS_LAYOUT[i] for i in ["template", "font_family", "font_size"]}
        )

        _plotter(fig=fig, directory=path, auto_open=auto_open)

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
        """Generate a general-purpose HTML bar plot for a selected matrix."""

        ### Inputs handling
        item_from = item
        if self.table_type == "SUT":
            if item_from == _MASTER_INDEX["s"] and matrix in [
                "z",
                "Z",
                "U",
                "u",
                "S",
                "s",
                "f_dis",
                "Y",
                "X",
            ]:
                raise WrongInput(
                    f"Please set 'item' as '{_MASTER_INDEX['c']}' or '{_MASTER_INDEX['a']}'"
                )
            if matrix not in ["v", "V", "E", "e", "EY", "F", "M"] and item_from not in [
                _MASTER_INDEX["c"],
                _MASTER_INDEX["a"],
            ]:
                raise WrongInput(
                    f"Please set 'item' as '{_MASTER_INDEX['c']}' or '{_MASTER_INDEX['a']}'"
                )
        if self.table_type == "IOT" and item_from != _MASTER_INDEX["s"]:
            raise WrongInput(f"Please set 'item' as '{_MASTER_INDEX['s']}'")

        if (
            self.table_type == "SUT"
            and matrix == "Z"
            and item_from == _MASTER_INDEX["c"]
        ):
            matrix = "U"
            log_time(
                logger,
                "Warning: according to the set combination of 'matrix' and 'item_from', "
                "matrix has been changed to '{}'".format(matrix),
                "warning",
            )
        if (
            self.table_type == "SUT"
            and matrix == "z"
            and item_from == _MASTER_INDEX["c"]
        ):
            matrix = "u"
            log_time(
                logger,
                "Warning: according to the set combination of 'matrix' and 'item_from', "
                "matrix has been changed to '{}'".format(matrix),
                "warning",
            )
        if (
            self.table_type == "SUT"
            and matrix == "Z"
            and item_from == _MASTER_INDEX["a"]
        ):
            matrix = "S"
            log_time(
                logger,
                "Warning: according to the set combination of 'matrix' and 'item_from', "
                "matrix has been changed to '{}'".format(matrix),
                "warning",
            )
        if (
            self.table_type == "SUT"
            and matrix == "z"
            and item_from == _MASTER_INDEX["a"]
        ):
            matrix = "s"
            log_time(
                logger,
                "Warning: according to the set combination of 'matrix' and 'item_from', "
                "matrix has been changed to '{}'".format(matrix),
                "warning",
            )

        ### Preparing filters
        for filt in filters:
            if filt in _NON_ACCEPTABLE_FILTERS[matrix][self.table_type]:
                raise WrongInput(
                    f"'{filt}' is not a valid filter option for matrix '{matrix}'"
                )

        filter_options = [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['r']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['a']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['a']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
        ]

        for filt in filter_options:
            filters[filt] = filters.get(filt, "all")
        filters = filtering(self, filters)

        # Setting the path
        path = self._getdir(path, "Plots", f"{matrix}.html")

        # Importing and defining customizing layout
        if layout == None:
            layout = _PLOTS_LAYOUT

        if base_scenario == None:
            layout["title"] = f"{MATRIX_TITLES[matrix]}"
        else:
            layout[
                "title"
            ] = f"{MATRIX_TITLES[matrix]} - Variation with respect to '{base_scenario}' scenario"

        if matrix in ["X", "p"]:
            plot_function = "_plotX"
        if matrix in ["Z", "z", "Y", "U", "u", "S", "s", "f_dis"]:
            plot_function = "_plotZYUS"
        if matrix in ["V", "v", "E", "e", "EY", "M", "F"]:
            plot_function = "_plotVEMF"

        eval(f"plt.{plot_function}")(
            self,
            matrix,
            x,
            y,
            color,
            facet_row,
            facet_col,
            animation_frame,
            base_scenario,
            path,
            item_from,
            "bar",
            mode,
            auto_open,
            layout,
            shared_yaxes,
            shared_xaxes,
            filters,
        )
