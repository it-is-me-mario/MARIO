:page-type: Guide
:summary: Select a technology or sales-structure assumption and construct a symmetric table.

Convert a SUT to an IOT
=======================

.. container:: mario-companion

   :download:`Download notebook <sut_to_iot.ipynb>`

.. container:: mario-recipe

   .. code-block:: python

      import mario

      sut = mario.load_test("SUT")
      iot = sut.to_iot(method="A", inplace=False)
      iot.Z

   .. container:: mario-result

      **Result** · A new IOT with one productive set, ``Sector``.
      ``inplace=False`` keeps the original SUT available for comparison.

Choose the assumption
---------------------

.. list-table::
   :header-rows: 1

   * - Method
     - Result
     - Assumption
   * - A
     - Product by product
     - Product technology
   * - B
     - Product by product
     - Industry technology
   * - C
     - Industry by industry
     - Fixed industry sales structure
   * - D
     - Industry by industry
     - Fixed product sales structure

**The conversion keeps the baseline and drops other scenarios.**
Methods A/C require square, invertible supply and zero activity final demand;
B/D preserve nonzero activity final demand and accounts on either side.

The transformation changes the model's assumptions and axes. Inspect
``iot.get_index("Sector")`` and the resulting units before reusing selectors.

.. mario-details:: Starting from BONSAI

   BONSAI publishes its own native hybrid IOT. Import it with
   ``mario.parse_bonsai(..., table="IOT")`` when you want that published model.
   See :doc:`../parsers/bonsai` for the distinction between Balanced HSUT and
   native HIOT inputs.

See :doc:`db.to_iot() <../../api_document/mario.Database.to_iot>` for the method
assumptions and implementation constraints.
