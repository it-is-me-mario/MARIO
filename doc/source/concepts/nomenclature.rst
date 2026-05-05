Nomenclature
============

This page defines the core terminoloty used across the MARIO documentation and
collects the canonical names used for indices and matrices.


Basic Definitions
-----------------

Database
   The MARIO object the users interact with. A *database* stores one *table*,
   its *scenarios*, the parsed and derived *matrices*, and the metadata
   needed to work with them.

Table
   The *table* is a collection of *matrices* arranged in a certain format.
   In MARIO, the structural *table* types are :ref:`Input-Output Tables (IOTs) <concept-iots>` 
   and :ref:`Supply and Use Tables (SUTs) <concept-suts>`.

Scenarios
   Different states of the same *table*. See the dedicated page on
   :doc:`scenarios`.

Matrix
   One named data structure shaping a *table* and stored in a *database*, such as ``Z``, ``Y``, ``U``
   or ``S``. A *database* contains many matrices, some parsed directly while others can be
   computed on demand.

Mode
   A *matrix* can be either stored in ``flows`` or ``coefficients`` mode, depending on
   whether it contains absolute accounting values or technical coefficients. The
   mode is therefore a *matrix-specific* property, not related to the whole
   *table* or *database*. For example, an IOT *table* can be represented both by flow 
   and coefficient *matrices*.

   .. important::

      By convention, in MARIO, matrices named with **capital letters** are flow
      matrices (for example ``Z`` or ``V``), while matrices named with
      **lowercase letters** are coefficient matrices (for example ``z`` or
      ``v``).


Indices
-------

Each matrix in MARIO has a set of *indices* that define its structure. 
The table below lists the canonical MARIO index names, where they apply, the
accepted aliases in the public API, and their intended meaning.

.. raw:: html
   :file: _generated/indices_table.html

Matrices
--------

The table below lists the *matrices* currently available in MARIO, their *mode*,
in which *table* format they are used, common names found in the literature, and the default row
and column *indices* used by the package.

Download the :download:`terminology workbook </_static/data/supporting_files/Terminology.xlsx>`
for the editable source table and the worked ``IOT``, ``SUT_IT`` and ``SUT_PT``
example sheets built from the MARIO test databases.

.. raw:: html
   :file: _generated/matrices_table.html

.. important::

   ``*`` means that, using ``matrix_layouts``, MARIO can accept richer
   row-index structures than the default one, for example by adding
   ``Region`` or ``Sector`` levels to ``V`` and ``E``.

   ``**`` means that ``s`` in SUTs can be either a market-share matrix or a
   product-mix matrix depending on the active
   :doc:`technology assumption </concepts/technology_assumptions>`.
