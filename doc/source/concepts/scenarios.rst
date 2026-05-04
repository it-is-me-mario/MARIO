Scenarios
=========

MARIO stores *matrices* by *scenario*. Even when you work with a single *table*,
the related *database* is scenario-aware. 


Baseline and derived scenarios
------------------------------

Every *database* has a ``baseline`` *scenario*. Additional *scenarios* are created
when you:

* :doc:`clone </api_document/mario.Database.clone_scenario>` an existing *scenario*
* :doc:`apply shocks </user_guide/transformations/apply_shocks>` into a new *scenario*

The main idea is simple: a *scenario* is another state of the same *table*,
not a different *database* class.

If a scenario already exists, you can still :doc:`update </api_document/mario.Database.update_scenarios>` selected stored *matrices*.
Such operation mutates an existing *scenario* and does not create a new one.


What is stored in a scenario
----------------------------

*Scenario* storage is *matrix*-based. MARIO does not need to materialize every
possible *matrix* for every *scenario*.

Instead, each *scenario* stores the *matrices* that are parsed or have
been explicitly computed. Missing matrices can still be rebuilt on demand.

This matters because:

* *scenarios* stay lighter than a full eager copy of every *matrix*
* users can choose whether to keep flows or coefficients after an operation
* derived quantities can be recomputed consistently from the *scenario* state

If you want to check which *matrices* are available in the ``baseline`` (or any other) *scenario*:
 
.. code-block:: python

   db.list_matrices(scenario="baseline")



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
  stored *scenarios*, namely:

  * :doc:`Database.to_iot </api_document/mario.Database.to_iot>`;
  * :doc:`Database.add_sectors </api_document/mario.Database.add_sectors>`;
  * :doc:`Database.add_extensions </api_document/mario.Database.add_extensions>`;
  * :doc:`Database.to_single_region </api_document/mario.Database.to_single_region>`.
