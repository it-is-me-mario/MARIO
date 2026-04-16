EORA
====

MARIO supports both the multi-regional EORA26 workflow and local single-region
EORA files.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_eora(...) <../api_document/mario.parse_eora>`

Download workflow
-----------------

Automatic EORA download is not part of the current MARIO workflow.

You should work from local EORA files that you already downloaded and, for
EORA26, from the associated label files.

Supported workflows
-------------------

MARIO exposes two practical modes:

* multi-regional EORA26 parsing with ``multi_region=True``;
* single-region EORA parsing with ``multi_region=False``.

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the EORA notebook <../notebooks/parsers/eora/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse an EORA26 multi-regional dataset:

.. code-block:: python

   db = mario.parse_eora(
       path="/path/to/eora26_directory",
       multi_region=True,
       table="IOT",
       indeces="/path/to/eora26_labels",
   )

If the label files already live next to the data files, ``indeces=`` can be
omitted.

Parse a single-region EORA file:

.. code-block:: python

   db = mario.parse_eora(
       path="/path/to/single_region_directory",
       multi_region=False,
       country="ITA",
   )

If you want full country names instead of abbreviations:

.. code-block:: python

   db = mario.parse_eora(
       path="/path/to/eora26_directory",
       multi_region=True,
       table="IOT",
       name_convention="full_name",
   )

For single-region workflows, you can also aggregate trade automatically:

.. code-block:: python

   db = mario.parse_eora(
       path="/path/to/single_region_directory",
       multi_region=False,
       country="ITA",
       aggregate_trade=True,
   )

Caveats
-------

* for multi-region parsing, only EORA26 is currently supported;
* the multi-region parser fixes some known inconsistencies during parsing;
  inspect ``db.meta_history()`` if you need the exact repair trail;
* for single-region parsing, table type can usually be inferred, while for
  multi-region parsing you should treat it as an ``IOT`` workflow.
