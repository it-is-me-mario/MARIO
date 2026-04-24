Calculate Linkages
==================

This workflow covers the standard computation of backward and forward linkages
from an existing database.

Core method
-----------

The relevant entry point is
:doc:`Database.calc_linkages </api_document/mario.Database.calc_linkages>`.

Typical use
-----------

.. code-block:: python

   linkages = db.calc_linkages()

You can also control common options such as normalization and diagonal removal
through the method arguments.

When to use it
--------------

This workflow is useful when you want to:

* inspect structural interdependencies across sectors or activities;
* compare linkage profiles across scenarios;
* support exploratory structural analysis before applying transformations.

Checks after calculation
------------------------

After computing linkages, it is usually worth checking:

* which scenario was used;
* whether normalization was applied;
* how diagonal terms were treated.
