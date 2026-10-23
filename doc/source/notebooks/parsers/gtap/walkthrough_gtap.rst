:page-type: Database guide
:summary: Import a licensed local GTAP bundle into MARIO.

GTAP
====

.. container:: mario-companion

   :download:`Run the notebook <walkthrough_gtap.ipynb>`

The example selects a Power MRIO CSV bundle. Standard, GDX and alternative layouts require the matching options. Access to the source remains subject to its licence.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_gtap(
          path="/path/to/GTAP", table="IOT", variant="power",
          layout="MRIO", input_format="csv", calc_all=False,
      )

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source pages

   - GTAP portal: `GTAP at Purdue University <https://www.gtap.agecon.purdue.edu/>`__
   - The current parser support follows the **GTAP Power MRIO** workflow used in the current ``ENTICE``-related work behind MARIO’s narrow GTAP support.
   - MARIO does **not** download GTAP assets automatically. Access to the underlying files depends on your own GTAP data availability and licensing arrangement, and the supported GTAP Power MRIO bundle is not always distributed in a form that MARIO can parse directly.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: GTAP bundle directory, or one file inside that directory;
   - ``table``: currently only ``"IOT"`` is supported;
   - ``variant``: currently only ``"power"`` is supported;
   - ``layout``: currently only ``"MRIO"`` is supported;
   - ``input_format``: use ``"auto"``, ``"csv"``, or ``"gdx"``;
   - ``matrix_layouts`` (optional): ``{"V": ("Region", "Sector"), "E": ("Region", "Sector")}`` exposes factor and satellite rows as a semantic MultiIndex instead of the historical flat row names. The default (``None``) keeps the flat rows.

   .. code:: python

      import mario

.. mario-details:: Expected local layouts and caveats

   Typical local layouts are:

   For the CSV workflow:

   .. code:: text

      GTAP/
      `-- bundle/
          |-- GSDFSRCxDST.csv
          |-- GSDFXTAX.csv
          |-- GSDF.csv
          |-- GSDFEMI.csv
          `-- GSDFNRG.csv

   For the GDX workflow:

   .. code:: text

      GTAP/
      `-- bundle/
          |-- GSDFSRCxDST.gdx
          |-- GSDFXTAX.gdx
          |-- GSDF.gdx
          |-- GSDFEMI.gdx
          `-- GSDFNRG.gdx

   Practical caveats:

   - MARIO works with local GTAP bundles only;
   - ``input_format="auto"`` prefers the CSV bundle when both payloads are complete;
   - ``gdx`` parsing requires the GAMS Python API in the active environment, because MARIO reads the containers through ``gams.transfer`` (the pip package ``gamsapi[transfer]`` is sufficient);
   - recent CSV exports flatten several GDX symbols into one file, so the same record key can appear more than once (for example combustion and non-combustion emissions): duplicated keys are summed;
   - output- and value-added-based emission accounts, which the CSV export encodes with the ``SRC="TOT"`` placeholder, are captured as domestic satellite rows of the destination region (for example ``EMI_CH4_dms_QO``), mirroring how the GDX bundles store them. Any satellite record mass the parser cannot attribute is reported with a parser warning instead of being silently dropped;
   - process emissions are stored in a dedicated GDX symbol (``Emi_Proc``, parsed into ``E_P_*`` rows) that the CSV export does not carry as separate rows: its mass is included in the output-based accounts instead;
   - parsing is record-based and fast: a full GTAP Power MRIO CSV bundle (about 7 GB) parses end-to-end in the order of one to two minutes;
   - the current backend is intentionally narrow and should be presented as targeted GTAP Power ``MRIO`` support, not yet as generic support for all GTAP products.

.. mario-details:: Parse a CSV bundle

   Use this when the local folder contains the GTAP Power MRIO CSV payload and you want to be explicit about the selected format.

   .. code:: python

      db = mario.parse_gtap(
          path="/path/to/gtap_bundle",
          table="IOT",
          variant="power",
          layout="MRIO",
          input_format="csv",
          calc_all=False,
      )

