:page-type: Database guide
:summary: Import a hybrid EXIOBASE IOT or SUT with native physical and monetary units.

EXIOBASE hybrid
===============

.. container:: mario-companion

   :download:`Download notebook <hybrid.ipynb>`

Keep the matching hybrid release files together. Native product units differ; inspect units before summing sectors or comparing footprints.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_exiobase(
          path="/path/to/3.3.18", table="SUT", unit="Hybrid", extensions="all",
      )

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Relevant Zenodo releases

   - `v3.3.18 <https://doi.org/10.5281/zenodo.7244919>`__
   - newer consequential release not yet covered by the current MARIO hybrid parser:

   Important limitation: the current hybrid parser targets the **3.3.18** bundle. It does **not** yet include the later consequential developments released separately on `Zenodo <https://zenodo.org/records/15421526>`__.

.. mario-details:: Key arguments and local layout

   The hybrid workflow uses the same ``mario.parse_exiobase(...)`` entry point with these main selectors:

   - ``table``: choose ``"IOT"`` or ``"SUT"``;
   - ``unit``: use ``"Hybrid"``;
   - ``path``: extracted ``3.3.18`` release root;
   - ``extensions``: ``None``, ``[]``, ``"all"``, or one explicit list of extension groups.

   Typical extracted layout:

   .. code:: text

      EXIOBASE/3.3.18/
      ├── MR_HSUT_*.txt
      ├── MR_HIOT_*.txt
      ├── Land_*.txt
      ├── Emiss_*.txt
      ├── waste_sup_*.txt
      └── waste_use_*.txt

   Supported extension groups are ``resource``, ``Land``, ``Emiss``, ``Emis_unreg_w``, ``waste_sup``, ``waste_use``, ``pack_sup_waste``, ``pack_use_waste``, ``mach_sup_waste``, ``mach_use_waste``, ``stock_addition``, and ``crop_res``. ``Unreg_w`` is available for ``HSUT`` only.

   .. code:: python

      import mario

.. mario-details:: Optional download step

   If you do not already have the bundle locally, MARIO exposes a helper for the hybrid release it supports.

   .. code:: python

      info = mario.download_hybrid_exiobase(
          path="/path/to/3.3.18",
          )
      info

.. mario-details:: Parse the hybrid SUT

   This is the standard starting point for the hybrid supply-use table.

   .. code:: python

      db_sut = mario.parse_exiobase(
          path="/path/to/3.3.18",
          table="SUT",
          unit="Hybrid",
          extensions="all",
      )

.. mario-details:: Parse the hybrid IOT

   Use this when you need the hybrid input-output representation instead of the HSUT.

   .. code:: python

      db_iot = mario.parse_exiobase(
          path="/path/to/3.3.18",
          table="IOT",
          unit="Hybrid",
          extensions=["resource", "Emiss"],
      )

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
