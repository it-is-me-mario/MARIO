Quickstart
==========

The quickest way to understand MARIO is to load one of the built-in test databases.

.. code-block:: python

   import mario

   db = mario.load_test("IOT")
   db

Inspect a few blocks:

.. code-block:: python

   db.Z
   db.Y
   db.V
   db.E

Run one simple workflow:

.. code-block:: python

   aggregated = db.aggregate(
       io="path/to/Aggregation.xlsx",
       ignore_nan=True,
       inplace=False,
   )

Or export the baseline scenario:

.. code-block:: python

   db.to_excel("database.xlsx")

If you want a worked notebook version of this flow, continue with
:doc:`../tutorials/index`.
