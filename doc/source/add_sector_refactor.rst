:orphan:

Add Sector Refactor
===================

This note captures the gap between the original compact add-sector helper and
the richer workbook-driven workflow that existed in an earlier development
line. The goal is to preserve the modern package structure while recovering the
full behavior without reviving the old ``core``/``tools`` design.


Current State
-------------

The live codebase currently supports a compact add-sector workflow centered on:

* ``Database.get_add_sectors_excel(...)`` in ``mario.api.database``
* ``Database.add_sectors(...)`` in ``mario.api.database``
* workbook writers in ``mario.ops.excel``
* the basic matrix patching helpers in ``mario.ops.sectoradd``

This implementation is intentionally small. It can write a simple workbook,
read user-filled blocks, append new sectors or SUT axes, and rebuild the
derived matrices. It does not support the richer inventory-driven logic
documented here.


What Existed in the Historical Richer Workflow
----------------------------------------------

The earlier implementation used a richer workflow around the class
``AddSectors`` in ``mario/tools/add_sectors.py`` plus workbook utilities in
``mario/tools/excelhandler.py``.

That workflow had four distinct stages.

Stage 1: master workbook definition
   The user defined new sectors or activities in a master sheet, together with
   inventory sheet names, units, parent mappings, final demand hints, market
   shares, optional cluster labels, and for IOT also the ``Add or Split``
   mode.

Stage 2: inventory workbook generation
   The code generated one inventory sheet per new item plus helper sheets for
   region clusters, item clusters, database units, and, for IOT split cases,
   extra sheets such as ``Total outputs``, ``Trades``, ``Exclusions`` and
   ``Tolerances``.

Stage 3: coefficient-side insertion
   ``AddSectors`` filled new coefficient slices by combining:

   * direct inventory updates;
   * unit conversion with ``pint``;
   * parent copying;
   * cluster-aware allocation across regions and items;
   * percentage changes relative to a parent profile;
   * factor and satellite updates;
   * final demand population;
   * SUT-only market-share population;
   * IOT-only uncertainty bookkeeping.

Stage 4: optional IOT split workflow
   After the coefficient-side insert, the branch could optionally start a
   second workflow driven by CVXLAB files and split metadata. That stage
   adjusted outputs, trade constraints and uncertainty levels to split a parent
   sector into new sectors.


Historical Workbook Schema
--------------------------

The historical workbook schema was much richer than the compact helper that
existed before this port.

Master sheet
   For SUT, the key columns were ``Region``, ``Activity``, ``Commodity``,
   ``Inventory sheet``, ``Quantity``, ``Unit``, ``Market share``,
   ``Final consumption``, ``Consumption category``, ``Parent Activity``,
   ``Leave empty``, ``Source`` and ``Notes``.

   For IOT, the key columns were ``Region``, ``Sector``, ``Inventory sheet``,
   ``Quantity``, ``Unit``, ``Final consumption``, ``Consumption category``,
   ``Parent Sector``, ``Leave empty``, ``Source``, ``Notes`` and
   ``Add or Split``.

Inventory sheets
   Each inventory sheet contained ``Quantity``, ``Unit``, ``Input``,
   ``Item type``, ``DB Item``, ``DB Region``, ``Change type``, ``Source`` and
   ``Notes``.

Helper sheets
   The workflow also supported region clusters, item clusters, output sheets,
   trade sheets, exclusions, tolerances and optional redefinition of the
   uncertainty parameters.

This is not a formatting difference only. The template encoded a richer data
model.


Functional Gaps Relative to the Current Codebase
------------------------------------------------

The live implementation in ``mario.ops.sectoradd`` does not yet cover:

* multi-sheet master and inventory workflow;
* region clusters;
* sector or commodity clusters;
* ``Parent Activity`` or ``Parent Sector`` bootstrap logic;
* ``Update`` versus ``Percentage`` semantics in inventories;
* unit conversion against database units;
* SUT market-share filling;
* final-demand filling from master metadata;
* IOT uncertainty matrix generation;
* the downstream split workflow based on output and trade constraints.

The richer behavior is therefore not a thin extension of the current helper
functions. It is a separate engine that needs a structured port.


Method Mapping
--------------

The legacy ``AddSectors`` methods fall into three buckets.

