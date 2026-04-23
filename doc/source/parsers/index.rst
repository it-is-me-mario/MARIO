Parsers
=======

This section is the dedicated to MARIO's parsing methods.

Use it to learn how to ingest a custom database or a known database source. Each
page will describe expected inputs, supported versions, common caveats and the
recommended tutorial or workflow to follow next.


Custom databases
----------------

.. toctree::
   :maxdepth: 1

   from_excel
   from_txt_parquet
   from_pymrio


Environmentally-extended databases
----------------------------------

.. toctree::
   :maxdepth: 1

   exiobase
   gloria
   eora
   emerging
   gtap
   wiod
   adb
   useeio
   ceads


Other MRIO and SRIO databases
-----------------------------

.. toctree::
   :maxdepth: 1

   oecd
   figaro
   eurostat
   cepalstat
   bea
   istat
   statcan


Coverage query
--------------

Use the query below to check which parser/source combinations are available for
each country and time range.

Choose a country, a year, or both. The second selector updates itself to the
still-available values before you run the query.

.. raw:: html
   :file: _generated/coverage_query.html
