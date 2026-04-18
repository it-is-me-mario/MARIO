Eora
====

MARIO supports two practical Eora workflows:

* multiregional ``Eora26`` parsing;
* local single-region Eora tables (``SRIO`` style files).

There is currently **no** parser for the full Eora multi-regional release.
The multi-region parser is restricted to ``Eora26`` only.

For this source, the most useful documentation format is a notebook-driven one:
this landing page stays short, while one practical notebook covers the
difference between ``Eora26`` and single-region workflows, required files,
``multi_region=``, ``indeces=``, ``country=``, ``price=``,
``name_convention=``, and ``aggregate_trade=``.

Relevant source links
---------------------

* official Eora website:
  `Eora MRIO portal <https://www.worldmrio.com/>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_eora(...) <../api_document/mario.parse_eora>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one Eora file or one directory containing the local dataset;
* ``multi_region``:
  use ``True`` for ``Eora26`` and ``False`` for local single-region files;
* ``table``:
  relevant mainly for single-region parsing. For multi-region parsing the
  practical workflow is ``IOT`` only;
* ``indeces``:
  optional path to the ``Eora26`` label files. If omitted, MARIO looks for
  ``labels_*.txt`` files next to the dataset files;
* ``name_convention``:
  use ``full_name`` or ``abbreviation`` for region labels in the single-region
  workflow;
* ``aggregate_trade``:
  single-region helper that collapses detailed import/export rows into total
  imports and exports;
* ``country``:
  single-region selector when the input path points to a directory containing
  multiple country files;
* ``price``:
  optional single-region selector when the local directory contains multiple
  price variants.

Download workflow
-----------------

Automatic Eora download is not part of the current MARIO workflow.

You should work from local Eora files that you already downloaded and, for
``Eora26``, from the associated label files.

Typical usage
-------------

Parse one ``Eora26`` directory:

.. code-block:: python

   import mario

   db = mario.parse_eora(
       path="/path/to/eora26_directory",
       multi_region=True,
       table="IOT",
       indeces="/path/to/eora26_labels",
   )

Parse one local single-region Eora file:

.. code-block:: python

   import mario

   db = mario.parse_eora(
       path="/path/to/single_region_directory",
       multi_region=False,
       country="ITA",
   )

Use abbreviated country labels in the single-region workflow:

.. code-block:: python

   import mario

   db = mario.parse_eora(
       path="/path/to/single_region_directory",
       multi_region=False,
       country="ITA",
       name_convention="abbreviation",
   )

Aggregate trade rows in the single-region workflow:

.. code-block:: python

   import mario

   db = mario.parse_eora(
       path="/path/to/single_region_directory",
       multi_region=False,
       country="ITA",
       aggregate_trade=True,
   )

Caveats
-------

* there is no parser here for the full Eora MRIO release;
* multi-region parsing means ``Eora26`` only;
* ``Eora26`` parsing requires the label files in addition to the numeric data
  files;
* the ``Eora26`` parser applies a few consistency repairs during parsing;
  inspect ``db.meta_history`` if you need the exact repair trail;
* single-region parsing can infer ``IOT`` versus ``SUT`` automatically from the
  local file structure.

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`Eora parser walkthrough <../notebooks/parsers/eora/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the Eora notebook <../notebooks/parsers/eora/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/eora/walkthrough
