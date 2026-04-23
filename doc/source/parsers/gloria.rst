Global Resource Input-Output Assessment (GLORIA)
================================================

MARIO supports local parsing of the GLORIA monetary multi-regional database.

The current backend supports:

* monetary ``SUT`` parsing
* valuation selection through ``valuation=``
* region subsetting through ``regions=``
* satellite filtering through ``satellites=``
* on-disk caching for repeated parses.


Relevant source links
---------------------

* official GLORIA overview page:
  `IELab GLORIA overview <https://ielab.info/resources/gloria/about>`_;
* supporting documents and release material:
  `IELab GLORIA supporting documents <https://ielab.info/resources/gloria/supportingdocs>`_.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_gloria(...) <../api_document/mario.parse_gloria>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  directory containing the ``GLORIA_MRIOs_*``. 
  It can contain multiple releases, provided that they respect the same sturcture of the original folder
* ``table``:
  optional, currently only ``"SUT"`` is provided
* ``valuation``:
  choose one markup branch such as ``basic``, ``trade``, ``transport``,
  ``taxes`` or ``subsidies`` (alternatively, use ``0``, ``1``, ``2``, ``3``, ``4``)
* ``year``:
  use it when the selected root contains more than one GLORIA year
* ``regions``:
  optional subset of GLORIA region acronyms
* ``satellites``:
  optional satellite group or row selector
* ``dtype``:
  numeric storage type, with ``float32`` as the practical default
* ``cache``:
  ``True`` or one explicit path to persist the parsed result. 
  This is especially useful for repeated runs, given the large size of GLORIA use blocks.


Notebook walkthrough
--------------------

Since automatic GLORIA download is not supported,
the typical workflow is:

1. obtain the GLORIA release locally
2. keep the raw ``T``, ``Y`` and ``V`` csv files together with the
   ``GLORIA_ReadMe_*.xlsx`` workbook. Optionally, keep the satellite accounts as well.
3. point ``mario.parse_gloria(...)`` to the release root or directly to the
   ``GLORIA_MRIOs_*`` directory

Use the notebook below as the main parser guide:

* :doc:`GLORIA parser walkthrough <../notebooks/parsers/gloria/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the GLORIA notebook <../notebooks/parsers/gloria/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/gloria/walkthrough


Caveats
-------

* The GLORIA database is very large. Parsing the full release can require
  several GB of RAM
* Satellite accounts are optional. If the satellite-account directory
  is absent or incomplete, MARIO falls back to
  empty extensions
