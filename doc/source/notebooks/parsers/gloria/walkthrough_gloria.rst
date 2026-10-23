:page-type: Database guide
:summary: Import a monetary supply-use model from a local GLORIA release.

GLORIA
======

.. container:: mario-companion

   :download:`Run the notebook <walkthrough_gloria.ipynb>`

The parser supports SUTs. Keep the economic files, matching ReadMe and optional satellite accounts together. Release 060 includes forecast years; record the year and release used.

**Full-database calculations:** install the optional UMFPACK backend.
See :doc:`installation and compute settings </user_guide/advanced/compute_settings>`.
The parser selects solve/direct, with a SciPy fallback when UMFPACK is unavailable.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_gloria(path="/path/to/GLORIA", year=2023)

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source pages

   - GLORIA overview: `IELab GLORIA overview <https://ielab.info/resources/gloria/about>`__
   - release notes and supporting material: `IELab GLORIA supporting documents <https://ielab.info/resources/gloria/supportingdocs>`__

   MARIO does not download GLORIA automatically. The expected workflow is to obtain the release locally and then point the parser to the release root, to the ``part_I`` economic-account folder, or directly to the ``GLORIA_MRIOs_*`` directory.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: GLORIA release root, the Google Drive ``part_I`` economic-account folder, or directly the ``GLORIA_MRIOs_*`` directory;
   - ``table``: currently only ``"SUT"`` is supported;
   - ``valuation``: choose one markup branch such as ``basic``, ``trade``, ``transport``, ``taxes``, or ``subsidies``;
   - ``year``: used when the selected root contains more than one GLORIA year;
   - ``regions``: optional subset of GLORIA region acronyms;
   - ``satellites``: optional satellite group or row selector;
   - ``dtype``: numeric storage type, with ``float32`` as the practical default;
   - ``cache``: ``True`` or one explicit path to persist the parsed result.

.. mario-details:: Local layout expectation

   The parser supports two local layouts.

   Compact layout:

   - one ``GLORIA_MRIOs_*`` directory with raw ``T``, ``Y``, and ``V`` csv files;
   - the matching ``GLORIA_ReadMe_*.xlsx`` workbook next to that dataset;
   - optionally, one matching ``GLORIA_SatelliteAccounts_*`` directory.

   Google Drive layout:

   - one ``GLORIA_MRIO_Loop*_part_I_MRIOdatabase`` folder containing the economic-account dataset;
   - one ``GLORIA_MRIO_Loop*_part_III_satelliteaccounts`` folder containing satellite accounts;
   - the matching ``GLORIA_ReadMe_*.xlsx`` workbook under the same release root.

   You can point MARIO to the release root, the ``part_I`` folder, or directly to one ``GLORIA_MRIOs_*`` directory.

   .. code:: python

      import mario

.. mario-details:: Parse one GLORIA SUT

   Use this when you want the default ``basic`` valuation and the full region set.

   .. code:: python

      db = mario.parse_gloria(
          path="/path/to/GLORIA",
          year=2023,
      )

      db

.. mario-details:: Restrict the satellite payload

   You can keep all satellites, one full row label, or one group name from the GLORIA ReadMe.

   .. code:: python

      db = mario.parse_gloria(
          path="/path/to/GLORIA",
          satellites="Emissions",
          year = 2023,
      )

      db

.. mario-details:: Practical warnings

   - ``GLORIA`` is currently ``SUT``-only in MARIO.
   - Full-region parses can be memory-intensive; ``regions=``, ``dtype="float32"``, and ``cache=True`` are usually sensible defaults.
   - If the local release does not include a complete satellite-account directory, MARIO falls back to empty extensions.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
