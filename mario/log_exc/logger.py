# -*- coding: utf-8 -*-
"""
Created on Fri Nov 20 11:44:48 2020

@author: Mario team

the log fucntion are taken from calliope code @ https://github.com/calliope-project/calliope
"""
import logging
import datetime
import sys

_time_format = "%Y-%m-%d %H:%M:%S"


def setup_root_logger(verbosity, capture_warnings):
    root_logger = logging.getLogger()

    # Removing all the existing handlers
    if root_logger.hasHandlers():
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    # Defining the formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s: %(message)s", datefmt=_time_format
    )

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(formatter)
    root_logger.addHandler(console)
    root_logger.setLevel(verbosity.upper())

    if capture_warnings:
        logging.captureWarnings(True)
        pywarning_logger = logging.getLogger("py.warnings")
        pywarning_logger.setLevel(verbosity.upper())

    return root_logger


def log_time(logger, comment, level="info"):
    getattr(logger, level)(comment)


def set_log_verbosity(verbosity="info", capture_warnings=True):
    """Sets the formatted logging level

    Parameters
    ----------
    verbosity : str
        defines the level of logging such as [debug,info,warning,critical]

    capture_warnings : boolean
        if True, will capture the warnings even if the verbosity level is lower than warning
    """

    if verbosity.upper() == "WARN":
        verbosity = "WARNING"
    backend_logger = logging.getLogger("mario.core.AttrData")
    backend_logger.setLevel(verbosity.upper())
    setup_root_logger(verbosity=verbosity, capture_warnings=capture_warnings)
