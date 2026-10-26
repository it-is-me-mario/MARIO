Scenarios
=========

MARIO stores *matrices* by *scenario*. Even when you work with a single *table*,
the related *database* is scenario-aware. 

NAM scenarios
-------------

NAM stores authoritative native flows. Clone a scenario, retrieve a copy of
a block and replace that block to change its payments:

.. code-block:: python

   # nam is an already parsed NAM database.
   nam.clone_scenario("baseline", "alternative")
   consumption = nam.get_block("CF_d", scenario="alternative")
   nam.set_block("CF_d", consumption * 1.01, scenario="alternative")
   coefficients = nam.resolve("cf_d", scenario="alternative")

``get_block`` returns a copy; editing it alone does not update the scenario.
``set_block`` replaces a complete native block and invalidates affected
derived caches. This example changes a payment; it does not propagate a
shock, rebalance the accounts or solve a behavioural model.

Use ``resolve(..., scenario=...)`` for NAM calculations. Dotted access uses
``baseline``. NAM keeps that baseline name fixed and does not implement
``query``, scenario renaming, ``update_scenarios`` or resets to coefficients.
Native Excel export preserves all scenarios. The exact supported interface
is in :doc:`the NAM database reference </reference/api_nam_database>`.

The remaining scenario workflows describe IOT/SUT.


Baseline and derived scenarios
------------------------------

Every *database* has a ``baseline`` *scenario*. Additional *scenarios* are created
when you:

* :doc:`clone </api_document/mario.Database.clone_scenario>` an existing *scenario*
* :doc:`apply shocks </user_guide/transformations/apply_shocks>` into a new *scenario*
* manually edit stored matrices through the manual workflow described in :doc:`apply shocks </user_guide/transformations/apply_shocks>`

Compatible parser runs can also populate new *scenarios* on the same
*database* instance.

Users may also
:doc:`rename the baseline </api_document/mario.Database.rename_baseline_scenario>`
to any public label they prefer.
This is safe: MARIO keeps the internal baseline storage consistent, exposes the
new public label through
:doc:`CoreModel.baseline_scenario_name </api_document/mario.CoreModel.baseline_scenario_name>`,
and still accepts ``"baseline"`` as a valid selector in scenario-aware methods.

If you want one uniform API for all scenarios, including the baseline, you can
also use :doc:`Database.rename_scenario </api_document/mario.Database.rename_scenario>`.
When the selected scenario is the baseline, it delegates to
``rename_baseline_scenario(...)``.

The main idea is simple: a *scenario* is another state of the same *table*,
not a different *database* class.

If a scenario already exists, you can still :doc:`update </api_document/mario.Database.update_scenarios>` selected stored *matrices*.
Such operation mutates an existing *scenario* and does not create a new one.
The manual workflow is documented in
:doc:`user guide: apply shocks </user_guide/transformations/apply_shocks>`.


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

.. note::

   Dotted access such as ``db.Z`` or ``db.X`` refers to the baseline
   scenario. To inspect or edit a non-baseline scenario, use
   :doc:`Database.query </api_document/mario.Database.query>` or
   ``get_block(..., scenario=...)`` instead.

If you want to check which *matrices* are available in the ``baseline`` (or any other) *scenario*:
 
.. code-block:: python

   db.list_matrices(scenario="baseline")



Common operations
-----------------

Typical scenario-related operations are:

* clone a scenario before applying a shock;
* rename the baseline to a different public label without breaking
  ``scenario="baseline"`` calls;
* rename a non-baseline scenario in place;
* update one or more *matrices* in an existing *scenario* and keep the rest implicit;
* compare a policy *scenario* against the baseline;
* reset *scenarios* to flows or coefficients before changing structural
  settings or before applying manual matrix updates.

For a complete worked explanation of
``clone_scenario(...) + reset_to_flows/reset_to_coefficients(...) + update_scenarios(...)``,
see :doc:`apply shocks </user_guide/transformations/apply_shocks>`.

.. important::

  Some structural operations rebuild a new ``baseline`` and discard the other
  stored *scenarios*, namely:

  * :doc:`Database.to_iot </api_document/mario.Database.to_iot>`;
  * :doc:`Database.add_sectors </api_document/mario.Database.add_sectors>`;
  * :doc:`Database.add_extensions </api_document/mario.Database.add_extensions>`;
  * :doc:`Database.to_single_region </api_document/mario.Database.to_single_region>`.
