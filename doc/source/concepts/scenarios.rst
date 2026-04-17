Scenarios
=========

MARIO stores *tables* data by *scenario*. Even when you work with a single baseline table,
the database is already scenario-aware. 


Baseline and derived scenarios
------------------------------

Every *database* has a ``baseline`` *scenario*. Additional *scenarios* are created
when you:

* :doc:`clone </api_document/mario.Database.clone_scenario>` an existing *scenario*
* :doc:`apply shocks </workflows/apply_shocks>` into a new *scenario*

The main idea is simple: a *scenario* is another state of the same *database*
structure, not a different *database* class.

If a scenario already exists, you can still :doc:`update </api_document/mario.Database.update_scenarios>` selected stored *matrices*.
Such operation mutates an existing *scenario* and does not create a new one.


What is stored
--------------

*Scenario* storage is *matrix*-based. MARIO does not need to materialize every
possible *matrix* for every *scenario*.

Instead, each *scenario* stores the *matrices* that are already available or have
been explicitly computed and cached. Missing matrices can still be rebuilt on
demand by the resolver.

This matters because:

* *scenarios* stay lighter than a full eager copy of every *matrix*;
* users can choose whether to keep flows or coefficients after an operation;
* derived quantities can be recomputed consistently from the *scenario* state.

If you want to check which *matrices* are available in the ``baseline`` *scenario*:
 
.. code-block:: python

   db.matrices['baseline']

This approach makes *scenario* workflows practical without forcing a full copy of
every *matrix* all the time.


Common operations
-----------------

Typical scenario-related operations are:

* clone a scenario before applying a shock;
* update one or more *matrices* in an existing *scenario* and keep the rest implicit;
* compare a policy *scenario* against the baseline;
* reset *scenarios* to flows or coefficients before changing structural
  settings.

.. important::

  Some structural operations rebuild a new ``baseline`` and discard the other
  stored *scenarios*. In the current implementation, this includes:

  * :doc:`Database.to_iot </api_document/mario.Database.to_iot>`;
  * :doc:`Database.add_sectors </api_document/mario.Database.add_sectors>`;
  * :doc:`Database.add_extensions </api_document/mario.Database.add_extensions>`;
  * :doc:`Database.to_single_region </api_document/mario.Database.to_single_region>`.
