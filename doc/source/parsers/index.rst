Parsers
=======

This section is the entry point for MARIO's parser layer.

Use it when you need to ingest a custom database or a known public source. Each
page will describe expected inputs, supported versions, common caveats and the
recommended tutorial or workflow to follow next.

The parser documentation is organized in three groups:

* custom parsers for user-provided data structures;
* official national-accounts parsers driven by national statistical sources;
* supranational and multiregional databases maintained by larger projects or
  multi-country institutions.

Custom Parsers
--------------

.. toctree::
   :maxdepth: 1

   custom_database
   from_excel
   from_txt
   from_parquet
   from_pymrio

Official National Accounts
--------------------------

.. toctree::
   :maxdepth: 1

   istat
   statcan
   eurostat_sdmx

Supranational and Multiregional Databases
-----------------------------------------

.. toctree::
   :maxdepth: 1

   exiobase
   figaro
   wiod
   oecd
   gloria
   emerging
   gtap
   eora
   adb
