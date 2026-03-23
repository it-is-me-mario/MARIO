# -*- coding: utf-8 -*-
"""Metadata container used by the public ``Database`` API."""

from datetime import datetime
import pickle
import json

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import TABLE_LEVELS


class MARIOMetaData:
    """Store metadata and history entries for MARIO database objects."""

    def __init__(self, name=None, meta=None, **kwargs):
        """Initialize metadata from explicit values or an existing metadata file."""
        if meta is None:
            self._history = []
            self.name = name

            for attribute, value in kwargs.items():
                self._add_attribute(attribute, value)
        else:
            meta = self.load(meta)
            for att, value in meta.__dict__.items():
                setattr(self, att, value)

            self._add_history("metadata file uploaded from {}".format(meta))

    def _add_attribute(self, **kwargs):
        for attribute, value in kwargs.items():
            if hasattr(self, attribute):
                if getattr(self, attribute) != value:
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
        """Append a time-stamped note to the metadata history."""
        self._history.append("[{}]    {}".format(self._time(), note))

    def _time(self):
        """Return the current timestamp string used in metadata history."""
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
        """Serialize metadata to disk in binary, text or JSON format."""
        if _format == "binary":
            with open(location, "wb") as config_dictionary_file:
                pickle.dump(self, config_dictionary_file)

        elif _format == "txt":
            with open("{}.txt".format(location), "w") as file_obj:
                for item in self._history:
                    file_obj.write("{}\n".format(item))

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
        """Check whether explicit metadata values conflict with stored metadata."""
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
        if var not in [*TABLE_LEVELS]:
            raise WrongInput("table can be: {}".format(*TABLE_LEVELS))

        self.__table = var
