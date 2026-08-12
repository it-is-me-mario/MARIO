:page-type: Guide
:summary: Import the complete REX3 monetary IOT with its detailed GHG and LULUCF extension.

EXIOBASE REX3
=============

.. container:: mario-companion

   :download:`Download notebook <rex3.ipynb>`

Use the extracted REX3 economic tables, their labels and the mandatory GHG
companion. Point MARIO at their common root and select the year:

.. container:: mario-recipe

   .. code-block:: python

      from pathlib import Path
      import mario

      rex_root = Path("/path/to/REX3")
      db = mario.parse_exiobase(
          path=rex_root, table="IOT", unit="Monetary",
          variant="REX3", year=2022, calc_all=False,
      )

   .. container:: mario-result

      **Result** · The complete 189-region, 163-sector monetary IOT, with
      17 native environmental accounts and six detailed GHG/LULUCF accounts.
      Economic blocks remain in flow form; derived matrices are calculated
      only when requested.

Obtain and arrange the files
----------------------------

This parser uses two pinned Zenodo releases:

* `REX3 database, record 10354283 <https://zenodo.org/records/10354283>`_:
  download ``REX3_2022.zip`` and ``REX3_Labels.zip`` for the example above.
* `GHG extension (+LULUCF), record 14724086 <https://zenodo.org/records/14724086>`_:
  download ``GHG_data_REX3.zip``. The separate analysis-code archive is not
  required for importing the data.

These pinned releases use **CC BY 4.0**. Credit the source authors and indicate
changes; REX3 retains its own terms independently of standard EXIOBASE releases.

The source covers 1995–2022. Extract the ZIP archives before local parsing.
Folder wrappers are allowed; for example::

   REX3/
   ├── Version REX3 database/
   │   ├── REX3_2022/
   │   │   ├── T_REX3.mat
   │   │   ├── Y_REX3.mat
   │   │   ├── Q_REX3.mat
   │   │   └── Q_Y_REX3.mat
   │   └── REX3_Labels/
   │       ├── Labels_Countries_REX3.mat
   │       ├── Labels_Sectors_REX3.mat
   │       ├── Labels_T_REX3.mat
   │       └── Labels_Q_REX3.mat
   └── Version GHG extension (+LULUCF)/
       └── GHG_data_REX3/
           ├── d_CC_REX3_timeline.mat
           ├── Q_LULUCF_REX3_timeline.mat
           ├── Q_Y_LULUCF_REX3_timeline.mat
           └── Labels/
               ├── Labels_years.mat
               └── Labels_Countrysector_combinations.mat

The archives contain additional source labels and notices; keep them with
the extracted data. Names of intermediate wrapper folders do not matter
when ``path`` is the common root. MARIO searches recursively for complete
bundles and requires an unambiguous labels/GHG match. For other arrangements,
pass ``labels_path=...`` and ``ghg_path=...`` explicitly; those arguments can
point to the companion itself or a wrapper containing it.

.. mario-details:: Download automatically

   :func:`~mario.download_exiobase_rex` downloads and extracts the selected
   year, shared labels and GHG companion. It uses the same resumable,
   checksum-checked Zenodo downloader as the other EXIOBASE releases.

   .. code-block:: python

      download_info = mario.download_exiobase_rex(rex_root, years=2022)

   Alternatively pass ``download=True`` to the parsing call. For manually
   arranged version folders, leave it at the default ``False`` to use those
   extracted files directly. The downloader's own layout places the three
   bundles directly under its destination root. Existing extracted bundles
   are reused; ``overwrite=True`` requests a fresh download/extraction.

Accounts and interpretation
---------------------------

MARIO imports ``T_REX3`` as ``Z`` and ``Y_REX3`` as ``Y``, retaining every
country-sector pair. The value-added row in ``Q_REX3`` becomes ``V``; the
remaining rows become ``E`` and ``EY`` with their published units. Output
used for the detailed extension is calculated from the complete table as
``Z.sum(axis=1) + Y.sum(axis=1)`` before constructing the database.

Coal, oil, gas, biogenic and calcination GHG flows are reconstructed from the
five published ``d_CC`` coefficient rows multiplied by output. LULUCF uses
the published absolute ``Q_LULUCF`` and ``Q_Y_LULUCF`` accounts instead of
coefficient reconstruction, retaining flows assigned to zero-output sectors.
The supplemental year and country-sector labels must match the economic
bundle. The native aggregate climate-change row is also retained separately;
its scope and the detailed source reconstruction need not coincide exactly.

The ``rex3`` database profile identifies these already characterised CO2eq
rows separately from standard monetary EXIOBASE. To sum the six detailed
sources, including LULUCF, without adding the overlapping native aggregate:

.. code-block:: python

   db.calc_ghg(profile="rex3", label="GHG detailed sources")

Changing ``ipcc_report`` or ``time_horizon`` does not recharacterise these
source CO2eq accounts. Use an explicit label describing the chosen inventory.
No standard EXIOBASE classification concordance is assumed for REX3.

Memory and calculation scope
----------------------------

The full transaction matrix contains 30,807 × 30,807 entries, about 7.1 GiB
in float64 before final demand, extensions and model overhead. Regional
slicing during import is not supported: removing trade blocks before output
and GHG reconstruction would change the source inventory. Use
``calc_all=False`` for the initial import and enough RAM for the full table.

The parser selects the shared solve-based compute preset for the current
session, preferring optional UMFPACK and falling back to SciPy when it is
unavailable. An explicitly requested inverse remains a large calculation.
See :doc:`../../../user_guide/advanced/compute_settings` for the available
solver options.

Full interfaces: :func:`~mario.parse_exiobase_rex`,
:func:`~mario.parse_exiobase` and :func:`~mario.download_exiobase_rex`.
