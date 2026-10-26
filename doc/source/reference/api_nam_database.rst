:page-type: API reference
:summary: Supported NAM database operations, native-flow updates, scenarios and Excel persistence.

NAM database interface
======================

**Table format: NAM.** The public parsers return a ``Database`` with a
NAM-specific interface. Obtain it through :func:`mario.parse_figaro` for
FIGARO source files or :func:`mario.parse_from_excel` for MARIO native
workbooks. No separate class import is required.

.. code-block:: python

   import mario

   nam = mario.parse_figaro("FIGARO_NAM_2023.csv", table="NAM", countries="IT")
   nam.get_index("si_d")
   flows = nam.get_block("CF_d")
   shares = nam.resolve("cf_d")

The :doc:`NAM format guide </get_started/table_formats/nam>` explains the
accounts and import representations; :doc:`api_nam_calculations` defines
totals and coefficients. The :doc:`FIGARO source guide
</notebooks/parsers/figaro/walkthrough_figaro>` describes required files
and source reconciliation.

Supported properties
--------------------

``table_type`` is ``"NAM"``; ``scenarios`` lists the stored scenarios and
``baseline_scenario_name`` is always ``"baseline"``. ``sets`` lists Region
and all registered accounting sets, including sets with no declared members.
``units`` is a dictionary containing ``currency``, ``scale`` and ``period``.
``meta`` contains source/name metadata; ``info`` contains source-specific
audit information, including ``info["figaro_nam"]`` for FIGARO imports.

``is_hybrid`` is false. ``is_multi_region`` tests whether more than one
reporting economy is stored; it does not certify an interregional system.
``nam_schema`` exposes the immutable account memberships, item metadata and
native layout declarations. ``matrices`` and ``nam[scenario]`` expose
read-only mappings of available DataFrames; the frames are independent copies.

Sets and available data
-----------------------

.. automethod:: mario.api.nam.NAMDatabase.get_index

.. automethod:: mario.api.nam.NAMDatabase.available_matrices

.. automethod:: mario.api.nam.NAMDatabase.list_matrices

.. automethod:: mario.api.nam.NAMDatabase.has_matrix

``available_blocks`` and ``has_block`` are aliases for
``available_matrices`` and ``has_matrix`` respectively.

Read and calculate blocks
--------------------------

.. automethod:: mario.api.nam.NAMDatabase.get_block

.. automethod:: mario.api.nam.NAMDatabase.get_block_spec

.. automethod:: mario.api.nam.NAMDatabase.get_block_as_pandas

.. automethod:: mario.api.nam.NAMDatabase.get_block_as_table

.. automethod:: mario.api.nam.NAMDatabase.get_block_as_matrix

.. automethod:: mario.api.nam.NAMDatabase.resolve

.. automethod:: mario.api.nam.NAMDatabase.resolve_many

.. automethod:: mario.api.nam.NAMDatabase.calc_all

.. automethod:: mario.api.nam.NAMDatabase.explain

Dotted access such as ``nam.U`` or ``nam.cf_d`` calls the resolver for
``baseline``. Other scenarios require ``scenario=...``. Registered names
come from :doc:`api_resolvable_matrices`; source coverage still determines
which results are calculable.

Updates, scenarios and copies
-----------------------------

.. automethod:: mario.api.nam.NAMDatabase.clone_scenario

.. automethod:: mario.api.nam.NAMDatabase.set_block

.. automethod:: mario.api.nam.NAMDatabase.copy

See :doc:`the scenario guide </get_started/scenarios>` for a native-flow
edit and its distinction from a propagated model shock.

Native Excel persistence
-------------------------

.. automethod:: mario.api.nam.NAMDatabase.to_excel

.. code-block:: python

   nam.to_excel("nam_native.xlsx")
   restored = mario.parse_from_excel("nam_native.xlsx", table="NAM", mode="flows")
   restored.resolve("cf_d")

The :doc:`Excel guide </notebooks/parsers/custom_database/from_excel>`
distinguishes native NAM workbooks from IOT/SUT layouts and FIGARO sources.

Scope of the interface
-----------------------

The remaining inherited IOT/SUT database operations raise
``NotImplementable`` for NAM. This includes ``query``, ``get_data``,
``search``, profile/concordance and cluster methods, custom operator
registration, plotting, scenario renaming, aggregation and shock propagation.
Only native-flow Excel export is supported; TXT/CSV, Parquet and pymrio
exports are not registered. NAM-to-SUT conversion, balancing and model
closure are not implemented. The matrix names alone do not select FIDELIO
or any other economic model.
