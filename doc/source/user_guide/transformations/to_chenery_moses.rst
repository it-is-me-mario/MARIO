To Chenery-Moses
================

This workflow covers the conversion of an Isard SUT into a Chenery-Moses SUT.

Core method
-----------

The relevant entry point is
:doc:`Database.to_chenery_moses </api_document/mario.Database.to_chenery_moses>`.

Typical use
-----------

.. code-block:: python

   db.to_chenery_moses()

or, if you want to keep the original object unchanged:

.. code-block:: python

   db_cm = db.to_chenery_moses(inplace=False)

You can also limit the operation to selected scenarios:

.. code-block:: python

   db.to_chenery_moses(scenarios=["baseline", "policy"])

What changes
------------

This transformation updates the relevant SUT matrices for the selected
scenarios and then resets those scenarios to flow matrices so coefficient-side
blocks can be rebuilt consistently on demand.

Checks after transformation
---------------------------

After the conversion, it is usually worth checking:

* the transformed ``Z`` and ``Y`` matrices;
* the available stored matrices in the affected scenarios;
* whether the database now satisfies the Chenery-Moses structure you expect.
