Testing Strategy
================

MARIO uses a mixed testing strategy: focused unit tests around formula and API
logic, plus integration-style tests around parsers, exports, workbook
workflows, and real-data fixtures.

Test layout
-----------

The suite is organized by owning domain:

* ``tests/api`` for the public ``Database`` and ``CoreModel`` surface;
* ``tests/compute`` for catalog, resolver, formula, runtime, and view logic;
* ``tests/ops`` for transformations, aggregation, add-sector workflows, and
	other state-changing operations;
* ``tests/parsers`` for source-specific parsers, roundtrips, and real-data
	regression coverage;
* ``tests/docs`` for documentation-facing checks such as API reference
	completeness.

This matters when adding new coverage: tests should usually live near the
abstraction that owns the behaviour, not under one generic regression file.

How to choose the smallest useful test slice
--------------------------------------------

For most contributor changes, start narrow:

* parser normalization: run the affected file in ``tests/parsers``;
* compute/catalog changes: run the relevant file in ``tests/compute``;
* public API behaviour: run the affected file in ``tests/api``;
* transformation logic: run the affected file in ``tests/ops``;
* docs structure or generated API pages: run ``tests/docs`` and a doc build.

If the change crosses layers, widen only after the owning slice is green.

Common commands
---------------

Run one domain:

.. code-block:: bash

	 pytest tests/api -q
	 pytest tests/compute -q
	 pytest tests/ops -q
	 pytest tests/parsers -q
	 pytest tests/docs -q

Run the most common targeted checks:

.. code-block:: bash

	 pytest tests/compute/test_compute_catalog.py -q
	 pytest tests/compute/test_resolver.py -q
	 pytest tests/parsers/test_realdata_workbooks.py -q
	 pytest tests/ops/test_addsector.py -q
	 pytest tests/docs/test_api_reference_docs.py -q

For documentation changes, also validate the built site:

.. code-block:: bash

	 conda run -n mario make -C doc html

Current priorities
------------------

The most valuable regression coverage currently comes from:

* parser correctness on real but manageable workbooks;
* export and re-import roundtrips;
* aggregation behaviour across legacy and explicit layouts;
* ``add_sectors`` workbook and engine behaviour;
* compute catalog and resolver correctness as the dependency-driven compute
	layer evolves;
* source-specific parser stability.

Real-data fixtures
------------------

The repository includes small real-data workbook fixtures under
``tests/fixtures/realdata``. These keep parser, export, and aggregation checks
grounded on representative layouts instead of only synthetic tables.

See :doc:`realdata_fixtures` for the fixture layout, local external-dataset
workflow, and recommended commands.
