GLORIA
======

MARIO supports local parsing of GLORIA monetary multi-regional SUT bundles.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_gloria(...) <../api_document/mario.parse_gloria>`

The current backend supports only ``SUT`` parsing.

Key arguments
-------------

The key public arguments are:

* ``path``:
  GLORIA release root or directly the ``GLORIA_MRIOs_*`` directory;
* ``table``:
  currently only ``"SUT"`` is supported;
* ``valuation``:
  choose one markup branch such as ``basic``, ``trade`` or ``taxes``;
* ``year``:
  use it when the selected root contains more than one GLORIA year;
* ``regions``:
  optional subset of GLORIA region acronyms;
* ``satellites``:
  optional satellite group or row selector;
* ``dtype``:
  numeric storage type, with ``float32`` as the practical default;
* ``cache``:
  ``True`` or one explicit path to persist the parsed result.

Download workflow
-----------------

Automatic GLORIA download is intentionally not supported because the source
requires login.

In practice, the workflow is:

1. obtain the GLORIA release locally;
2. keep the raw ``T``, ``Y`` and ``V`` csv files together with the
   ``GLORIA_ReadMe_*.xlsx`` workbook;
3. point ``mario.parse_gloria(...)`` to the release root or directly to the
   ``GLORIA_MRIOs_*`` directory.

Supported options
-----------------

The GLORIA parser is richer than most local-file parsers. In particular it
supports:

* ``valuation=`` for markup selection:
  ``basic``, ``trade``, ``transport``, ``taxes`` or ``subsidies``;
* ``regions=`` to keep only one subset of GLORIA region acronyms;
* ``satellites=`` to keep only selected satellite groups or rows;
* ``dtype=`` to control numeric storage for large blocks;
* ``cache=True`` or a custom cache path to persist the parsed result.

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the GLORIA notebook <../notebooks/parsers/gloria/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse one GLORIA SUT:

.. code-block:: python

   db = mario.parse_gloria(
       path="/path/to/gloria_release",
       table="SUT",
   )

Select a different valuation:

.. code-block:: python

   db = mario.parse_gloria(
       path="/path/to/gloria_release",
       table="SUT",
       valuation="trade",
   )

Restrict the region set:

.. code-block:: python

   db = mario.parse_gloria(
       path="/path/to/gloria_release",
       table="SUT",
       regions=["ITA", "DEU", "FRA"],
   )

Restrict satellites:

.. code-block:: python

   db = mario.parse_gloria(
       path="/path/to/gloria_release",
       table="SUT",
       satellites="Emissions",
   )

Enable cache for repeated runs:

.. code-block:: python

   db = mario.parse_gloria(
       path="/path/to/gloria_release",
       table="SUT",
       cache=True,
   )

Caveats
-------

* GLORIA parsing currently supports only ``SUT`` tables;
* GLORIA use matrices are very large, so region restriction and caching are
  often the right defaults;
* ``dtype="float32"`` is the default for a reason: it reduces memory pressure
  on large parses.
