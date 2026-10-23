:page-type: Database guide
:summary: Import an EMERGING MATLAB release, including the electricity-focused E variant.

EMERGING
========

.. container:: mario-companion

   :download:`Download notebook <walkthrough_emerging.ipynb>`

Choose the release, year and native variant together. The E variant needs its own input and variant selector; source CO2eq totals retain their original characterization.

**Full-database calculations:** install the optional UMFPACK backend.
See :doc:`installation and compute settings </user_guide/advanced/compute_settings>`.
The parser selects solve/direct, with a SciPy fallback when UMFPACK is unavailable.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_emerging(
          path="/path/to/EMERGING_V2_2023_m.mat", table="IOT",
      )

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Selecting a release

   Use ``variant="standard"`` for numbered releases and ``variant="E"`` for EMERGING-E. Point ``path=`` to the folder for the chosen version; the database profile above lists the verified years.

   Release records: `2.2 <https://doi.org/10.5281/zenodo.19461860>`__, `2.0 <https://doi.org/10.5281/zenodo.17557778>`__, `1.0 <https://doi.org/10.5281/zenodo.10956623>`__ and `EMERGING-E <https://doi.org/10.5281/zenodo.18303090>`__.

   The local 2.0 collection is incomplete. A companion CO2 file does not add an economic year without its matching MRIO bundle.

   For MATLAB v7.3 files, MARIO normalizes the stored axes while the economic matrix is sparse. No manual transpose of ``Z`` is needed.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: one EMERGING ``.mat`` file or a directory containing multiple yearly bundles;
   - ``table``: currently only ``"IOT"`` is supported;
   - ``year``: use it when one directory contains more than one EMERGING year;
   - ``regions``: optional ISO3 subset to keep only one manageable part of the database;
   - ``load_co2``: enable or disable automatic companion CO2 import;
   - ``co2_path``: explicit path to one companion CO2 file when auto-detection is not enough;
   - ``labels_path``: optional Excel workbook with explicit sector labels; for ``variant="E"`` it overrides workbook auto-detection next to the bundle;
   - ``variant``: keep ``"standard"`` for the original EMERGING releases and use ``"E"`` for the EMERGING-E power-disaggregated bundle.

.. mario-details:: Local file naming conventions

   In practice MARIO accepts these local naming conventions:

   - ``global_mrio_<year>.mat`` for ``v1.0``;
   - ``EMERGING_V2_<year>_m.mat`` for ``v2.x``;
   - ``EMERGING_V2_<year>.mat`` for older local ``v2.x`` copies when the internal MATLAB structure is still compatible;
   - ``EMERGING_E_<year>.mat`` for the EMERGING-E power-disaggregated variant.

   For local ``v2.x`` files, MARIO does not try to infer the exact sub-version ``2.0`` versus ``2.1`` versus ``2.2`` from the filename alone, because the public naming convention is shared across those releases.

.. mario-details:: Expected path structure

   ``path`` can point either to one yearly ``.mat`` file or to a directory containing the yearly EMERGING bundle and, optionally, the companion CO2 file.

   Typical directory layout:

   .. code:: text

      EMERGING/2.2/
      ├── EMERGING_V2_2023_m.mat
      └── EMERGING_CO2_2023.mat

   For the older ``v1.0`` naming convention, the economic bundle is typically named like ``global_mrio_<year>.mat``. For EMERGING-E, the local bundle is typically named like ``EMERGING_E_<year>.mat`` and may ship a sibling ``Figure data.xlsx`` workbook that MARIO uses to recover ISO3 region codes.

   When ``path`` is a directory, use ``year=`` to select the economic bundle. With ``load_co2=True``, MARIO first looks for the matching CO2 file in the same directory, for example ``EMERGING_CO2_2023.mat`` for ``year=2023``. Use ``co2_path=`` when the companion file is stored elsewhere or has a non-standard name.

