Documentation
=============

This page documents the documentation workflow used in this repository,
with a focus on notebook-backed pages and contributor maintenance tasks.

Notebook Paths: Public Placeholders, Local Execution
----------------------------------------------------

The public documentation must not expose machine-specific paths such as
``/Users/...`` or ``/Volumes/...``. At the same time, maintainers need to
execute notebooks locally against real files.

MARIO supports this through a two-layer workflow:

* notebook-backed docs committed under ``doc/source/notebooks/...`` and
  ``doc/source/user_guide/...`` keep generic placeholders instead of local
  absolute paths;
* local machine paths are stored in ``doc/notebook_paths.local.yaml``
  (git-ignored);
* ``doc/scripts/resolve_notebooks.py`` executes an in-memory copy where
  placeholders are replaced with local paths, then copies only outputs back to
  the source notebook;
* output sanitization replaces local paths back to placeholders before writeback
  and fails on private path leaks by default.

This keeps examples executable for maintainers and generic for users.

The current docs build keeps ``nbsphinx_execute = "never"`` in
``doc/source/conf.py``. In practice, that means notebook outputs are committed
artifacts: Read the Docs renders them, but does not execute them during the
build.

Configuration
-------------

Start from:

.. code-block:: bash

	 cp doc/notebook_paths.example.yaml doc/notebook_paths.local.yaml

Then fill local values in ``doc/notebook_paths.local.yaml``.

The configuration supports:

* global replacements;
* notebook-scoped replacements;
* optional cell-scoped replacements (zero-based cell indexes);
* optional ``skip_cells`` for expensive or intentionally non-executed cells.

Execution Workflow
------------------

Execute one or more notebooks with local replacements:

.. code-block:: bash

	python doc/scripts/resolve_notebooks.py \
		doc/source/notebooks/parsers/oecd/walkthrough_oecd.ipynb

Execute a user-guide notebook:

.. code-block:: bash

	python doc/scripts/resolve_notebooks.py \
		doc/source/user_guide/advanced/greenhouse_gas_calculations.ipynb

Execute many notebooks (shell glob expansion):

.. code-block:: bash

	python doc/scripts/resolve_notebooks.py doc/source/notebooks/parsers/**/*.ipynb

Useful options:

* ``--dry-run``: validate replacements without executing;
* ``--kernel-name <name>``: force a specific kernel;
* ``--sanitize-local-paths``: migrate accidental local literals in notebook
  sources into placeholders and append mappings to
  ``doc/notebook_paths.local.yaml``.

Other maintainer tasks
----------------------

The docs also include a few generated assets and helper indexes.

If you touch the terminology workbook, regenerate the terminology tables:

.. code-block:: bash

	python doc/scripts/generate_terminology_tables.py

If you touch parser coverage metadata or the packaged country coverage workbook,
regenerate the parser coverage assets:

.. code-block:: bash

	python doc/scripts/generate_parser_coverage_table.py

When adding, moving, or deleting public pages, also check:

* the relevant ``toctree`` entries and high-level indexes;
* links in ``doc/source/_static/data/docs-assistant-manifest.json``;
* links in ``doc/source/_static/docs-assistant-data.js`` when the docs assistant
  should expose the page.

Validation
----------

For non-trivial doc changes, run a local build before committing:

.. code-block:: bash

	conda run -n mario make -C doc html

Policy
------

When editing notebook docs:

* keep public source cells generic;
* never commit private machine paths;
* keep local mappings only in ``doc/notebook_paths.local.yaml``;
* run ``resolve_notebooks.py`` to refresh outputs before doc builds when needed.
