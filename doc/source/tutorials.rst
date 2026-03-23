Tutorials
=========

This section collects lightweight Jupyter notebooks for the current MARIO codebase.
They are meant to be practical starting points for both the ``Database`` API
and the newer ``Dataset`` core.

The intended reading order is deliberate:

* start with the database workflows if you are a normal MARIO user;
* use the ``Dataset`` notebooks only when you need the newer modular core directly.

The notebooks are kept small on purpose: they should be easy to run locally,
easy to adapt, and stable enough to evolve with the package.

Database Workflows
------------------

These notebooks keep the user-facing API as close as possible to historical MARIO.

.. toctree::
   :maxdepth: 1

   tutorials/tutorial_database_quickstart
   tutorials/tutorial_database_parse_transform
   tutorials/tutorial_database_scenarios_export

Advanced Core Workflows
-----------------------

These notebooks are for the newer internal architecture. They are useful, but they
should not be confused with the primary public path.

.. toctree::
   :maxdepth: 1

   tutorials/tutorial_dataset_core
   tutorials/tutorial_parse_datasets
   tutorials/tutorial_custom_parser
