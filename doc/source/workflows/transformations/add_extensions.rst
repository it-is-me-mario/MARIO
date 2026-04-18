Add Extensions
==============

This workflow covers how to append new environmental extensions or value-added
rows to an existing database.

Core methods
------------

The main entry points are:

* :doc:`Database.get_extensions_excel </api_document/mario.Database.get_extensions_excel>` to export the expected template;
* :doc:`Database.add_extensions </api_document/mario.Database.add_extensions>` to insert the new rows.

Typical use
-----------

The usual flow is:

* export the template for ``E`` or ``V``;
* fill the new rows and their units;
* apply the update to the database.

For example:

.. code-block:: python

   db.get_extensions_excel(matrix="E", path="extensions.xlsx")

   db.add_extensions(
       io="extensions.xlsx",
       matrix="E",
       units=units_df,
   )

What changes
------------

This is not a local scenario-only edit. MARIO rewrites the ``baseline`` with
the extended matrix and discards the other scenarios.

Checks after extension
----------------------

After insertion, it is worth checking:

* the updated extension labels;
* the associated units table;
* the availability of the recomputed dependent matrices.
