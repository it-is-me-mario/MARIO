Settings and Utilities
======================

Settings apply to the current Python process (or notebook kernel). By default,
changes last only for that session. Pass ``persist=True`` explicitly to save
defaults for future sessions. The installed package is never modified.
Notebooks sharing the same kernel also share active settings.

For an explanation of the compute options and practical configurations, see
:doc:`../user_guide/advanced/compute_settings`.

Matrix aliases in one session
-----------------------------

Matrix names are public aliases over fixed internal identifiers. You can
change them before or after loading a database:

.. code-block:: python

   import mario

   db = mario.load_test("IOT")
   settings = mario.download_settings()
   settings["nomenclature"].update({"E": "R", "EY": "Ry", "F": "Re"})
   mario.upload_settings(settings)

   emissions = db.query("R")  # db.query("E") still works
   footprint = db.query("Re")

   mario.reset_settings()
   emissions = db.query("E")  # the loaded data is preserved

``available_matrices()`` lists the currently configured public names. The
low-level ``matrices`` mappings and ``list_matrices()`` expose canonical keys;
matrix lookup also accepts current aliases. After resetting settings, use the
standard names again. Settings changes apply to all databases in the process.

Save defaults for future sessions
---------------------------------

Use the same dictionary (or a YAML file) with ``persist=True``:

.. code-block:: python

   settings = mario.download_settings()
   settings["nomenclature"].update({"E": "R", "EY": "Ry", "F": "Re"})
   mario.upload_settings(settings, persist=True)
   print(mario.get_settings_path())

New processes automatically load this profile when settings are first used.
Kernels that already loaded their settings retain their own configuration.
The profile belongs to the user and is shared by that user's Python
environments using this feature; it is not specific to one notebook or conda
environment.

``get_settings_path()`` returns the file location without creating it:

.. list-table:: Default profile locations
   :header-rows: 1
   :widths: 20 80

   * - Platform
     - File
   * - macOS
     - ``~/Library/Application Support/MARIO/settings.yaml``
   * - Windows
     - ``%APPDATA%/MARIO/settings.yaml`` (fallback: ``~/AppData/Roaming/MARIO/settings.yaml``)
   * - Linux and other platforms
     - ``$XDG_CONFIG_HOME/mario/settings.yaml`` (default: ``~/.config/mario/settings.yaml``)

To keep separate profiles for projects or environments, set the environment
variable ``MARIO_CONFIG_DIR`` to an absolute directory before starting Python
or the notebook kernel. MARIO will use ``settings.yaml`` in that directory.

Temporarily ignore or permanently remove saved defaults
-------------------------------------------------------

.. code-block:: python

   # At the beginning of a notebook: built-in names in this kernel only.
   mario.reset_settings()

   # Explicitly remove the saved profile and reset this kernel too.
   mario.reset_settings(persist=True)

The first call leaves the saved profile intact, so future sessions still load
it. The second removes only the user ``settings.yaml``; future sessions use
built-in defaults. Neither call changes data in loaded databases or settings
already active in other kernels. To restore a temporarily ignored profile in
the same session, use ``mario.upload_settings(mario.get_settings_path())``.

Share a configuration as a project file
---------------------------------------

Exporting YAML is separate from saving automatic defaults. Save and load a
project configuration explicitly:

.. code-block:: python

   mario.download_settings("my_existing_directory")
   # In a later session:
   mario.upload_settings("my_existing_directory/settings.yaml")

This workflow changes only the current session. The compute-setting helpers
also remain session-local; save their result with
``mario.upload_settings(mario.download_settings(), persist=True)`` if needed.

Validation and older configurations
-----------------------------------

Older MARIO versions saved changes directly in the package's ``settings.yaml``.
That file is no longer loaded automatically. To retain an older custom
configuration, copy it to your project and pass its path to ``upload_settings``.
Add ``persist=True`` if it should become the new user default. The built-in
compute method is ``inverse``; a saved profile may select a different method.
``reset_settings()`` restores ``inverse`` along with the other built-in defaults.

Invalid configuration keys, matrix aliases or compute options raise
``WrongFormat`` without replacing the active settings or the saved profile.
Profile writes are atomic; a failed write leaves the previous configuration
intact. A malformed or unreadable profile encountered in a new session emits a
warning and falls back to built-in defaults. The file is left untouched so it
can be corrected, replaced with a valid upload, or removed with
``reset_settings(persist=True)``.

