Conventions and Nomenclature
============================

This page defines the core terms used across the MARIO documentation and
collects the canonical names used for indices and matrices.

Basic Definitions
-----------------

Database
   The user-facing object used throughout MARIO. A *database* stores one *table*,
   its *scenarios*, the *matrices* already parsed or computed, and the metadata
   needed to work with them.

Table
   The *table* format represented inside a database. In MARIO, the structural
   *table* types are :ref:`Input-Output Tables (IOTs) <concept-iots>` and :ref:`Supply and Use Tables (SUTs) <concept-suts>`.

Matrix
   One named data operator stored in the *database*, such as ``Z``, ``Y``, ``U``
   or ``S``. A *database* contains many matrices, some parsed directly and others
   computed on demand.

Mode
   The mode of a *matrix* is either ``flows`` or ``coefficients``, depending on
   whether the *matrix* contains absolute flows or technical coefficients. The
   mode is therefore a property of the specific *matrix*, not of the whole
   *table*. For example, an IOT *table* can contain both flow and coefficient
   *matrices*.

   .. important::

      By convention, matrices written with **capital letters** are flow
      matrices (for example ``Z`` or ``V``), while matrices written with
      **lowercase letters** are coefficient matrices (for example ``z`` or
      ``v``).

Scenarios
   Different states of the same *table*. See the dedicated page on
   :doc:`scenarios`.


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

.. raw:: html
   :file: _generated/matrices_table.html

.. important::

   ``*`` means that, using :doc:`matrix_layouts </concepts/matrix_layouts>`,
   MARIO can accept richer row-index structures than the default one, for
   example by adding ``Region`` or ``Sector`` levels to ``V`` and ``E``.

   ``**`` means that ``s`` in SUTs can be either a market-share matrix or a
   product-mix matrix depending on the active
   :doc:`technology assumption </concepts/technology_assumptions>`.
