Projects & Publications
=======================

How MARIO is used in research projects and peer-reviewed publications, and the
software projects it works closely with.


Research projects
-----------------

.. mario-cards::
   :columns: 3
   :links:

   .. mario-card:: `ENTICE <https://enticeproject.eu>`_
      :kicker: Horizon Europe · 101184775
      :logo: /_static/images/logo_entice.svg

      Builds data and models to assess how trade and trade policy interact with
      climate, industry and environmental outcomes.

   .. mario-card:: `IAM COMPACT <https://www.iam-compact.eu>`_
      :kicker: Horizon Europe · 101056306
      :logo: /_static/images/logo_iam_compact.png

      Extended integrated assessment modelling for climate policy beyond technology
      pathways, with model ensembles and co-creation.

   .. mario-card:: `FULFILL <https://fulfill-sufficiency.eu>`_
      :kicker: Horizon 2020 · 101003656
      :logo: /_static/images/logo_fulfill.png

      Studied how sufficiency and lifestyle change can contribute to deep
      decarbonisation.


Close software projects
-----------------------

.. mario-cards::
   :columns: 3

   .. mario-card:: pymrio
      :kicker: Handshake protocol
      :logo: /_static/images/logos/pymrio.png

      Python library for multi-regional input-output analysis. Databases move
      between the two tools with :func:`parse_from_pymrio <mario.parse_from_pymrio>` and
      :meth:`to_pymrio <mario.Database.to_pymrio>`.

      .. rst-class:: mario-link-pills

      `GitHub <https://github.com/IndEcol/pymrio>`__
      `Docs <https://pymrio.readthedocs.io/en/latest/>`__
      `Article <https://openresearchsoftware.metajnl.com/articles/10.5334/jors.251>`__

   .. mario-card:: CVXlab
      :kicker: Developed in POLIMI
      :logo: /_static/images/logos/cvxlab.png

      Python laboratory for convex optimisation models, built on cvxpy. MARIO
      uses it to solve the sector split in
      :meth:`add_sectors <mario.Database.add_sectors>`, with more
      integrations to come.

      .. rst-class:: mario-link-pills

      `GitHub <https://github.com/cvxlab/cvxlab>`__
      `Docs <https://cvxlab.readthedocs.io/en/latest/>`__

   .. mario-card:: Industrial Ecology Dashboard
      :kicker: IndEcol community list
      :logo: /_static/images/logos/github.svg

      Curated list of open-source software for industrial ecology. MARIO is
      listed among the input-output analysis tools, next to pymrio.

      .. rst-class:: mario-link-pills

      `GitHub <https://github.com/IndEcol/Dashboard>`__


Publications
------------

.. mario-publications::
   :bib: ../publications/mario.bib
   :code: Rinaldi2026=https://github.com/it-is-me-mario/pv-hlca-model
   :cite: Tahavori2023
