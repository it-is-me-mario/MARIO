Setup
=====

What is MARIO
-------------

MARIO is a Python library for working with :ref:`Input-Output Tables (IOTs) <concept-iots>` and
:ref:`Supply and Use Tables (SUTs) <concept-suts>`. Its core object is a database that can be parsed
from source files, inspected, whose matrices can be computed on demand, transformed, and exported
again.

In practice, MARIO is built around a simple workflow:

* parse or load a database
* inspect its structure and available matrices
* compute derived matrices on demand
* compute forward and backward linkages
* transform, aggregate/**disaggregate**, or shock the database
* export the results

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

Head over to :doc:`../concepts/index` to understand the cornerstone definitions and conventions, 
before moving to the :doc:`../parsers/index` and :doc:`../workflows/index` sections.
