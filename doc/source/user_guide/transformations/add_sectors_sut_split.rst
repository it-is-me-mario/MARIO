Splitting activities and commodities in a SUT
=============================================

``Database.add_sectors(split=True)`` can carve new activities and/or commodities
out of existing ones in a **SUT** database, analogously to the sector split that
is available for IOT. This page describes the add-sectors workbook expected for
a SUT split and how MARIO uses it.

How it differs from the IOT split
---------------------------------

* An IOT split inserts the new sectors first and refines them afterwards. A SUT
  split does **not** run the insertion step: the a-priori Use (``U0``), Make
  (``M0``), Final demand (``Y0``) and Value added (``V0``) matrices are built
  directly from the original table and the workbook sheets, and handed to
  CVXLab.
* A SUT workbook is either **all** ``Split`` or **all** ``Add`` in the
  ``Add or Split`` column of the ``Master`` sheet. Mixing both modes raises an
  error. An empty cell means ``Add``. With ``split=False`` a workbook marked
  ``Split`` raises an error asking for ``split=True``.
* There is no ``Trades`` sheet: the regional pattern comes from the
  ``Region_to`` columns of ``Supply coef``, ``Use coef`` and ``Final dem share`` and from the
  ``DB Region`` column of the inventory sheets.

Variants: activities only, commodities only, or both
-----------------------------------------------------

The CVXLab model is chosen from the ``Master`` sheet:

===========================  ===================  ===============================
Items split                  CVXLab model         Priors that are built
===========================  ===================  ===============================
only activities              ``Split_sut_act``    ``U0``, ``M0``, ``V0``
only commodities             ``Split_sut_com``    ``U0``, ``M0``, ``Y0``
activities and commodities   ``Split_sut``        ``U0``, ``M0``, ``Y0``, ``V0``
===========================  ===================  ===============================

* In the activity-only model the output of a new activity is its total cost
  (Use plus Value added). In the commodity-only model ``Total outputs`` of a new
  commodity is a **constraint**: it fixes the total use (Use plus Final demand,
  and therefore the supply) of the new commodity in each region.
* Final demand is not touched by an activity-only split and value added,
  emissions and the final-demand satellite accounts are not touched by a
  commodity-only split.
* The commodity-only model has no a-priori for the Use matrix, so the Use of the
  split commodity by each activity is one of the feasible splits and may change
  with the solver.

Workbook
--------

``Master``
   One row per new item and region. A new **activity** row fills ``Activity`` and
   ``Parent Activity``; a new **commodity** row fills ``Commodity`` and
   ``Parent Commodity`` (never both in the same row). ``Inventory sheet`` names
   the inventory of that item and region; ``Add or Split`` is ``Split``.

Inventory sheets
   * *Activity* inventory (e.g. ``a2b_DE``): per unit of output of the new
     activity in that region, the commodities it uses (``Item type`` =
     ``Commodity``, with ``DB Item`` and ``DB Region``), its value added
     (``Factor of production``) and, optionally, its satellite accounts
     (``Satellite account``). If satellite values are omitted, the new activity
     inherits the intensity per unit of output of its parent.
     If the inventory has no ``Factor of production`` rows, value added closes the
     balance of the new activity (output minus inputs) and is distributed like the
     value added of its parent.
   * *Commodity* inventory (e.g. ``c2b_DE``): the share of the output of the new
     commodity in that region made by each activity (``Item type`` =
     ``Activity``, with ``DB Item`` and ``DB Region`` of the producing
     activity).

``Total outputs`` (required)
   ``Activity`` or ``Commodity``, ``Region``, ``Quantity``, ``Unit``. The output of
   each new activity is a constraint of the optimization. The output of a new
   commodity is a constraint in a commodity-only split and only a first guess
   used in the prior when activities are split too.

``Supply coef`` (required when activities are split)
   ``Region_from``, ``Region_to``, ``Activity_from``, ``Commodity_to``,
   ``Coefficient``: the share of the output of the commodity in ``Region_to``
   supplied by the new activity in ``Region_from``. Only existing commodities
   (stable or parent, with their original names) are listed: the supply of a new
   commodity is given by its commodity inventory.

``Final dem share`` (required when commodities are split)
   ``Region_from``, ``Region_to``, ``Commodity``, ``Consumption category``,
   ``Share``: the share of the final demand for the parent commodity that goes
   to the new commodity. Missing combinations take a share of 0 (with a
   warning); shares must lie in [0, 1].

``Use coef`` (optional, commodities split)
   ``Region_from``, ``Region_to``, ``Commodity_from``, ``Activity_to``,
   ``Coefficient``: the use of the new commodity ``Commodity_from`` (produced
   in ``Region_from``) per unit of total output of the activity ``Activity_to``
   in ``Region_to``. It can be empty or list only a few cells. Only stable or
   parent activities (with their original names) are listed: the use of a new
   commodity by a new activity comes from the activity inventory. For a parent
   activity the output is the output left after the split. See
   :ref:`use of the new commodities <sut-split-use-prior>`.

A split of only one kind does not need the sheet of the other kind. If it is
present and filled, MARIO warns that it is ignored (``Supply coef`` for a
commodity-only split; ``Final dem share`` and ``Use coef`` for an activity-only
split).

