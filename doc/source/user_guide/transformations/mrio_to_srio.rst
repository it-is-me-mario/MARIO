:page-type: Guide
:summary: Keep selected regions and represent their exchanges with the remaining economy.

Extract a region or subset
==========================

.. container:: mario-companion

   :download:`Run the notebook <mrio_to_srio.ipynb>`

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      regional = db.to_single_region("Reg1", inplace=False)
      regional.regions

   .. container:: mario-result

      **Result** · A database for the retained region, with external exchanges
      represented in value-added and final-demand accounts.

Keep several regions
--------------------

.. code-block:: python

   subset = db.to_region_subset(["Reg1", "Reg2"], inplace=False)

Check the new boundary
----------------------

.. code-block:: python

   regional.factors
   regional.consumption_categories
   regional.Z

This operation changes the model boundary. Inspect the new trade accounts
before interpreting regional value added or final demand.

See :doc:`db.to_single_region() <../../api_document/mario.Database.to_single_region>`
and :doc:`db.to_region_subset() <../../api_document/mario.Database.to_region_subset>`.
