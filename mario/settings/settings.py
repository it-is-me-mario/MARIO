"""Load, validate and override MARIO settings."""

import copy
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

CANONICAL_INDEX = {
    "r": "Region",
    "a": "Activity",
    "c": "Commodity",
    "s": "Sector",
    "k": "Satellite account",
    "f": "Factor of production",
    "n": "Consumption category",
}

DEFAULT_INDEX_ALIASES = {
    "r": ["region", "regions", "country", "countries"],
    "a": ["activity", "activities"],
    "c": ["commodity", "commodities", "product", "products"],
    "s": ["sector", "sectors", "industry", "industries"],
    "k": ["satellite account", "satellite accounts", "extension", "extensions"],
    "f": ["factor of production", "factors of production", "value added"],
    "n": [
        "consumption category",
        "consumption categories",
        "final demand",
        "final demand category",
        "final demand categories",
    ],
}

DEFAULT_NOMENCLATURE = {
    "e": "e",
    "E": "E",
    "X": "X",
    "EY": "EY",
    "VY": "VY",
    "Y": "Y",
    "y": "y",
    "V": "V",
    "v": "v",
    "F": "F",
    "f": "f",
    "M": "M",
    "m": "m",
    "b": "b",
    "g": "g",
    "w": "w",
    "p": "p",
    "z": "z",
    "Z": "Z",
    "u": "u",
    "U": "U",
    "s": "s",
    "S": "S",
}

DEFAULT_COMPUTE = {
    "compute_method": "auto",
    "linear_solver": "scipy",
    "linear_strategy": "auto",
    "auto_w_memory_fraction": 0.25,
    "auto_w_overhead_factor": 3.0,
}


