Documentation
=============

This page documents the documentation workflow used in this repository,
with a focus on notebook-backed pages.

Notebook Paths: Public Placeholders, Local Execution
----------------------------------------------------

The public documentation must not expose machine-specific paths such as
``/Users/...`` or ``/Volumes/...``. At the same time, maintainers need to
execute notebooks locally against real files.

MARIO supports this through a two-layer workflow:

* notebooks committed in ``doc/source/notebooks/...`` keep generic placeholders
	(for example ``/path/to/ITA2022ttl.csv``);
* local machine paths are stored in ``doc/notebook_paths.local.yaml``
	(git-ignored);
* ``doc/scripts/resolve_notebooks.py`` executes an in-memory copy where
	placeholders are replaced with local paths, then copies only outputs back to
	the source notebook;
* output sanitization replaces local paths back to placeholders before writeback
	and fails on private path leaks by default.

This keeps examples executable for maintainers and generic for users.

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

Execute many notebooks (shell glob expansion):

.. code-block:: bash

	 python doc/scripts/resolve_notebooks.py doc/source/notebooks/parsers/**/*.ipynb

Useful options:

* ``--dry-run``: validate replacements without executing;
* ``--kernel-name <name>``: force a specific kernel;
* ``--sanitize-local-paths``: migrate accidental local literals in notebook
	sources into placeholders and append mappings to
	``doc/notebook_paths.local.yaml``.

Policy
------

When editing notebook docs:

* keep public source cells generic;
* never commit private machine paths;
* keep local mappings only in ``doc/notebook_paths.local.yaml``;
* run ``resolve_notebooks.py`` to refresh outputs before doc builds when needed.
