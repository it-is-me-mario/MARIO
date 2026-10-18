"""Load, validate and override MARIO settings."""

import copy
import yaml
import math
import os
from numbers import Real
from types import MappingProxyType
from mario.log_exc.exceptions import WrongFormat

path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
    )
)

_ACTIVE_SETTINGS = None

CANONICAL_INDEX = {
    "r": "Region",
    "a": "Activity",
    "c": "Commodity",
    "s": "Sector",
    "k": "Satellite account",
    "f": "Factor of production",
    "n": "Consumption category",
}

FALLBACK_INDEX_ALIASES = {
    "r": ["region", "regions", "country", "countries"],
    "a": ["activity", "activities", "activitiy", "industry", "industries"],
    "c": ["commodity", "commodities", "product", "products"],
    "s": ["sector", "sectors", "industry", "industries"],
    "k": [
        "satellite",
        "satellites",
        "satellite account",
        "satellite accounts",
        "satellite_accounts",
        "extension",
        "extensions",
    ],
    "f": [
        "factor",
        "factors",
        "factor of production",
        "factors of production",
        "factor_of_production",
        "factors_of_production",
        "value added",
    ],
    "n": [
        "consumption category",
        "consumption categories",
        "consumption_category",
        "consumption_categories",
        "demand categories",
        "demand_categories",
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
    "bu": "bu",
    "bs": "bs",
    "g": "g",
    "gcc": "gcc",
    "gca": "gca",
    "gac": "gac",
    "gaa": "gaa",
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
    "compute_method": "inverse",
    "linear_solver": "scipy",
    "linear_strategy": "auto",
    "auto_w_memory_fraction": 0.25,
    "auto_w_overhead_factor": 3.0,
}

COMPUTE_METHODS = {"auto", "inverse", "solve"}
LINEAR_SOLVERS = {"scipy"}
LINEAR_STRATEGIES = {"auto", "direct", "iterative"}


def _as_alias_list(value):
    """Return one alias payload as a flat list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _default_index_aliases():
    """Return the built-in set aliases for the public API."""
    return {code: list(values) for code, values in FALLBACK_INDEX_ALIASES.items()}


def _normalize_index_aliases(raw_aliases=None, legacy_index=None):
    """Merge built-in aliases with user aliases and legacy index renames."""
    aliases = _default_index_aliases()

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
        "index_aliases": _normalize_index_aliases(),
        "nomenclature": copy.deepcopy(DEFAULT_NOMENCLATURE),
        "compute": copy.deepcopy(DEFAULT_COMPUTE),
    }


def _reserved_matrix_names():
    """Return built-in matrix names that cannot be reused as aliases."""
    from mario.compute.catalog import available_matrix_names

    reserved = set()
    for table in ("IOT", "SUT"):
        reserved.update(available_matrix_names(table))
    return reserved


def _validate_nomenclature_payload(nomenclature):
    """Reject empty, duplicate or reserved matrix labels in settings."""
    reserved_names = _reserved_matrix_names()
    seen = {}

    for canonical, configured in nomenclature.items():
        if not isinstance(configured, str):
            raise WrongFormat(f"The nomenclature label for {canonical!r} must be a string.")
        token = configured.strip()

        if not token:
            raise WrongFormat(
                f"The nomenclature label for {canonical!r} cannot be empty."
            )

        if token in reserved_names and token != canonical:
            raise WrongFormat(
                f"The nomenclature label {token!r} for {canonical!r} is blocked because "
                f"{token!r} is already a reserved built-in matrix name."
            )

        if token in seen and seen[token] != canonical:
            raise WrongFormat(
                f"The nomenclature label {token!r} is already assigned to {seen[token]!r}; "
                f"matrix names must remain unique."
            )

        seen[token] = canonical
        nomenclature[canonical] = token


def _validate_compute_payload(compute):
    """Validate session defaults before replacing any active settings."""
    for key, choices in (
        ("compute_method", COMPUTE_METHODS),
        ("linear_solver", LINEAR_SOLVERS),
        ("linear_strategy", LINEAR_STRATEGIES),
    ):
        value = compute[key]
        if not isinstance(value, str) or value.strip().lower() not in choices:
            raise WrongFormat(f"Invalid {key}: {value!r}. Expected one of {sorted(choices)}.")
        compute[key] = value.strip().lower()
    for key in ("auto_w_memory_fraction", "auto_w_overhead_factor"):
        value = compute[key]
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
            raise WrongFormat(f"{key} must be a finite positive number.")
        if key == "auto_w_memory_fraction" and value > 1:
            raise WrongFormat("auto_w_memory_fraction must be at most 1.")
        compute[key] = float(value)


def _normalize_settings_payload(raw_settings):
    """Return a settings payload with canonical index labels and explicit aliases."""
    settings = copy.deepcopy(raw_settings)
    if not isinstance(settings, dict):
        raise WrongFormat("Settings must be a dictionary of configuration sections.")

    normalized = _default_settings_payload()
    for section, values in settings.items():
        if section not in normalized:
            raise WrongFormat(f"Unknown settings section: {section!r}.")
        if not isinstance(values, dict):
            raise WrongFormat(f"Settings section {section!r} must be a dictionary.")
        unknown = set(values).difference(normalized[section])
        if unknown:
            raise WrongFormat(f"Unknown keys in {section!r}: {sorted(unknown, key=str)}.")
    for section in ("index", "index_aliases"):
        for code, values in settings.get(section, {}).items():
            aliases = [values] if isinstance(values, str) else values
            if not isinstance(aliases, (list, tuple)) or any(
                not isinstance(value, str) or not value.strip() for value in aliases
            ):
                raise WrongFormat(f"{section}.{code} must contain nonempty string aliases.")
    if "nomenclature" in settings:
        normalized["nomenclature"].update(settings["nomenclature"])
    _validate_nomenclature_payload(normalized["nomenclature"])
    if "compute" in settings:
        normalized["compute"].update(settings["compute"])
    _validate_compute_payload(normalized["compute"])
    normalized["index_aliases"] = _normalize_index_aliases(
        raw_aliases=settings.get("index_aliases"),
        legacy_index=settings.get("index"),
    )
    return normalized


def _active_settings():
    """Return process-local settings, starting from built-in defaults."""
    global _ACTIVE_SETTINGS
    if _ACTIVE_SETTINGS is None:
        _ACTIVE_SETTINGS = _default_settings_payload()
    return _ACTIVE_SETTINGS


def canonical_matrix_name(name):
    """Translate a public alias at the API boundary; canonical IDs stay valid."""
    if name in DEFAULT_NOMENCLATURE:
        return name
    for canonical, alias in _active_settings()["nomenclature"].items():
        if name == alias:
            return canonical
    return name


def public_matrix_name(name):
    """Return the current display alias without changing stored matrix keys."""
    canonical = canonical_matrix_name(name)
    return _active_settings()["nomenclature"].get(canonical, canonical)


class Setting:
    """Base wrapper around a validated settings section."""

    def __init__(self):
        """Load and validate the configured subsection for this settings object."""
        self.setting = self._validate_dict(self.key, self.vars)
        self._check_duplicates()

    def _validate_dict(self, key, vars):
        """Return a snapshot of an already validated session settings section."""
        return copy.deepcopy(_active_settings()[key])

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
            "bu",
            "bs",
            "g",
            "gcc",
            "gca",
            "gac",
            "gaa",
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


class CanonicalNomenclature(Nomenclature):
    """Immutable internal matrix IDs, independent of public session aliases."""

    def __init__(self):
        self.key = "nomenclature"
        self.setting = MappingProxyType(DEFAULT_NOMENCLATURE.copy())


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
    """Return a copy of the current session settings, optionally exporting YAML.

    Parameters
    -----------
    destination_path : str,None
        if a directory path given, will download the config yaml file, if None, will only return a dict

    Returns
    -------
    dict
        config dict
    """

    settings = copy.deepcopy(_active_settings())
    if destination_path is not None:
        with open(os.path.join(destination_path, "settings.yaml"), "w") as yaml_file:
            yaml.safe_dump(settings, yaml_file, default_flow_style=False, sort_keys=False)
    return settings


def upload_settings(source):
    """Replace settings for this Python process without modifying the package.

    Settings are shared by databases in the current process. New processes
    start with built-in defaults. Export with :func:`download_settings` and
    explicitly upload that YAML file to reuse settings in another session.
    Matrix aliases can change after loading a database: stored matrix IDs
    remain canonical and their data is not renamed or rewritten.

    Parameteres
    -----------
    source : str,dict
        the path to the custom yaml file or the config dict should be passed
    """

    global _ACTIVE_SETTINGS
    if isinstance(source, os.PathLike):
        source = os.fspath(source)
    if isinstance(source, str):
        if not source.endswith(".yaml"):
            raise WrongFormat("only yaml file is acceptable.")
        with open(source, "r") as yaml_file:
            payload = yaml.safe_load(yaml_file)

    elif isinstance(source, dict):
        payload = source

    else:
        raise WrongFormat("Only dict or a yaml file directory can be passed")

    _ACTIVE_SETTINGS = _normalize_settings_payload(payload)


def reset_settings():
    """Restore built-in defaults in this session, leaving stored matrices intact."""
    upload_settings(_default_settings_payload())


def set_compute_method(method: str):
    """Set the default runtime method used for demand-driven IOT/SUT calculations.

    Parameters
    ----------
    method:
        One of ``"auto"``, ``"inverse"`` or ``"solve"``.

        - ``"auto"`` lets MARIO choose between explicit-inverse and
          solve-based formulas according to the requested target and the
          estimated memory cost of materializing the ``w`` Leontief inverse
          matrix.
        - ``"inverse"`` forces the historical path based on the explicit ``w``
          Leontief inverse matrix.
        - ``"solve"`` prefers linear-system solves that avoid materializing
          explicit inverse blocks for large demand-driven targets such as the
          IOT ``X`` total production vector, ``f`` total (direct+indirect)
          environmental transaction coefficients matrix, ``F`` total
          (direct+indirect) environmental transaction flows matrix, ``m`` total
          (direct+indirect) value added coefficients matrix, ``M`` total
          (direct+indirect) value added transaction matrix, ``p`` price index
          vector and the analogous split SUT targets.

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
    on the explicit-inverse path used to build the ``w``/``wcc``/``waa``
    Leontief inverse matrices directly.
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
