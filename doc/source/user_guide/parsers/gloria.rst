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

* :doc:`mario.parse_gloria(...) <../../api_document/mario.parse_gloria>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  directory containing a GLORIA release, one ``part_I`` economic-account folder,
  or one specific ``GLORIA_MRIOs_*`` dataset folder
* ``table``:
  optional, currently only ``"SUT"`` is provided
* ``valuation``:
  choose one markup branch such as ``basic``, ``trade``, ``transport``,
  ``taxes`` or ``subsidies`` (alternatively, use ``1``, ``2``, ``3``, ``4``, ``5``)
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

Expected path structure
-----------------------

``path`` can point to either of the two common local layouts.

The compact GLORIA layout keeps the yearly dataset directory, optional
satellite-account directory and readme workbook under the same root:

.. code-block:: text

   GLORIA/
   ├── GLORIA_MRIOs_060_2025/
   │   ├── ..._T-Results_2025_060_Markup001(full).csv
   │   ├── ..._Y-Results_2025_060_Markup001(full).csv
   │   └── ..._V-Results_2025_060_Markup001(full).csv
   ├── GLORIA_SatelliteAccounts_060_2025/
   │   ├── ..._TQ-Results_2025_060_Markup001(full).csv
   │   └── ..._YQ-Results_2025_060_Markup001(full).csv
   └── GLORIA_ReadMe_060.xlsx

The Google Drive release layout is also accepted. MARIO uses the ``part_I``
folder for economic accounts and the ``part_III`` folder for satellite
accounts when both are present under the same release root:

.. code-block:: text

   GLORIA/latest_releases/060/
   ├── GLORIA_MRIO_Loop060_part_I_MRIOdatabase/
   │   └── GLORIA_MRIOs_060_2025/
   │       ├── ..._T-Results_2025_060_Markup001(full).csv
   │       ├── ..._Y-Results_2025_060_Markup001(full).csv
   │       └── ..._V-Results_2025_060_Markup001(full).csv
   ├── GLORIA_MRIO_Loop060_part_III_satelliteaccounts/
   │   └── GLORIA_SatelliteAccounts_060_2025/
   │       ├── ..._TQ-Results_2025_060_Markup001(full).csv
   │       └── ..._YQ-Results_2025_060_Markup001(full).csv
   └── GLORIA_ReadMe_060.xlsx

In both layouts, ``path`` can point to the release root, to the economic-account
container, or directly to one ``GLORIA_MRIOs_*`` folder. Keep
``GLORIA_ReadMe_*.xlsx`` and the matching satellite-account directory in the
same release tree so MARIO can discover labels and extensions.

Use ``year=`` when the selected root contains several yearly datasets and
``valuation=`` to choose the markup branch. If ``cache=True`` or
``cache=/path/to/cache`` is used, MARIO stores a parsed cache next to the
workflow you selected.


Notebook walkthrough
--------------------

Since automatic GLORIA download is not supported,
the typical workflow is:

1. obtain the GLORIA release locally
2. keep the ``part_I`` economic accounts, ``part_III`` satellite accounts and
   ``GLORIA_ReadMe_*.xlsx`` workbook under the same release root
3. point ``mario.parse_gloria(...)`` to the release root, to the ``part_I``
   economic-accounts directory or directly to one ``GLORIA_MRIOs_*`` directory

Use the notebook below as the main parser guide:

* :doc:`GLORIA parser walkthrough <../../notebooks/parsers/gloria/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the GLORIA notebook <../../notebooks/parsers/gloria/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/gloria/walkthrough


Caveats
-------

* The GLORIA database is very large. Parsing the full release can require
  several GB of RAM
* Satellite accounts are optional. If the satellite-account directory
  is absent or incomplete, MARIO falls back to
  empty extensions
