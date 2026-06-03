Real-Data Fixtures
==================

MARIO keeps a small set of real-data fixtures in the repository to catch the
kind of bugs that synthetic toy tables usually miss: layout drift, workbook
quirks, parser normalization mistakes, and export roundtrip regressions.

There are two distinct fixture families in the current test setup:

Vendored fixtures
   Small redistributable workbooks committed under
   ``tests/fixtures/realdata``. These are used in CI and should stay compact
   and stable.

External local datasets
   Larger or non-redistributable datasets discovered through local environment
   configuration in ``tests/parsers/test_external_realdata_workflow.py``.


What the Vendored Fixtures Cover
--------------------------------

The committed fixtures are split into:

* ``tests/fixtures/realdata/data`` for MARIO-readable IOT and SUT workbooks;
* ``tests/fixtures/realdata/aggregations`` for aggregation templates applied to
  those workbooks.

The central regression harness is
``tests/parsers/test_realdata_workbooks.py``. It uses these fixtures to
verify:

* Excel parsing across legacy and explicit layout variants;
* TXT and Parquet roundtrips in both matrix and flat export modes;
* aggregation workflows across IOT and SUT cases;
* preservation of flow blocks and units after re-import.

These fixtures are intentionally small, but they should still be structurally
representative. The goal is not statistical realism; it is coverage of the
layouts and conventions that have broken before.


What Belongs in a Vendored Fixture
----------------------------------

A fixture is a good candidate for ``tests/fixtures/realdata`` when it is:

* legally redistributable inside the repository;
* small enough for fast CI runs;
* representative of a parser or export edge case that synthetic tables do not
  exercise well;
* stable enough that expected behaviour can be asserted over time.

Typical good reasons to add one are:

* a new row-index layout for ``V`` or ``E`` blocks;
* a source-specific regression that only appears on real workbook structure;
* an aggregation case that depends on realistic labels or sheet organization;
* a roundtrip bug that needs a permanent non-synthetic reproducer.

Very large source dumps, confidential files, or datasets that are mostly
duplicates of existing fixture coverage should stay out of the vendored set.


How to Add a New Vendored Fixture
---------------------------------

For the current test harness, the workflow is:

1. add the workbook under ``tests/fixtures/realdata/data``;
2. add or reuse any matching aggregation templates under
   ``tests/fixtures/realdata/aggregations``;
3. register the case in ``REALDATA_DATASETS`` inside
   ``tests/parsers/test_realdata_workbooks.py`` with:

   * ``table`` set to ``"IOT"`` or ``"SUT"``;
   * ``matrix_layouts`` describing any non-default row layout expectations;
   * ``aggregation_files`` listing compatible aggregation workbooks.

Once registered, the existing parametrized tests will automatically include the
new case in parser, export, roundtrip, and aggregation coverage.


Layout Variants Matter
----------------------

These fixtures are not only about parser breadth. They also pin down supported
layout variants.

For example, ``tests/test_realdata_workbooks.py`` distinguishes cases such as:

* legacy IOT/SUT workbooks;
* ``V`` indexed only by ``Region`` versus ``Region`` + ``Sector`` or
  ``Activity``;
* ``E`` indexed only by ``Region`` versus richer explicit layouts.

When you add a new fixture, think in terms of which public layout contract it
is proving, not only which file happens to parse on your machine.


External Real-Data Workflows
----------------------------

Some parser checks cannot live in the repository because the datasets are too
large, licensed differently, or environment-specific.

Those workflows are handled by
``tests/parsers/test_external_realdata_workflow.py`` and the optional env file
``tests/realdata.local.env``. Start from the committed example file
``tests/realdata.env.example`` and copy it locally. The relevant variables are:

* ``MARIO_REALDATA_ROOT``;
* ``MARIO_REALDATA_CONFIG``;
* ``MARIO_REALDATA_FILTER``;
* ``MARIO_REALDATA_RUN_AGGREGATE``.

If needed, you can also override the env-file location itself with
``MARIO_REALDATA_ENV``.

Use that path when the goal is to validate a local mirror of a real source
family without making the repository heavier or less shareable.


Recommended Verification
------------------------

For vendored fixtures, the minimum useful check is:

.. code-block:: bash

   pytest tests/parsers/test_realdata_workbooks.py -q

For local external datasets, run:

.. code-block:: bash

   cp tests/realdata.env.example tests/realdata.local.env
   pytest tests/parsers/test_external_realdata_workflow.py -q

before merging parser changes that rely on those sources.
