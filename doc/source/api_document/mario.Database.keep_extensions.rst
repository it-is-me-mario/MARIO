mario.Database.keep\_extensions
================================

.. currentmodule:: mario

.. automethod:: Database.keep_extensions

Call this before requesting multipliers when only a few satellite accounts are
needed. For example, on a database containing a ``CO2`` account:

.. code-block:: python

   db.keep_extensions(["CO2"])

   # One indicator row, instead of all original satellite accounts.
   multipliers = db.fc  # SUT; use db.f for an IOT.

To retain the original database:

.. code-block:: python

   reduced = db.keep_extensions(["CO2"], inplace=False)

Use the exact labels returned by ``db.get_index("Satellite account")``.
The operation applies to every scenario, including direct final-demand accounts
and already calculated satellite matrices. Economic and value-added matrices
are retained. Keeping fewer accounts reduces the number of indicator systems
to solve, but does not change the size or conditioning of the economic system.
