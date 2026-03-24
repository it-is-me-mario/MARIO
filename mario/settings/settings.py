"""Load, validate and override MARIO settings."""

import yaml
from mario.log_exc.logger import log_time
import logging
import os
import shutil
from mario.log_exc.exceptions import WrongFormat
import importlib

logger = logging.getLogger(__name__)
path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
    )
)


class Setting:
    """Base wrapper around a validated settings section."""

    def __init__(self):
        """Load and validate the configured subsection for this settings object."""
        self.setting = self._validate_dict(self.key, self.vars)
        self._check_duplicates()

    def _read_yaml(self, path):
        """Read a YAML file from disk and return its parsed object."""
        with open(path, "r") as yml_file:
            file = yaml.safe_load(yml_file)

        return file

    def _validate_dict(self, key, vars):
        """Load the requested settings section, falling back to packaged defaults."""
        setting = self._read_yaml(f"{path}/settings.yaml")

        correct_setting = True
        if key in setting:
            setting = setting[key]

            setting_vars = [*setting]

            if set(setting_vars) != set(vars):
                correct_setting = False

        else:
            correct_setting = False

        if correct_setting:
            return setting

        log_time(
            logger=logger,
            level="warning",
            comment=f"The user settings is not correctly build for {key}, so the original mario settings are used.",
        )

        setting = self._read_yaml(f"{path}/original_settings.yaml")

        return setting[key]

    def __getitem__(self, var):
        """Return one configured value by key."""
        return self.setting[var]

    def __getattr__(self, attr):
        """Expose configured values as attributes as well as mapping entries."""
        if attr in self.__dict__:
            return self.__dict__[attr]

        else:
            if attr in self.setting:
                return self.setting[attr]
            else:
                raise AttributeError(attr)

    def items(self):
        """Return the underlying key-value pairs."""
        return self.setting.items()

    def _check_duplicates(self):
        """Reject settings sections that map multiple keys to the same value."""
        vars = list(self.setting.values())

        if len(vars) != len(set(vars)):
            raise ValueError(f"Settings for {self.key} has duplicate values.")

    def __getstate__(self):
        """Return the instance state for pickle serialization."""
        return self.__dict__

    def __setstate__(self, value):
        """Restore the instance state after pickle deserialization."""
        self.__dict__ = value

    def reverse(self, var):
        """Return the configuration key that maps to ``var``."""
        for k, v in self.setting.items():
            if var == v:
                return k

        raise KeyError(f"{var} does not exist.")


class Index(Setting):
    """Expose the configured short codes for MARIO index levels."""

    def __init__(self):
        """Load the configured index-level short codes."""
        self.vars = list("racskfn")
        self.key = "index"
        super().__init__()


class Nomenclature(Setting):
    """Expose the configured matrix names used across MARIO."""

    def __init__(self):
        """Load the configured matrix nomenclature used by the public API."""
        self.vars = [
            "e",
            "E",
            "X",
            "EY",
            "VY",
            "Y",
            "y",
            "V",
            "v",
            "F",
            "f",
            "M",
            "m",
            "b",
            "g",
            "w",
            "p",
            "z",
            "Z",
            "u",
            "U",
            "s",
            "S",
        ]
        self.key = "nomenclature"
        super().__init__()


def download_settings(destination_path=None):
    """Return the current MARIO settings dictionary.

    Parameters
    -----------
    destination_path : str,None
        if a directory path given, will download the config yaml file, if None, will only return a dict

    Returns
    -------
    dict
        config dict
    """

    if destination_path is not None:
        shutil.copyfile(
            src=f"{path}/settings.yaml", dst=f"{destination_path}/settings.yaml"
        )

    with open(f"{path}/settings.yaml", "r") as yml_file:
        file = yaml.safe_load(yml_file)

    return file


def upload_settings(source):
    """Replace the active MARIO settings with a custom configuration.

    Parameteres
    -----------
    source : str,dict
        the path to the custom yaml file or the config dict should be passed
    """

    if isinstance(source, str):
        if not source.endswith(".yaml"):
            raise WrongFormat("only yaml file is acceptable.")
        shutil.copyfile(src=source, dst=f"{path}/settings.yaml")

    elif isinstance(source, dict):
        with open(f"{path}/settings.yaml", "w") as yaml_file:
            yaml.dump(source, yaml_file, default_flow_style=False)

    else:
        raise WrongFormat("Only dict or a yaml file directory can be passed")

    import mario.model.conventions as conventions

    importlib.reload(conventions)


def reset_settings():
    """Restore the packaged default settings."""

    with open(f"{path}/original_settings.yaml", "r") as yml_file:
        file = yaml.safe_load(yml_file)

    upload_settings(file)
