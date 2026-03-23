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
Today the repository exposes both:

* the historical ``Database`` API, still used as the main public surface;
* the new ``Dataset`` core, designed for modular parsing, storage and compute work.

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

The current package has two complementary layers.

``mario.Database``
   The main user-facing API. This remains the primary public entry point
   and the base for the workflows already documented in the project.

``mario.Dataset``
   The newer modular core. It separates model, compute, parser, storage,
   operations more cleanly, while preserving the
   same domain grammar used by the existing package.

This means MARIO can evolve internally without forcing a full rewrite of user code.


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

* ``polars`` for ``Dataset.to_polars(...)``
* ``scipy`` for ``Dataset.to_sparse(...)``
* ``pyarrow`` for Parquet-backed storage
* ``duckdb`` for the optional DuckDB helper layer

From source, you can install the full optional stack with:

.. code-block:: bash

   pip install -e ".[all]"


Quickstart: Legacy API
----------------------

The historical ``Database`` API is still available and remains the easiest way
to start if you already know MARIO.

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


Quickstart: Dataset Core
------------------------

The new ``Dataset`` API is useful when you want a cleaner programmatic core,
scenario inheritance, pluggable parsers, or alternative storage backends.

Build a dataset from an existing database:

.. code-block:: python

   import mario

   db = mario.load_test("IOT")
   dataset = mario.Dataset.from_database(db)

   w = dataset.compute("w")
   print(dataset.list_blocks())
   print(dataset.explain("w"))

Parse directly into a ``Dataset``:

.. code-block:: python

   import mario

   dataset = mario.parse_dataset_from_excel(
       "mario/test/SUT.xlsx",
       table="SUT",
       mode="flows",
       name="Demo SUT",
   )

   Z = dataset.compute("Z")
   X = dataset.compute("X")

Use a repository explicitly when you want persistent block storage:

.. code-block:: python

   from mario.model import Dataset, DatasetMetadata, TableKind
   from mario.storage import ParquetBlockRepository

   dataset = Dataset(
       metadata=DatasetMetadata(table_kind=TableKind.IOT, name="Parquet demo"),
       repository=ParquetBlockRepository("data/mario_blocks"),
   )


Parsers and Extensibility
-------------------------

The new parser layer is intentionally small. Third-party parsers can register
themselves without editing the MARIO core.

.. code-block:: python

   from mario.model import Dataset, DatasetMetadata, TableKind
   from mario.parsers import register_parser


   @register_parser("my_parser")
   def parse_my_parser(**kwargs):
       return Dataset(
           metadata=DatasetMetadata(
               table_kind=TableKind.IOT,
               name=kwargs.get("name"),
           )
       )

Built-in dataset-oriented entry points currently include:

* ``mario.parse_dataset("excel", ...)``
* ``mario.parse_dataset_from_excel(...)``
* ``mario.parse_dataset_exiobase_sut(...)``

Parsers such as ``parse_from_excel`` and the existing EXIOBASE / EORA /
EUROSTAT entry points remain available as well.


Architecture Snapshot
---------------------

The repository is now organized around a few explicit layers:

``mario.model``
   ``Dataset``, ``Scenario``, metadata, labels and table enums.

``mario.compute``
   Compute catalog, dependency resolution, views and formula implementations.

``mario.parsers``
   Parser base classes, registry and parser adapters.

``mario.storage``
   In-memory and Parquet-backed block repositories, with DuckDB helpers prepared
   for future work.

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
the historical ``Database`` API, while the modular ``Dataset`` core is the main
direction for internal and future-facing work.


Citation
--------

If you use MARIO in academic work, please cite the software paper:

* `Tahavori, Golinucci, Rinaldi, et al. <https://openresearchsoftware.metajnl.com/articles/10.5334/jors.473>`_

Selected application papers are listed in the documentation and project history.


License
-------

MARIO is distributed under the
`GNU General Public License v3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>`_.
