To Chenery-Moses
================

This workflow covers the conversion of an Isard SUT into a Chenery-Moses SUT.

Core method
-----------

The relevant entry point is
:doc:`Database.to_chenery_moses </api_document/mario.Database.to_chenery_moses>`.

Typical use
-----------

.. code-block:: python

   db.to_chenery_moses()

or, if you want to keep the original object unchanged:

.. code-block:: python

   db_cm = db.to_chenery_moses(inplace=False)

You can also limit the operation to selected scenarios:

.. code-block:: python

   db.to_chenery_moses(scenarios=["baseline", "policy"])

What changes
------------

This transformation updates the relevant SUT matrices for the selected
scenarios and then resets those scenarios to flow matrices so coefficient-side
blocks can be rebuilt consistently on demand.

Checks after transformation
---------------------------

After the conversion, it is usually worth checking:

* the transformed ``Z`` and ``Y`` matrices;
* the available stored matrices in the affected scenarios;
* whether the database now satisfies the Chenery-Moses structure you expect.

Notebook walkthrough
--------------------

Use the notebook below as the main Chenery-Moses guide:

* :doc:`To Chenery-Moses walkthrough <../../notebooks/user_guide/transformations/to_chenery_moses>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the Chenery-Moses notebook <../../notebooks/user_guide/transformations/to_chenery_moses.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/user_guide/transformations/to_chenery_moses
