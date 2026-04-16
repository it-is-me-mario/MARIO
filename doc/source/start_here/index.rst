Quick Setup
===========

Use this page for the shortest path into MARIO.

What Is MARIO
-------------

MARIO is a Python library for working with Input-Output Tables (IOTs) and
Supply and Use Tables (SUTs). Its core object is a database that can be parsed
from source files, inspected, computed on demand, transformed, and exported
again.

In practice, MARIO is built around a simple workflow:

* parse or load a database;
* inspect its structure and available matrices;
* compute derived matrices on demand;
* transform, aggregate/**disaggregate**, or shock the database;
* export the results.

Installation
------------

Preferably, create a clean Python environment:

.. code-block:: bash

   conda create -n mario python=3.10
   conda activate mario

Then install MARIO from PyPI:

.. code-block:: bash

   pip install mariopy

For development work or parser-heavy workflows, a dedicated environment is the
safer default. Some optional features also benefit from extra packages such as
``country_converter`` or Sphinx tooling for the documentation build.

A quick sanity check after installation is:

.. code-block:: python

   import mario
   db = mario.load_test("IOT") # or SUT
   db

If this works, the package is installed correctly and the core runtime is
available.

Next Step
---------

Head over to :doc:`../tutorials/index` to unlock the full capacbilities of MARIO with hands-on examples and step-by-step guides.
