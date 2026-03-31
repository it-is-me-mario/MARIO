****************
Release History
****************

Unreleased
----------

Architecture and public API
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Reorganized MARIO around clearer ``api``, ``compute``, ``ops``, ``parsers``,
  ``views``, ``storage`` and ``internal`` modules.
* Moved most legacy logic out of ``core`` and ``tools`` and consolidated the
  public surface around ``Database``.
* Added a more explicit compute layer with planner, resolver, primitives,
  formula modules and dependency graph utilities.

Parsing and export
~~~~~~~~~~~~~~~~~~

* Unified Excel, TXT and Parquet parsing through a shared parser-state flow.
* Added native flat TXT/Parquet export and matching re-import support.
* Introduced ``matrix_layouts`` support for richer IOT and SUT layouts,
  including cases where ``V`` and ``E`` carry additional ``Region`` and
  ``Sector``/``Activity`` levels.
* Preserved legacy public axes for historical workbooks while allowing newer
  explicit layouts without forcing ``Level`` markers back into exports.

Add sectors and structural operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Refactored ``add_sectors`` around a workbook-driven workflow with a single
  template format.
* Added CVXLab-backed ``split=True`` support for IOT workflows, including a
  packaged ``Split_sectors`` model template.
* Improved ``add_sectors`` compatibility with explicit IOT layouts where
  ``V``/``E`` do not follow the old ``Region/Level/Item`` convention.
* Added overwrite protection to ``get_add_sectors_excel(...)`` and
  ``get_inventory_sheets(...)`` so existing files and inventory sheets are not
  replaced unless ``overwrite=True`` is passed explicitly.

Aggregation and transforms
~~~~~~~~~~~~~~~~~~~~~~~~~~

* Made aggregation robust to layout-aware ``V`` and ``E`` blocks without
  breaking the legacy public surface.
* Added ``VY`` as a first-class factor-of-production final-demand block across
  MARIO.
* Kept transformation utilities in the new ``ops`` layout and aligned them with
  the refactored parser/database flow.

Parsers and downloaders
~~~~~~~~~~~~~~~~~~~~~~~

* Added or rewrote direct parsers for Eurostat SDMX, FIGARO, OECD ICIO, WIOD,
  ADB MRIO, EMERGING, EORA, GTAP, StatCan and EXIOBASE IOT/SUT/hybrid data.
* Separated raw-data download utilities from parser-side logic and exposed a
  cleaner downloader surface.

Testing and documentation
~~~~~~~~~~~~~~~~~~~~~~~~~

* Greatly expanded the automated test suite across compute, parser, export,
  downloader and add-sectors workflows.
* Added vendored real-data workbook fixtures for IOT and SUT plus aggregation
  templates, with roundtrip tests for Excel, TXT and Parquet exports.
* Rewrote and expanded developer-facing documentation, tutorials and parser
  development guidance.

v 0.3.4
-------

Parsing functions error fixed
~~~~~~~~
Recent pandas versions have changed the way they interpret "None" in DataFrames indices and values, which are currently interpreted it as NaN. 
This mario update fixes the issue by replacing NaN with the string "None" when parsing excel files.

Deprecated functions
~~~~~~~~
Parser for old-fashioned Eurostat SUTs is deprecated. This function relied on peculiarly structured SUTs formats.
In case you need to parse such SUTs, please rearrange them into the standard MARIO format.
You can check the MARIO format from 'SUT.xlsx' file in the mario/test directory in this repository.


v 0.3.3
-------

Settings
~~~~~~~~
to_excel function bug in flow mode fixed.


v 0.3.0
-------

Settings
~~~~~~~~

New functionalities are provided to allow the user to change some naming convensions in mario indexing and input-output nomenclature convensions in mario.

Isard to Chenery-Moses Transformation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The transformation implies moving from trades accounted in the USE matrix to trades accounted in the SUPPLY matrix.

Data Templates
~~~~~~~~~~~~~~

New functionalities are added to create an enpty IO/SU tables  from tabular data.

Figaro Parser
~~~~~~~~~~~~~

New download and parsing functionalities are added to parser figaro database.


Table Downloader
~~~~~~~~~~~~~~~~

Donwload functions are added to the software. Some of the download functions are using pymrio database download functionalities, and some other databases are mario exclusive.

Deprecated functions
~~~~~~~~~~~~~~~~~~~~

is_productive and backup methods are deprecated.

Improvements
~~~~~~~~~~~~

* The add_sector function imprvements are implemented to make the code faster.
* Updating dependencies versioning (specifically pandas, numpy and xlsxwriter) 


Documentation
~~~~~~~~~~~~~

* The tutorials are updated to improve the readiblity and quality of the juputer notebook functionalities.
* New templates for the readthedocs.
