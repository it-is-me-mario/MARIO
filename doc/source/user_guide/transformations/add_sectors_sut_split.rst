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
  ``Region_to`` columns of ``Supply coef`` and ``Final dem share`` and from the
  ``DB Region`` column of the inventory sheets.

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
   commodity is only a first guess used in the prior.

``Supply coef`` (required)
   ``Region_from``, ``Region_to``, ``Activity_from``, ``Commodity_to``,
   ``Coefficient``: the share of the output of the commodity in ``Region_to``
   supplied by the new activity in ``Region_from``. Only existing commodities
   (stable or parent, with their original names) are listed: the supply of a new
   commodity is given by its commodity inventory.

``Final dem share`` (required)
   ``Region_from``, ``Region_to``, ``Commodity``, ``Consumption category``,
   ``Share``: the share of the final demand for the parent commodity that goes
   to the new commodity. Missing combinations take a share of 0 (with a
   warning); shares must lie in [0, 1].

``Exclusions use`` and ``Exclusions supply`` (optional)
   Cells of the Use (``Region_from``, ``Commodity_from``, ``Region_to``,
   ``Activity_to``) and Make (``Region_from``, ``Activity_from``, ``Region_to``,
   ``Commodity_to``) tables that must be zero. If omitted, only the zeros
   inherited from the original table (a cell of the disaggregated table is zero
   when its aggregated original cell is zero) are imposed.

``Tolerances`` (optional)
   ``delta`` and ``eps``. Defaults to ``1e-5`` each.

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
``input_data_files_type``). ``parent_name`` accepts a string only when exactly
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
