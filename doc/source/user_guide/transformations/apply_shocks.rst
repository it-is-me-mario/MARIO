Apply Shocks
============

This workflow covers the standard way to create a new scenario from an Excel
shock workbook.

Core methods
------------

The two main entry points are:

* :doc:`Database.get_shock_excel </api_document/mario.Database.get_shock_excel>` to write the workbook template;
* :doc:`Database.shock_calc </api_document/mario.Database.shock_calc>` to read that workbook and store a shocked scenario.

Typical flow
------------

The usual sequence is:

* export a template workbook from the current database;
* fill the rows you want to shock;
* apply the workbook into a named scenario.

For example:

.. code-block:: python

   db.get_shock_excel("policy_shock.xlsx")

   db.shock_calc(
       "policy_shock.xlsx",
       z=True,
       e=True,
       v=True,
       Y=True,
       scenario="policy",
   )

The ``scenario`` argument controls the output name. If omitted, MARIO creates a
name such as ``shock 1`` automatically.

Which matrices are read
-----------------------

The boolean switches ``z``, ``e``, ``v`` and ``Y`` tell MARIO which workbook
sheets should be read.

For IOT databases, these correspond directly to the standard matrices:

* ``z`` for the inter-industry coefficients;
* ``v`` for value added coefficients;
* ``e`` for extension coefficients;
* ``Y`` for final demand.

For SUT databases, MARIO prefers the split-native workbook layout:

* ``u`` and ``s`` for ``z``;
* ``va`` and ``vc`` for ``v``;
* ``ea`` and ``ec`` for ``e``;
* ``Ya`` and ``Yc`` for ``Y``.

Legacy unified sheets are still accepted for backward compatibility.

Clusters
--------

Shock templates and shock application both understand clusters.

You can:

* rely on default clusters already available on the database;
* store reusable custom clusters on the database;
* pass ad hoc clusters directly to ``get_shock_excel(...)`` or ``shock_calc(...)``.

This is useful when a single workbook row should target multiple regions,
sectors, activities, commodities, or final-demand categories at once.

Rewriting an existing shocked scenario
--------------------------------------

By default, ``shock_calc(...)`` does not overwrite an existing non-baseline
scenario.

If you want to recompute a scenario with the same name, use:

.. code-block:: python

   db.shock_calc(
       "policy_shock.xlsx",
       z=True,
       scenario="policy",
       force_rewrite=True,
   )

If instead you want to edit selected stored matrices of an already existing
scenario directly, use
:doc:`Database.update_scenarios </api_document/mario.Database.update_scenarios>`.

Notebook walkthrough
--------------------

Use the notebook below as the main shocks guide:

* :doc:`Apply shocks walkthrough <../../notebooks/user_guide/transformations/apply_shocks>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the shocks notebook <../../notebooks/user_guide/transformations/apply_shocks.ipynb>`
