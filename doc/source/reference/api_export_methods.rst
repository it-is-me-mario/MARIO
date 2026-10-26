Exports
=======

These methods write MARIO databases or scenarios to external formats.

NAM supports native-flow Excel export through ``nam.to_excel(path)``. Its
layouts, block states and scenarios are retained; derived caches are
recomputed after reload. See :doc:`api_nam_database` for the NAM signature.
The generic ``export`` dispatcher, TXT/CSV, Parquet and pymrio exports below
currently apply to IOT/SUT.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.Database.export
   ../api_document/mario.Database.to_excel
   ../api_document/mario.Database.to_txt
   ../api_document/mario.Database.to_parquet
   ../api_document/mario.Database.to_pymrio
