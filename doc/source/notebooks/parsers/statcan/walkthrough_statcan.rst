:page-type: Database guide
:summary: Import Canadian national or provincial supply-use and input-output tables.

Statistics Canada
=================

.. container:: mario-companion

   :download:`Download notebook <walkthrough_statcan.ipynb>`

Choose geography and detail level. The retrieval workflow requires source access unless the necessary files are already cached.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_statcan(year=2022, table="SUT", level="summary", geo="Canada")

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant source pages

   - Official StatCan SUT catalogue: `Supply and use tables <https://www150.statcan.gc.ca/n1/en/catalogue/36100478>`__
   - Official StatCan IOT catalogue: `Symmetric input-output tables <https://www150.statcan.gc.ca/n1/en/catalogue/36100001>`__
   - StatCan WDS documentation: `WDS user guide <https://www.statcan.gc.ca/en/developers/wds/user-guide>`__

   MARIO can query the official WDS API directly, so there is no need to download the raw ``.csv`` bundles manually unless you want a local cache.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``year``: reference year to parse;
   - ``table``: choose ``"SUT"`` or ``"IOT"``;
   - ``level``: choose ``summary``, ``detail``, or ``link1997`` when supported;
   - ``geo``: geography label such as ``Canada`` or one province/territory;
   - ``valuation``: only for ``IOT``, usually ``basic`` or ``purchaser``;
   - ``path``: optional directory for locally cached raw files;
   - ``download``: when ``True``, MARIO downloads the raw WDS bundle into ``path`` and then parses it locally.

.. mario-details:: `SUT` versus `IOT`

   Use ``table="SUT"`` when you want the native split structure with ``S``, ``U``, ``Yc``, ``Ya``, ``Va``, and ``Vc``.

   Use ``table="IOT"`` when you want the symmetric input-output representation with ``Z``, ``Y``, and ``V``.

   For ``SUT``, ``level="link1997"`` is also available. For ``IOT``, ``valuation=`` matters because the tables are exposed at both basic and purchaser prices.

.. mario-details:: Direct online parsing versus local cache

   Use direct online parsing when you just want the database and do not need the raw files afterwards.

   Use ``download=True`` together with ``path=...`` when you want MARIO to keep the raw WDS ``.csv`` bundle locally. This is the most useful option when you parse the same StatCan table repeatedly or want a reproducible local cache.

.. mario-details:: Cache layout and supported values

   ``path`` is optional and acts as a local WDS cache:

   .. code:: text

      StatCan/
      └── cache/
          ├── 36-10-0438-01_*.csv
          └── 36-10-0001-01_*.csv

   Supported levels:

   - ``SUT``: ``summary``, ``detail``, ``link1997``;
   - ``IOT``: ``summary``, ``detail``.

   For ``IOT``, ``valuation`` can be ``basic`` or ``purchaser``.

   .. code:: python

      import mario

.. mario-details:: Parse a Canada `SUT` directly from WDS

   This is the simplest StatCan workflow.

   .. code:: python

      db = mario.parse_statcan(
          year=2022,
          table="SUT",
          level="summary",
          geo="Canada",
      )

      db

.. mario-details:: Parse a provincial `SUT`

   The ``SUT`` tables expose provinces and territories as separate geographies. The parser expects the published StatCan geography label.

   .. code:: python

      db = mario.parse_statcan(
          year=2022,
          table="SUT",
          level="detail",
          geo="Ontario",
      )

      db

.. mario-details:: Parse an `IOT` at basic prices

   For ``IOT``, pass ``valuation="basic"`` or ``valuation="purchaser"``.

   .. code:: python

      db = mario.parse_statcan(
          year=2022,
          table="IOT",
          level="detail",
          valuation="basic",
      )

      db

.. mario-details:: Parse an `IOT` at purchaser prices

   The public API stays the same; only the ``valuation`` selector changes.

   .. code:: python

      db = mario.parse_statcan(
          year=2022,
          table="IOT",
          level="summary",
          valuation="purchaser",
      )

      db

.. mario-details:: Keep the raw WDS files locally

   When ``download=True``, MARIO stores the downloaded raw ``.csv`` bundle inside ``path`` and then parses the local file. This is useful when you want to avoid re-downloading the same table.

   .. code:: python

      db = mario.parse_statcan(
          year=2022,
          table="SUT",
          level="detail",
          geo="Quebec",
          path="/path/to/StatCan",
          download=True,
      )

      db

.. mario-details:: Caveats

   - the parser is API-driven, so network availability matters more than for local-file parsers;
   - ``download=True`` is optional, not required;
   - this walkthrough focuses on the economic StatCan tables only;
   - environmental extensions are intentionally left out here.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
