:page-type: Database guide
:summary: Import Italian national supply-use and input-output tables.

ISTAT
=====

.. container:: mario-companion

   :download:`Download notebook <walkthrough_istat.ipynb>`

This example downloads the selected edition. Choose the table, valuation and industry or product system before comparing results.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_istat(
          path="istat_cache", year=2022, table="IOT", iot_mode="product",
          download=True, edition="latest",
      )

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source page

   - Official ISTAT tag page: `ISTAT sistema input-output <https://www.istat.it/tag/sistema-input-output/>`__

   This parser targets the official ISTAT release bundles, not arbitrary spreadsheets with a similar shape.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: local workbook, extracted release directory, release zip, or cache directory;
   - ``year``: reference year to select from the ISTAT release;
   - ``table``: choose ``"IOT"`` or ``"SUT"``;
   - ``iot_mode``: for ``IOT``, either ``"product"`` or ``"industry"``;
   - ``level``: for ``SUT``, either ``"63"`` or ``"20"``;
   - ``price``: for ``SUT``, either ``"current"`` or ``"pyp"``;
   - ``valuation``: for ``SUT``, either ``"basic"`` or ``"purchaser"``;
   - ``download``: when ``True``, MARIO downloads the official release before parsing it;
   - ``edition`` and ``page_url``: downloader selectors for the official ISTAT release page.

.. mario-details:: `IOT` versus `SUT`

   Use ``table="IOT"`` when you want the symmetric representation with ``Z``, ``Y``, and ``V``.

   Use ``table="SUT"`` when you want the native split structure with ``S``, ``U``, ``Yc``, ``Ya``, ``Va``, and ``Vc``.

   For ``IOT``, the key selector is ``iot_mode=``. For ``SUT``, the key selectors are ``level=``, ``price=``, and ``valuation=``.

.. mario-details:: Workbook, extracted directory, or zip archive

   For ``IOT``, passing the workbook directly is often the simplest workflow.

   For ``SUT``, passing the extracted release directory or the release zip is usually more convenient, because MARIO resolves the required workbook triplet from the official file names.

.. mario-details:: Download workflow

   If you already have the official release locally, point the parser to the workbook, directory, or zip file.

   If you want MARIO to fetch the official release first, use ``download=True`` together with a cache directory in ``path``.

.. mario-details:: Expected local release layout

   Typical local structure:

   .. code:: text

      ISTAT/
      ├── input_output_2015_2020.zip
      ├── input_output_2020_2022.zip
      └── extracted_release/
          ├── *.xlsx
          └── *.xls

   For local parsing, the workbook names and sheets must come from the official ISTAT release. For ``download=True``, ``path`` is the cache directory where MARIO stores the downloaded archive and extracted files. The direct helper is ``mario.download_istat_io(...)``.

   .. code:: python

      import mario

.. mario-details:: Parse one local `IOT` workbook

   This is the simplest ``IOT`` workflow. If you haven’t downloaded it, you can indicate a folder path and download=True

   .. code:: python

      db = mario.parse_istat(
          path="/path/to/IOT",
          year=2022,
          table="IOT",
          iot_mode="product",
          download=True,
          edition="latest",
      )

.. mario-details:: Parse one `SUT` release

   The ``SUT`` workflow needs the structural selectors explicitly.

   .. code:: python

      db = mario.parse_istat(
          path="/path/to/SUT",
          year=2022,
          table="SUT",
          level="63",
          price="current",
          valuation="basic",
          download=True,
          edition="latest",
      )

      db

.. mario-details:: First inspection

   Once the release is parsed, the normal MARIO inspection helpers work exactly as for the other parsers.

   .. code:: python

      db.table_type

   .. code:: python

      db.activities

   .. code:: python

      db.units

.. mario-details:: Caveats

   - the parser expects the official ISTAT workbook and release naming conventions;
   - ``SUT`` parsing has more structural selectors than ``IOT``, so explicit arguments are usually the better choice;
   - ``download=True`` is optional, but it is often the cleanest workflow when you want a stable local archive of the release.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
