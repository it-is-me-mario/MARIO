# -*- coding: utf-8 -*-
"""
metadata for traking all the processes that user may follow using MARIO
"""

from datetime import datetime
import pickle
from mario.log_exc.exceptions import WrongInput
from mario.tools.constants import _LEVELS

import json


class MARIOMetaData:

    """
    Organizes the MARIO Metadata.

    An instanc should not be built directly by the user.

    While, any class that is initialzed, a metadata will be built or will be passed
    to the class and will be updated continuesly.

    """

    def __init__(self, name=None, meta=None, **kwargs):
        """
        Initializng the metadata with any given sets of inputs or a given metafile
        """

        # if no metadata file is not given
        if meta is None:
            # _history is a free list, that appends the history when ever it is needed.
            self._history = []

            self.name = name

            # Adding the attributes
            for attribute, value in kwargs.items():
                self._add_attribute(attribute, value)

        # if a metadata file is given
        else:
            meta = self.load(meta)
            for att, value in meta.__dict__.items():
                setattr(self, att, value)

            self._add_history("metadata file uploaded from {}".format(meta))

    def _add_attribute(self, **kwargs):
        for attribute, value in kwargs.items():
            # if the attribute already exists
            if hasattr(self, attribute):
                # if the existed attribuute has the same value pass
                if getattr(self, attribute) == value:
                    pass
                else:
                    # otherwise, delete the attribute and update it to the new value
                    self._add_history(
                        "{} updated from {} to {}.".format(
                            attribute, getattr(self, attribute), value
                        )
                    )
                    delattr(self, attribute)
            else:
                self._add_history(
                    "{} added into metadata with value equal to {}.".format(
                        attribute.title(), value
                    )
                )

            setattr(self, attribute, value)

    def _add_history(self, note):
        """
        Adds a history or note to the _history attribute to track all the events
        in the instances build by the user.
        """
        self._history.append("[{}]    {}".format(self._time(), note))

    def _time(self):
        """
        returns the current time
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        history_lines_2_show = 15

        history = "\n".join(self._history[:history_lines_2_show])

        if history_lines_2_show < len(self._history):
            history = (
                history
                + "\n ... (more lines in history. To access, use .meta._history)"
            )

        return history

    def __repr__(self):
        return self.__str__()

    def _save(self, location, _format="binary"):
        """
        this function will save the metadata with a database so if the database
        wants to imported with its own metadata in order not to build the metadat again,
        this can be used.
        """
        if _format == "binary":
            with open(location, "wb") as config_dictionary_file:
                pickle.dump(self, config_dictionary_file)

        elif _format == "txt":
            with open("{}.txt".format(location), "w") as f:
                for item in self._history:
                    f.write("{}\n".format(item))

        elif _format == "json":
            meta = self._to_dict()
            with open(f"{location}.json", "w") as fp:
                json.dump(meta, fp)

    def _to_dict(self):
        meta_as_dict = {}

        for attr in ["price", "name", "year", "source"]:
            try:
                meta_as_dict[attr] = getattr(self, attr)
            except AttributeError:
                pass

        meta_as_dict["history"] = self._history

        return meta_as_dict

    def load(self, location):
        with open(location, "rb") as load_file:
            meta = pickle.load(load_file)

        return meta

    def meta_check(self, **kwargs):
        """
        This fucntion can be used in case that an object of a database is build
        based on a metadata file to check if the given info are not in contrast
        with the meta data.
        """
        warnings = []
        contrast = False

        for kwarg, value in kwargs.items():
            if hasattr(self, kwarg) and getattr(self, kwarg) != value:
                contrast = True
                warnings.append(
                    "{} given in the function (equal to {}) is in contrast with "
                    "imported metafile (equal to {})".format(
                        kwarg, value, getattr(self, kwarg)
                    )
                )

        return contrast, warnings

    @property
    def table(self):
        return self.__table

    @table.setter
    def table(self, var):
        if var not in [*_LEVELS]:
            raise WrongInput("table can be: {}".format(*_LEVELS))

        self.__table = var
