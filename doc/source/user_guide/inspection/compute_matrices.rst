Compute Results
===============

This workflow collects the quickest ways to calculate *matrices* that are not
yet materialized in a parsed *database*.

Typical calculations
--------------------

Useful first calculations are:

* ``calc_all`` and dotted access;
* inspect which *matrices* are already stored;
* calculate selected derived *matrices*;
* inspect the calculated results;
* calculate or query results in a non-baseline *scenario*.

Examples
--------

Start from a parsed database. The examples below use the packaged MARIO test
table:

.. code-block:: python

   import mario

   db = mario.load_test("IOT")

Check which matrices are already stored in the ``baseline`` scenario:

.. code-block:: python

   db.matrices["baseline"].keys()

Calculate selected matrices with ``calc_all``:

.. code-block:: python

   db.calc_all(["X", "z", "f"])
   db.matrices["baseline"].keys()

``calc_all`` also materializes the intermediate matrices needed to derive the
requested ones.

Inspecting calculated matrices
------------------------------

Calculated matrices can be accessed directly:

.. code-block:: python

   db.X
   db.z
   db.f

By default, direct matrix access returns the ``baseline`` scenario.

Calculating in scenarios
------------------------

Calculations can also be triggered in a non-baseline scenario. First create a
scenario from the current baseline:

.. code-block:: python

   db.clone_scenario("baseline", "new_scenario")

Then query a matrix in that scenario:

.. code-block:: python

   db.query("p", "new_scenario")

To compare which matrices are materialized in each scenario:

.. code-block:: python

   db.matrices["baseline"].keys()
   db.matrices["new_scenario"].keys()

Notebook walkthrough
--------------------

Use the notebook below as the main compute-results guide:

* :doc:`Compute results walkthrough <../../notebooks/user_guide/inspection/compute_matrices>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the compute results notebook <../../notebooks/user_guide/inspection/compute_matrices.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/user_guide/inspection/compute_matrices
