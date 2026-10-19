Settings and Utilities
======================

Settings apply to the current Python process (or notebook kernel). By default,
changes last only for that session. Pass ``persist=True`` explicitly to save
defaults for future sessions. The installed package is never modified.
Notebooks sharing the same kernel also share active settings.

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
   ../api_document/mario.set_log_verbosity
   ../api_document/mario.set_palette
   ../api_document/mario.slicer
