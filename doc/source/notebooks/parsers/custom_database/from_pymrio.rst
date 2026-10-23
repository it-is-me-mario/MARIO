:page-type: Database guide
:summary: Convert a populated pymrio IOSystem into a MARIO database.

pymrio objects
==============

.. container:: mario-companion

   :download:`Run the notebook <from_pymrio.ipynb>`

First load an IOSystem as io with pymrio. Select which extensions should become factors of production and satellite accounts.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_from_pymrio(
          io=io, value_added="all", satellite_account="all",
      )

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Expected input and assignment patterns

   This parser expects one already-loaded ``pymrio.IOSystem``, not a filesystem path.

   Key arguments:

   - ``io``: the ``pymrio.IOSystem`` to convert;
   - ``value_added``: dictionary or ``"all"`` selector for the factor side;
   - ``satellite_account``: dictionary or ``"all"`` selector for the satellite side;
   - ``include_meta``: when ``True``, copy the upstream metadata trail into the MARIO notes.

   Both ``value_added`` and ``satellite_account`` can be one explicit dictionary or the shorthand ``"all"``. Dictionary values can also be ``"all"`` or one slicer for part of an extension. With the ``"all"`` / ``"all"`` shorthand, MARIO looks for one factor-like extension such as ``factor_inputs``, ``factor_of_production``, ``value_added``, or ``primary_inputs``, and assigns the remaining extensions to satellites.

   The conversion result is an ``IOT``, not a ``SUT``.

   .. code:: python

      import mario
      import pymrio

.. mario-details:: Parse one local EXIOBASE bundle with pymrio

   The path below is only an example. Replace it with your local EXIOBASE directory.

   .. code:: python

      io = pymrio.parse_exiobase3(
          path="/path/to/IOT_2013_pxp.zip",
      )

.. mario-details:: Inspect available pymrio Extensions

   This helps you decide whether to pass explicit dictionaries or to rely on the ``"all"`` shorthand.

   .. code:: python

      [
          name
          for name in dir(io)
          if isinstance(getattr(io, name), pymrio.Extension)
      ]

.. mario-details:: Use the full shorthand

   When one unique factor-like Extension exists, you can use ``value_added="all"`` and ``satellite_account="all"``. This is practical for EXIOBASE parsed through ``pymrio``, where ``factor_inputs`` is the natural value-added block.

   .. code:: python

      db = mario.parse_from_pymrio(
          io=io,
          value_added="all",
          satellite_account="all",
      )

   .. code:: python

      db

.. mario-details:: Reference notes and caveats

   Upstream documentation: `pymrio documentation <https://pymrio.readthedocs.io/en/latest/index.html>`__.

   This is not a file parser. It converts one already-loaded ``pymrio.IOSystem``, so any filesystem layout requirements belong to the upstream ``pymrio`` parser that created ``io``.

   Practical caveats:

   - every ``pymrio.Extension`` must be classified explicitly, either through one mapping or through the ``"all"`` shorthand;
   - the ``"all"`` / ``"all"`` shorthand works only when MARIO can infer one unique factor-like extension;
   - this is a conversion bridge, not a generic harmonizer between arbitrary ``pymrio`` objects and MARIO;
   - the resulting MARIO database is currently an ``IOT``, not a ``SUT``.

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
