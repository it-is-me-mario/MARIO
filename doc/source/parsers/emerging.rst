EMERGING
========

MARIO supports the EMERGING MATLAB bundles distributed through the official
Zenodo version records.

The parser currently supports only the multiregional ``IOT`` workflow.

The official version records currently relevant for MARIO are:

* ``v2.2``:
  `Zenodo 19461860 <https://doi.org/10.5281/zenodo.19461860>`_;
* ``v2.1``:
  `Zenodo 18518911 <https://doi.org/10.5281/zenodo.18518911>`_;
* ``v2.0``:
  `Zenodo 17557778 <https://doi.org/10.5281/zenodo.17557778>`_;
* ``v1.0``:
  `Zenodo 10956623 <https://doi.org/10.5281/zenodo.10956623>`_.

Any other version reference should be treated as deprecated in the MARIO
documentation.

For this source, the most useful documentation format is a notebook-driven one:
this landing page stays short, while one practical notebook covers the
official Zenodo versions, local-file naming conventions, downloader usage,
``year=``, ``regions=``, ``load_co2=``, and ``co2_path=``.

Relevant source links
---------------------

* concept DOI:
  `Zenodo concept 10956622 <https://doi.org/10.5281/zenodo.10956622>`_;
* ``v2.2`` record:
  `Zenodo 19461860 <https://doi.org/10.5281/zenodo.19461860>`_;
* ``v2.1`` record:
  `Zenodo 18518911 <https://doi.org/10.5281/zenodo.18518911>`_;
* ``v2.0`` record:
  `Zenodo 17557778 <https://doi.org/10.5281/zenodo.17557778>`_;
* ``v1.0`` record:
  `Zenodo 10956623 <https://doi.org/10.5281/zenodo.10956623>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_emerging(...) <../api_document/mario.parse_emerging>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one EMERGING ``.mat`` file or a directory containing multiple yearly bundles;
* ``table``:
  currently only ``"IOT"`` is supported;
* ``year``:
  use it when one directory contains more than one EMERGING year;
* ``regions``:
  optional ISO3 subset to keep only one manageable part of the database;
* ``load_co2``:
  enable or disable automatic companion CO2 import;
* ``co2_path``:
  explicit path to one companion CO2 file when auto-detection is not enough.

Download workflow
-----------------

Automatic download is available:

* ``mario.download_emerging(...)``

``latest`` currently resolves to ``v2.2``.

Typical usage
-------------

Download one official version explicitly:

.. code-block:: python

   import mario

   mario.download_emerging(
       path="/path/to/emerging",
       version="2.2",
       years=[2023],
   )

Parse one local EMERGING bundle:

.. code-block:: python

   import mario

   db = mario.parse_emerging(
       path="/path/to/EMERGING_V2_2023_m.mat",
       table="IOT",
   )

Parse from a directory and select one year:

.. code-block:: python

   import mario

   db = mario.parse_emerging(
       path="/path/to/emerging_directory",
       table="IOT",
       year=2023,
   )

Restrict the region set to keep the database manageable:

.. code-block:: python

   import mario

   db = mario.parse_emerging(
       path="/path/to/emerging_directory",
       table="IOT",
       year=2023,
       regions=["ITA", "DEU", "FRA"],
   )

Control CO2 loading explicitly:

.. code-block:: python

   import mario

   db = mario.parse_emerging(
       path="/path/to/emerging_directory",
       table="IOT",
       year=2023,
       load_co2=False,
   )

Caveats
-------

* EMERGING parsing currently supports only ``IOT`` tables;
* the full EMERGING matrix is very large, so ``regions=...`` is often the
  right first step;
* local ``v2.x`` file names do not identify the exact sub-version
  ``2.0`` versus ``2.1`` versus ``2.2``, so MARIO treats them generically as
  ``v2.x``-compatible local bundles;
* ``load_co2=False`` is useful when you want to parse the core IOT first and
  deal with extensions separately.

Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`EMERGING parser walkthrough <../notebooks/parsers/emerging/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the EMERGING notebook <../notebooks/parsers/emerging/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/emerging/walkthrough
