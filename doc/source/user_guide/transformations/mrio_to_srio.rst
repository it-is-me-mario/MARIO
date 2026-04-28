MRIO to SRIO
============

This workflow covers the standard reduction of a multi-regional database to a
single-region one.

Core method
-----------

The relevant entry point is
:doc:`Database.to_single_region </api_document/mario.Database.to_single_region>`.

Typical use
-----------

.. code-block:: python

   db.to_single_region("Italy")

or, if you want to keep the original object unchanged:

.. code-block:: python

   db_it = db.to_single_region("Italy", inplace=False)

What changes
------------

This operation rebuilds a new ``baseline`` around the selected region:

* only one region is kept;
* imports are consolidated into value added;
* exports are represented inside final demand;
* non-baseline scenarios are discarded.

Checks after transformation
---------------------------

After reducing the database, it is usually worth checking:

* the remaining region label;
* the updated value-added and final-demand labels;
* the available stored matrices in the new baseline.

For example:

.. code-block:: python

   db.get_index("Region")
   db.get_index("Factor of production")
   db.get_index("Consumption category")
   db.list_blocks()

Notebook walkthrough
--------------------

Use the notebook below as the main MRIO-to-SRIO guide:

* :doc:`MRIO to SRIO walkthrough <../../notebooks/user_guide/transformations/mrio_to_srio>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the MRIO-to-SRIO notebook <../../notebooks/user_guide/transformations/mrio_to_srio.ipynb>`
