:page-type: Database guide
:summary: Import Chinese provincial multi-regional input-output tables.

CEADS
=====

.. container:: mario-companion

   :download:`Run the notebook <walkthrough_ceads.ipynb>`

Use a supported CEADS workbook. Optional province-level CO2 data needs an explicit mapping to the table.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_ceads(path="/path/to/MRIO2018.xlsx", format="auto", calc_all=False)

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Source pages

   - CEADS portal: `Input-Output Tables <https://www.ceads.net/data/input_output_tables/>`__
   - Scientific Data descriptor: `China’s Provincial Multi-Regional Input-Output Database for 2018 and 2020 <https://www.nature.com/articles/s41597-025-06543-y>`__
   - Dataset DOI: `10.6084/m9.figshare.29927291 <https://doi.org/10.6084/m9.figshare.29927291>`__

   MARIO does not download the CEADS workbook automatically. Download the workbook locally before running this notebook.

.. mario-details:: What MARIO currently parses

   The current backend is intentionally narrow:

   - it parses local Excel workbooks only;
   - it currently supports the verified CEADS provincial MRIO workbook family for ``2018`` and ``2020``;
   - it reads the English table sheet, not the Chinese one;
   - it uses the ``Sector`` and ``Province`` sheets as metadata support.

.. mario-details:: What `format` means

   ``format=`` is the parser-side layout selector. It does not mean “which CEADS dataset” you are using; it means “which workbook structure” MARIO should expect.

   At the moment, MARIO supports:

   - ``format="auto"``: inspect the workbook and resolve the known layout automatically;
   - ``format="ceads_provincial_workbook"``: force the verified 2018/2020 workbook structure.

.. mario-details:: Configure local paths

   Set ``MARIO_DOC_DATA`` to the root folder where you keep real parser datasets, or set ``MARIO_CEADS_PATH`` directly to the CEADS folder.

   Expected local structure:

   .. code:: text

      CEADS/
      ├── MRIO 2018.xlsx
      └── MRIO 2020.xlsx

   .. code:: python

      from pathlib import Path
      import os

      import mario

.. mario-details:: Parse one explicit workbook

   Use this form when you want to parse a specific downloaded workbook.

   .. code:: python

      db_2018 = mario.parse_ceads(
          path="/path/to/MRIO 2018.xlsx",
          format="auto",
          calc_all=False,
      )

      db_2018

.. mario-details:: Parse from a directory

   Use this form when one folder contains multiple CEADS workbooks. In that case, ``year=`` selects which workbook to parse.

   .. code:: python

      db_2020 = mario.parse_ceads(
          path="/path/to/MRIO 2020.xlsx",
          year=2020,
          calc_all=False,
      )

      db_2020

.. mario-details:: How the parsed table is mapped

   For the verified CEADS workbook family:

   - ``Z`` comes from the main intermediate-transactions block;
   - ``Y`` contains the domestic final-demand block plus one ``Exports`` column per province;
   - ``V`` contains ``Imports`` plus the four value-added rows exposed by the workbook;
   - ``E`` contains the optional ``CO2 (Mt)`` row when it exists;
   - ``EY`` is initialized at zero.

   .. code:: python

      db_2020["baseline"].keys()

.. mario-details:: Caveats

   - The CEADS portal lists older provincial MRIO releases too, such as ``2012``, ``2015``, and ``2017``. MARIO does not assume those older workbook families are compatible until they are checked explicitly.
   - The parser intentionally relies on the English worksheet. If only a Chinese worksheet is available, that workbook is not currently supported.
   - The workbook metadata sheets can contain minor naming inconsistencies. For the verified 2018/2020 family, MARIO treats the main transaction axis as canonical when such conflicts appear.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