``Exclusions use`` and ``Exclusions supply`` (optional)
   Cells of the Use (``Region_from``, ``Commodity_from``, ``Region_to``,
   ``Activity_to``) and Make (``Region_from``, ``Activity_from``, ``Region_to``,
   ``Commodity_to``) tables that must be zero. If omitted, only the zeros
   inherited from the original table (a cell of the disaggregated table is zero
   when its aggregated original cell is zero) are imposed.

``Tolerances`` (optional)
   ``delta`` and ``eps``, relative and non-negative; they default to ``1e-5``
   each, and a value above ``1e-2`` triggers a warning. The constraints of the
   CVXLab models are tolerance bands (``x <= y * (1 + tol)`` and
   ``x >= y * (1 - tol)``), except the zero masks, which are exact:

   * ``delta``: the commodity balance (use equals supply) and the activity
     balance (cost equals revenue);
   * ``eps``: consistency of the disaggregated Use, Make, Final demand and
     Value added with the original table once parents and children are added
     up, and the known totals (``Total outputs``) of the new items.

   After the optimization MARIO logs the largest relative residual of each of
   these constraints and warns about those above their tolerance; the table is
   not rebalanced afterwards. ``eps = delta = 0`` gives exact equalities.

All sheets refer to parents by their **original** name (e.g. ``c2``).

Running the split
-----------------

.. code-block:: python

   db.add_sectors(
       io="add_sector_SUT.xlsx",
       split=True,
       cvxlab_path="path/to/an/existing/folder",
       parent_names={"Activity": {"a2": "a2_rest"}, "Commodity": {"c2": "c2_rest"}},
   )

The same parameters as the IOT split are available (``only_input_data_gen``,
``keep_all_split_steps``, ``residue``, ``solver``, ``solver_parameters``,
``input_data_files_type``). Unless ``solver`` is given, MARIO tries CLARABEL,
then ECOS, then SCS. ``parent_name`` accepts a string only when exactly
one parent is split. Unless ``keep_all_split_steps=True``, the result of the
optimization replaces the ``baseline`` scenario; otherwise ``original``,
``split_<scenario>`` (the priors) and ``split_cvxlab`` are kept as well.

How the priors are built
------------------------

For a new activity ``a_n`` with parent ``a_p`` (and analogously for commodities):

* output prior: ``X(a_n)`` = ``Total outputs``; ``X(a_p)`` = original - children;
* ``U0[:, a_n]`` and ``V0[:, a_n]`` = inventory coefficients x ``X(a_n)``;
  ``U0`` and ``V0`` of the parent = original - children;
* ``M0[a, c_n]`` = commodity-inventory share x output prior of ``c_n``;
  ``M0[a_n, c]`` = ``Supply coef`` x output prior of ``c``; the remaining cells
  of an aggregated parent cell are the original value minus the cells
  attributed to the new items;
* ``Y0[c_n]`` = original ``Y[c_p]`` x ``Final dem share``; ``Y0[c_p]`` = original - children.

Negative values that this subtraction may produce are clipped to zero with a
warning; a child output larger than its parent output raises an error.

.. _sut-split-use-prior:

Use of the new commodities
~~~~~~~~~~~~~~~~~~~~~~~~~~

When commodities are split, the rows of the new commodities of the Use matrix
(for the stable and the parent activities) get a prior of their own. For a parent
commodity ``c_p``, a new commodity ``c_n``, an activity ``j`` and the regions of
the row ``r`` and of the column ``s``:

#. **Amount to split.** For a stable activity it is the original cell
   ``U[c_p, j]``. For a parent activity ``a_p`` it is what is left of
   ``U[c_p, a_p]`` once the new activities of ``a_p`` have taken their use of
   ``c_p`` and ``c_n`` from the inventories, so that the four cells of the block
   (parent and new commodity, residual parent and new activity) add up to the
   original self-consumption. If nothing is left (negative amount) the cells of the
   residual parent activity are set to zero, with a warning.
#. **Baseline.** The amount is split between ``c_n`` and the residual ``c_p``
   proportionally to the commodity outputs, in the region ``r`` of the
   commodity: ``X(c_n) / X_original(c_p)``. Cells known to be zero (the
   zeros of the original table and ``Exclusions use``) get nothing and their
   share goes to the other cells.
#. **Coefficients.** If ``Use coef`` gives a coefficient, the new commodity cell
   becomes ``Coefficient x X(j)`` with the output of the activity in the
   region ``s`` of the column, and the residual parent takes what is left of the
   amount. If the residual would be negative, the whole group (all new
   commodities and the residual parent of that cell) goes back to the baseline
   and a single warning lists the cells affected. A coefficient on a cell known
   to be zero is ignored with a warning.

The three SUT models (``Split_sut``, ``Split_sut_com``, ``Split_sut_act``) measure the distance to every prior with the complete
Kullback-Leibler distance ``x log(x / x0) - x + x0``. Only the **informed** cells enter the optimization: the cells given by a
coefficient and the residual parent cell of the same group. The baseline of every
other cell is only a first guess, used for the prior scenario
``split_<scenario>``; the model leaves those cells free (they are bound by the
balances and the consistency constraints). Without ``Use coef`` the optimization
is therefore the same as before. A coefficient of 0 informs nothing (a zero prior
is ignored); use ``Exclusions use`` to force a cell to zero.
