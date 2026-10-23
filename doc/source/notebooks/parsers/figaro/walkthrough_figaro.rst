:page-type: Database guide
:summary: Import Eurostat’s inter-country supply-use or input-output tables.

FIGARO
======

.. container:: mario-companion

   :download:`Download notebook <walkthrough_figaro.ipynb>`

The parser uses Eurostat data and a local cache. Select table type and, for IOTs, the product or industry system.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_figaro(table="SUT", year=2022, path="figaro_cache")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Source links

   - `FIGARO data and releases <https://ec.europa.eu/eurostat/web/esa-supply-use-input-tables/database>`__
   - `FIGARO methodology and classifications <https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_fcp_esms.htm>`__
   - `Eurostat Statistics API <https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction>`__
   - `Eurostat reuse terms <https://ec.europa.eu/eurostat/help/copyright-notice>`__

   FIGARO IOT values are in **million EUR at current basic prices**. Products follow CPA 2.1 and activities NACE Rev.2. Browser monetary values are converted to current USD using same-year exchange rates. Derived calculations must credit Eurostat; Eurostat is not responsible for these calculations.

.. mario-details:: Dataflow groups

   The parser selects the dataflow suffix from ``year``:

   - ``2010``-``2013``: ``s1``, ``u1``, ``ip1``, ``ii1``
   - ``2014``-``2017``: ``s2``, ``u2``, ``ip2``, ``ii2``
   - ``2018``-``2021``: ``s3``, ``u3``, ``ip3``, ``ii3``
   - ``2022`` onwards: ``s4``, ``u4``, ``ip4``, ``ii4``

   For example, a 2022 SUT uses ``naio_10_fcp_s4`` and ``naio_10_fcp_u4``.

   Supply flows use a single ``geo`` dimension: MARIO places domestic production on the same region on both axes of ``S``. Use and IOT flows retain their origin and destination dimensions.

.. mario-details:: Key arguments

   - ``table``: choose ``"SUT"`` or ``"IOT"``.
   - ``year``: reference year, required; this is separate from the dataset edition.
   - ``path``: optional directory of normalized API-cache CSVs and JSON sidecars. Matching caches are reused; missing requests are downloaded into that directory.
   - ``countries``: optional FIGARO country-code selection; keep it consistent with the cached request. A subset is not a complete global MRIO.
   - ``iot_mode``: ``"product"`` → ``pxp``; ``"industry"`` → ``ixi``; ``"auto"`` defaults to product. This is an IOT system, separate from table format.
   - ``unit``: Eurostat monetary unit, currently ``"MIO_EUR"``.

.. mario-details:: Local caches and API requests

   MARIO checks ``path=`` for a matching cache before calling the API. The cache key includes the dataflow, year, monetary unit, country selection and factor-row selection; keep the original cache filenames. ``path`` is a cache directory, not a single CSV path.

   Without a matching cache, MARIO chunks requests by ``c_orig`` to respect Eurostat extraction limits. Full tables are large, so country subsets can help during development; they do not replace the full global parse used in the browser.

   The DOM/W2 rows supply the factor matrix ``V``. For GDP, sum D1 + D29X39 + B2A3G and add net product taxes D21X31 on **intermediate and final uses**. The IOT parser retains intermediate taxes in ``V``; the browser independently reads final-use taxes from the same source cache. Residence-purchase adjustment rows are excluded from this income calculation.

   .. code:: python

      import mario

.. mario-details:: Parse a FIGARO SUT

   Point ``path`` to the directory containing matching supply and use API caches. If either cache is absent, MARIO downloads that request.

   .. code:: python

      db_sut = mario.parse_figaro(
          table="SUT",
          year=2022,
          path="/path/to/figaro/sut_directory"
      )

      db_sut

   .. code:: python

      db_sut

.. mario-details:: Parse a FIGARO IOT

   The local series uses ``iot_mode="product"`` (pxp). Change ``year`` and select its cache directory to read another annual table. ``industry`` (ixi) is supported by MARIO but is not present in the supplied local IOT inventory.

   .. code:: python

      db_iot = mario.parse_figaro(
          table="IOT",
          year=2022,
          iot_mode="product",
          path="/path/to/figaro/iot_directory",
          calc_all=False,
      )

      db_iot

.. mario-details:: First inspection

   Once parsed, the result is a standard MARIO database.

   .. code:: python

      db_sut.get_index("Region")[:5]

   .. code:: python

      db_sut.get_index("Activity")[:5]

   .. code:: python

      db_sut.get_index("Commodity")[:5]

.. mario-details:: Practical notes

   - ``ip1``–``ip4`` and ``ii1``–``ii4`` partition reference years; their suffixes are not database versions.
   - Preserve cache filenames and the original country selection. ``countries=`` changes the request key.
   - The public browser groups identical native sets into one Excel inventory; equal coverage does not mean equal annual values.
   - No GHG indicator is inferred from monetary factors or MARIO placeholder extension rows. Environmental accounts require separate source files.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
