# -*- coding: utf-8 -*-
"""
Created on Tue Jun 29 17:14:52 2021

@author: MARIO TEAM
"""
from mario.log_exc.exceptions import (
    LackOfInput,
    WrongInput,
    NotImplementable,
    DataMissing,
)
from mario.log_exc.logger import log_time
from mario.core.mariometadata import MARIOMetaData
from mario.tools.tableparser import dataframe_parser


from mario.tools.iomath import (
    calc_X,
    calc_Z,
    calc_w,
    calc_g,
    calc_X_from_w,
    calc_X_from_z,
    calc_E,
    calc_V,
    calc_e,
    calc_v,
    calc_z,
    calc_b,
    calc_F,
    calc_f,
    calc_f_dis,
    calc_y,
    calc_p,
)

from tabulate import tabulate
from collections import namedtuple
from typing import List

import numpy as np
import pandas as pd
import logging
import os
import copy
import re

import warnings

# Filter out the specific warning from openpyxl
warning_message = "Data Validation extension is not supported and will be removed"
warnings.filterwarnings("ignore", message=warning_message)

# constants
from mario.tools.constants import (
    _LEVELS,
    _MASTER_INDEX,
    _ENUM,
    _CALC,
    _ALL_MATRICES,
)

logger = logging.getLogger(__name__)


