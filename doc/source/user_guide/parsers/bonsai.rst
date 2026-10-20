BONSAI Balanced HSUT
====================

.. image:: /_static/images/logos/bonsai.webp
   :alt: BONSAI project logo
   :width: 180px
   :target: https://bonsai.uno/

``mario.parse_bonsai`` reads the Balanced hybrid supply-use graph exports from
the `BONSAI project <https://gitlab.com/bonsamurais/bonsai>`_. It accepts the
original ZIP or an extracted directory and detects a single nested release
folder automatically. No download or archive extraction is needed.

The parser has been checked against the ``_b Next version/Balanced/20260615``
bundle. Its **reference year is 2016**: ``20260615`` is a release-folder label,
not the accounting year. The parser reads the year from ``classification.csv``.
HIOT and monetary SUT exports use different layouts and are not supported by
this entry point.

Usage
-----

.. code-block:: python

   import mario

   db = mario.parse_bonsai("/path/to/Balanced/20260615.zip")
   # The equivalent extracted release directory is also supported:
   # db = mario.parse_bonsai("/path/to/Balanced/20260615")

   S = db.matrices["baseline"]["S"]
   U = db.matrices["baseline"]["U"]
   Yc = db.matrices["baseline"]["Yc"]
   report = db.info["bonsai"]

``calc_all=False`` is the default. All nine imported blocks are pandas sparse
DataFrames with implicit zeros. Economic CSVs are read in chunks directly from
the ZIP. Avoid converting the full economic matrices to dense arrays or
computing full inverse matrices before reducing the model to the required
scope. ``chunksize=100_000`` controls input buffering.

Required files
--------------

* ``classification.csv``: UUIDs, activity/product codes, regions, node properties
  and reference year.
* ``hybrid_supply_w_characteristic_unit.csv``: balanced process-to-object flows.
* ``hybrid_use_w_characteristic_unit.csv``: balanced object-to-process flows,
  including final demand and interregional trade.
* ``all_elementary_flows_AB_and_BB.csv``: recalculated elementary flows after
  balancing, including emissions and extracted resources.

The fourth file is required by default. Use ``extensions=False`` to import only
economic flows with zero satellite placeholders. Pickle files, Leontief
matrices, intermediate ``hybrid_sut`` exports and separate emission-component
files are not read.

Mapping to MARIO
----------------

The parser joins UUIDs to the classification. Only objects with
``object_type='product'`` enter the economic matrices: the supply/use exports
also contain substances, which must not become commodities. Processes with
``activity_type='final_demand'`` enter final demand; their names alone do not
determine their role.

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Block
     - Content
   * - ``S``
     - Activity-to-product supply.
   * - ``U``
     - Product use by activities, retaining cross-region flows.
   * - ``Yc``
     - Product use by final-demand processes, including negative inventory flows.
   * - ``Ea``, ``EY``
     - Recalculated elementary flows assigned to activities or directly to final demand.
   * - ``Ya``, ``Ec``
     - Zero blocks: no corresponding flows are imported from this layout.
   * - ``Va``, ``Vc``
     - Zero placeholder row ``-``: value added is unavailable in these inputs.

Activity, commodity and final-demand axes retain the source codes and existing
regional nodes; the parser does not invent a rectangular region-by-item grid.
Commodity units remain native (for example tonnes, TJ, items or Meuro).
Conflicting units for one commodity code are rejected. Activity and placeholder
factor units are ``"None"``. Value added is never inferred by summing mixed
physical units. Duplicate edges are summed and legitimate negative flows are
preserved. No rebalancing is performed: not all source products are constrained
to balance.

Satellite labels contain the substance name (UUID when unnamed), compartment,
unit and UUID, separated by `` | ``. Distinct substances and compartments remain
separate even when names coincide. Missing compartments are labelled
``unspecified`` without inferring an emission or resource compartment.

Import diagnostics
------------------

The checked release includes 362 elementary-flow rows whose region/activity
pair is absent from its classification. By default the parser warns, omits
these rows from ``Ea``/``EY``, and retains every omitted source row under
``db.info["bonsai"]["unmatched_extensions"]``. Use
``unmatched_extensions="raise"`` to reject such a bundle instead.
The report also contains file names, economic row counts and satellite
identities. Import assumptions are recorded in the metadata history.

``model="ModelState"`` returns an internal state with the same report at
``state.metadata.extra["bonsai"]``. To import another compatible release into
an existing database, use
``db.parse_scenario("bonsai", path=other_path, new_scenario="alternative")``.

See :doc:`../../api_document/mario.parse_bonsai` for the complete signature.

Reproduce the release check
---------------------------

From a MARIO source checkout, the optional integration test imports the complete
release and compares supply and use totals for all 53,400 products against
``product_validate_after_balance.csv``, selecting each product's characteristic
layer. It also checks source balance constraints with an absolute and relative
tolerance, while leaving the data unchanged.

.. code-block:: bash

   MARIO_BONSAI_BALANCED_ZIP=/path/to/20260615.zip \
     python -m pytest tests/parsers/test_bonsai_realdata.py -q

The integration test is skipped when the environment variable is absent.

Regional method compatibility
-----------------------------

BONSAI uses different activity, commodity and final-demand memberships across
regions. ``get_index`` exposes these as regional dictionaries while retaining
lists for common classifications. See :doc:`bonsai_methods` for the first
implementation's method diagnosis, known regressions and reproduction steps.

.. toctree::
   :hidden:

   bonsai_methods
