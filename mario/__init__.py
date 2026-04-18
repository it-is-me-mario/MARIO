"""
MARIO: Multifunctional Analysis of Regions through Input-Output
A python package for automating input-output (IO) calculations and models
==============================================================================

The package will work with different types of databases such as:
    - Supply and Use Tables
    - Input-Output Tables
    - Multi-Regional and Single-Regional Tables
    - Monetary and Hybrid Tables

In this version, Database class is in interaction with the user and is created
based the CoreModel handling the main functionalities of IO systems.

A Databases object can be instantiated directly by passing pandas.DataFrames and
information on the units of measure or can be parsed using standard parsing functions.

In this version, standard EORA and EXIOBASE parsers are implemented and user
can also parse database from Excel and txt files based on the structure defined
on the tutorial.


The package has implemented methods for handling scenario analysis, and basic IO
analysis such as:
    - Aggregation
    - Productivity Test
    - Balance Test
    - Adding new sectors/activities/commodities or extensions to the database
    - Shock analysis + Sensitivity analysis
    - Comparative analysis
    - Linkages analysis

Package dependencies:
    - Plotly
    - Pandas
    - Numpy
    - Tabulate
    - Cvxpy (optional)

:Authors: Mohammad Amin Tahavori, Lorenzo Rinaldi, Nicolò Golinucci

:license: GNU General Public License v3.0

"""


import pandas as pd

from mario.version import __version__
from mario.api import Database, CoreModel
from mario.compute.primitives import (
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
    calc_f_from_z,
    calc_f_dis,
    calc_m,
    calc_m_from_z,
    calc_M,
    calc_y,
    calc_p,
    calc_p_from_z,
)
from mario.log_exc.logger import set_log_verbosity
from mario.model.builders import MatrixBuilder, DataTemplate

from mario.parsers.entrypoints import (
    parse_adb,
    parse_cepalstat,
    parse_ceads,
    parse_emerging,
    parse_from_txt,
    parse_from_parquet,
    parse_from_excel,
    parse_exiobase_3,
    parse_eora,
    parse_eurostat,
    hybrid_iot_exiobase,
    parse_exiobase_sut,
    parse_from_pymrio,
    hybrid_sut_exiobase,
    parse_exiobase,
    parse_figaro,
    parse_gloria,
    parse_gtap,
    parse_istat,
    parse_oecd,
    parse_statcan,
    parse_useeio,
    parse_wiod,
)

from mario.views.plots import set_palette

from mario.log_exc import exceptions
from mario.test.mario_test import load_test
from mario.utils import slicer
from mario.download import *
from mario.settings.settings import (
    upload_settings,
    download_settings,
    reset_settings,
    set_compute_method,
    set_linear_solver,
    set_linear_strategy,
    Nomenclature,
    Index,
    IndexAliases,
    Compute,
)

from mario.parsers.handshake import parse_exiobase_3_9_4

from mario.model.conventions import IOT, SUT


__authors__ = " 'Mohammad Amin Tahavori', Lorenzo Rinaldi', 'Nicolò Golinucci' "


# Configure a usable default logging surface on import so users see MARIO's
# informational messages without needing an explicit setup call first.
set_log_verbosity("info")
