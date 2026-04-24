Basic Inspections
=================

This workflow collects the quickest ways to inspect a parsed *database* before
you start transforming or exporting it.

Typical checks
--------------

Useful first checks are:

* print the database object in a notebook or REPL to inspect its metadata;
* inspect available *scenarios*;
* inspect the canonical *indices*;
* inspect which *matrices* are already stored;
* query one or more *matrices* in pandas form.

Examples
--------

.. code-block:: python

   db
   db.scenarios
   db.sets
   db.get_index("all")
   db.list_blocks()

If you want to inspect one specific set:

.. code-block:: python

   db.get_index("Region")
   db.get_index("Sector")

The public set resolver also accepts aliases and case-insensitive names:

.. code-block:: python

   db.region
   db.search("sector", "manufact")

Inspecting stored matrices
--------------------------

To check whether a *matrix* is already available in one *scenario*:

.. code-block:: python

   db.has_block("z")
   db.list_blocks(scenario="baseline")

To inspect one stored *matrix* as pandas data:

.. code-block:: python

   z = db.get_block_as_pandas("z")
   Y = db.get_block_as_pandas("Y")

For compact multi-matrix inspection:

.. code-block:: python

   data = db.query(matrices=["z", "Y"])

This is usually the right starting point before running heavier workflows such
as aggregation, shocks, or structural transformations.
