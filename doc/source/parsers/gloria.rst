GLORIA
======

MARIO supports local parsing of GLORIA monetary multi-regional ``SUT``
bundles.

The current backend supports:

* monetary ``SUT`` parsing only;
* valuation selection through ``valuation=``;
* region subsetting through ``regions=``;
* satellite filtering through ``satellites=``;
* on-disk caching for repeated parses.

For this source, the most useful documentation format is a notebook-driven one:
this landing page stays short, while one practical notebook covers the local
release layout, valuation branches, regional subsetting, satellite filters,
memory-sensitive options, and cache usage.

Relevant source links
---------------------

* official GLORIA overview page:
  `IELab GLORIA overview <https://ielab.info/resources/gloria/about>`_;
* supporting documents and release material:
  `IELab GLORIA supporting documents <https://ielab.info/resources/gloria/supportingdocs>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_gloria(...) <../api_document/mario.parse_gloria>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  GLORIA release root or directly the ``GLORIA_MRIOs_*`` directory;
* ``table``:
  currently only ``"SUT"`` is supported;
* ``valuation``:
  choose one markup branch such as ``basic``, ``trade``, ``transport``,
  ``taxes`` or ``subsidies``;
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

Automatic GLORIA download is intentionally not supported.

In practice, the workflow is:

1. obtain the GLORIA release locally;
2. keep the raw ``T``, ``Y`` and ``V`` csv files together with the
   ``GLORIA_ReadMe_*.xlsx`` workbook;
3. point ``mario.parse_gloria(...)`` to the release root or directly to the
   ``GLORIA_MRIOs_*`` directory.

Typical usage
-------------

Direct path to one GLORIA release:

.. code-block:: python

   import mario

   db = mario.parse_gloria(
       path="/path/to/gloria_release",
       table="SUT",
   )

Select one valuation branch and one region subset:

.. code-block:: python

   import mario

   db = mario.parse_gloria(
       path="/path/to/gloria_release",
       table="SUT",
       valuation="trade",
       regions=["ITA", "DEU", "FRA"],
   )

Enable cache for repeated runs:

.. code-block:: python

   import mario

   db = mario.parse_gloria(
       path="/path/to/gloria_release",
       table="SUT",
       cache=True,
   )

Warnings
--------

.. warning::

   GLORIA parsing currently supports only ``SUT`` tables.

.. warning::

   GLORIA use blocks are very large. Parsing the full release can require
   several GB of RAM, so ``regions=``, ``dtype="float32"``, and ``cache=True``
   are often the right defaults.

.. warning::

   Satellite accounts are optional in the local release structure. If the
   satellite-account directory is absent or incomplete, MARIO falls back to
   empty extensions.

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`GLORIA parser walkthrough <../notebooks/parsers/gloria/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the GLORIA notebook <../notebooks/parsers/gloria/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/gloria/walkthrough
