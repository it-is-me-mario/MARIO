MARIO Documentation
===================

MARIO is an open-source Python toolkit for working with Input-Output Tables
(IOTs) and Supply and Use Tables (SUTs). It provides a consistent workflow for
turning external datasets into structured MARIO databases, computing derived
matrices, aggregating classifications, transforming tables and exporting
results to different formats.

The package is designed for practical analytical work, but also for
maintainable model-building workflows. In everyday use that usually means:

* reading structured or semi-structured IO data from Excel, TXT, Parquet or
  source-specific parsers;
* inspecting and manipulating a public ``Database`` object with stable,
  high-level methods;
* running operational workflows such as aggregation, extensions, shocks,
  ``add_sectors(...)`` and layout-aware export/re-import.

MARIO therefore sits halfway between a user-facing analysis toolkit and a
developer-oriented modeling framework. The documentation mirrors that split:
you can enter from a quick installation path, from notebook-based tutorials, or
from a more technical reference and contributor view.

Useful links
------------

* `GitHub repository <https://github.com/it-is-me-mario/MARIO>`_
* :doc:`publications/index`
* :doc:`resources/index`
* :doc:`changelog`

Package features
----------------

MARIO is built around a few core capabilities:

* Unified database API: once a dataset is parsed, most workflows are exposed
  through the same ``Database`` interface, regardless of the original source.
* Support for both IOT and SUT workflows: MARIO keeps the distinction explicit,
  while still offering common methods for parsing, aggregation, export and
  structural operations.
* Flexible parser layer: the package supports legacy ``Level``-based workbooks,
  newer explicit matrix layouts, flat text formats and a growing set of
  source-specific parsers.
* Operational workflows: MARIO includes ready-to-use workflows for aggregation,
  extensions, shocks, export, structural add-sectors templates and related
  workbook-driven operations.
* Real-world interoperability: the package is designed to move data in and out
  of spreadsheets and analysis pipelines without forcing users to rebuild their
  entire data stack.

MARIO in a nutshell
-------------------

In a typical workflow, the user follows a small number of recurring steps:

1. Parse an external IOT or SUT source into a MARIO database.
2. Inspect the database, compute the required matrices and derived indicators.
3. Aggregate or transform sets when moving between analytical scopes.
4. Export the result to Excel, TXT, Parquet or other downstream formats.
5. Optionally generate structured templates for shocks, extensions or
   add-sectors workflows and feed the results back into the database.

Documentation contents
----------------------

The documentation is organized around five main entry points:

* Installation: the shortest path to a working local setup.
* User Guide: the main narrative path through practical tasks and core concepts.
* Tutorials: notebook-based examples that show complete workflows end to end.
* API Reference: exact method names, parser entry points and format details.
* Resources: publications, glossary, settings notes, changelog and contributor
  material.

.. toctree::
   :maxdepth: 2

   getting_started/installation
   user_guide/index
   tutorials/index
   reference/index
   resources/index

.. toctree::
   :hidden:

   getting_started/index


Where to go next
----------------

New to MARIO
   Start from :doc:`getting_started/installation`.

Looking for practical examples
   Go to :doc:`tutorials/index`.

Need practical guidance together with the core concepts
   Use :doc:`user_guide/index`.

Looking for a method, parser or file format
   Use :doc:`reference/index`.

Looking for supporting material, publications or contributor information
   Use :doc:`resources/index`.
