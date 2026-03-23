.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

.. image:: https://readthedocs.org/projects/mario-suite/badge/?version=latest
    :target: https://mario-suite.readthedocs.io/en/latest/index.html
    :alt: Documentation Status

.. image:: https://badge.fury.io/py/mariopy.svg
    :target: https://badge.fury.io/py/mariopy

.. image:: https://zenodo.org/badge/421900437.svg
   :target: https://zenodo.org/badge/latestdoi/421900437

*******
MARIO
*******

**MARIO** stands for **Multifunctional Analysis of Regions through Input-Output**.
It is a Python package for reading, transforming, aggregating and computing on
input-output tables (IOT) and supply-use tables (SUT).

MARIO is not being rebuilt by discarding its established semantics. The current codebase
keeps the historical MARIO conventions for matrices, indexes and table structure,
while progressively moving the implementation toward a cleaner internal architecture.
The public surface remains centered on ``mario.Database``. Internal restructuring
is intentionally kept behind that facade instead of introducing a second primary
user object.

Documentation is available on `Read the Docs <https://mario-suite.readthedocs.io/en/latest/index.html>`_.
The current restructuring direction is documented in
`doc/architecture/mario2_restructure_plan.md <doc/architecture/mario2_restructure_plan.md>`_.


What MARIO Covers
-----------------

MARIO is built for common IO workflows such as:

* reading structured IOT and SUT datasets;
* working with single-region and multi-region tables;
* handling monetary and hybrid systems when supported by the parser;
* computing missing matrices from dependency rules;
* aggregating tables;
* transforming SUT into IOT;
* exporting to Excel, text formats and ``pymrio`` objects;
* managing scenarios and shock-style variations;
* extending the parser layer without editing the core package.


Project Status
--------------

The current package has one official user-facing object model.

``mario.Database``
   The main public API. Parsing, computing, querying, transforming, aggregating,
   exporting and scenario workflows should all be understood from this surface.

Internally, MARIO now uses more modular compute, parser, storage and operation
layers, but those are implementation details rather than a second public API.


Installation
------------

The package name on PyPI is ``mariopy``, while the import name is ``mario``.

Install from PyPI:

.. code-block:: bash

   pip install mariopy

Install from source:

.. code-block:: bash

   git clone https://github.com/it-is-me-mario/MARIO.git
   cd MARIO
   pip install -e .

The core package depends mainly on ``pandas``, ``numpy``, ``openpyxl`` and
``pymrio``. Some newer helpers are optional:

* ``polars`` for internal developer-facing dataframe conversions
* ``scipy`` for internal sparse conversions
* ``pyarrow`` for Parquet-backed storage helpers
* ``duckdb`` for the optional DuckDB helper layer used in future storage/parser work

From source, you can install the full optional stack with:

.. code-block:: bash

   pip install -e ".[all]"


Quickstart: Legacy API
----------------------

``Database`` remains the main and recommended way to use MARIO.

.. code-block:: python

   import mario

   db = mario.load_test("IOT")

   print(db)
   print(db.get_index("Region"))

   db.calc_all(["w"])
   w = db.query(matrices=["w"], scenarios=["baseline"])

   db.to_excel(path="output_folder")

For SUT workflows, the classic transformation methods are still available:

.. code-block:: python

   import mario

   sut = mario.load_test("SUT")
   iot = sut.to_iot(method="B")


Parsers and Extensibility
-------------------------

The parser surface documented for users is still the ``Database``-returning one.
The main entry points are:

* ``mario.parse_from_excel(...)``
* ``mario.parse_from_txt(...)``
* ``mario.parse_exiobase_sut(...)``
* ``mario.parse_exiobase_3(...)``
* ``mario.parse_eora(...)``
* ``mario.parse_eurostat_sut(...)``

Parser restructuring is ongoing internally, but user workflows should continue
to target ``Database`` objects.


Architecture Snapshot
---------------------

The repository is now organized around a few explicit layers:

``mario.model``
   Shared domain conventions, labels, builders and table enums.

``mario.compute``
   Compute catalog, dependency resolution, views and formula implementations.

``mario.parsers``
   Database parser entry points plus lower-level parser adapters.

``mario.storage``
   Repository abstractions and storage helpers used internally by the modular core.

``mario.ops``
   Aggregation, export and transformation wrappers extracted from the monolithic
   database classes.

``mario.views``
   Output-oriented views such as tabular rendering.

Logging
-------

MARIO now keeps logging intentionally quiet by default. When enabled, internal
messages use a minimal format and external dependency noise stays suppressed.

.. code-block:: python

   import mario

   mario.set_log_verbosity("info")


Development
-----------

Run the test suite with:

.. code-block:: bash

   pytest

Format code with:

.. code-block:: bash

   black mario tests

The package is under active development. The most stable public surface is still
``mario.Database``. Internal restructuring is focused on making that public API
cleaner, faster and easier to maintain rather than replacing it with a new
user-facing object.


Citation
--------

If you use MARIO in academic work, please cite the software paper:

* `Tahavori, Golinucci, Rinaldi, et al. <https://openresearchsoftware.metajnl.com/articles/10.5334/jors.473>`_

Selected application papers are listed in the documentation and project history.


License
-------

MARIO is distributed under the
`GNU General Public License v3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>`_.
