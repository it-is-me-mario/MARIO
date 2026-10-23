:page-type: Database guide
:summary: Import national supply-use or input-output tables through the supported Eurostat datasets.

Eurostat
========

.. container:: mario-companion

   :download:`Download notebook <walkthrough_eurostat.ipynb>`

This call retrieves source data. For IOTs, select the product or industry system explicitly; availability varies by country and year.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_eurostat(country="IT", year=2022, table="SUT")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Key arguments

   The key public arguments are:

   - ``country``: Eurostat geo code such as ``IT`` or ``DE``
   - ``year``: reference year to parse
   - ``table``: choose ``"SUT"`` or ``"IOT"``
   - ``iot_mode``: IOT-only selector, either ``"product"`` or ``"industry"``
   - ``unit``: choose ``"MIO_EUR"`` or ``"MIO_NAC"``
   - ``path``: optional local cache directory for raw SDMX CSV files
   - ``download``: when ``True``, MARIO stores the raw CSV locally before parsing it

.. mario-details:: Available years

   Year availability depends on the country and on the table family.

   - Official Eurostat metadata states that national ``SUT`` annual tables are published from ``2010`` onward.
   - Official Eurostat metadata also states that national ``IOT`` tables are published from ``2010`` onward, but mandatory transmission is only for years ending in ``0`` or ``5``.
   - Additional ``IOT`` years depend on voluntary country transmission.

   On the live official API, checked on **18 April 2026** with **Italy (``IT``)** as one concrete example, MARIO currently finds:

   - ``SUT``: ``2010`` to ``2022``
   - ``IOT``: ``2010`` and then ``2015`` to ``2022``

   So for ``SUT`` you should expect a broadly annual series, while for ``IOT`` you should treat ``2010``, ``2015``, and ``2020`` as the core mandatory years and any extra years as country-specific.

.. mario-details:: Relevant source pages and local cache

   Relevant official pages:

   - `ESA supply, use and input-output tables <https://ec.europa.eu/eurostat/web/esa-supply-use-input-tables>`__
   - `Eurostat metadata for ``naio_10_n`` <https://ec.europa.eu/eurostat/cache/metadata/en/naio_10_n_esms.htm>`__
   - `Eurostat API introduction <https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction>`__

   ``path`` is optional and, when provided, acts as a raw SDMX cache:

   .. code:: text

      EUROSTAT/
      └── cache/
          ├── NAIO_10_CP15_*.csv
          ├── NAIO_10_CP16_*.csv
          ├── NAIO_10_CP1700_*.csv
          └── NAIO_10_CP1750_*.csv

   If ``download=False``, MARIO reads directly from the API. If ``download=True``, MARIO stores the raw slices under ``path`` before building the database.

   .. code:: python

      import mario

.. mario-details:: Parse a SUT directly from the API

   .. code:: python

      db = mario.parse_eurostat(
          country="IT",
          year=2022,
          table="SUT",
      )

      db

.. mario-details:: Parse an IOT

   .. code:: python

      db = mario.parse_eurostat(
          country="IT",
          year=2022,
          table="IOT",
          iot_mode="product",
      )

      db

.. mario-details:: Optional raw download and cache

   .. code:: python

      mario.download_eurostat(
          path="/path/to/SUT",
          country="IT",
          year=2022,
          table="SUT",
      )

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