def _as_alias_list(value):
    """Return one alias payload as a flat list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _normalize_index_aliases(raw_aliases=None, legacy_index=None):
    """Merge built-in aliases with user aliases and legacy index renames."""
    aliases = {code: list(values) for code, values in DEFAULT_INDEX_ALIASES.items()}

    for code, value in (legacy_index or {}).items():
        if code in CANONICAL_INDEX and value != CANONICAL_INDEX[code]:
            aliases.setdefault(code, []).extend(_as_alias_list(value))

    for code, values in (raw_aliases or {}).items():
        if code in CANONICAL_INDEX:
            aliases.setdefault(code, []).extend(_as_alias_list(values))

    for code, values in aliases.items():
        deduped = []
        seen = set()
        for alias in values:
            token = str(alias).strip()
            if not token:
                continue
            marker = token.casefold()
            if marker not in seen:
                seen.add(marker)
                deduped.append(token)
        aliases[code] = deduped

    return aliases


def _default_settings_payload():
    """Return the built-in MARIO settings payload."""
    return {
        "index": copy.deepcopy(CANONICAL_INDEX),
        "index_aliases": copy.deepcopy(DEFAULT_INDEX_ALIASES),
        "nomenclature": copy.deepcopy(DEFAULT_NOMENCLATURE),
        "compute": copy.deepcopy(DEFAULT_COMPUTE),
    }


def _normalize_settings_payload(raw_settings):
    """Return a settings payload with canonical index labels and explicit aliases."""
    settings = copy.deepcopy(raw_settings or {})
    if not isinstance(settings, dict):
        settings = {}

    normalized = _default_settings_payload()
    if isinstance(settings.get("nomenclature"), dict):
        normalized["nomenclature"].update(settings["nomenclature"])
    if isinstance(settings.get("compute"), dict):
        normalized["compute"].update(settings["compute"])
    normalized["index_aliases"] = _normalize_index_aliases(
        raw_aliases=settings.get("index_aliases"),
        legacy_index=settings.get("index"),
    )
    return normalized


def _load_settings_file(path_to_yaml):
    """Read and normalize one settings YAML file."""
    with open(path_to_yaml, "r") as yml_file:
        file = yaml.safe_load(yml_file)
    return _normalize_settings_payload(file)


class Setting:
    """Base wrapper around a validated settings section."""

    def __init__(self):
        """Load and validate the configured subsection for this settings object."""
        self.setting = self._validate_dict(self.key, self.vars)
        self._check_duplicates()

    def _read_yaml(self, path):
        """Read a YAML file from disk and return its parsed object."""
        return _load_settings_file(path)

    def _validate_dict(self, key, vars):
        """Load the requested settings section, falling back to packaged defaults."""
        try:
            setting = self._read_yaml(f"{path}/settings.yaml")
        except Exception:
            log_time(
                logger=logger,
                level="warning",
                comment=f"The user settings could not be read for {key}, so the packaged MARIO defaults are used.",
            )
            return _default_settings_payload()[key]

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
            comment=f"The user settings is not correctly built for {key}, so the packaged MARIO defaults are used.",
        )

        return _default_settings_payload()[key]

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


class IndexAliases(Setting):
    """Expose the configured set-name aliases accepted by MARIO."""

    def __init__(self):
        """Load the configured set alias lists."""
        self.vars = list("racskfn")
        self.key = "index_aliases"
        super().__init__()

    def _check_duplicates(self):
        """Alias lists are validated elsewhere and may contain overlapping values."""
        return None


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


class Compute(Setting):
    """Expose runtime compute defaults used by MARIO numerical backends."""

    def __init__(self):
        """Load the configured compute defaults."""
        self.vars = [
            "compute_method",
            "linear_solver",
            "linear_strategy",
            "auto_w_memory_fraction",
            "auto_w_overhead_factor",
        ]
        self.key = "compute"
        super().__init__()

    def _check_duplicates(self):
        """Allow repeated scalar defaults such as ``auto`` across compute keys."""
        return None


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
        normalized = _load_settings_file(f"{path}/settings.yaml")
        with open(f"{destination_path}/settings.yaml", "w") as yaml_file:
            yaml.dump(normalized, yaml_file, default_flow_style=False, sort_keys=False)

    return _load_settings_file(f"{path}/settings.yaml")


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
        with open(source, "r") as yaml_file:
            payload = yaml.safe_load(yaml_file)

    elif isinstance(source, dict):
        payload = source

    else:
        raise WrongFormat("Only dict or a yaml file directory can be passed")

    payload = _normalize_settings_payload(payload)

    with open(f"{path}/settings.yaml", "w") as yaml_file:
        yaml.dump(payload, yaml_file, default_flow_style=False, sort_keys=False)

    import mario.model.conventions as conventions
    import mario.model.labels as labels

    importlib.reload(conventions)
    importlib.reload(labels)


def reset_settings():
    """Restore the packaged default settings."""
    upload_settings(_default_settings_payload())


def set_compute_method(method: str):
    """Set the default runtime method used for demand-driven IOT/SUT calculations.

    Parameters
    ----------
    method:
        One of ``"auto"``, ``"inverse"`` or ``"solve"``.

        - ``"auto"`` lets MARIO choose between explicit-inverse and
          solve-based formulas according to the requested target and the
          estimated memory cost of materializing the Leontief inverse.
        - ``"inverse"`` forces the historical path based on the explicit
          Leontief inverse ``w = (I - z)^-1``.
        - ``"solve"`` prefers linear-system solves that avoid materializing
          explicit inverse blocks for large demand-driven targets such as IOT
          ``X``, ``f``, ``F``, ``m``, ``M``, ``p`` and the analogous split SUT
          targets.

    Notes
    -----
    This setting is used whenever no per-call override is passed to
    :meth:`mario.CoreModel.calc_all`, :meth:`mario.CoreModel.resolve` or
    :meth:`mario.CoreModel.resolve_many`. Dotted access such as ``db.f`` also
    goes through this default because it delegates to ``calc_all()`` without
    explicit overrides.
    """
    from mario.compute.runtime import normalize_compute_method

    settings = download_settings(None)
    settings.setdefault("compute", {})
    settings["compute"]["compute_method"] = normalize_compute_method(method)
    upload_settings(settings)


def set_linear_solver(solver: str):
    """Set the default backend used by solve-based demand-driven formulas.

    Parameters
    ----------
    solver:
        Linear solver backend name. The currently supported value is
        ``"scipy"``.

    Notes
    -----
    This setting only affects solve-based IOT/SUT formulas. It has no effect
    on the explicit-inverse path used to build ``w``/``wcc``/``waa`` directly.
    """
    from mario.compute.runtime import normalize_linear_solver

    settings = download_settings(None)
    settings.setdefault("compute", {})
    settings["compute"]["linear_solver"] = normalize_linear_solver(solver)
    upload_settings(settings)


def set_linear_strategy(strategy: str):
    """Set how MARIO should solve sparse linear systems under ``compute_method='solve'``.

    Parameters
    ----------
    strategy:
        One of ``"auto"``, ``"direct"`` or ``"iterative"``.

        - ``"auto"`` chooses between sparse direct factorization and iterative
          Krylov solves based on matrix size and number of right-hand sides.
        - ``"direct"`` forces sparse direct factorization.
        - ``"iterative"`` forces iterative sparse solves.

    Notes
    -----
    This setting only affects formulas that already run through the
    solve-based path. It does not change the higher-level choice between
    explicit-inverse and solve-based formulas, which is controlled by
    :func:`mario.set_compute_method`.
    """
    from mario.compute.runtime import normalize_linear_strategy

    settings = download_settings(None)
    settings.setdefault("compute", {})
    settings["compute"]["linear_strategy"] = normalize_linear_strategy(strategy)
    upload_settings(settings)