class CoreModel:

    """This class serves as the main IO parent class which contains some basic
    input-output properties,


    Notes
    -----
    This class will never be used by the user!

    Also meta data will be created in the initialization process.
    a backup object (as namedtuple) is created to have the ability to keep a backup
    in every step before implementing impactful changes.
    """

    def __init__(
        self,
        name=None,
        table=None,
        Z=None,
        E=None,
        V=None,
        Y=None,
        EY=None,
        units=None,
        price=None,
        source=None,
        calc_all=True,
        year=None,
        **kwargs,
    ):
        name: str
        table: str
        Z: pd.DataFrame
        E: pd.DataFrame
        V: pd.DataFrame
        Y: pd.DataFrame
        EY: pd.DataFrame
        units: dict
        price: str
        source: str
        calc_all: bool
        year: int
        """
        Initializing a BaseClass can be done based on different ways.
        1. Giving the Dataframes + units
        2. initializing by the method kwargs that is called: init_by_parsers.
        In this case, 3 sets of data are needed: A. matrices, B. units, C.indeces
        """
        self._dir = ""
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
                renamed_matrices[_ENUM[m]] = v

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
                    "For building an instance using dataframes, all the data [Y,E,Z,V,EY,units,table] should be given."
                )
            else:
                self.matrices, self._indeces, self.units = dataframe_parser(
                    Z, Y, E, V, EY, units, table
                )

                matrices = self.matrices["baseline"]
                renamed_matrices = {}

                for m, v in matrices.items():
                    renamed_matrices[_ENUM[m]] = v

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
        """Calculates the input-output matrices for different scenarios.

        Notes
        -----

        By default, the function avoid the calculation of the already existing matrices in
        the scenario datasets. In case the user needs to overwrite the matrices,
        force_rewrite = True can be used.

        It tries to find the missing data for calculating another data in a recursive
        process with maximum five tries.

        Parameters
        ------------
        matrices : list
            a list of matrices to be calculated (default values are ["z", "v", "e",'Z','V','E'])
        scenario : str
            the name of the scenario
        force_rewrite : bool
            False if over-write is not allowed (faster)
        """

        _OPTIONS = copy.deepcopy(_ALL_MATRICES[self.table_type])

        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

        for i in matrices:
            if i not in _OPTIONS:
                raise WrongInput(
                    "{} not present in acceptable item for calc_all. Acceptable matrices are {}".format(
                        i, _OPTIONS
                    )
                )

        for item in matrices:
            if item not in [*self.matrices[scenario]] or force_rewrite:
                _try = kwargs.get("try", 0)
                kwargs["try"] = _try
                try:
                    if item != _ENUM.X:
                        eq = _CALC[item][0]

                        kw = _CALC[item][1]

                        data = eval(eq.format(scenario=scenario, **kw))
                    else:
                        if _ENUM.z in self.matrices[scenario]:
                            data = calc_X_from_z(
                                z=self.matrices[scenario][_ENUM.z],
                                Y=self.matrices[scenario][_ENUM.Y],
                            )

                        elif _ENUM.Z in self.matrices[scenario]:
                            data = calc_X(
                                Z=self.matrices[scenario][_ENUM.Z],
                                Y=self.matrices[scenario][_ENUM.Y],
                            )

                        else:
                            raise DataMissing(
                                f"MARIO is not able to calculate the {item} becuase of missing data."
                                " Presence of Y and of the [z,Z] is necessary."
                            )

                    self.matrices[scenario].update({item: data})

                    log_time(logger, f"Database: {item} calculated for {scenario}")

                except KeyError as error:
                    # calculate automatically all the dependecies if possible in an recursive process
                    if kwargs.get("try", 0) < 5:
                        kwargs["try"] += 1

                        log_time(
                            logger,
                            f"Database: to calculate {item} following matrices are need.\n{list(error.args)}."
                            f"Trying to calculate dependencies.",
                            "warning",
                        )
                        self.calc_all(list(error.args), scenario, **kwargs)
                        self.calc_all([item], scenario, **kwargs)

                    else:
                        raise DataMissing(
                            f"MARIO is not able to calculate the {item} after 5 tries becuase of missing data."
                        )

    def add_note(self, notes):
        """Adds notes to the meta history

        Parameters
        ----------

        notes: list
            a list of notes to be recorded on metadata
        """

        if isinstance(notes, str):
            notes = [notes]

        for note in notes:
            self.meta._add_history(f"User Note: {note}")

    def update_scenarios(self, scenario, **matrices):
        """Updates the matrices for a specific scenario.

        .. note::

            using update scenarios, will update only the matrices passed. In case,
            that the update, impacts other matrices, this should be done manually
            using update_scenarios and updating other matrices or reseting the datbases
            using reset_to_flows or reset_to_coefficients and recalculate the matrices
            based on the inputs.

        Parameters
        ----------
        scenario : str
            the name of the scenario

        matrices : pd.DataFrame
            dict of the matrices as dataframes (keys are the name of the
            matrices and values are the DataFrames)

        Example
        -------
        To update the z and v matrices in example object for scenario baseline
        with new_z and new_v

        .. code-block:: python

            example.update_scenarios(scenario='baseline',z=new_z,v=new_v)

        """

        if scenario not in self.scenarios:
            raise WrongInput(f"Existing scenarios are {self.scenarios}")

        if not all([isinstance(value, pd.DataFrame) for value in matrices.values()]):
            raise WrongInput("items should be DataFrame")

        for matrix, value in matrices.items():
            self.matrices[scenario][matrix] = value

    def clone_scenario(
        self,
        scenario,
        name,
    ):
        """Creates a new scenario by cloning an existing scenario

        Parameters
        ----------
        scenario : str
            from which scenario clone

        name : str
            the name of the new scenario to be created


        Example
        ---------
        Creating a new scenario called scenario\_2 by cloning the data in scenario baseline

        .. code-block:: python

            database.clone_scenario(scenario= 'baseline', name='scenario_2')
        """

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
        """Deletes the coefficients of a scenario and keeps only flows

        Parameters
        ----------
        scenario : str
            the specific scenario to reset

        """

        keep = [_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.EY, _ENUM.Y]

        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

        matrices = {}
        for key in keep:
            if key in self.matrices[scenario]:
                matrices[key] = copy.deepcopy(self.matrices[scenario][key])
            else:
                self.calc_all(matrices=[key], scenario=scenario)
                matrices[key] = copy.deepcopy(self.matrices[scenario][key])

        log_time(logger, "Databases: reset to flows.")
        self.matrices[scenario] = matrices

    def reset_to_coefficients(self, scenario):
        """Deletes the flows of a scenario and keeps only coefficients

        Parameters
        -----------
        scenario : str
            the specific scenario to reset

        """
        keep = [_ENUM.z, _ENUM.e, _ENUM.v, _ENUM.EY, _ENUM.Y]

        if scenario not in self.scenarios:
            raise WrongInput(f"Acceptable scenarios are {self.scenarios}")

        matrices = {}
        for key in keep:
            if key in self.matrices[scenario]:
                matrices[key] = copy.deepcopy(self.matrices[scenario][key])
            else:
                self.calc_all(matrices=[key], scenario=scenario)
                matrices[key] = copy.deepcopy(self.matrices[scenario][key])

        log_time(logger, "Databases: reset to coefficients.")
        self.matrices[scenario] = matrices

    def get_index(self, index, level="main"):
        """Returns a list or a DataFrame of different levels of indeces in the database.

        Parameters
        -----------
        index : str
            if 'all' return all the indeces else representing the level such as Region, Sector, ...
        level : str
            main for the main indeces and aggregated for aggregated level if exists

        Returns
        -------
        dict:
            if index='all' returns a dictionary of all indeces
        list:
            if index is not 'all' returns a list of requested index level
        """

        if index == "all":
            return {
                key: self._indeces[value].get(level)
                for key, value in _LEVELS[self.table_type].items()
            }

        if index not in self.sets:
            raise WrongInput(
                "'{}' is not a valid index. Valid indeces are: \n{}".format(
                    index, self.sets
                )
            )

        if level not in [*self._indeces[_LEVELS[self.table_type][index]]]:
            raise WrongInput(
                "'{}' is not a valid level for '{}' . Valid levels are: \n{}".format(
                    level, index, [*self._indeces[_LEVELS[self.meta.table][index]]]
                )
            )

        return copy.deepcopy(self._indeces[_LEVELS[self.table_type][index]][level])

    def is_balanced(
        self,
        method,
        data_set="baseline",
        margin=0.05,
        as_dataframe=False,
    ):
        """Checks if a specific data_set in the database is balance or not

        .. note::

            If the datase is not balance, a table will be printed spotting
            the inbalances.

        parameters
        ----------
        method : str
            represents the method to check the balance:

                #. 'flow'
                #. 'coefficient': (zeros wont be considered)
                #. 'price': (zeros wont be considered)

        data_set : str
            defines the scenario to be checked

        margin : float
            float which will be considered as a margin for the balance

        as_dataframe: boolean
            if True, in case that datbase is not balance, will return a pd.DataFrame
            spotting the imbalances

        Returns
        -------

        if balance:
            returns True

        if not balance:
            if as_dataframe= False, return a boolean (False)
            if as_dataframe= True, return a pd.DataFrame


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
        """Checks whether a table is in Isard format.
        Isard SUT tables account for trades among regions in the USE matrix

        Parameters
        ------------
        scenario: str
            defining the scenario to be checked

        RETURN
        -------------
        boolean

                True if the dataset is isard
                Flase if the dataset is not isard
        """

        if self.meta.table != "SUT":
            raise NotImplementable("This test is implementable only on SUT tables")
        elif len(self.get_index(_MASTER_INDEX["r"])) == 1:
            raise NotImplementable(
                "This test is not implementable on single-region tables"
            )

        if scenario not in self.scenarios:
            raise WrongInput("Acceptable data_sets are:\n{}".format(self.scenarios))

        if (
            _ENUM.z in self.matrices[scenario]
        ):  # this avoid to calculate z or Z in case one of them is missing, to avoid losing time
            matrix = self.matrices[scenario][_ENUM.z]
        else:
            matrix = self.matrices[scenario][_ENUM.Z]

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
        """Checks whether a table is in Isard format.
        Isard SUT tables account for trades among regions in the USE matrix

        Parameters
        ------------
        scenario: str
            defining the scenario to be checked

        RETURN
        -------------
        boolean
                True if the dataset is isard
                Flase if the dataset is not isard
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

        if (
            _ENUM.z in self.matrices[scenario]
        ):  # this avoid to calculate z or Z in case one of them is missing, to avoid losing time
            matrix = self.matrices[scenario][_ENUM.z]
        else:
            matrix = self.matrices[scenario][_ENUM.Z]

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
        """Returns a deepcopy of the instance

        Returns
        --------
        MARIO.Database

        """
        new = copy.deepcopy(self)
        new.meta._add_history("deep copy created from object")
        return new

    def save_meta(self, path, format="txt"):
        """Saves the metadata in different formats

        Parameters
        ------------
        path : str
            defines the path to save metadata

        format : str
            the format of the file: ['txt','binary','json']
        """
        self.meta._save(path, format)

    def __str__(self):
        to_print = (
            "name = {}\n"
            "table = {}\n"
            "scenarios = {}\n".format(self.meta.name, self.meta.table, self.scenarios)
        )
        for item in _LEVELS[self.meta.table]:
            to_print += "{} = {}\n".format(item, len(self.get_index(item)))

        return to_print

    def __repr__(self):
        return self.__str__()

    def GDP(
        self,
        exclude=[],
        scenario="baseline",
        total=True,
        share=False,
    ):
        """Return the value of the GDP based scenario.

        .. note::

            GDP based on the total V. In case that some of the items
            should be ignored for the calulation of the GDP (such as the imports in
            single region models), the user can use exclude argument to ignore some
            of the value added items.

        Parameters
        -----------
        exclude: list, Optional
            the items to be avoided excluded from the Value added for the
            calculation of the GDP.

        scenario : str
            the scenario to take

        total : boolean
            if True, it will return the total GDP.
            if False, it returns the sectoral GDP

        share : boolean
            if total = False, it adds a new column with sectoral share of regions

        Returns
        -------
        pd.DataFrame

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

    def search(self, item, search, ignore_case=True):
        """Searches for specific keywords in a given item

        Parameters
        ----------
        item : str
            specific level of information like Region, Satellite account, Secotr, ...

        search : str
            a keyword to search

        ignore_case : bool
            if True will ignore uppercase and lowercase sensitivity

        Returns
        -------
        list :
            a list of items found in the search
        """

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
        """Returns all the scenarios existed in the model

        Returns
        -------
        list
        """
        return [*self.matrices]

    @property
    def table_type(self):
        """Returns the type of the database

        Returns
        -------
        str
        """
        return self.meta.table

    @property
    def is_multi_region(self):
        """Defines if a database is single region or multi-region

        Returns
        -------
        boolean
            True if database is multi region else False
        """
        if len(self.get_index(_MASTER_INDEX["r"])) - 1:
            return True

        return False

    @property
    def sets(self):
        """Returns a list of levels of info in the model

        Returns
        -------
        lists
        """
        return [*_LEVELS[self.table_type]]

    @property
    def is_hybrid(self):
        """checks if the database is hybrid or monetary

        .. note::

            * for IOT table checks the unity of the Secotr + Factor of production
            * for SUT table checks the unity of the Activity+Commodity+Factor of production

        Returns
        -------
        bool
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
        """checks if the given path is correct or not."""

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
        """The defualt directory of the database

        .. note::
            by defualt, mario chooses the working directory as default directory


        Example
        -------
        Changing the default directory to a specific path called my_directory

        .. code-block:: python

            database.directory = r'my_directory'

        """

        if self._dir == "":
            self.directory = r"{}/Output".format(os.getcwd())

        return self._dir

    @directory.setter
    def directory(self, _dir):
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
        """Returns the whole history of the metadata

        Returns
        -------
        list

        """
        history = "\n".join(self.meta._history[:])
        print(history)

    def __getitem__(self, key):
        """get item method retuns the data regarding the scenarios"""
        if key not in self.scenarios:
            raise WrongInput(
                "{} is not a valid scenario. Valid scenarios are {}".format(
                    key, self.scenarios
                )
            )

        return self.matrices[key]

    def __iter__(self):
        self.__it__ = self.scenarios
        return self

    def __next__(self):
        """generating an iterator over the scenarios"""
        if len(self.__it__):
            key = self.__it__[0]
            value = self.matrices[key]

            self.__it__.pop(0)

            return (key, value)

        else:
            raise StopIteration

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]
        else:
            all_mat = copy.deepcopy(_ALL_MATRICES[self.table_type])

            if attr in all_mat:
                self.calc_all(matrices=[attr])
                return self["baseline"][attr]

            else:
                raise AttributeError(attr)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, value):
        self.__dict__ = value

    def __eq__(self, other):
        """Checks the equality if two databases"""
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
        """The function creates a backup of the last configuration of database
        to be returned in case needed.
        """
        self._backup = self._backup_(
            copy.deepcopy(self.matrices),
            copy.deepcopy(self._indeces),
            copy.deepcopy(self.units),
        )
