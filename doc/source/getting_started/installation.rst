Installation
============

MARIO can be installed in a standard Python environment with ``pip`` or in a
Conda/Mamba environment.

Minimal installation
--------------------

.. code-block:: bash

   pip install mario

Repository environment
----------------------

If you are working from the MARIO repository, the two main environment files are:

* ``requirements.txt`` for a pip-oriented workflow;
* ``requirements.yml`` for a Conda/Mamba-oriented workflow.

Documentation build
-------------------

To build the local documentation:

.. code-block:: bash

   pip install -r doc/docs-requirements.txt
   make -C doc html

Then open ``doc/build/html/index.html`` in your browser.

Optional dependencies
---------------------

Some workflows need extra dependencies:

* plotting relies on Plotly and related packages;
* parser-specific workflows may need optional reader dependencies;
* ``add_sectors(split=True)`` requires CVXLab;
* notebook rendering in the documentation requires Pandoc.
