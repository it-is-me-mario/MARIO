Settings and Utilities
======================

Settings apply to the current Python process (or notebook kernel). Changing
them does not edit the installed package, and a new process starts with the
built-in defaults. Notebooks sharing the same kernel also share settings.

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

To reuse a configuration in another session, save and load it explicitly:

.. code-block:: python

   mario.download_settings("my_existing_directory")
   # In a later session:
   mario.upload_settings("my_existing_directory/settings.yaml")

Older MARIO versions saved changes directly in the package's ``settings.yaml``.
That file is no longer loaded automatically. To retain an older custom
configuration, copy it to your project and pass its path to ``upload_settings``.
Both a fresh session and ``reset_settings()`` use ``compute_method="inverse"``;
choose another method with ``set_compute_method`` when needed.

Invalid configuration keys, matrix aliases or compute options raise
``WrongFormat`` without replacing the active settings.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.download_settings
   ../api_document/mario.upload_settings
   ../api_document/mario.reset_settings
   ../api_document/mario.set_compute_method
   ../api_document/mario.set_linear_solver
   ../api_document/mario.set_linear_strategy
   ../api_document/mario.set_log_verbosity
   ../api_document/mario.set_palette
   ../api_document/mario.slicer
