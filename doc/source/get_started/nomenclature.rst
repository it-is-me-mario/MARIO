Nomenclature
============

This page defines the core terminology used across the MARIO documentation and
collects the canonical names used for indices and matrices.


Basic definitions
-----------------

.. mario-cards::
   :columns: 2

   .. mario-card:: Database
      :kicker: mario.Database

      The MARIO object the users interact with. A *database* stores one *table*,
      its *scenarios*, the parsed and derived *matrices*, and the metadata
      needed to work with them.

   .. mario-card:: Table
      :kicker: db.table_type

      The *table* is a collection of *matrices* arranged in a certain format.
      In MARIO, the structural *table* types are :ref:`Input-Output Tables (IOTs) <concept-iots>`
      and :ref:`Supply and Use Tables (SUTs) <concept-suts>`.

   .. mario-card:: Scenarios
      :kicker: db.scenarios

      Different states of the same *table*. See the dedicated page on
      :doc:`scenarios`.

   .. mario-card:: Matrix
      :kicker: db.Z

      One named data structure shaping a *table* and stored in a *database*, such as ``Z``, ``Y``, ``U``
      or ``S``. A *database* contains many matrices, some parsed directly while others can be
      computed on demand.

   .. mario-card:: Mode
      :kicker: Z · z
      :wide:

      A *matrix* can be either stored in ``flows`` or ``coefficients`` mode, depending on
      whether it contains absolute accounting values or technical coefficients. The
      mode is therefore a *matrix-specific* property, not related to the whole
      *table* or *database*. For example, an IOT *table* can be represented both by flow
      and coefficient *matrices*.

      By convention, the case of a matrix name tells its mode:

      .. container:: mario-convention mario-convention--symbols

         .. container::

            Flows: capital letters

            ``Z`` ``V`` ``E``

         .. container::

            Coefficients: lowercase letters

            ``z`` ``v`` ``e``


Default canonical labels
------------------------

Below, the default names for indices and matrices are listed, along with their accepted aliases in the public API and their intended meaning.

.. important::

   The tables below list MARIO's canonical default names, but users can
   customize the public labels of matrices and accepted set aliases through
   settings. See :doc:`Custom matrices and indices labels
   </user_guide/inspection/custom_labels_and_aliases>` for the full workflow.
   Names that would collide with existing reserved built-in matrix names are
   blocked explicitly to avoid ambiguous API calls.


The same tables are in the :download:`nomenclature and formulas workbook </_static/data/supporting_files/Nomenclature_and_formulas.xlsx>`.


Indices
~~~~~~~

Each matrix in MARIO has a set of *indices* that define its structure.
The table below lists the canonical MARIO index names, where they apply, the
accepted aliases in the public API, and their intended meaning.

.. raw:: html
   :file: _generated/indices_table.html

Matrices
~~~~~~~~

The table below lists the *matrices* currently available in MARIO, their *mode*,
in which *table* format they are used, common names found in the literature, and the default row
and column *indices* used by the package.

Download the :download:`nomenclature and formulas workbook </_static/data/supporting_files/Nomenclature_and_formulas.xlsx>`
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
   :ref:`technology assumption <concept-technology-assumptions>`.


.. rubric:: Check available matrices in a database

*Matrices* are stored in a dictionary within the database class and are defined
for each :doc:`scenario <scenarios>`.

If you want to check which matrices are available in the ``baseline`` scenario:

.. code-block:: python

   db.list_matrices(scenario="baseline")

The resulting list is dynamic: after parsing the database, every *matrix* the
user computes is stored in this dictionary.


.. _concept-clusters:

Clusters
--------

.. mario-cards::

   .. mario-card:: Cluster
      :kicker: db.available_clusters
      :wide:

      A *cluster* is a named group of labels inside one set. Workflows can reuse it
      without rewriting the member lists every time. At the moment, MARIO
      auto-generates default clusters only for the ``Region`` set, but you can
      define your own for any set.

      .. container:: mario-convention

         .. container::

            Cluster

            A reusable named group, such as ``EU`` or ``continent:Europe``.
            Shocks and sector additions use clusters as selection shortcuts.

         .. container::

            Aggregation

            A one-to-one mapping from each original label to one target label,
            as required by ``Database.aggregate(...)``.

.. rubric:: How to use them

.. mario-steps::

   .. mario-step:: Inspect

      ``db.default_clusters`` returns only the clusters MARIO generates
      automatically from the database coverage. ``db.available_clusters`` merges
      them with the clusters you saved yourself. For example, on a parsed
      EXIOBASE database:

      .. code-block:: python

         # automatic groups, such as continents and EU
         db.default_clusters["Region"].keys()

         # the members of the EU cluster
         db.available_clusters["Region"]["EU"]

   .. mario-step:: Define

      Save your own groups with ``db.set_clusters(...)``: they become part of
      ``available_clusters``. Set names accept the usual MARIO aliases, and
      members must be valid labels of their set.

      .. code-block:: python

         db.set_clusters({
             "Region": {"Europe custom": ["AUT", "DEU", "FRA", "ITA"]},
             "Sector": {"Energy": ["Electricity", "Gas"]},
         })
         db.available_clusters["Sector"]["Energy"]

   .. mario-step:: Aggregate

      ``region_aggregation`` builds a Region aggregation index from the same
      coverage logic, so you can aggregate regions without editing a workbook.
      The presets rely on the `country_converter package <https://github.com/IndEcol/country_converter>`_:

      .. container:: mario-chip-list

         ``continent`` ``UNregion`` ``EU`` ``OECD`` ``G7`` ``G20``

      .. code-block:: python

         by_continent = db.aggregate(
             io=None,
             levels="Region",
             region_aggregation="continent",
             inplace=False,
         )

      An explicit mapping, a pandas ``Series`` or a ``DataFrame`` also work. For the
      workbook-based workflow and full examples, see the
      :doc:`Aggregation guide <../user_guide/transformations/aggregate>`.
