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


# constants
from mario.tools.constants import (
    _LEVELS,
    _MASTER_INDEX,
    _CALC,
    _ALL_MATRICES,
)

logger = logging.getLogger(__name__)

try:
    import cvxpy as cp

    __cvxpy__ = True
except ModuleNotFoundError:
    log_time(
        logger,
        "cvxpy module is not installed in your system. This will raise problems in some of the abilities of MARIO",
        "critical",
    )
    __cvxpy__ = False


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
            for item in ["matrices", "units", "_indeces"]:
                setattr(self, item, kwargs["init_by_parsers"][item])

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
        matrices=["z", "v", "e", "Z", "V", "E"],
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

                    if item != "X":
                        data = eval(_CALC[item].format(scenario, scenario))
                    else:
                        if "z" in self.matrices[scenario]:
                            data = calc_X_from_z(
                                z=self.matrices[scenario]["z"],
                                Y=self.matrices[scenario]["Y"],
                            )

                        elif "Z" in self.matrices[scenario]:
                            data = calc_X(
                                Z=self.matrices[scenario]["Z"],
                                Y=self.matrices[scenario]["Y"],
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
                            "warn",
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

    def reset_to_flows(self, scenario, backup=True):
        """Deletes the coefficients of a scenario and keeps only flows

        Parameters
        ----------
        scenario : str
            the specific scenario to reset

        backup : boolean
            if True, will create a backup of database before changes
        """
        if backup:
            self.backup()

        keep = ["Z", "E", "V", "EY", "Y"]

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

    def reset_to_coefficients(self, scenario, backup=True):
        """Deletes the flows of a scenario and keeps only coefficients

        Parameters
        -----------
        scenario : str
            the specific scenario to reset

        backup : boolean
            if True, will create a backup of database before changes
        """
        keep = ["z", "e", "v", "EY", "Y"]

        if backup:
            self.backup()

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
            "flows": {"matrices": ["V", "Z", "X"], "header": ["\u0394X"]},
            "coefficients": {"matrices": ["v", "z"], "header": ["v+z"]},
            "prices": {"matrices": ["p"], "header": ["\u0394p"]},
        }

        if method not in methods:
            raise WrongInput(f"Acceptable methods are {[*methods]}")
        if self.is_hybrid:
            raise NotImplementable(
                "Balance test is not applicable for hybrid units tables."
            )

        data = self.get_data(
            matrices=methods[method]["matrices"],
            units=False,
            indeces=False,
            scenarios=[data_set],
            format="object",
            auto_calc=True,
        )[data_set]

        if method == "flows":
            balance = (data.Z.sum() + data.V.sum() - data.X.sum(1)).to_frame()
            balance.columns = ["col"]

            imbalances = balance[
                (balance["col"] >= margin) | (balance["col"] <= -margin)
            ]

        elif method == "coefficients":
            balance = (data.z.sum() + data.v.sum()).to_frame()
            balance.columns = ["col"]

            imbalances = balance[
                (balance["col"] >= 1 + margin)
                | (balance["col"] <= 1 - margin) & (balance["col"] != 0)
            ]

        elif method == "prices":
            balance = data.p
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

    def is_productive(self, method: str, data_set: str = "baseline") -> bool:

        """Checks the productivity of the system

        Parameters
        ------------
        method : str
            represents the method to check the balance:

                #. 'flow'
                #. 'coefficient'
                #. 'price'

        data_set: str
            defining the scenario to be checked

        margin: float which will be considered as a margin for the balance

        RETURN
        -------------

        boolean

                True if the dataset is balance
                Flase if the dataset is not balance --> it also prints in a table the imbalances

        """
        _methods = {
            "A": "SPECTRAL RADIUS",
            "B": "POWER SERIES EXPANSION",
            "C": "SLACK VARIABLE",
        }

        if data_set not in self.scenarios:
            raise WrongInput("Acceptable data_sets are:\n{}".format(self.scenarios))

        if method.upper() not in _methods:
            raise WrongInput("Acceptable methods are: \n{}".format([*_methods]))

        z = copy.deepcopy(self.matrices[data_set]["z"])
        Y = copy.deepcopy(self.matrices[data_set]["Y"])
        Y = Y.sum(axis=1).to_frame()
        I = np.eye(z.shape[0])
        L = np.linalg.inv(I - z)

        log_time(
            logger, "Productivity test by {} method".format(_methods[method.upper()])
        )

        _productive = True

        if method == "A":

            eigen_value = np.linalg.eig(z)[0]
            rho = max(abs(eigen_value))

            if rho < 1:
                log_time(
                    logger,
                    "Test: productive system (spectral radius = {})".format(
                        round(rho, 2)
                    ),
                )

            else:
                log_time(
                    logger,
                    "Test: non-productive system (spectral radius = {})".format(
                        round(rho, 2)
                    ),
                )
                _productive = False

        elif method == "B":

            M = {}
            M[0] = I
            M_cum = {}
            M_cum[0] = M[0]
            residuals = []  # initial point
            error = 0.1
            i = 0

            while residuals[i] >= error:
                M[i + 1] = np.linalg.matrix_power(z, i + 1)
                M_cum[i + 1] = M_cum[i] + M[i + 1]
                residuals.append(sum(sum(abs(L - M_cum[i + 1]))))
                if residuals[i + 1] > residuals[i]:
                    log_time(
                        logger,
                        "Test: non-productive system (non-convergent power series)",
                    )
                    _productive = False
                    break
                i += 1
            else:
                log_time(
                    logger, "Test: productive system (non-convergent power series)"
                )

        elif method == "C" and __cvxpy__:

            x = cp.Variable((Y.shape[0], 1))
            s = cp.Variable((Y.shape[0], 1))

            Z = cp.sum(s, 0)
            obj = cp.Minimize(Z)

            const = [
                cp.matmul(I - z, x) + s == np.ones((Y.shape[0], 1)),
                x >= 0,
                s >= 0,
            ]

            prob = cp.Problem(obj, const)
            prob.solve(verbose=False)
            print(s.value)

            if all(s.value == 0):
                log_time(
                    logger, "Test: productive system (all industries are productive)"
                )

            else:
                log_time(
                    logger,
                    "Test: non-productive system (number of non-productive industries: {})",
                )
                _productive = False

        return _productive

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

        data = self.get_data(
            matrices=["V"],
            scenarios=[scenario],
            units=False,
            indeces=False,
            format="object",
        )[scenario].V

        GDP = (
            data.drop(exclude).sum().to_frame().loc[(slice(None), slicer, slice(None))]
        )
        GDP.columns = ["GDP"]
        GDP.index.names = (
            ["Region", "Level", "Sector"]
            if self.table_type == "IOT"
            else ["Region", "Level", "Activity"]
        )

        if total:
            return GDP.groupby(
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

    def search(self, item, search,ignore_case=True):
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
            r = re.compile(f".*{search}",re.IGNORECASE)
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
                "warn",
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

    def __eq__(self,other):
        """ Checks the equality if two databases
        """
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