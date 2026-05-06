Setup
=====

.. toctree::
   :maxdepth: 1
   :hidden:

   installation

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

The documentation currently follows the code in ``main``, while the
corresponding PyPI release has not been published yet.

For now, please use the temporary installation instructions in
:doc:`installation`.

Next steps
----------

Head over to :doc:`../concepts/index` to understand the cornerstone definitions and conventions, 
before moving to the :doc:`../user_guide/index` sections.
