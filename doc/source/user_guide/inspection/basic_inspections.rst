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
   db.matrices["baseline"].keys()

If you want to inspect one specific set:

.. code-block:: python

   db.get_index("Region")
   db.get_index("Sector")

The public API also accepts aliases and case-insensitive names:

.. code-block:: python

   db.region
   db.search("sector", "manufact")

Inspecting stored matrices
--------------------------

To check whether a *matrix* is already available in one *scenario*:

.. code-block:: python

   db.matrices["baseline"].keys()

To inspect one stored *matrix* as pandas data:

.. code-block:: python

   z = db.z. # this by default returns the "baseline" scenario
   Y = db.Y

For compact multi-matrix inspection:

.. code-block:: python

   data = db.query(
      matrices=["z", "Y"], 
      scenarios="baseline" # you can specify one or more scenarios
      )

This is usually the right starting point before running heavier workflows such
as aggregation, shocks, or structural transformations.

Notebook walkthrough
--------------------

Use the notebook below as the main inspection and calculation guide:

* :doc:`Basic inspections walkthrough <../../notebooks/user_guide/inspection/basic_inspections>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the basic inspections notebook <../../notebooks/user_guide/inspection/basic_inspections.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/user_guide/inspection/basic_inspections
