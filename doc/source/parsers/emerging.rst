EMERGING
========

MARIO supports the EMERGING MATLAB bundles distributed on Zenodo through the
EMERGING concept DOI.

Relevant source links
---------------------

* concept DOI:
  `Zenodo concept 10956622 <https://doi.org/10.5281/zenodo.10956622>`_;
* older supported record:
  `Zenodo 10956623 <https://doi.org/10.5281/zenodo.10956623>`_;
* newer supported record:
  `Zenodo 18518911 <https://doi.org/10.5281/zenodo.18518911>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_emerging(...) <../api_document/mario.parse_emerging>`

The current backend supports only the multiregional ``IOT`` workflow.

Download workflow
-----------------

Automatic download is available:

* ``mario.download_emerging(...)``

Typical usage:

.. code-block:: python

   import mario

   mario.download_emerging(
       path="/path/to/emerging",
       version="2.1",
       years=[2023],
   )

You can also work entirely from local files if you already downloaded the
MATLAB bundles yourself.

Supported local file names
--------------------------

The parser currently supports at least these naming conventions:

* older main files such as ``global_mrio_2017.mat``;
* newer main files such as ``EMERGING_V2_2023_m.mat``;
* legacy local names such as ``EMERGING_V2_<year>.mat`` when the internal
  MATLAB structure matches.

For satellite accounts, MARIO currently supports companion CO2 bundles such as:

* ``EMERGING_CO2_<year>.mat``
* ``EMERGING_CO2_<year>_IEA.mat``

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the EMERGING notebook <../notebooks/parsers/emerging/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse one local EMERGING file:

.. code-block:: python

   db = mario.parse_emerging(
       path="/path/to/EMERGING_V2_2023_m.mat",
       table="IOT",
   )

Parse from a directory and select one year:

.. code-block:: python

   db = mario.parse_emerging(
       path="/path/to/emerging_directory",
       table="IOT",
       year=2023,
   )

Restrict the region set to keep the database manageable:

.. code-block:: python

   db = mario.parse_emerging(
       path="/path/to/emerging_directory",
       table="IOT",
       year=2023,
       regions=["ITA", "DEU", "FRA"],
   )

Control CO2 loading explicitly:

.. code-block:: python

   db = mario.parse_emerging(
       path="/path/to/emerging_directory",
       table="IOT",
       year=2023,
       load_co2=False,
   )

Or provide a specific CO2 file:

.. code-block:: python

   db = mario.parse_emerging(
       path="/path/to/emerging_directory",
       table="IOT",
       year=2023,
       co2_path="/path/to/EMERGING_CO2_2023.mat",
   )

Caveats
-------

* EMERGING parsing currently supports only ``IOT`` tables;
* the full EMERGING matrix is very large, so ``regions=...`` is often the
  right first step;
* ``load_co2=False`` is useful when you want to parse the core IOT first and
  deal with extensions separately.
