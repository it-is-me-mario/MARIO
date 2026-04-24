Setup
=====

What is MARIO
-------------

MARIO is a Python library for working with :ref:`Input-Output Tables (IOTs) <concept-iots>` and
:ref:`Supply and Use Tables (SUTs) <concept-suts>`. Once parsed, any readble *table* becomes a *database* 
object that can be inspected, transformed and whose *matrices* can be computed.

In practice, MARIO is built around a simple workflow:

* parse or load a *database*
* inspect its structure and available *matrices*
* compute derived *matrices* or other indicators on demand 
* transform, aggregate/**disaggregate**, or shock the *database*
* export the results

Installation
------------

Preferably, create a clean Python environment:

.. code-block:: bash

   conda create -n mario python=3.10
   conda activate mario

Then install MARIO from PyPI:

.. code-block:: bash

   pip install mariopy

A quick sanity check after installation is:

.. code-block:: python

   import mario
   db = mario.load_test("IOT") # or SUT
   db

If this works, the package is installed correctly.

Next steps
----------

Head over to :doc:`../concepts/index` to understand the cornerstone definitions and conventions, 
before moving to the :doc:`../user_guide/parsers/index` and :doc:`../user_guide/index` sections.