.. mario-details:: Auto-detect the available payload

   Use ``input_format="auto"`` when you want MARIO to inspect the bundle directory and pick a supported payload automatically. If both payloads are present and complete, MARIO prefers the CSV workflow.

   .. code:: python

      db = mario.parse_gtap(
          path="/path/to/gtap_bundle",
          table="IOT",
          input_format="auto",
          calc_all=False,
      )

.. mario-details:: Parse a GDX bundle

   Use this when the available GTAP Power MRIO bundle is stored as GDX files and the active environment already includes the GAMS Python API.

   .. code:: python

      db = mario.parse_gtap(
          path="/path/to/gtap_bundle",
          table="IOT",
          input_format="gdx",
          calc_all=False,
      )

.. mario-details:: Optional structured row layouts

   By default the GTAP factor and satellite rows keep the historical flat string names, for example ``MTAX_AUS_GRO`` or ``EMI_CO2_AUS_COA``. Passing ``matrix_layouts`` exposes the same rows as a semantic ``(Region, Sector, item)`` MultiIndex instead — values are identical, only the index representation changes — and registers the matching block specifications on the database, like the Excel/parquet custom parsers do.

   Row families that do not have a region or a sector of their own carry the ``"TOTAL"`` sentinel on the levels that do not apply:

   +--------------------------------+-----------------------+----------------------------------------+
   | family                         | flat row name         | structured row                         |
   +================================+=======================+========================================+
   | import tariffs / trade margins | ``MTAX_AUS_GRO``      | ``("AUS", "GRO", "MTAX")``             |
   +--------------------------------+-----------------------+----------------------------------------+
   | export taxes                   | ``ETAX_AUS``          | ``("AUS", "TOTAL", "ETAX")``           |
   +--------------------------------+-----------------------+----------------------------------------+
   | production taxes               | ``PTAX_REG``          | ``("TOTAL", "TOTAL", "PTAX")``         |
   +--------------------------------+-----------------------+----------------------------------------+
   | value added / endowments       | ``VAAD_REG_Capital``  | ``("TOTAL", "TOTAL", "VAAD_Capital")`` |
   +--------------------------------+-----------------------+----------------------------------------+
   | input taxes                    | ``DTAX_REG_GRO``      | ``("TOTAL", "GRO", "DTAX")``           |
   +--------------------------------+-----------------------+----------------------------------------+
   | imported-input emissions       | ``EMI_CO2_AUS_COA``   | ``("AUS", "COA", "EMI_CO2")``          |
   +--------------------------------+-----------------------+----------------------------------------+
   | domestic-input emissions       | ``EMI_CO2_dms_COA``   | ``("TOTAL", "COA", "EMI_CO2_dms")``    |
   +--------------------------------+-----------------------+----------------------------------------+

   Two semantic notes:

   - on satellite rows, the Region level of the *import* accounts is the source region of the input (where the fuel came from), while the region where the emission occurs is always the column region. On *domestic* accounts the source coincides with the column region by definition, so those rows carry the ``"TOTAL"`` sentinel instead of duplicating the column information;
   - the sentinel is **not** part of the Region/Sector sets (``db.get_index("Region")`` only lists real regions), and aggregation maps labels with a keep-unmapped policy, so sentinel rows pass through aggregation untouched and no ``"TOTAL"`` entry is needed in aggregation mapping files.

   Only the full ``("Region", "Sector")`` layout is currently supported, and ``VY``/``EY`` must resolve to the same layout as ``V``/``E``.

   .. code:: python

      db = mario.parse_gtap(
          path="/path/to/gtap_bundle",
          table="IOT",
          input_format="auto",
          matrix_layouts={"V": ("Region", "Sector"), "E": ("Region", "Sector")},
          calc_all=False,
      )

      # factor and satellite rows are now semantic MultiIndexes:
      # db.V.index.names -> ["Region", "Sector", "Factor of production"]
      # db.E.index.names -> ["Region", "Sector", "Satellite account"]
      # db.get_index("Factor of production") -> ["MTAX", "ITTM", "ETAX", "PTAX", ...]

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
