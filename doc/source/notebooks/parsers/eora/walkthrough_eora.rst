:page-type: Database guide
:summary: Import an Eora26 model or a supported Eora1 national table.

EORA
====

.. container:: mario-companion

   :download:`Download notebook <walkthrough_eora.ipynb>`

Obtain the economic files and their matching labels locally. Eora1/Eora26 and Eora2 are distinct source families; this guide covers the supported Eora1/Eora26 inputs.

Import
------

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.parse_eora(path="/path/to/Eora26_2017_bp", multi_region=True)

   .. container:: mario-result

      **Result** · A MARIO database. Inspect ``db``, ``db.get_index("all")``
      and ``db.units`` before selecting quantities for your analysis.

Inputs and options
------------------

.. mario-details:: Important scope note

   MARIO does **not** parse the full Eora MRIO release.

   The supported workflows are only:

   - ``Eora26`` as the multi-region workflow;
   - local single-region Eora tables.

.. mario-details:: Relevant source page

   - Official Eora website: `Eora MRIO portal <https://www.worldmrio.com/>`__

   Automatic download is not part of the current MARIO workflow. The expected path is to work from local files that you already downloaded.

.. mario-details:: Key arguments

   The key public arguments are:

   - ``path``: one Eora file or one local dataset directory;
   - ``multi_region``: use ``True`` for ``Eora26`` and ``False`` for local single-region files;
   - ``table``: mainly relevant for single-region parsing;
   - ``indeces``: optional path to the ``Eora26`` label files;
   - ``name_convention``: ``full_name`` or ``abbreviation`` in the single-region workflow;
   - ``aggregate_trade``: whether to collapse detailed import/export rows in the single-region workflow;
   - ``country``: country selector when a directory contains multiple single-region files;
   - ``price``: optional selector when a single-region directory contains multiple price variants.

.. mario-details:: `Eora26` versus single-region Eora

   Use ``multi_region=True`` only for ``Eora26``. This workflow expects the standard ``Eora26_<year>_<price>_*.txt`` files plus the ``labels_*.txt`` files.

   Use ``multi_region=False`` for the local single-region tables. In that case MARIO resolves one file such as ``IO_ITA_2015_BasicPrice.txt`` and can usually infer whether it behaves like an ``IOT`` or a ``SUT``.

.. mario-details:: Label files for `Eora26`

   For ``Eora26``, MARIO needs both:

   - the numeric files such as ``T``, ``FD``, ``VA``, ``Q``, and ``QY``;
   - the label files such as ``labels_T.txt``, ``labels_FD.txt``, ``labels_VA.txt``, and ``labels_Q.txt``.

   If the label files already live next to the dataset files, ``indeces=`` can be omitted. Otherwise, point ``indeces=`` to the directory that contains them. The locally held 2016 copy lacks ``labels_VA.txt``. Its VA matrix has the same dimensions as 2017 and the other labels match byte-for-byte, so set ``indeces=`` to a complete common label folder, such as ``Eora26_2017_bp``, when parsing that 2016 copy.

.. mario-details:: Local layout examples

   There is no dedicated Eora 2 parser yet; current MARIO support is still limited to the Eora 1 style workflows covered here.

   ``Eora26`` expects a directory like:

   .. code:: text

      EORA/
      ├── Eora26_2017_bp/
      │   ├── Eora26_2017_bp_T.txt
      │   ├── Eora26_2017_bp_FD.txt
      │   ├── Eora26_2017_bp_VA.txt
      │   ├── Eora26_2017_bp_Q.txt
      │   └── Eora26_2017_bp_QY.txt
      └── indices/
          ├── labels_T.txt
          ├── labels_FD.txt
          ├── labels_VA.txt
          └── labels_Q.txt

   For single-region workflows, ``path`` can point to one file or to one directory of files named like ``IO_ITA_2015_BasicPrice.txt``. Use ``country=`` and ``price=`` when the directory contains multiple candidates.

   .. code:: python

      import mario

.. mario-details:: Parse one `Eora26` directory

   This is the supported multi-region Eora1 26 workflow. Replace the year in ``path`` to parse another verified local year. For the local 2016 copy, also pass ``indeces="/path/to/Eora26_2017_bp"``.

   .. code:: python

      db = mario.parse_eora(
          path="/path/to/Eora26_2017_bp",
          multi_region=True,
      )

      db

.. mario-details:: Parse one local single-region file

   This is the non-multi-region Eora workflow. When ``path`` points to a directory, ``country=`` selects the file to parse.

   .. code:: python

      db = mario.parse_eora(
          path="/path/to/IO_ITA_2017_BasicPrice.txt",
          multi_region=False,
      )

      db

.. mario-details:: Select one price variant in the single-region workflow

   Use ``price=`` when the directory contains more than one variant for the same country and year.

   .. code:: python

      db = mario.parse_eora(
          path="/path/to/IO_All_2017",
          multi_region=False,
          country="ITA",
          price="BasicPrice",
      )

      db

.. mario-details:: Aggregate trade rows in the single-region workflow

   Use ``aggregate_trade=True`` when you want imports and exports collapsed into totals instead of preserving bilateral trade labels.

   .. code:: python

      db = mario.parse_eora(
          path="/path/to/IO_All_2017",
          multi_region=False,
          country="ITA",
          price="BasicPrice",
          aggregate_trade=True,
      )

      db

.. mario-details:: Notes and caveats

   - there is no parser here for the full Eora MRIO release;
   - multi-region means ``Eora26`` only;
   - the ``Eora26`` parser applies a few consistency repairs during parsing; those notes are stored in metadata;
   - single-region parsing can infer ``IOT`` versus ``SUT`` automatically from the local file structure.

   .. code:: python

      db.meta_history

   .. code:: python

      db.sets

   .. code:: python

      db.units

Continue with :doc:`Inspect and query a database </user_guide/inspection/basic_inspections>`
or :doc:`Calculate matrices </user_guide/inspection/compute_matrices>`.