See the executable walkthrough in
:doc:`../user_guide/inspection/custom_labels_and_aliases`.

Compute presets for large databases
-----------------------------------

BONSAI, GLORIA and EMERGING select ``compute_method="solve"`` and
``linear_strategy="direct"`` during parsing. They prefer the optional UMFPACK
backend and use SciPy when that backend cannot be imported. The selected
solver is recorded in the import log and can be inspected with
``mario.download_settings()["compute"]``. These defaults apply to this Python
session, including other databases loaded later, and do not alter saved settings.
An unsuccessful import restores the previous session settings. Other parsers
leave the active compute settings unchanged.

Install the optional solver before loading a full database. With conda:

.. code-block:: shell

   conda install -c conda-forge scikit-umfpack

With pip, install SuiteSparse using your system package manager first, then:

.. code-block:: shell

   python -m pip install "mariopy[umfpack]"

The Python wrapper is ``scikit-umfpack>=0.4.2``; SuiteSparse supplies its native
UMFPACK library and is not installed by pip. See the
`upstream installation guide <https://scikit-umfpack.github.io/scikit-umfpack/>`_.
The ``all`` extra includes this optional wrapper and has the same SuiteSparse
prerequisite. A regular ``pip install mariopy`` does not require it.

The preset choice uses the already catalogued model sizes, without parsing new
inputs or benchmarking solver speed:

.. list-table:: Full readings represented in the local metadata catalogue
   :header-rows: 1
   :widths: 26 27 20 27

   * - Database
     - Economic dimensions
     - One dense float64 square block
     - Automatic parser preset
   * - BONSAI b2 HIOT (21 Oct 2026 inputs)
     - 53,750 native production nodes
     - 21.53 GiB
     - Solve / direct; UMFPACK preferred
   * - EMERGING 2.2 / EMERGING-E
     - 32,585 / 35,770 nodes
     - 7.91 / 9.53 GiB
     - Solve / direct; UMFPACK preferred
   * - GLORIA v060 SUT
     - 19,680 activities and 19,680 commodities
     - 2.89 GiB per block
     - Solve / direct; UMFPACK preferred
   * - EXIOBASE monetary ixi / pxp
     - 7,987 / 9,800 nodes
     - 0.48 / 0.72 GiB
     - Active settings unchanged
   * - Eora26
     - 4,914 nodes
     - 0.18 GiB
     - Active settings unchanged
   * - OECD ICIO Extended / FIGARO
     - 4,050 / 3,200 nodes
     - 0.12 / 0.08 GiB
     - Active settings unchanged
   * - WIOD 2016 / ADB 74-economy reading
     - 2,464 / 2,625 nodes
     - 0.05 / 0.05 GiB
     - Active settings unchanged

These are lower bounds for storing a single dense block, calculated as
``8 * n**2`` bytes. They exclude inputs, copies and factorization memory.
GLORIA's combined activity/commodity system would need 11.54 GiB as a dense
square matrix; solve-based calculations can avoid materializing it. The actual
cost of sparse factorization also depends on sparsity and fill-in, so node
counts alone do not establish which solver is fastest. Eora26 counts do not
describe full-resolution Eora; GTAP and regional subsets need their own reading's
dimensions. No new source database is read to choose these presets.

Singularity handling is separate from performance: BONSAI retains
``singular_policy="partial"`` with warnings and NaN for affected results;
GLORIA and EMERGING select ``"raise"``. Missing optional libraries trigger the
SciPy fallback; a numerical or factorization error does not. An explicit
``mario.set_linear_solver("umfpack")`` still requires the backend to be installed.
Keep ``calc_all=False`` to compute only requested matrices; requesting a full
inverse explicitly can still allocate the large blocks described above.

API reference
-------------

.. toctree::
   :maxdepth: 1

   ../api_document/mario.download_settings
   ../api_document/mario.get_settings_path
   ../api_document/mario.upload_settings
   ../api_document/mario.reset_settings
   ../api_document/mario.set_compute_method
   ../api_document/mario.set_linear_solver
   ../api_document/mario.set_linear_strategy
   ../api_document/mario.set_singular_policy
   ../api_document/mario.PartialResultWarning
   ../api_document/mario.set_log_verbosity
   ../api_document/mario.set_palette
   ../api_document/mario.slicer
