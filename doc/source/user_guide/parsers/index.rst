Parsing guide
=============

This section is dedicated to MARIO's parsing methods.

Use it to learn how to ingest a custom database or a known database source. Each
page is a notebook-backed guide with the parser workflow, expected inputs,
supported versions, local-layout notes, and common caveats. Each parser page
also exposes a notebook download link at the bottom.


Custom databases
----------------

.. toctree::
   :maxdepth: 1

   Excel custom parser <../../notebooks/parsers/custom_database/from_excel>
   TXT, CSV, and Parquet custom parser <../../notebooks/parsers/custom_database/from_txt>
   Pymrio bridge <../../notebooks/parsers/custom_database/from_pymrio>


Environmentally-extended databases
----------------------------------

.. toctree::
   :maxdepth: 1

   EXIOBASE - Monetary version <../../notebooks/parsers/exiobase/monetary>
   EXIOBASE - Hybrid-units version <../../notebooks/parsers/exiobase/hybrid>
   EORA <../../notebooks/parsers/eora/walkthrough_eora>
   GLORIA <../../notebooks/parsers/gloria/walkthrough_gloria>
   GTAP <../../notebooks/parsers/gtap/walkthrough_gtap>
   EMERGING <../../notebooks/parsers/emerging/walkthrough_emerging>
   WIOD <../../notebooks/parsers/wiod/walkthrough_wiod>
   Asian Development Bank IO tables <../../notebooks/parsers/adb/walkthrough_adb>
   USEEIO v2.5 <../../notebooks/parsers/useeio/walkthrough_useeio>
   CEADS <../../notebooks/parsers/ceads/walkthrough_ceads>
   

Other MRIO and SRIO databases
-----------------------------

.. toctree::
   :maxdepth: 1

   OECD IO tables <../../notebooks/parsers/oecd/walkthrough_oecd>
   FIGARO <../../notebooks/parsers/figaro/walkthrough_figaro>
   EUROSTAT <../../notebooks/parsers/eurostat/walkthrough_eurostat>
   BEA <../../notebooks/parsers/bea/walkthrough_bea>
   ISTAT <../../notebooks/parsers/istat/walkthrough_istat>
   StatCan <../../notebooks/parsers/statcan/walkthrough_statcan>
   CEPALSTAT <../../notebooks/parsers/cepalstat/walkthrough_cepalstat>


Coverage query
--------------

Use the query below to check which parser/source combinations are available for
each country and time range.

Choose a country, a year, or both. The second selector updates itself to the
still-available values before you run the query.

.. raw:: html
   :file: _generated/coverage_query.html
