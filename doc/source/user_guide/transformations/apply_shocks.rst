:page-type: Guide
:summary: Create an alternative scenario from specified changes to a baseline.

Apply shocks and compare scenarios
==================================

.. container:: mario-companion

   :download:`Download notebook <apply_shocks.ipynb>`

.. container:: mario-flow

   **Baseline** → **Specified changes** → **Alternative** → **Comparison**

Use a filled shock workbook
---------------------------

The packaged example changes technical and satellite coefficients in the test IOT.
:download:`Download the filled workbook <../../_static/data/supporting_files/shock_IOT_filled.xlsx>`
and save it beside your script.

.. container:: mario-recipe

   .. code-block:: python

      import mario

      db = mario.load_test("IOT")
      db.shock_calc(
          io="shock_IOT_filled.xlsx", z=True, e=True,
          scenario="alternative",
      )
      change = db.query(
          "z", scenarios="alternative",
          base_scenario="baseline", type="relative",
      )

   .. container:: mario-result

      **Result** · A new scenario and a DataFrame of relative changes against
      the baseline. Inspect both the changed inputs and the resulting outputs.

Prepare your own workbook
-------------------------

.. code-block:: python

   db.get_shock_excel(path="my_shocks.xlsx")

Fill the relevant sheets, then enable those blocks in ``shock_calc()``.
For a SUT, generate the template from that SUT to obtain its activity and
commodity labels.

.. mario-details:: Plot the result

   .. code-block:: python

      fig = db.plot(
          matrix="Z", scenarios=["alternative"],
          base_scenario="baseline", difference="relative",
          preset="heatmap", auto_open=False, path=False,
      )
      fig.show()

.. mario-details:: Chain changes or edit inputs programmatically

   ``shock_calc(..., base_scenario="alternative", scenario="step 2")``
   applies a second change to an existing scenario. The
   :doc:`API reference <../../api_document/mario.Database.shock_calc>` describes
   selectors and coefficient changes.

   If you edit matrices directly, reset stale calculated quantities before
   recalculating. Follow the complete code and reset sequence in the companion
   notebook; editing an input does not make cached results valid automatically.

For generation or trade shares, use :doc:`../advanced/electricity_mix`.
