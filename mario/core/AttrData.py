# -*- coding: utf-8 -*-
"""
Database class is the main Database handler in MARIO.

It is suggested not to use the classes directly but use the API methods from
MARIO module.
"""

from mario.log_exc.exceptions import (
    WrongInput,
    WrongExcelFormat,
    NotImplementable,
    DataMissing,
)

from mario.log_exc.logger import log_time

from mario.tools.ioshock import Y_shock, V_shock, Z_shock
from mario.tools.tabletransform import SUT_to_IOT, ISARD_TO_CHENERY_MOSES
import json
from mario.tools.utilities import (
    _manage_indeces,
    check_clusters,
    run_from_jupyter,
    filtering,
    pymrio_styling,
    sort_frames,
)

from mario.tools.excelhandler import (
    database_excel,
    database_txt,
    _add_sector_iot,
    _add_sector_sut,
    _sh_excel,
)

from mario.tools import plots as plt
from mario.tools.plots import _plotter
from mario.tools.plots_manager import (
    _NON_ACCEPTABLE_FILTERS,
    _PLOTS_LAYOUT,
    Color,
)

from mario.tools.aggregation import _aggregator
from mario.tools.iomath import (
    calc_all_shock,
    calc_X,
    calc_Z,
    calc_w,
    calc_g,
    calc_X_from_w,
    calc_E,
    calc_V,
    calc_e,
    calc_v,
    calc_z,
    calc_b,
    calc_F,
    calc_f,
    calc_f_dis,
    calc_X_from_z,
    linkages_calculation,
)

from mario.tools.sectoradd import add_new_sector

from collections import namedtuple
import plotly.offline as pltly

import numpy as np
import pandas as pd
import logging
import copy
from typing import Dict
import plotly.express as px


# constants
from mario.tools.constants import (
    _LEVELS,
    _INDECES,
    _MASTER_INDEX,
    _ALL_MATRICES,
    _MATRICES_NAMES,
    _PYMRIO_MATRICES,
    _ENUM,
)

from mario.core.CoreIO import CoreModel
import pymrio

logger = logging.getLogger(__name__)

try:
    import cvxpy as cp

    __cvxpy__ = True
except ModuleNotFoundError:
    __cvxpy__ = False


