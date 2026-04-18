SUT to IOT
==========

This workflow covers the standard transformation of a SUT *database* into an
IOT one.

Core method
-----------

The relevant entry point is
:doc:`Database.to_iot </api_document/mario.Database.to_iot>`.

Typical use
-----------

.. code-block:: python

   db_iot = db.to_iot(method="B", inplace=False)

or, in place:

.. code-block:: python

   db.to_iot(method="B")

What changes
------------

This is a structural transformation, not a local matrix edit. After the
operation:

* the *table* type becomes `IOT`;
* the baseline matrices are rebuilt accordingly;
* non-baseline scenarios are discarded.

Checks after transformation
---------------------------

After the transformation, it is usually worth checking:

* the new table type;
* the available matrices in the new baseline;
* the resulting sector structure and final-demand labels.

For example:

.. code-block:: python

   db.table_type
   db.list_blocks()
   db.get_index("Sector")
   db.get_index("Consumption category")
