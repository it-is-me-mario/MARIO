:page-type: Explanation
:summary: Read supply, use and extensions with distinct activity and commodity axes.

.. _concept-suts:

Supply and Use Tables
=====================

:doc:`Table formats <../table_formats>` / :doc:`IOT <iot>` · **SUT**

A SUT separates **activities**, which produce, from **commodities**, which are
produced and used. Their labels and counts can differ. The supply and use
blocks therefore need not be square.

Structure and native matrices
-----------------------------

Select a block to see its definition and default axes.

.. raw:: html
   :file: ../_generated/sut_structure.html

``U`` reads **commodity inputs → using activities**. In MARIO, ``S`` reads
**producing activities → supplied commodities**; this orientation matters when
importing a source that publishes supply in the opposite orientation.
The empty diagonal cells are not additional native flow blocks.

.. container:: mario-format-note

   **Suffixes identify the side.** ``a`` means activity and ``c`` means commodity:
   ``Ea`` and ``Ec`` attach satellite accounts to those respective axes.
   ``Yc`` and ``Ya`` are final-demand blocks; ``VY`` and ``EY`` attach accounts
   directly to final demand. Some blocks may be zero or unavailable in a source.

Inspect a small SUT
-------------------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("SUT", tech_assumption="IT")
      use = db.U
      supply = db.S
      activities = db.get_index("Activity")
      commodities = db.get_index("Commodity")

   .. container:: mario-result

      **Result** · ``use`` has commodity rows and activity columns; ``supply``
      has activity rows and commodity columns. Both retain the region labels.

Indices
-------

A productive axis combines ``Region`` with ``Activity`` or ``Commodity``.
MARIO's pandas representation also stores the set label in its ``Level`` index
level. Satellite and factor accounts can carry extra levels through
``matrix_layouts`` (marked ``*`` in the block descriptions).

.. raw:: html
   :file: ../_generated/sut_indices.html

Regional classifications can vary independently for activities and commodities.
See :ref:`regional classifications <regional-classifications>` and the
:doc:`index reference </reference/api_indices>` for query conventions and aliases.

Coefficients and production
---------------------------

``Xa`` is activity output; ``Xc`` is commodity output/demand. Use coefficients
normalize each column of ``U`` by the output of the using activity:

.. math::

   u = U\,\operatorname{diag}(X_a)^{-1}

Likewise, ``ea`` and ``va`` normalize activity accounts by ``Xa``; ``ec`` and
``vc`` normalize commodity accounts by ``Xc``. In hybrid tables, coefficients
can express one physical unit per another: check the source units.

.. _concept-technology-assumptions:

Technology assumptions
----------------------

The assumption controls the supply coefficients ``s``, which connect commodity
demand to activity production. MARIO uses these two conventions:

.. mario-cards::
   :columns: 2

   .. mario-card:: Industry-based
      :kicker: IT · industry-based

      Uses the observed market share of each activity in a commodity's output.

      .. math::

         s = S\,\operatorname{diag}(X_c)^{-1}

      This is the default. It supports different activity and commodity counts.

   .. mario-card:: Product-based
      :kicker: PT · product-based

      Builds the activity product mix, then inverts it:

      .. math::

         c = S^{\mathsf T}\operatorname{diag}(X_a)^{-1},\qquad s = c^{-1}

      Requires equal activity and commodity counts. On a non-square SUT,
      MARIO warns and falls back to IT.

The current PT builder uses a pseudoinverse if the product-mix matrix is
singular. See :doc:`db.s </api_document/mario.CoreModel.lower_s>` for the numerical
behaviour. An invertible product mix and a singular one need different
interpretation even when both return a result.

.. mario-details:: Switching assumption

   .. code-block:: python

      db.change_assumption("PT")
      assumption = db.tech_assumption
      coefficients = db.s

   This changes the whole database. MARIO first resets every scenario to flows,
   so coefficients can be rebuilt under the new assumption. The long names
   ``"industry-based"`` and ``"product-based"`` are also accepted.
   See :doc:`db.change_assumption()
   </api_document/mario.Database.change_assumption>`.

.. mario-details:: Matrix names and default axes

   .. raw:: html
      :file: ../_generated/sut_derived.html

   In a two-letter suffix, the first letter identifies the row side and the
   second identifies the column side: ``wca`` has commodity rows and activity
   columns. ``fa`` and ``fc`` are footprint intensities on the respective axes;
   ``Fa`` and ``Fc`` are absolute allocations. The :doc:`matrix reference
   </reference/api_resolvable_matrices>` gives their equations and dependencies.

Calculations and conversions
----------------------------

MARIO can compute directly on the SUT's native blocks:

.. code-block:: python

   activity_output = db.Xa
   commodity_intensity = db.fc

Unified views such as ``Z``, ``Y``, ``V`` and ``E`` combine the split blocks for
inspection and compatible exports. They do not convert the SUT into an IOT.

Continue with :doc:`calculating matrices </user_guide/inspection/compute_matrices>`,
:doc:`SUT-to-IOT conversion </user_guide/transformations/sut_to_iot>` or
:doc:`importing a database </user_guide/parsers/index>`.
