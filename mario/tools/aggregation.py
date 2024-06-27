# -*- coding: utf-8 -*-
"""
the module contains the functions used for databases aggregation
"""
import copy
import logging
from mario.tools.iomath import calc_X
import pandas as pd
from mario.log_exc.logger import log_time
from mario.log_exc.exceptions import WrongInput
from copy import deepcopy
from mario.tools.utilities import delete_duplicates, rename_index

from mario.tools.constants import _MASTER_INDEX, _ENUM

logger = logging.getLogger(__name__)


def return_pdIndex(Y, E, V, table):
    Y = deepcopy(Y)
    E = deepcopy(E)
    V = deepcopy(V)

    indeces = {
        "r": {
            "s": Y.index.get_level_values(0),
            "n": Y.columns.get_level_values(0),
        },
        "n": {"n": Y.columns.get_level_values(-1)},
        "f": {"f": V.index},
        "k": {"k": E.index},
    }

    if table == "IOT":
        indeces["s"] = {"s": Y.index.get_level_values(-1)}

    else:
        indeces["a"] = {
            "a": Y.loc[
                slice(None), _MASTER_INDEX["a"], slice(None)
            ].index.get_level_values(-1),
        }
        indeces["c"] = {
            "c": Y.loc[
                slice(None), _MASTER_INDEX["c"], slice(None)
            ].index.get_level_values(-1),
        }

    return indeces


def index_replacer(indeces: dict, mapper, level=None):
    for target, index in indeces.items():
        index = pd.DataFrame(index, index=index, columns=["Aggregation"])

        for item, aggregation in mapper.iterrows():
            index.loc[item, "Aggregation"] = aggregation["Aggregation"]

        indeces[target] = index["Aggregation"].values


def _aggregator(instance, drop):
    data = instance.query(matrices=[_ENUM.Y, _ENUM.V, _ENUM.E])

    # checking the consistencey of units at first
    units = unit_aggregation_check(instance, drop)

    agg_indeces = instance.get_index("all", "aggregated")
    org_indeces = return_pdIndex(
        data[_ENUM.Y], data[_ENUM.E], data[_ENUM.V], instance.table_type
    )

    """
    check the consistency of the databasess
    """
    matrices = {}

    for item in [*_MASTER_INDEX.setting]:
        if agg_indeces.get(_MASTER_INDEX[item]) is not None:
            index_replacer(
                indeces=org_indeces[item],
                mapper=agg_indeces[_MASTER_INDEX[item]],
            )

    E_index = EY_index = org_indeces["k"]["k"]

    V_index = org_indeces["f"]["f"]

    Y_columns = EY_columns = [
        org_indeces["r"]["n"],
        instance.query(_ENUM.Y).columns.get_level_values(1),
        org_indeces["n"]["n"],
    ]

    # finding last level index (defined for Sector,Activity,Commodity)
    if "s" in org_indeces:
        last_index = org_indeces["s"]["s"]

    else:
        reverse_MI = {value: key for key, value in _MASTER_INDEX.items()}

        items = delete_duplicates(instance.Y.index.get_level_values(1))

        last_index = org_indeces[reverse_MI[items[0]]][reverse_MI[items[0]]].tolist()
        last_index.extend(
            org_indeces[reverse_MI[items[1]]][reverse_MI[items[1]]].tolist()
        )

    Y_index = V_columns = E_columns = Z_index = Z_columns = [
        org_indeces["r"]["s"],
        getattr(instance, _ENUM.Y).index.get_level_values(1),
        last_index,
    ]

    for scenario, values in instance:
        matrices[scenario] = {}

        for matrix in [_ENUM.Z, _ENUM.E, _ENUM.V, _ENUM.EY, _ENUM.Y]:
            item = deepcopy(values[matrix])

            for level in ["index", "columns"]:
                setattr(item, level, eval(f"{_ENUM.reverse(matrix)}_{level}"))

                if isinstance(getattr(item, level), pd.MultiIndex):
                    item = item.groupby(
                        axis=0 if level == "index" else 1,
                        level=[0, 1, 2],
                        sort=False,
                    ).sum()
                else:
                    item = item.groupby(
                        axis=0 if level == "index" else 1,
                        level=[0],
                        sort=False,
                    ).sum()

                if (
                    level == "index"
                    and matrix in [_ENUM.E, _ENUM.EY]
                    and drop is not None
                ):
                    try:
                        item = item.drop(drop, axis=0)
                        log_time(
                            logger,
                            "{} removed from {}.".format(drop, _MASTER_INDEX["k"]),
                            "info",
                        )
                    except KeyError:
                        log_time(
                            logger,
                            "{} does not found in {} and can not be removed.".format(
                                drop, _MASTER_INDEX["k"]
                            ),
                            "warning",
                        )

            matrices[scenario][matrix] = item

        matrices[scenario][_ENUM.X] = calc_X(
            matrices[scenario][_ENUM.Z], matrices[scenario][_ENUM.Y]
        )

        log_time(logger, f"Aggregation: scenario: `{scenario}` aggregated.")

    # Refixing the index/columns names
    for ss in matrices:
        rename_index(matrices[ss])

    return matrices, units


def unit_aggregation_check(instance, drop):
    """
    This function checks if two items with diffrerent units are not being aggregated
    """

    if isinstance(drop, str):
        drop = [drop]

    units = copy.deepcopy(instance.units)
    new_units = {}

    indeces = copy.deepcopy(instance.get_index("all", "aggregated"))
    for item in [*units]:
        aggregation = indeces.get(item)
        if aggregation is not None:
            aggregation.reset_index(level=0, inplace=True)
            aggregation = aggregation.set_index("Aggregation")

            aggregation.columns = ["values"]

            aggregated = aggregation.index.unique()

            _new_units = {}
            # make a loop over the new items

            for index in aggregated:
                if index in drop:
                    continue

                match = list(aggregation.loc[index, :].values.flatten())

                take_units = delete_duplicates(
                    units[item].loc[match, "unit"].values.flatten()
                )

                if len(take_units) > 1:
                    raise WrongInput(
                        "Aggregation of items with different units are not allowed for {}.(check aggregation of {})".format(
                            item, index
                        )
                    )
                # if everything is fine, store the units.
                _new_units[index] = take_units[0]

            # finally make a new dataframe of indeces for the given item
            _new_units = pd.DataFrame.from_dict(
                _new_units, orient="index", columns=["unit"]
            )

            # update the dictionary of units
            new_units[item] = _new_units

        else:
            new_units[item] = units[item]

    return new_units
