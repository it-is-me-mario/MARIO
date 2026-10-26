:page-type: Explanation
:summary: Read sector-to-sector flows, final demand and extensions in an input-output table.

.. _concept-iots:

Input-Output Tables
===================

:doc:`Table formats <../table_formats>` / **IOT** · :doc:`SUT <sut>` · :doc:`NAM <nam>`

An IOT uses the same **Sector** set on the rows and columns of its square
transaction matrix. A sector represents an industry or a product, depending
on the source. In a multiregional table, each sector is also identified by region.

Structure and native matrices
-----------------------------

Select a block to see its definition and default axes. Switch between **Flows**
and **Coefficients** to see the lowercase coefficient names with softer colours.
Final-demand blocks without a registered coefficient remain labelled as
exogenous flows in the coefficient view.

.. raw:: html
   :file: ../_generated/iot_structure.html

Read ``Z`` **from the supplying row to the purchasing column**. ``Y`` sends
output to final-demand categories. ``V`` and ``E`` attach factors of production
and satellite accounts to producing sectors; ``VY`` and ``EY`` attach them
directly to final demand.

.. container:: mario-format-note

   **Units follow the account.** Transactions may be monetary or physical;
   satellite rows may use kg, energy or other units. ``*`` in an axis description
   means that an extension can carry additional index levels through
   ``matrix_layouts``. Some sources supply no values for particular blocks.

Inspect a small IOT
-------------------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      transactions = db.Z
      sectors = db.get_index("Sector")
      transactions.index[:3]

   .. container:: mario-result

      **Result** · A pandas DataFrame. Transaction rows and columns identify
      regions and sectors; ``sectors`` contains the native sector labels.

Indices
-------

An axis combines the relevant sets. For example, a transaction connects a
``(Region, Sector)`` to another ``(Region, Sector)``; final-demand columns use
``(Region, Consumption category)``. MARIO's pandas representation also stores
the set label in its ``Level`` index level.

.. raw:: html
   :file: ../_generated/iot_indices.html

Some sources have different sector labels in each region. See
:ref:`regional classifications <regional-classifications>` for regional queries,
and the :doc:`index reference </reference/api_indices>` for accepted aliases.

Coefficients and derived matrices
---------------------------------

.. mario-cards::
   :columns: 2

   .. mario-card:: Direct inputs
      :kicker: z · v · e

      Divide each flow column by that sector's output ``X``:

      .. math::

         z = Z\,\operatorname{diag}(X)^{-1}

      The same column normalization gives ``v`` from ``V`` and ``e`` from ``E``.
      ``e`` has satellite-account units per unit of sector output.

   .. mario-card:: Supply-chain requirements
      :kicker: w · f

      The Leontief system adds direct and upstream requirements:

      .. math::

         w = (I-z)^{-1},\qquad f = e\,w

      ``f`` is a footprint intensity per unit of final demand for sector output.
      Direct final-demand accounts ``EY`` are separate.

.. code-block:: python

   output = db.X
   intensity = db.f

MARIO resolves dependencies on demand. The formula for ``f`` does not require
materializing ``w`` when the selected computation method uses a linear solve.

.. mario-details:: Matrix names and default axes

   .. raw:: html
      :file: ../_generated/iot_derived.html

   ``F`` and ``M`` are absolute allocations to final demand; lowercase ``f``
   and ``m`` are intensities. See the :doc:`calculation reference
   </reference/api_calculation_methods>` for the equations, including how direct
   final-demand accounts are treated. The :doc:`full matrix catalogue
   </reference/api_resolvable_matrices>` includes additional decompositions.

Continue with :doc:`calculating matrices </user_guide/inspection/compute_matrices>`,
:doc:`GHG characterization </user_guide/analysis/ghg_characterization>` or
:doc:`importing a database </user_guide/parsers/index>`.
