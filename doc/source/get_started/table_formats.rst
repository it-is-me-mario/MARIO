:page-type: Overview
:summary: Read the structure, indices and matrix names of an IOT or a SUT.

Table formats
=============

Choose the format of your database. Each guide explains its blocks, names,
axes and calculation assumptions together.

.. container:: mario-format-choices

   .. mario-cards::
      :columns: 2

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

.. _format-basic-definitions:

Objects in MARIO
----------------

.. container:: mario-object-strip

   .. container::

      **Database**

      The ``mario.Database`` object holding your table, metadata and scenarios.

   .. container::

      **Table**

      The accounting structure: IOT or SUT. Inspect it with ``db.table_type``.

   .. container::

      **Scenario**

      A state of that table, such as the baseline or a modified scenario.

   .. container::

      **Matrix**

      A named block or result, such as ``db.Z`` or ``db.U``.

Each scenario stores its own matrices. MARIO can calculate missing quantities
when requested; :doc:`scenarios` explains how the states are managed.

.. _format-conventions:

Model configurations
--------------------

Each table has an accounting configuration. Inspect the baseline with
:attr:`db.configuration <mario.CoreModel.configuration>` or select a scenario
with :meth:`db.get_configuration() <mario.CoreModel.get_configuration>`.

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Choice
     - Meaning
   * - Table format
     - IOT has one productive set. SUT separates activities and commodities.
   * - Regional scope
     - Single-region or multi-region, determined by endogenous Region members.
   * - Trade representation
     - Isard carries trade in SUT use and final demand. Chenery–Moses carries
       commodity trade in supply. IOT transactions are bilateral.
   * - Import representation (``import_representation``)
     - Single-region models can include external imports in factor accounts
       with ``"factor-accounts"`` or use native blocks with ``"separate"``.
   * - External trade resolution (``trade_resolution``)
     - ``"aggregate"`` combines foreign origins and export partners.
       ``"by_region"`` retains their regional labels.
   * - Import detail (``imports_by``)
     - Total imports, or imports by Sector, Commodity or producing Activity.
       The classification and the foreign-partner resolution are independent.
   * - Technology assumption
     - Industry-based or product-based SUT supply coefficients. For an IOT,
       ``sector_type`` records the productive classification when available.

Trade representation belongs to each scenario. The import representation and
descriptors are shared by the database's scenarios. Existing national tables
without declared import accounts report unspecified import detail. Mixed
regional SUT patterns report ``mixed``. A table with zero international flows
reports ``domestic-only``. A coefficient-only or incomplete source can report
``unspecified`` until its regional pattern is available.

The IOT and SUT diagrams provide single-region selectors named
``import_representation``, ``trade_resolution`` and ``imports_by``, matching
:meth:`db.to_single_region() <mario.Database.to_single_region>` and the fields
exposed by :attr:`db.configuration <mario.CoreModel.configuration>`.
The diagrams show the resulting import rows, their foreign origins and the
export-partner detail. F1/F2 illustrate foreign partners, with regions inside
the imported classification. Each matrix has one symbol across its rows.

The SUT multiregional selector **Trade representation** chooses Isard or
Chenery–Moses. Foreign origin descriptors identify external suppliers.
The endogenous Region set determines regional scope. Both diagrams also
provide flow and coefficient views.
See :doc:`separate import accounts </user_guide/transformations/import_accounts>`
for extraction and reversible conversion.

Flows, coefficients and units
-----------------------------

For paired names such as ``Z`` / ``z`` or ``E`` / ``e``, capitals indicate
**absolute flows** and lowercase indicates **coefficients per unit of output**.
A table can contain both. Final-demand blocks remain flows.

The format describes the arrangement of the table. Monetary or physical units
come from the database: a hybrid table can use different units for different
products. Check units before summing quantities or comparing coefficients.

These guides use MARIO's default names. See :doc:`custom labels
</user_guide/inspection/custom_labels_and_aliases>` to change them, or the
:doc:`matrix reference </reference/api_resolvable_matrices>` for the full catalogue.

.. toctree::
   :hidden:

   table_formats/iot
   table_formats/sut

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
