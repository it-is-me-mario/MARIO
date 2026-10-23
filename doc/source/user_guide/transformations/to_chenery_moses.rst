:page-type: Guide
:summary: Convert an Isard SUT into the Chenery–Moses representation.

Change the SUT trade representation
===================================

.. container:: mario-companion

   :download:`Download notebook <to_chenery_moses.ipynb>`

.. container:: mario-recipe

   .. code-block:: python

      import mario

      sut = mario.load_test("SUT")
      converted = sut.to_chenery_moses(inplace=False)
      converted.is_isard()

   .. container:: mario-result

      **Result** · A SUT with a different representation of interregional
      flows. The activity and commodity distinction remains.

Inspect the affected blocks
---------------------------

.. code-block:: python

   converted.U
   converted.Yc
   converted.S

Compare these with the original table before continuing the analysis.
Use :doc:`db.to_chenery_moses()
<../../api_document/mario.Database.to_chenery_moses>` for the transformation
rules and assumptions.
