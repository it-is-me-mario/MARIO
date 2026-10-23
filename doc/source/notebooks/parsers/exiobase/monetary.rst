:page-type: Database guide
:summary: Import monetary input-output tables or the supported supply-use release.

EXIOBASE monetary
=================

.. container:: mario-companion

   :download:`Run the notebook <monetary.ipynb>`

Recent releases provide IOTs; monetary SUT parsing uses release 3.8.2. Check extension coverage by year: recent economic years can contain now-cast emissions rather than observed inventories.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_exiobase(
          path="/path/to/IOT_2024_ixi", table="IOT", unit="Monetary",
      )

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant Zenodo releases

   - `v3.11.2 (IOTs only) <https://doi.org/10.5281/zenodo.23039074>`__
   - `v3.10.2 (IOTs only) <https://doi.org/10.5281/zenodo.20051562>`__
   - `v3.10.1 (IOTs only) <https://doi.org/10.5281/zenodo.18937492>`__
   - `v3.9.6 (IOTs only) <https://doi.org/10.5281/zenodo.15689391>`__
   - `v3.9.5 (IOTs only) <https://doi.org/10.5281/zenodo.14869924>`__
   - `v3.9.4 (IOTs only) <https://doi.org/10.5281/zenodo.14614930>`__
   - `v3.8.2 (IOTs and SUTs available) <https://doi.org/10.5281/zenodo.5589597>`__

.. mario-details:: What changed in 3.11.2

   EXIOBASE 3.11.2 is a substantive data update rather than only a correction release. The main differences from 3.10.2 are:

   +---------------------------------+-------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------+
   | Area                            | 3.10.2                                                      | 3.11.2                                                                                                                   |
   +=================================+=============================================================+==========================================================================================================================+
   | Economic core                   | Source data through 2022                                    | Core SUT and product-output estimation rebuilt and extended through 2023                                                 |
   +---------------------------------+-------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------+
   | Energy and combustion emissions | Energy balances through 2022                                | Updated energy/emissions pipeline through 2023, with revised now-casting                                                 |
   +---------------------------------+-------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------+
   | Air emissions                   | Corrected non-fuel extension                                | Re-anchored to EDGAR v8.1; transport and bunker-fuel corrections; combustion sulfur reported as SO2; NF3 added from 1995 |
   +---------------------------------+-------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------+
   | Employment                      | Updated through 2022; extension name corrected              | Rebuilt against the new SUTs and distributed through 2024                                                                |
   +---------------------------------+-------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------+
   | Water and land                  | Water correction release; land source coverage through 2021 | Water accounts expanded and land accounts updated through 2023                                                           |
   +---------------------------------+-------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------+
   | Deforestation                   | Not included as a separate extension                        | Deforestation area and emissions added for 2001–2023                                                                     |
   +---------------------------------+-------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------+

   The release provides annual IOT archives from 1995 through 2024 in both ``ixi`` and ``pxp`` form. Extension availability varies by year: for example, the official 2023 archive contains the ``deforestation`` extension, while the 2024 archive omits extension families whose published series stop in 2023. MARIO discovers the directories present in each archive instead of assuming that every year has the same set.

.. mario-details:: CO2 coverage in the latest years

   Yes: the 3.11.2 ``IOT_2024_ixi`` archive contains populated ``CO2 - combustion - air`` and ``CO2_bio - combustion - air`` rows in both ``F`` and ``F_Y``. In a direct check of the official archives, the 3.10.2 2024 ``ixi`` bundle exposed those two combustion rows but filled them with zeroes; 3.11.2 contains non-zero values. Non-combustion CO2 rows are also available.

   The date on the archive and the observation year are not the same thing. According to the 3.11.2 release metadata, the energy, combustion-emission and non-fuel GHG source series reach 2023. Values in the 2024 archive are therefore **now-cast estimates**, not a fully observed 2024 emissions inventory. EXIOBASE explicitly recommends extra caution for now-cast years because they rely more heavily on interpolation and scaling.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``table``: choose ``"IOT"`` or ``"SUT"``
   - ``unit``: use ``"Monetary"``
   - ``path``: local EXIOBASE directory to parse
   - ``year``: optional metadata override, usually inferred from the payload
   - ``add_extensions``: monetary SUT-only helper to import extensions from a matching IOT

.. mario-details:: Local layout expectation

   The current monetary parsers expect the EXIOBASE dataset to be available as a local directory with the files required by the corresponding release. The parser auto-detects the layout and database version from the directory contents and metadata.

   For SUT parsing, extensions can be added by pointing ``add_extensions`` to the matching monetary IOT directory.

.. mario-details:: Local layout details and caveats

   ``path`` points to one extracted monetary EXIOBASE release.

   Typical layouts are:

   .. code:: text

      EXIOBASE/3.11.2/
      ├── IOT_2024_ixi/
      └── IOT_2024_pxp/

   .. code:: text

      EXIOBASE/3.8.2/
      └── MRSUT_2011/

   When ``download=True``, ``path`` becomes the destination/cache directory used by the downloader before parsing.

   Practical caveats:

   - monetary ``SUT`` parsing is currently available only for ``3.8.2``;
   - the newer supported monetary releases, including ``3.11.2``, are ``IOT``-only;
   - extension directories vary with source-year coverage and are auto-detected;
   - EXIOBASE 3.9 and later use a customized non-commercial CC-BY-SA-NC-derived license; check the license supplied with the dataset before use;
   - EXIOBASE 1 and 2 are not handled by this parser family.

   .. code:: python

      import mario

.. mario-details:: Optional download step

   If you do not already have the monetary dataset locally, MARIO can download the supported monetary releases directly from Zenodo.

   For IOT releases, you must specify the system (``"ixi"`` or ``"pxp"``).

   .. code:: python

      download_iot = mario.download_exiobase3(
          path="/path/to/3.11.2",
          years=[2024],
          table="IOT",
          system="ixi",
          version="3.11.2",
      )

   The SUT download path is currently available only for **3.8.2**.

   .. code:: python

      download_sut = mario.download_exiobase3(
          path="/path/to/3.8.2",
          years=[2019],
          table="SUT",
          version="3.8.2",
      )

.. mario-details:: Parse a monetary IOT

   Use this path when you have a monetary EXIOBASE input-output table already available locally.

   .. code:: python

      db_iot = mario.parse_exiobase(
          path="/path/to/IOT_2024_ixi",
          table="IOT",
          unit="Monetary",
          version="3.11.2",
          system="ixi",
      )

   The parsed satellite-account index can be inspected directly before selecting or aggregating greenhouse-gas rows:

   .. code:: python

      co2_rows = [
          row
          for row in db_iot.get_index("Satellite account")
          if str(row).startswith("CO2")
      ]
      co2_rows

.. mario-details:: Parse a monetary SUT

   Use this path when the source dataset is the monetary supply-use table.

   At the moment, this path is tied to EXIOBASE **3.8.2**.

   .. code:: python

      db_sut = mario.parse_exiobase(
          path="/path/to/MRSUT_2019",
          table="SUT",
          unit="Monetary",
      )

.. mario-details:: Add SUT extensions from the matching monetary IOT

   If you have both the monetary SUT and the corresponding monetary IOT, MARIO can read the extension blocks from the IOT and attach them to the SUT parse.

   .. code:: python

      db_eesut = mario.parse_exiobase(
          path="/path/to/MRSUT_2019",
          table="SUT",
          unit="Monetary",
          add_extensions="/path/to/IOT_2019_ixi",
      )

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