.. mario-details:: Download workflow

   Use ``mario.download_emerging(...)`` when you want MARIO to fetch one of the supported official version records, including the newer ``version="E"`` EMERGING-E record.

   ``latest`` currently resolves to ``v2.2``.

   .. code:: python

      import mario

.. mario-details:: Download one official version explicitly

   .. code:: python

      mario.download_emerging(
          path="/path/to/2.2",
          version="2.2",
          years=[2023],
      )

.. mario-details:: Download the EMERGING-E record

   Use ``version="E"`` when you want MARIO to fetch the public EMERGING-E Zenodo record. With ``years=[2018]``, MARIO keeps the main ``.mat`` file and the companion ``Figure data.xlsx`` workbook used to recover ISO3 region codes.

   .. code:: python

      mario.download_emerging(
          path="/path/to/emerging-e",
          version="E",
          years=[2018],
      )

   Also for EMERGING-E, you can use the ``co2_path`` argument, passing the path of the CO2 emissions files from standard EMERGING releases.

.. mario-details:: Parse one local EMERGING bundle

   .. code:: python

      db = mario.parse_emerging(
          path="/path/to/EMERGING_V2_2023_m.mat",
          table="IOT",
      )

      db

.. mario-details:: Parse one local EMERGING-E bundle

   ``EMERGING-E`` is currently a local-file workflow. Use ``variant="E"`` and point ``path`` to ``EMERGING_E_<year>.mat``.

   .. code:: python

      db_e = mario.parse_emerging(
          path="/path/to/EMERGING_E_2018.mat",
          table="IOT",
          variant="E"
      )

      db_e

.. mario-details:: Parse from a directory and select one year

   .. code:: python

      db = mario.parse_emerging(
          path="/path/to/2.2",
          table="IOT",
          year=2023,
      )

      db

.. mario-details:: Restrict the region set

   The full EMERGING matrix is very large, so ``regions=`` is often the right first step.

   .. code:: python

      db = mario.parse_emerging(
          path="/path/to/2.2",
          table="IOT",
          year=2023,
          regions=["DEU", "FRA", "ITA"],
      )

      db

.. mario-details:: Control CO2 loading explicitly

   .. code:: python

      db = mario.parse_emerging(
          path="/path/to/2.2",
          table="IOT",
          year=2023,
          co2_path="/path/to/EMERGING_CO2_2023.mat",
      )

      db

.. mario-details:: Reading the economic and emissions accounts

   ``V`` contains the source value-added row, in current million US dollars. Sum its columns for a region or the whole model, and multiply by ``1e6`` when expressing the result in US dollars. The available bundles do not expose a separate, verified product-tax bridge, so the browser also presents the native ``va`` sum as a **GDP proxy**, without an invented tax adjustment. A note beneath the chart explains that equivalence to GDP at market prices is unverified.

   The standard companion files contain seven fossil CO2 accounts, one per fuel. MARIO imports them into ``E``, preserving the native unit and order. They are not a complete GHG inventory and do not supply direct final-demand emissions. The browser presents their sum as a **CO₂-only proxy under GHG**, with a visible caveat: CH₄, N₂O and F-gases are absent. The native Mt CO₂eq values are multiplied by ``1e6`` to obtain tonnes; CO₂ has GWP 1 under both AR5 and AR6. EMERGING-E in this collection has economic accounts only.

   - EMERGING currently supports ``IOT`` tables.
   - The containing release directory identifies 2.0 versus 2.2; their economic filenames are shared.
   - ``regions=`` can restrict the parse when the full model is unnecessary.
   - Use a same-year, same-release CO2 file. ``load_co2=False`` reads only the economic accounts.
   - ANT and SER retain historical grouping labels; TMP is the historical code mapped to TLS. Current memberships of the historical groups are not inferred.

   .. code:: python

      db.table_type

   .. code:: python

      db.get_index("Region")[:10]

   .. code:: python

      db.get_index("Satellite account")

   .. code:: python

      db.meta.source

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