Workbook parsing and request shaping
   ``read_add_sectors_excel(...)``, ``get_inventory_sheets(...)``,
   ``read_inventory_sheets(...)``, ``_read_add_sectors(...)``,
   ``_read_add_inventories(...)`` and ``_get_new_add_sectors_sets(...)``.

Core add-sector engine
   ``add_new_units(...)``, ``get_empty_table_slices(...)``,
   ``get_slice_indices(...)``, ``fill_slices(...)``,
   ``make_units_consistent_to_database(...)``, ``copy_from_parent(...)``,
   ``fill_commodities_inputs(...)``, ``fill_fact_sats_inputs(...)``,
   ``fill_market_shares(...)``, ``fill_final_demand(...)``,
   ``leave_empty(...)``, ``add_slices(...)`` and ``reindex_matrices(...)``.

Optional split workflow
   ``split_info`` handling in ``AttrData.add_sectors(...)`` plus the functions
   in ``mario/tools/new_sectors.py`` and the CVXLAB integration.

This split is useful because only the second bucket is required to recover the
full add-sector feature. The third bucket should remain a separate concern.


Recommended Target Architecture
-------------------------------

The public API should remain simple.

* ``Database.get_add_sectors_excel(...)``
* ``Database.add_sectors(...)``

The internal implementation should be decomposed more clearly than it was in
the historical implementation.

``mario.ops.add_sector_specs``
   Canonical workbook schemas, column names and validation-level constants.

``mario.ops.add_sector_workbook``
   Workbook readers and writers for the current template. This layer should be
   responsible only for I/O and request normalization, not matrix math.

``mario.ops.add_sector_engine``
   Pure engine that receives normalized master rows, inventories, cluster maps
   and baseline blocks, then returns updated coefficient blocks plus any
   metadata such as units and uncertainty matrices.

``mario.ops.sector_split``
   Optional IOT-only split workflow. This should not be mixed into the base
   add-sector engine, because the split logic is materially different and can
   remain unavailable unless the extra inputs are present.

``mario.api.database``
   Thin wrapper layer that keeps the public ``Database`` methods stable and
   delegates to the workbook and engine modules.


Compatibility Strategy
----------------------

Two compatibility goals matter.

First, user code should keep calling the same public methods. No user should be
forced to import a new class just to add sectors.

Second, the workbook-driven flow should be available without fragmenting the
public API again.

The clean way to do this is to converge on a single workbook format and keep
all backward-compatibility handling internal when needed.


Recommended Port Order
----------------------

Phase 1: workbook model
   Port the schema and readers for the workbook-driven flow into a new
   workbook-specific module. This phase should stop at producing a normalized
   request object.

Phase 2: add-sector engine
   Port the coefficient-side logic only. This includes unit conversion, parent
   copying, cluster expansion, inventory change handling, SUT market shares and
   final-demand filling. Do not mix split logic into this phase.

Phase 3: Database integration
   Rewire ``Database.get_add_sectors_excel(...)`` and
   ``Database.add_sectors(...)`` so they keep the public surface stable while
   delegating to the new workbook and engine modules.

Phase 4: split workflow
   Port the IOT split path and its CVXLAB-related metadata only after the base
   workbook-driven add-sector engine is stable.


Tests Needed for the Port
-------------------------

The current test coverage is not enough. The historical branch did not add many
tests for the richer behavior either, so the port needs new coverage.

At minimum the port should add tests for:

* parsing the master workbook;
* grouping inventory sheets by target item;
* unit conversion against database units;
* copying from a parent and then overriding selected rows;
* cluster-based commodity or sector allocation;
* percentage updates relative to a parent profile;
* SUT market-share and final-demand filling;
* IOT uncertainty-matrix generation;
* end-to-end add-sector integration for both IOT and SUT.


Implementation Note
-------------------

The workbook-driven add-sector workflow should be ported as a new internal engine, not
as a direct copy of the old ``AddSectors`` class. The historical
implementation mixed:

* workbook concerns,
* mutable database state,
* coefficient updates,
* split preparation,
* optimizer handoff.

The new codebase already has a cleaner separation between API, ops, parsers and
internal state. The port should respect that separation and treat the old class
as a behavior reference, not as an implementation to transplant verbatim.
