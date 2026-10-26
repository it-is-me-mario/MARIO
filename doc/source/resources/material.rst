Downloadable material
=====================

Download set inventories, classification lookups and runnable guide notebooks.
Sources and conditions of reuse travel with each file; MARIO does not replace
the licence of the original database.


Nomenclature and formulas
-------------------------

.. mario-cards::
   :columns: 1
   :links:

   .. mario-card:: :download:`Nomenclature and formulas workbook <../_static/data/supporting_files/Nomenclature_and_formulas.xlsx>`
      :kicker: Excel · Matrices, Indices, IOT, SUT_IT, SUT_PT
      :logo: /_static/images/logos/file-xlsx.svg

      MARIO's canonical names for indices and matrices, with the step-by-step
      calculation of every matrix on the IOT and SUT test tables, under both
      technology assumptions.

NAM nomenclature and account-normalized equations are documented separately
in :doc:`the NAM guide </get_started/table_formats/nam>` and
:doc:`the NAM calculation reference </reference/api_nam_calculations>`.
The FIGARO companion in the notebook list includes local NAM parsing;
the IOT/SUT formulas workbook does not contain NAM calculations.


.. _database-set-downloads:

Database set lists
------------------

Original regions, economic classifications, satellite accounts, factors of
production, consumption categories and units. Readings with identical native
sets and units share an Excel; its year list identifies the verified inputs.
Each Excel includes a **Read me** sheet with its source, scope and reuse terms.
These inventories contain labels and units, not database observations or
emission factors. Eora set downloads are withheld pending redistribution
permission.
Compare regions and sectors in :doc:`Classifications <data-explorer/scope>`.

.. mario-database-profiles::

Classification concordances
---------------------------

:download:`Reviewed NACE Rev. 2.1 and CPA 2.2 concordances <../_static/data/economy/classification-concordances.xlsx>`
include native categories, every intermediate route, source locations and explicit
qualifications. Use the Match ID to follow a result through Routes and Intermediate
links. These are classification lookups; they do not provide numerical allocation weights.
Explore them in :ref:`Sectoral coverage <sectoral-coverage>`.


Notebooks
---------

Download database parser notebooks and complete analysis examples. Each file
contains code and explanations, without cached results, execution history or
local paths. Install MARIO and supply
your own source files under their applicable licence. Links to example files
are kept in the notebook; download these before running cells that use them.

.. mario-notebook-downloads::
