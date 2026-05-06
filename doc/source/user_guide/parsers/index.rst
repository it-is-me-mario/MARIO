Parsers
=======

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
   pymrio bridge <../../notebooks/parsers/custom_database/from_pymrio>


Environmentally-extended databases
----------------------------------

.. toctree::
   :maxdepth: 1

   Monetary EXIOBASE <../../notebooks/parsers/exiobase/monetary>
   Hybrid EXIOBASE <../../notebooks/parsers/exiobase/hybrid>
   GLORIA <../../notebooks/parsers/gloria/walkthrough>
   Eora <../../notebooks/parsers/eora/walkthrough>
   EMERGING <../../notebooks/parsers/emerging/walkthrough>
   WIOD <../../notebooks/parsers/wiod/walkthrough>
   ADB <../../notebooks/parsers/adb/walkthrough>
   USEEIO <../../notebooks/parsers/useeio/walkthrough>
   CEADS <../../notebooks/parsers/ceads/walkthrough>
   GTAP <../../notebooks/parsers/gtap/walkthrough>


Other MRIO and SRIO databases
-----------------------------

.. toctree::
   :maxdepth: 1

   OECD <../../notebooks/parsers/oecd/walkthrough>
   FIGARO <../../notebooks/parsers/figaro/walkthrough>
   EUROSTAT <../../notebooks/parsers/eurostat/walkthrough>
   BEA <../../notebooks/parsers/bea/walkthrough>
   ISTAT <../../notebooks/parsers/istat/walkthrough>
   StatCan <../../notebooks/parsers/statcan/walkthrough>


Coverage query
--------------

Use the query below to check which parser/source combinations are available for
each country and time range.

Choose a country, a year, or both. The second selector updates itself to the
still-available values before you run the query.

.. raw:: html
   :file: _generated/coverage_query.html