class Database(CoreModel):
    """class that handles the Database

    Notes
    ------
    Avoid deleting, adding, or modifying anything from the matrices attribute. To make
    changes, it is suggested to specific APIs provided in MARIO.

    The attributes representing the IO matrices, respect the following logic borrowed from thermodynamics:
        . lowercase characters represent coefficients
        . uppercase characters represent flows
            For example Z is the intermediate flow and z is the technical ceofficient matrix
        . attributes with _c representes the corresponding values of the last scenario
          implemented while without it, it always returns the baseline values.


    Be careful in the definition of the units because it will impact the aggregation
    of the Database. The aggregation of different items with different units is not
    possible. It also impacts the visualization of the data.

    When MARIO needs to save a file (Excels, txt, plots,...), if the path is not
    provided by the user, it tries to create a Folder in the working directory
    called Outputs with subfolders for different outputs of the model.



    Attributes
    ----------
    matrices: dict
        A nested dictionary that contains all the scenarios data. The key is
        the name of the scenario and the value is a dict which keys are the
        matrices and the values pd.DataFrame.
    name:
        By default, name is set to unknows but is suggested to use a name for the
        Database. This will be usefull for visualization purposes and metadata.

    table:
        Defines the type of table. Acceptable values are 'IOT' for the Input-Output
        Tables and 'SUT' for Supply-and-Use Tables.
    Z:
        The intermediate flow pd.DataFrame. It should has 3 level pd.MultiIndex
        for index and columns respecting the rules specified in test model
    Y:
        The final demand flow pd.DataFrame. It should has 3 level pd.MultiIndex
        for index and columns respecting the rules specified in test model
    E:
        The satellite account flow pd.DataFrame. It should has the accounts as pd.Index
        for index and 3 level pd.MultiIndex for the columns respecting the rules specified
        in test model
    V:
        The value added flow pd.DataFrame. It should has the accounts as pd.Index
        for index and 3 level pd.MultiIndex for the columns respecting the rules specified
        in test model
    EY:
        The final demand satellite account flow pd.DataFrame. It should has the accounts as pd.Index
        for index and 3 level pd.MultiIndex for the columns respecting the rules specified
        in test model

    units:
        A dictionary of pd.DataFrames representing the units in which the key should
        have the level name such as: Sector, Activity, Commodity, Satellite account,
        Factor of production and the pd.DataFrame has the name of a single item in the
        rows and the unit as the value.


    """

    def __init__(
        self,
        name: str = "unknow",
        table: str = None,
        Z: pd.DataFrame = None,
        E: pd.DataFrame = None,
        V: pd.DataFrame = None,
        Y: pd.DataFrame = None,
        EY: pd.DataFrame = None,
        units: Dict = None,
        price: str = None,
        source: str = None,
        **kwargs,
    ):
        """Init function - see docstring class"""

        super().__init__(
            name=name,
            table=table,
            Z=Z,
            E=E,
            V=V,
            Y=Y,
            EY=EY,
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
        """This function returns a new instance of Database which the baseline
        scenario can be any given scenario. This is specifically useful in case
        a shock needs to be implemented around a non-baseline scenario. Indeed,
        shocks will always be implemented with respect to the baseline.

        Parameters
        ----------
        scenario : str
            representing the scenario name

        Returns
        -------
        mario.Database :
            A new MARIO.Database object with a scenario given as baseline
        """

        if scenario not in self.scenarios:
            raise WrongInput(
                "{} is not a valid scenario. Valid scenarios are {}".format(
                    scenario, self.scenarios
                )
            )

        data = self.query(
            matrices=[_ENUM.Y, _ENUM.E, _ENUM.V, _ENUM.Z, _ENUM.EY],
            scenarios=scenario,
        )

        return Database(
            Y=data[_ENUM.Y],
            E=data[_ENUM.E],
            V=data[_ENUM.V],
            Z=data[_ENUM.Z],
            EY=data[_ENUM.EY],
            units=self.units,
            table=self.meta.table,
        )

    def to_iot(
        self,
        method,
        inplace=True,
    ):
        """The function will transform a SUT table to a IOT table


        .. note::

            Calling this function will delete all the existing scenarios in the database
            and create the new baseline scenario.

        Parameters
        ----------
        method : str
            Defines the method for transformation of the database:

                A. Product-by-product input-output table based on product technology assumption (possible negative values)
                B. Product-by-product input-output table based on industry technology assumption
                C. Industry-by-industry input-output table based on fixed industry sales structure assumption (possible negative values)
                D. Industry-by-industry input-output table based on fixed product sales structure assumption

        inplace : boolean
            if True, implements the changes on the Database else returns
            a new object without changing the original Database object

        Returns
        -------
        None :
            if inplace True

        mario.Database :
            if inplace False
        """
        if not inplace:
            new = self.copy()
            new.to_iot(method, inplace=True)
            return new

        if self.meta.table == "IOT":
            raise NotImplementable("IOT table cannot be transformed to IOT.")

        log_time(
            logger,
            "Database: Transforming the database from SUT to IOT via method {}".format(
                method
            ),
        )
        matrices, indeces, units = SUT_to_IOT(self, method)

        for scenario in self.scenarios:
            log_time(logger, f"{scenario} deleted from the database", "warning")
            self.meta._add_history(f"{scenario} deleted from the database")

        self.matrices = matrices

        self._indeces = indeces
        self.units = units

        self.meta.table = "IOT"
        self.meta._add_history(
            "Transformation of the database from SUT to IOT via method {}".format(
                method
            )
        )
        log_time(
            logger,
            "Transformation of the database from SUT to IOT via method {}".format(
                method
            ),
        )

    def to_chenery_moses(
        self,
        inplace: bool = True,
        scenarios: list = None,
    ):
        """The function will transform an Isard SUT table to a Chenery-Moses SUT table.
        The transformation implies moving from trades accounted in the USE matrix to trades accounted in the SUPPLY matrix.
        For further notes on the transformation check:
        - John M. Hartwick, 1970. "Notes on the Isard and Chenery-Moses Interregional Input-Output Models," Working Paper 16, Economics Department, Queen's University.

        .. note::

            Calling this function will modify all scenarios in the database

        Parameters
        ----------

        inplace : boolean
            if True, implements the changes on the Database else returns
            a new object without changing the original Database object

        scenarios : list
            if None, will implement the changes on all the scenarios, else will
            implement the changes on the given scenarios

        Returns
        -------
        None :
            if inplace True

        mario.Database :
            if inplace False
        """
        if not inplace:
            new = self.copy()
            new.to_chenery_moses(inplace=True, scenarios=scenarios)
            return new

        if scenarios is None:
            scenarios = self.scenarios

        for scenario in scenarios:
            if self.is_chenerymoses(scenario=scenario):
                raise NotImplementable(
                    f"scenario {scenario} is already in Chenery-Moses format"
                )

        log_time(
            logger,
            "Database: Transforming the database into Chenery-Moses",
        )

        for scenario in scenarios:
            Z_chenery, Y_chenery = ISARD_TO_CHENERY_MOSES(self, scenario)
            to_update = {_ENUM.Z: Z_chenery, _ENUM.Y: Y_chenery}
            sort_frames(to_update)
            self.update_scenarios(scenario, **to_update)
            self.reset_to_flows(scenario=scenario)

            self.meta._add_history(
                f"Transformation of the database from into Chenery-Moses for scenario {scenario}"
            )

        log_time(logger, "Transformation of the database from into Chenery-Moses")

    def get_aggregation_excel(
        self,
        path=None,
        levels="all",
    ):
        """Generates the Excel file for aggregation of the database

        Parameters
        ---------
        path : str
            path to generate an Excel file for database aggregation. The Excel
            file has different sheets named by the level to be aggregated.

        levels : str
            levels to be printed as Excel sheets. If 'all' it will print out all
            the levels, else different levels should be passed as a list of
            levels such as ['Region','Sector']

        """

        if levels != "all":
            # To avoid any issue, in case that levels is a string, return a list instead of str
            if isinstance(levels, str):
                levels = [levels]

            difference = set(levels).difference(set(self.sets))
            if difference:
                raise WrongInput(
                    "\{}' is/are not an acceptable level/s for the database.\n"
                    "Acceptable items are \n{}".format(
                        difference,
                        self.sets,
                    )
                )
        elif levels == "all":
            levels = [*_LEVELS[self.meta.table]]

        with pd.ExcelWriter(self._getdir(path, "Excels", "Aggregation.xlsx")) as writer:
            for level in levels:
                data = pd.DataFrame(
                    index=self.get_index(level), columns=["Aggregation"]
                )
                data.to_excel(writer, level)

    def read_aggregated_index(
        self,
        io,
        levels="all",
        ignore_nan=False,
    ):
        """Reads information over the aggregation of levels without aggregating the data


        Parameters
        ----------
        io : str, Dict[pd.DataFrame]
            string definining the path of the Excel file or a dict of different
            aggregation levels in which the keys are the single level and value
            is a pd.DataFrame mapping the aggregations.

        levels : str, list
            if 'all' will intend to read the aggregation info for all the levels
            otherwise, should be a list of levels to be aggregated such as ['Region','Sector'].

        ignore_nan: boolean
            if False, will stop the code from running if some of the data
            in the pd.DataFrame is missed otherwise, will not aggregate the missing
            items.
        """

        if levels != "all":
            # To avoid any issue, in case that levels is a string, return a list instead of str
            if isinstance(levels, str):
                levels = [levels]

            for level in levels:
                if level not in [*_LEVELS[self.meta.table]]:
                    raise WrongInput(
                        "'{}' is not an acceptable label for the database.\n"
                        "Acceptable items are \n{}".format(
                            level, [*_LEVELS[self.meta.table]]
                        )
                    )

        if levels == "all":
            levels = [*_LEVELS[self.meta.table]]

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
            self._indeces[_LEVELS[self.meta.table][level]]["aggregated"] = indeces[
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
        """This function is in charge of reading data regarding the aggregation
           of different levels and aggregate data.

        Parameters
        ----------
        io : str, Dict[pd.DataFrame]

            #. in case that the data should be given through an Excel file, represents the path of the Excel file
            #. in case that the data needs to be given by DataFrame, a dictionary of DataFrames can be give in which the keys are the name of the levels and values are the DataFrames

        drop : str, List[str]
            representing the items/items that should be droped (only allowed for E and EY matrix)

        levels : str, List[str]
            #. in case that a single level or 'all' levels should be aggregated, str can be used
            #. in case that multiple levels should be aggregated, a list of levels should be used


        calc_all : boolean
            if True, ['v','z','e'] will be calculated automatically after the
            aggregation of flows

        ignore_nan : booelan
            #. if False, will stop the code if finds some nan values in the aggregation dataframes
            #. if True, will ignore the NaNs and do not aggregated the specific items with NaN values

        inplace : booelan
            if True will aggrgate the datbase object itself otherwise will return
            the aggregated object as a new database object

        Returns
        -------
        mario.Database :
            if inplace = False returns a new mario.Database
        None :
            if inplace = True implents the changes in place

        """

        # ensure of Y,E,V,Z,EY exist
        for scenario in self.scenarios:
            self.calc_all([_ENUM.E, _ENUM.V, _ENUM.Z], scenario=scenario)

        if not inplace:
            new = self.copy()
            new.aggregate(
                io=io,
                drop=drop,
                levels=levels,
                calc_all=calc_all,
                ignore_nan=ignore_nan,
                inplace=True,
            )

            return new

        else:
            if isinstance(drop, str):
                drop = [drop]

            if io is None:
                matrices, self.units = _aggregator(self, drop)

            else:
                self.read_aggregated_index(
                    levels=levels,
                    io=io,
                    ignore_nan=ignore_nan,
                )
                __new_matrices = {}

                __new_matrices, units = _aggregator(self, drop)

            for scenario in self.scenarios:
                self.matrices[scenario] = __new_matrices[scenario]

            self.meta._add_history(
                "original matrices changed to the aggregated level based on the inputs from {}".format(
                    io
                )
            )
            self.units = units

            old_index = copy.deepcopy(self._indeces)
            # Now we have to change the indeces too. The one that are aggregated
            # should switch to main
            _manage_indeces(self, "aggregation")

            new_index = copy.deepcopy(self._indeces)

            if calc_all:
                for scenario in self.scenarios:
                    self.calc_all(scenario=scenario)

    def get_extensions_excel(
        self,
        matrix,
        path=None,
    ):
        """Generates an Excel file for easing the add extension functionality


        Parameters
        ----------

        matrix: str
            the name of the matrix to add extensions ['V','E']
        path: str
            defines the of the Excel file to save the Excel file such as: Extensions.xlsx

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
        """Adding a new extension [Factor of production or Satellite account] to the database
        passing the coefficients or the absolute values.

        .. note::
            This function will delete all the exisiting scenarios and implement the
            new sets of the matrices in the baseline.

        Parameters
        ----------
        io : str, pd.DataFrame
            if the data is given from an excel file, is the path to the file else is
            a pd.DataFrame

        matrix : str
            defines where the new extension should be added to.
            The options are :

                * 'v' value added by coefficient
                * 'V' value added by absolute value
                * 'e' satellite account by coefficient
                * 'E' satellite account by absolute

        units : pd.DataFrame
            a dataframe whose rows are the items to be added and single column
            which contains the units for every row

        inplace : boolean
            if True, will change the database inplace otherwise will return
            a new object

        calc_all : boolean
            if True, will calculate the main missing data

        notes : list, Optional
            to add notes to the metadata

        EY : pd.DataFrame, Optional
            In case that E,e are used as the matrix, EY can be updated too

        Returns
        -------
        mario.Database:
            if inplace= True retunrs a new mario.Databases
        None:
            if inplace= False, changes the database inplace
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

    def to_single_region(self, region, inplace=True):
        """Extracts a single region from multi-region databases

        .. note::
            Following assumptions are considered (on flow matrices):

                * intermediate imports accounted as 'Import' in V
                * intermediate exports are accounted as 'Intermediate exports' in Y
                * final demand exports are accounted as 'Final demand exports' in Y
                * EY is accounted only for local final demand


        Parameters
        ----------
        region : str
            the region to extract

        inplace : boolean
            if True, changes the database inplace otherwise, returns a new object

        Returns
        -------
        mario.Database:
            if inplace= True retunrs a new mario.Databases
        None:
            if inplace= False, changes the database inplace
        """
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
            matrices=[_ENUM.Y, _ENUM.X, _ENUM.Z, _ENUM.V, _ENUM.E, _ENUM.EY],
        )

        Z = data[_ENUM.Z]
        V = data[_ENUM.V]
        Y = data[_ENUM.Y]
        E = data[_ENUM.E]
        EY = data[_ENUM.EY]

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
        for matrix in ["Y", "Z", "E", "EY", "Y", "V", "X"]:
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
        """Calculates the linkages in different modes

        .. note::

            * Only implementable on IOTs.
            * Normalized is applicable only for single region database.
            * multi_mode is applicable only for multi region databases.

        .. math::
            Linkages^{backward, direct}_j = \sum_{i=1}^n z_{ij}
        .. math::
            Linkages^{backward, total}_j = \sum_{i=1}^n w_{ij}
        .. math::
            Linkages^{forward, direct}_i = \sum_{j=1}^n b_{ij}
        .. math::
            Linkages^{forward, total}_i = \sum_{j=1}^n g_{ij}

        Parameters
        ----------
        scenario : str
            the scenario that the linkages should be calculated for

        normalized : boolean
            normalizes linkages with average.

        cut_diag : boolean
            sets the diagonals (self consumptions) to zero.

        multi_mode : True
            **work in progress**

        Returns
        -------
        pd.DataFrame

        """

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
        """Plots linkages in different modes

        .. note::

            when caclulating linkages, possible negative numbers, are ignore

        Parameters
        ----------
        scenarios : str,List[str]
            A scenario or a list of scenarios to plot

        normalized : boolean
            if True, plots normalized linkages

        cut_diag : boolean
            if True, ignores the self consumption of sectors in calculating linkages

        multi_mode : boolean
            --TODO--

        path : str,Optional
            the path and the name of the plot file. (path should contain the name of the file with .htlm extension)
            for example 'path\\linkagesPlot.html'

        plot : str
            Options are:

                * 'Total' to plot the total linkages
                * 'Direct' to plot the direct linkages

        auto_open : boolean
            if True, opens the plot automatically

        """
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
        """Saves the database into an Excel file

        .. note::
            * The function will create a single Excel file with different sheets.
            * The sheets bsed on the inputs will be:

                * coefficients
                * flows
                * units

            * It is suggested to keep the units = True so the output file can be used to parse with MARIO again.

        Parameters
        ----------
        path : str
            the path that the Excel file should be saved. If it is None, MARIO
            will try to use the default path and inform the user with a warning.
            (the path should contain the name of excel file like 'path\\database.xlsx')

        flows : boolean
            if True, in the Excel file, a sheet will be created named flows containing
            the data of the flows

        coefficients : boolean
            if True, in the Excel file, a sheet will be created named coefficients containing
            the data of the coefficients

        scenario : str
            defines the scenario to print out the data

        include_meta : bool
            saves the metadata as a json file along with the data

        """

        if scenario not in self.scenarios:
            raise WrongInput(
                "{} is not a valid scenario. Existing scenarios are {}".format(
                    scenario, [*self.matrices]
                )
            )

        if flows==False and coefficients==False:
            raise WrongInput("At least one of the flows or coefficients should be True")

        database_excel(
            self,
            flows,
            coefficients,
            self._getdir(path, "Database", "New_Database.xlsx"),
            scenario,
        )
        if include_meta:
            meta = self.meta._to_dict()
            meta_path = self._getdir(path, "Database", "")
            meta_path = meta_path.split("/")[:-1]
            meta_path = ('/').join(meta_path) + "/metadata.json"

            with open(meta_path, "w") as fp:
                json.dump(meta, fp)

    def to_txt(
        self,
        path=None,
        flows=True,
        coefficients=False,
        scenario="baseline",
        _format="txt",
        include_meta=False,
        sep=",",
    ):
        """Saves the database multiple text file based on given inputs

        .. note::
            * The function will create multiple text files carring on the name of the matrices based on the given inputs.
            * It is suggested to keep the units = True so the output file can be used to parse with MARIO again.

        Parameters
        ----------
        path : str
            the path that the Excel file should be saved. If it is None, MARIO
            will try to use the default path and inform the user with a warning.

        flows : boolean
            if True, in the Excel file, a sheet will be created named flows containing
            the data of the flows

        coefficients : boolean
            if True, in the Excel file, a sheet will be created named coefficients containing
            the data of the coefficients

        units : boolean
            if True, in the Excel file, a sheet will be created named units containing
            the data of the units

        scenario : str
            defines the scenario to print out the data

        _format : str
            * txt to save as txt files
            * csv to save as csv files

        include_meta : bool
            saves the metadata as a json file along with the data

        sep : str
            txt file separator
        """

        if scenario not in self.scenarios:
            raise WrongInput(
                "{} is not a valid scenario. Existing scenarios are {}".format(
                    scenario, [*self.matrices]
                )
            )

        if flows==False and coefficients==False:
            raise WrongInput("At least one of the flows or coefficients should be True")
        
        database_txt(
            self,
            flows,
            coefficients,
            self._getdir(path, "Database", ""),
            scenario,
            _format,
            sep,
        )

        if include_meta:
            meta = self.meta._to_dict()
            with open(self._getdir(path, "Database", "") + "/metadata.json", "w") as fp:
                json.dump(meta, fp)

    def to_pymrio(
        self,
        satellite_account="satellite_account",
        factor_of_production="factor_of_production",
        include_meta=True,
        scenario="baseline",
        **kwargs,
    ):
        """Returns a pymrio.IOSystem from a mario.Database

        Parameters
        -----------
        satellite_acount : str
            Defines the name of the pymrio.Extension built from mario satellite account

        factor_of_production : str
            Defines the name of the pymrio.Extension built from mario factor of production

        include_meta : str
            If True, will record mario.meta into pymrio.meta

        scenario : str
            The specific scenario to create the pymrio.IOSystem from

        **kwargs : (pymrio.IOSystem **kwargs)


        Returns
        -------
        pymrio.IOSystem

        Raises
        ------
        NotImplementable
            if table_type is SUT

        WrongInput
            incorrect naming for factor_of_production and satellite_acount
        """

        if self.table_type != "IOT":
            raise NotImplementable("pymrio supports only IO tables.")

        if any([" " in i for i in [satellite_account, factor_of_production]]):
            raise WrongInput(
                "satellte_account and factor_of_production does not accept values containing space."
            )

        matrices = self.query(
            matrices=[_ENUM.V, _ENUM.Z, _ENUM.Y, _ENUM.E, _ENUM.EY],
            scenarios=[scenario],
        )

        factor_input = pymrio.Extension(
            name=factor_of_production,
            F=pymrio_styling(df=matrices[_ENUM.V], **_PYMRIO_MATRICES["V"]),
            unit=self.units[_MASTER_INDEX["f"]],
        )

        satellite = pymrio.Extension(
            name=satellite_account,
            F=pymrio_styling(df=matrices[_ENUM.E], **_PYMRIO_MATRICES["E"]),
            F_Y=pymrio_styling(df=matrices[_ENUM.EY], **_PYMRIO_MATRICES["EY"]),
            unit=self.units[_MASTER_INDEX["k"]],
        )

        units = pd.DataFrame(
            data=np.tile(
                self.units[_MASTER_INDEX["s"]].values,
                (len(self.get_index(_MASTER_INDEX["r"])), 1),
            ),
            index=matrices[_ENUM.Z].index,
            columns=["unit"],
        )

        io = pymrio.IOSystem(
            Z=pymrio_styling(df=matrices[_ENUM.Z], **_PYMRIO_MATRICES["Z"]),
            Y=pymrio_styling(df=matrices[_ENUM.Y], **_PYMRIO_MATRICES["Y"]),
            unit=units,
            **kwargs,
        )

        setattr(io, satellite_account, satellite)
        setattr(io, factor_of_production, factor_input)

        io.meta.note("IOSystem and Extension initliazied by mario")

        if include_meta:
            for note in self.meta._history:
                io.meta.note(f"mario HISTORY - {note}")

        return io

    def get_add_sectors_excel(self, new_sectors, regions, path=None, item=None):
        """Generates an Excel file to add a sector/activity/commodity to the database

        Parameters
        ----------
        new_sectors : list
            new sectors/activities/commodities to be added to the database

        regions : list
            specific regions that the new technology will be specified

        path : str
            the path in which the Excel file will be saved (path should contain the name of file like 'path\\add_sector.xlsx')

        item : str
            the item to be added. Sector for IOT table and Activity or Commodity for SUT

        """

        if (not isinstance(regions, list)) and (not isinstance(new_sectors, list)):
            raise WrongInput("'regions' and 'new_sectors' should be a list.")

        difference = set(regions).difference(self.get_index(_MASTER_INDEX["r"]))

        if difference:
            raise WrongInput(
                "Regions: {} do not exist in the database. Existing regions are:\n{}".format(
                    difference,
                    self.get_index(_MASTER_INDEX["r"]),
                )
            )

        if self.meta.table == "SUT":
            if item not in [_MASTER_INDEX["c"], _MASTER_INDEX["a"]]:
                raise WrongInput(
                    "For SUT, item should be {} or {}".format(
                        _MASTER_INDEX["c"], _MASTER_INDEX["a"]
                    )
                )
            _add_sector_sut(
                self,
                new_sectors,
                regions,
                self._getdir(path, "Excels", "add_sectors.xlsx"),
                item,
                num_validation=30,
            )

        else:
            _add_sector_iot(
                self,
                new_sectors,
                regions,
                self._getdir(path, "Excels", "add_sectors.xlsx"),
                num_validation=30,
            )

    def add_sectors(
        self,
        io,
        new_sectors,
        regions,
        item,
        inplace=True,
        notes=None,
    ):
        """Adds a Sector/Activity/Commodity to the database

        .. note::

            This function will delete all the scenarios in the datbase and overwirte
            the new matrices to the baseline.

        Parameters
        ----------
        io : str, Dict[pd.DataFrame]
            the path of the Excel file containing the information or an equal dictionary with
            keys as the names of the sheets and values as dataframes of the excel file

        new_sectors : list
            new sectors/activities/commodities to be added to the database

        regions : list
            specific regions that the new technology will be specified

        item : str
            the item to be added. Sector for IOT table and Activity or Commodity for SUT
            Sector if IOT, Activity or Commodity if SUT
        inplace : boolean
            if True will implement the changes directly in the database else
            returns a new new mario.Database

        notes: list, Optional
            notes to be recorded in the metadata

        Returns
        -------
        mario.Database:
            if inplace = True will return a new mario.Database
        None:
            if inplace = False returns None and implements the changes in the databases
        """
        if not inplace:
            new = self.copy()
            new.add_sectors(
                io=io, new_sectors=new_sectors, regions=regions, item=item, inplace=True
            )
            return new

        difference = set(regions).difference(self.get_index(_MASTER_INDEX["r"]))

        if difference:
            raise WrongInput(
                "Regions: {} do not exist in the database. Existing regions are:\n{}".format(
                    difference,
                    self.get_index(_MASTER_INDEX["r"]),
                )
            )

        if self.meta.table == "SUT":
            if item not in [_MASTER_INDEX["c"], _MASTER_INDEX["a"]]:
                raise WrongInput(
                    "For SUT, item should be {} or {}".format(
                        _MASTER_INDEX["c"], _MASTER_INDEX["a"]
                    )
                )
        else:
            item = _MASTER_INDEX["s"]

        log_time(
            logger,
            "Database: All the scenarios will be deleted from the database",
            "warning",
        )

        new_data, units = add_new_sector(self, io, new_sectors, item, regions)

        new_data["X"] = calc_X_from_z(new_data["z"], new_data["Y"])
        new_data["E"] = calc_E(new_data["e"], new_data["X"])
        new_data["V"] = calc_E(new_data["v"], new_data["X"])
        new_data["Z"] = calc_Z(new_data["z"], new_data["X"])

        # add new sector in the index
        index_take = [key for key, take in _MASTER_INDEX.items() if take == item][0]
        for sec in new_sectors:
            self.units[item].loc[sec, "unit"] = units.loc[sec, "unit"]
            self._indeces[index_take]["main"].append(sec)
            if index_take != "s":
                self._indeces["s"]["main"].append(sec)

        new_data["EY"] = self.EY

        # Deleting old values
        for matrix in ["z", "e", "v", "Y", "X", "Z", "E", "V", "EY"]:
            self.matrices["baseline"][_ENUM[matrix]] = new_data[matrix]

        self.meta._add_history(
            "Scenarios: all the scenarios deleted from the database."
        )
        self.meta._add_history(
            f"Database: new {item}: {new_sectors} added to the database"
            f" for regions: {regions} based on data imported from {io}"
        )

        log_time(
            logger,
            f"New {item}: {new_sectors} added to the database"
            f" for regions: {regions} sucessfully.",
        )

        if notes:
            for note in notes:
                self.meta._add_history(f"User note: {note}")

    def query(
        self,
        matrices,
        scenarios=["baseline"],
        base_scenario=None,
        type="absolute",
    ):
        """Requests a specific data from the database

        Parameters
        ----------
        matrices : str
            list of the matrices to return

        scenarios : str, List[str]
            list of scenarios for returing the matrices

        base_scenario : str
            str representing the base scenario in case that the data should be returned for the change in data between scenarios

        type: str
            #. 'absolute' for absolute difference for scenarios
            #. 'relative' for relative difference for scenarios


        Returns
        -------
        dict,pd.DataFrame
            If multiple scenarios are passed, it returns a dict where keys are the scenarios and vals are the matrices. matrices itself could be a dict or pd.DataFrame depending if multiple matrices or one matrix is passed


        Example
        -------
        Let's consider the case that multiple scenarios ['sc.1','sc.2'] and multiple matrices ['X','z'] are passed:

        .. code-block:: python

            output = example.query(scenarios= ['sc.1','sc.2'], matrices = ['X','z'])

        the output in this case would be:

        type: Dict[Dict[pd.DataFrame]]

        {
            "sc.1" : {
                "X": pd.DataFrame,
                "z": pd.DataFrame,
            },
            "sc.2" : {
                "X": pd.DataFrame,
                "z": pd.DataFrame,
            },

        }

        if only one scenario ("sc.1") is passed, output will be:

        type Dict[pd.DataFrame]
        {
            "X": pd.DataFrame,
            "Y": pd.DataFrame,
        }

        if only one scenario ("sc.1") and one matrix ("X") is passed the output will be a single pd.DataFrame.
        """
        if isinstance(scenarios, str):
            scenarios = [scenarios]
        data = self.get_data(
            matrices=matrices,
            units=False,
            indeces=False,
            format="dict",
            scenarios=scenarios,
            base_scenario=base_scenario,
            type=type,
        )

        if len(matrices) == 1:
            for scenario in scenarios:
                data[scenario] = data[scenario][matrices[0]]

        if len(scenarios) == 1:
            data = data[scenarios[0]]

        return data

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
        """Returns specific data and calculating them or the changes for scenarios in a database
           if requested

        Parameters
        ----------
        matrices : str
            list of the matrices to return

        units : boolean
            Returns the units for every scenario

        indeces : boolean
            Returns the indeces for every scenario

        auto_calc : boolean
            If True, will try to the missing data if possible

        format : str
            #. 'object' returns a namedtuple
            #. 'dict' returns a dictionary

        scenarios : str, List[str]
            list of scenarios for returing the matrices

        base_scenario : str
            str representing the base scenario in case that the data should be returned for the change in data between scenarios

        type: str
            #. 'absolute' for absolute difference for scenarios
            #. 'relative' for relative difference for scenarios

        Returns
        -------
        dict:
            a nested dict of scnearios and the data asked

        namedtuples:
            a nested dict of namedtuples with keys refering to scenarios and values namedtuples of data
        """

        def calc_data():
            if base_scenario is None:
                data[item] = copy.deepcopy(self.matrices[scenario][item])
            else:
                if type == "absolute":
                    data[item] = copy.deepcopy(
                        self.matrices[scenario][item]
                        - self.matrices[base_scenario][item]
                    )

                elif type == "relative":
                    data[item] = copy.deepcopy(
                        (
                            self.matrices[scenario][item]
                            - self.matrices[base_scenario][item]
                        )
                        / self.matrices[base_scenario][item]
                    )

        _OPTIONS = copy.deepcopy(_ALL_MATRICES[self.table_type])

        if isinstance(scenarios, str):
            scenarios = [scenarios]

        if isinstance(matrices, str):
            matrices = [matrices]

        if type not in ["absolute", "relative"]:
            raise WrongInput(
                "Acceptable values for type are:\n{}".format(["absolute", "relative"])
            )

        diff = set(matrices).difference(set(_OPTIONS))

        if diff:
            raise WrongInput(
                "{} is/are not an acceptable input/s. Acceptabel values are:\n{}".format(
                    diff, _OPTIONS
                )
            )

        for scenario in scenarios:
            if scenario not in [*self.matrices]:
                raise WrongInput(
                    "{} is not an acceptable scenario. Acceptable scenarios are:\n{}".format(
                        scenario, [*self.matrices]
                    )
                )

        if base_scenario is not None and base_scenario not in [*self.matrices]:
            raise WrongInput(
                "{} is not an acceptable scenario for base_scenario. Acceptabel scenarios are:\n{}".format(
                    base_scenario, [*self.matrices]
                )
            )

        if units:
            matrices.append("units")
        if indeces:
            matrices.append("indeces")

        dict_scenarios = {}
        for scenario in scenarios:
            data = {}
            for item in matrices:
                if item == "units":
                    data["units"] = copy.deepcopy(self.units)
                elif item == "indeces":
                    data["indeces"] = copy.deepcopy(self._indeces)
                else:
                    try:
                        calc_data()

                    except KeyError:
                        if auto_calc:
                            try:
                                calc_missed = {}

                                if (
                                    base_scenario is not None
                                    and self.matrices[base_scenario].get(item) is None
                                ):
                                    calc_missed[base_scenario] = item
                                if self.matrices[scenario].get(item) is None:
                                    calc_missed[scenario] = item

                                for key, value in calc_missed.items():
                                    self.calc_all(
                                        matrices=[value], scenario=key, setattr=False
                                    )

                                calc_data()

                            except:
                                raise NotImplementable(
                                    f"Model is not able to calculate the missing data {item} for scenario {scenario}. Please use the calc_all function before calling this function."
                                )

                        else:
                            raise DataMissing(
                                "{} is not calculated. Using auto_calc = True, can track the missing data and calculate them".format(
                                    item
                                )
                            )

            if format == "dict":
                dict_scenarios[scenario] = data
            else:
                mini_object = namedtuple("data", matrices)
                if len(scenario) == 1:
                    dict_scenarios = mini_object(**data)
                else:
                    dict_scenarios[scenario] = mini_object(**data)

        return dict_scenarios

    def DataFrame(
        self,
        scenario="baseline",
    ):
        """Returns a single DatFrame which is the whole flows all together.


        Parameters
        ----------
        scenario : str
            scenario requested


        Returns
        -------
        pd.DataFrame
        """

        data = self.query(
            matrices=[_ENUM.Z, _ENUM.Y, _ENUM.V, _ENUM.E, _ENUM.EY],
            scenarios=scenario,
        )

        Z = data[_ENUM.Z]
        Y = data[_ENUM.Y]
        V = data[_ENUM.V]
        E = data[_ENUM.E]
        EY = data[_ENUM.EY]

        V.index = [[""] * len(V), [_MASTER_INDEX["f"]] * len(V), V.index]
        E.index = [[""] * len(E), [_MASTER_INDEX["k"]] * len(E), E.index]
        EY.index = [[""] * len(EY), [_MASTER_INDEX["k"]] * len(EY), EY.index]

        index = []
        columns = []

        for i in range(3):
            index.append(
                Z.index.get_level_values(i).to_list()
                + E.index.get_level_values(i).to_list()
                + V.index.get_level_values(i).to_list()
            )
            columns.append(
                Z.columns.get_level_values(i).to_list()
                + Y.columns.get_level_values(i).to_list()
            )

        dataframe = pd.DataFrame(
            np.zeros((len(index[0]), len(columns[0]))), index=index, columns=columns
        )

        for item in [Z, Y, V, E, EY]:
            dataframe.loc[item.index, item.columns] = item.loc[item.index, item.columns]

        return dataframe

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
        """Implements shocks on different matrices with the
        possibility of defining clusters on every level of information.

        .. note::

            * Shocks can be implemented only with respect to the baseline
            * Shocks will be implemented only on coefficients

        Parameters
        ----------
        io : str, Dict[pd.DataFrame]
            pass a str defining the excel file containing the shock data or pass a dict of dataframes in which keys are the name of matrices and values are the dataframes of the shock (exactly the same format of excel file)

        z : boolean
            if True will implement shock on the Z or z

        e : boolean
            if True will implement shock on the E or e

        v : boolean
            if True will implement shock on the V or v

        Y : boolean
            if True will implement shock on Y

        notes : list
            extra info can be recoreded in the metadata

        scenario : str, Optional
            the name for the scenario implemented, in the instance.matrices. If nothing passed, default names will be considered (shock #)

        fore_rewrite : boolean
            if False will avoid overwriting existing scenario

        **cluster : dict
            can be used to implement complex shocks by defining clusters (refer to tutorials)
        """

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

        _results = calc_all_shock(z_c, e_c, v_c, Y_c)
        _results["EY"] = EY_c

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
        """Creates an Excel file based on the shape and the format
           of the database for the shock impelemntation.


        .. note::

            The generated Excel file will have list validations to simplify the error
            handling and help the user. In case the number of shocks are more than 10,
            it is suggested to increse num_shock to have more validated rows in every
            sheet of the Excel file.

        Parameters
        ----------
        path : str
            defines the path which the Excel file will be stored

        clusters : dict
             nested dictwith clusters the user can define a sets of clusters for more specificed
             shock implementation.
             e.g. clusters = {'Region':{'cluster_1':['reg1','reg2']}}
        """

        check_clusters(
            index_dict=self.get_index("all"), table=self.table_type, clusters=clusters
        )

        _sh_excel(self, num_shock, self._getdir(path, "Excels", "shock.xlsx"), clusters)

    def replace_units_name(self, level, names):
        if level not in [*_LEVELS[self.meta.table]]:
            raise WrongInput(
                "'{}' is not a valid index. Valid indeces are: \n{}".format(
                    level, [*_LEVELS[self.meta.table]]
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
        """Creates bubble plots

        Parameters
        ----------
        x : str
            item to locate on x-axis. valid items should be a factor of production, satellite account or GDP

        y : str
            item to locate on y-axis. valid items should be a factor of production, satellite account or GDP

        size : str
            item to locate on size of bubble. valid items should be a factor of production, satellite account or GDP

        path : str
            the path and the name of the file to save the plot. Like 'path\\plot.html'

        auto_open : boolean
            if True, opens the plot automatically

        scenario : str
            scenario to plot

        log_x : boolean
            if True, will plot with x-axis with Logarithmic scale

        log_y : boolean
            if True, will plot with y-axis with Logarithmic scale
        """

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
        """Plots sectoral GDP with additional info

        Parameters
        ----------
        path : str, Optional
            the path and the name of the file to save the plot

        plot : str
            type of the plot ['treemap','sunburst']

        scenario : str
            scenario to plot

        extension : str, optional
            a satellite account item that can be used for scaling the colors

        extension_value : str
            # 'relative' for scaling on specific satellite account (e.g. CO2/Euro of production)
            # 'absolute' for abolute scaling on satellite account (e.g. total CO2)

        auto_open : boolean
            if True, the plot will be opened automatically

        drop_reg : str, optional
            a region to be excluded in the plot can be passed. Useful when using MRIO with one region and a Rest of the World region.

        title: str, optional
            here the user can pass a costume title for the plot
        """

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
        """Generates a general html barplot giving the user certain degrees of freedom such as:

            * Regions (both the ones on the indices and columns)
            * Sectors/Commodities/Activities (both the ones on the indices and columns)
            * Scenarios
            * Units

        Parameters
        ----------
        matrix : str
            Matrix to be plotted. Three families of matrix can be read according to their intrinsic structure:

            #. The first family includes only matrix 'X', which has 3 levels of indices and 1 level of columns
            #. The second family includes matrices 'Z','z','U','u','S','s','Y', which have 3 levels of indices and 3 levels of columns
            #. The third family includes matrices 'E','e','V','v','EY', which have 1 level of indices and 3 levels of columns

        path : str
            Path where to save the html file

        x : str
            Degree of freedom to be showed on the x axis.
            Acceptable options change according to the matrix family

        y : str
            Degree of freedom to be showed on the y axis. Default y='Value'.
            Acceptable options change according to the matrix family

        item: str
            Indicates the main level to be plot.
            Possible options are "Commodity","Activity" for SUT tables and "Sector" for IOT tables.
            It is mandatory to be defined only for SUT tables.
            For "Z","z","U","u","S","s","Y","X", it selects the rows level between 'Activity' and 'Commodity'.
            For "V","v","E","e","EY","M","F", it selectes the columns level between 'Activity' and 'Commodity'.

        facet_row:
            String referring to one level of indices of the given matrix.
            Values from this column or array_like are used to assign marks to facetted subplots in the vertical direction

        facet_col:
            String referring to one level of indices of the given matrix.
            Values from this column or array_like are used to assign marks to facetted subplots in the horizontal direction

        animation_frame:
            Defines whether to switch from one scenario to the others by means of sliders

        base_scenario : str
            By setting None, the passed matrix will be displayed for each scenario available.
            By setting this parameter equal to one of the scenarios available,
            the passed matrix will be displayed in terms of difference with respect to each of the other scenarios.
            In this last case, the selected scenario will not be displayed

        mode : str
            Equivalent to plotly.grap_object.figure.update_layout barmode. Determines how bars at the same location coordinate are displayed on the graph.
            * With "stack", the bars are stacked on top of one another
            * With "relative", the bars are stacked on top of one another
            * With "group", the bars are plotted next to one another centered around the shared location.
            * With "overlay", the bars are plotted over one another, you might need to an "opacity" to see multiple bars.

        auto_open : boolean
            if True, it opens automatically the saved file in the default html reader application

        filters : dict
            The user has the option to filter the sets according to the necessity.
            Acceptable options are the following and must be provided as list:

            * 'filter_Region_from',
            * 'filter_Region_to',
            * 'filter_Sector_from',
            * 'filter_Sector_to',
            * 'filter_Consumption category',
            * 'filter_Activity',
            * 'filter_Commodity'

        """

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
            print(
                "Warning: according to the set combination of 'matrix' and 'item_from', matrix has been changed to '{}'".format(
                    matrix
                )
            )
        if (
            self.table_type == "SUT"
            and matrix == "z"
            and item_from == _MASTER_INDEX["c"]
        ):
            matrix = "u"
            print(
                "Warning: according to the set combination of 'matrix' and 'item_from', matrix has been changed to '{}'".format(
                    matrix
                )
            )
        if (
            self.table_type == "SUT"
            and matrix == "Z"
            and item_from == _MASTER_INDEX["a"]
        ):
            matrix = "S"
            print(
                "Warning: according to the set combination of 'matrix' and 'item_from', matrix has been changed to '{}'".format(
                    matrix
                )
            )
        if (
            self.table_type == "SUT"
            and matrix == "z"
            and item_from == _MASTER_INDEX["a"]
        ):
            matrix = "s"
            print(
                "Warning: according to the set combination of 'matrix' and 'item_from', matrix has been changed to '{}'".format(
                    matrix
                )
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
            layout["title"] = f"{_MATRICES_NAMES[matrix]}"
        else:
            layout[
                "title"
            ] = f"{_MATRICES_NAMES[matrix]} - Variation with respect to '{base_scenario}' scenario"

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
