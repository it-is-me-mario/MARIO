:page-type: Overview
:summary: Read the structure, indices and matrix names of IOT, SUT and NAM tables.

Table formats
=============

Choose the format of your database. Each guide explains its blocks, names,
axes and calculation assumptions together.

.. container:: mario-format-choices

   .. mario-cards::
      :columns: 3

      .. mario-card:: :doc:`Input-Output Tables <table_formats/iot>`
         :kicker: IOT
         :class: mario-format-choice

         **One sector set** on both sides of the transaction matrix.
         Sectors represent industries or products, depending on the source.

         .. mario-scheme:: IOT blocks: sectors, final demand, factors and satellite accounts
            :flows: Z Y / V VY / E EY
            :col-sizes: 3 1.5
            :row-sizes: 2 0.6 0.6

         .. container:: mario-format-cta

            Explore IOT structure and nomenclature

      .. mario-card:: :doc:`Supply and Use Tables <table_formats/sut>`
         :kicker: SUT
         :class: mario-format-choice

         **Activities and commodities** have separate axes.
         Supply records what activities produce; use records their inputs.

         .. mario-scheme:: SUT blocks: commodities, activities, final demand, factors and satellite accounts
            :flows: . U Yc / S . Ya / Vc Va VY / Ec Ea EY
            :col-sizes: 1.5 1.5 1.5
            :row-sizes: 1 1 0.6 0.6

         .. container:: mario-format-cta

            Explore SUT structure and nomenclature

      .. mario-card:: :doc:`National Accounting Matrices <table_formats/nam>`
         :kicker: NAM
         :class: mario-format-choice

         **Production, income, consumption and capital accounts** in one
         accounting system, with native partner detail where observed.

         .. mario-scheme:: Selected NAM blocks: factors, institutional income, saving and fixed assets
            :flows: Va_f . Vinst_f_f . / . RI_d . . / . . RS_dd . / . . . IK_d
            :col-sizes: 1.2 1.2 1.2 1.2
            :row-sizes: 1 1 1 1

         .. container:: mario-format-cta

            Explore NAM structure and native workbooks

.. _format-basic-definitions:

Objects in MARIO
----------------

.. container:: mario-object-strip

   .. container::

      **Database**

      The ``mario.Database`` object holding your table, metadata and scenarios.

   .. container::

      **Table**

      The accounting structure: IOT, SUT or NAM. Inspect it with ``db.table_type``.

   .. container::

      **Scenario**

      A state of that table, such as the baseline or a modified scenario.

   .. container::

      **Matrix**

      A named block or result, such as ``db.Z`` or ``db.U``.

Each scenario stores its own matrices. MARIO can calculate registered results
when their required inputs are available; :doc:`scenarios` explains how the
states are managed. A table format also determines which operations and
equations are supported. The NAM interface currently covers inspection,
account totals, coefficients, native-flow edits, Excel round trips and
:doc:`FIGARO national SUT/IOT projections </user_guide/transformations/nam_to_sut>`;
its :doc:`guide <table_formats/nam>` lists the modelling limits.

.. _format-conventions:

Flows, coefficients and units
-----------------------------

For IOT/SUT paired names such as ``Z`` / ``z`` or ``E`` / ``e``, capitals indicate
**absolute flows** and lowercase indicates **coefficients per unit of output**.
A table can contain both. Final-demand blocks remain flows.

NAM roles are declared explicitly: ``T`` is a view and ``B9_d``/``B9_f`` are results.
NAM coefficients use lowercase flow names and divide by the full paying-account
total. Each format has its own equations and supported calculation blocks;
see :doc:`the calculation reference </reference/api_calculation_methods>`.

The format describes the arrangement of the table. Monetary or physical units
come from the database: a hybrid table can use different units for different
products. Check units before summing quantities or comparing coefficients.

These guides use MARIO's default names. IOT/SUT support :doc:`custom labels
</user_guide/inspection/custom_labels_and_aliases>`. NAM uses the registered
set names and source-defined item labels described in its guide. The
:doc:`matrix reference </reference/api_resolvable_matrices>` contains each
format's catalogue.

.. toctree::
   :hidden:

   table_formats/iot
   table_formats/sut
   table_formats/nam

.. raw:: html

   <div hidden data-format-legacy-links>
     <a id="concept-iots" href="table_formats/iot.html#concept-iots">IOT</a>
     <a id="input-output-tables-iots" href="table_formats/iot.html#concept-iots">IOT</a>
     <a id="concept-suts" href="table_formats/sut.html#concept-suts">SUT</a>
     <a id="supply-use-tables-suts" href="table_formats/sut.html#concept-suts">SUT</a>
     <a id="concept-technology-assumptions" href="table_formats/sut.html#technology-assumptions">Technology assumptions</a>
     <a id="technology-assumptions" href="table_formats/sut.html#technology-assumptions">Technology assumptions</a>
     <a id="mathematics" href="table_formats/sut.html#technology-assumptions">Equations</a>
     <a id="switching-assumption" href="table_formats/sut.html#switching-assumption">Switching assumption</a>
     <a id="caveats" href="table_formats/sut.html#technology-assumptions">Technology assumptions</a>
     <a id="why-this-matters" href="table_formats/sut.html#calculations-and-conversions">Calculations</a>
   </div>
