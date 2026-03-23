# -*- coding: utf-8 -*-
"""Logging helpers for MARIO."""
import logging
import sys
import warnings

try:
    from pandas.errors import PerformanceWarning as PandasPerformanceWarning
except Exception:  # pragma: no cover - pandas is a hard dependency, this is just defensive
    PandasPerformanceWarning = Warning

_MARIO_LOGGER = "mario"
_LOG_FORMAT = "%(levelname)s %(message)s"
_DEPENDENCY_LOGGERS = (
    "asyncio",
    "fontTools",
    "matplotlib",
    "numexpr",
    "openpyxl",
    "pandas",
    "PIL",
    "plotly",
    "pymrio",
    "requests",
    "urllib3",
)
_DEPENDENCY_WARNING_FILTERS = (
    {
        "action": "ignore",
        "category": DeprecationWarning,
        "module": r"openpyxl\..*",
    },
    {
        "action": "ignore",
        "category": FutureWarning,
        "module": r"pandas\..*",
    },
    {
        "action": "ignore",
        "category": FutureWarning,
        "module": r"pymrio\..*",
    },
    {
        "action": "ignore",
        "category": UserWarning,
        "message": r"Data Validation extension is not supported and will be removed",
    },
    {
        "action": "ignore",
        "category": DeprecationWarning,
        "message": r".*datetime\.datetime\.utcnow\(\) is deprecated.*",
        "module": r"openpyxl\..*",
    },
    {
        "action": "ignore",
        "category": FutureWarning,
        "message": r"The 'axis' keyword in DataFrame\.groupby is deprecated.*",
    },
    {
        "action": "ignore",
        "category": FutureWarning,
        "message": r"DataFrame\.groupby with axis=1 is deprecated.*",
    },
    {
        "action": "ignore",
        "category": PandasPerformanceWarning,
    },
)

_library_logger = logging.getLogger(_MARIO_LOGGER)
if not any(isinstance(handler, logging.NullHandler) for handler in _library_logger.handlers):
    _library_logger.addHandler(logging.NullHandler())


def _clear_handlers(logger):
    """Remove all handlers from a logger before reconfiguration."""
    for handler in list(logger.handlers):
        logger.removeHandler(handler)


def _configure_dependency_logging(include_dependency_logs: bool) -> None:
    """Mute or re-enable selected third-party library loggers."""
    level = logging.NOTSET if include_dependency_logs else logging.CRITICAL
    for name in _DEPENDENCY_LOGGERS:
        dependency_logger = logging.getLogger(name)
        _clear_handlers(dependency_logger)
        dependency_logger.setLevel(level)
        dependency_logger.propagate = include_dependency_logs
        if not include_dependency_logs:
            dependency_logger.addHandler(logging.NullHandler())


def _configure_dependency_warnings(include_dependency_logs: bool) -> None:
    """Apply warning filters for noisy dependencies when requested."""
    if include_dependency_logs:
        return

    for rule in _DEPENDENCY_WARNING_FILTERS:
        warnings.filterwarnings(**rule)


def suppress_dependency_warnings(include_dependency_logs: bool = False) -> None:
    """Apply MARIO's default warning suppression without configuring logging.

    This keeps the package quiet even when users import and use MARIO without
    ever calling ``set_log_verbosity(...)``.
    """
    _configure_dependency_warnings(include_dependency_logs=include_dependency_logs)


def setup_root_logger(verbosity, capture_warnings, include_dependency_logs=False):
    """Configure MARIO logging and dependency-noise suppression."""
    root_logger = logging.getLogger()
    mario_logger = logging.getLogger(_MARIO_LOGGER)

    _clear_handlers(root_logger)
    _clear_handlers(mario_logger)

    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    mario_logger.addHandler(console)
    mario_logger.setLevel(verbosity.upper())
    mario_logger.propagate = False

    root_logger.setLevel(logging.CRITICAL)
    _configure_dependency_logging(include_dependency_logs=include_dependency_logs)
    _configure_dependency_warnings(include_dependency_logs=include_dependency_logs)

    if capture_warnings:
        logging.captureWarnings(True)
        pywarning_logger = logging.getLogger("py.warnings")
        _clear_handlers(pywarning_logger)
        pywarning_logger.setLevel(logging.WARNING if include_dependency_logs else logging.CRITICAL)
        pywarning_logger.propagate = include_dependency_logs
        if not include_dependency_logs:
            pywarning_logger.addHandler(logging.NullHandler())
    else:
        logging.captureWarnings(False)

    return mario_logger


def log_time(logger, comment, level="info"):
    """Log one message using a dynamic standard logging level name."""
    getattr(logger, level)(comment)


def set_log_verbosity(
    verbosity="info",
    capture_warnings=False,
    include_dependency_logs=False,
):
    """Configure MARIO logging verbosity and warning capture.

    Parameters
    ----------
    verbosity : str
        defines the level of logging such as [debug,info,warning,critical]

    capture_warnings : boolean
        if True, will capture the warnings even if the verbosity level is lower than warning

    include_dependency_logs : boolean
        if True, allows logs and captured warnings coming from external dependencies
    """

    if verbosity.upper() == "WARN":
        verbosity = "WARNING"
    setup_root_logger(
        verbosity=verbosity,
        capture_warnings=capture_warnings,
        include_dependency_logs=include_dependency_logs,
    )


suppress_dependency_warnings()
