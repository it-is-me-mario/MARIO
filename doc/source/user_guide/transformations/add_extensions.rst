:page-type: Guide
:summary: Attach new environmental or other extension rows with explicit units.

Add satellite accounts
======================

.. container:: mario-companion

   :download:`Run the notebook <add_extensions.ipynb>`

.. mario-steps::

   .. mario-step:: 1 · Prepare values

      .. code-block:: python

         import mario

         db = mario.load_test("IOT")
         db.get_extensions_excel(path="extensions.xlsx", matrix="E")

      Fill the new account values against the model's native columns.
      :download:`See the filled example <../../_static/data/supporting_files/add_extensions_filled.xlsx>`.

   .. mario-step:: 2 · Set the unit

      For an account named ``CH4`` whose values are in kilograms:

      .. code-block:: python

         units = db.units["Satellite account"].iloc[:1].copy()
         units.index = ["CH4"]
         units.loc["CH4", "unit"] = "kg"

      The unit describes the supplied values; it does not convert them.

   .. mario-step:: 3 · Attach and check

      .. code-block:: python

         extended = db.add_extensions(
             io="extensions.xlsx", matrix="E", units=units, inplace=False,
         )
         extended.E.loc[["CH4"]]

For greenhouse gases, continue with :doc:`../analysis/greenhouse_gases`.
See :doc:`db.add_extensions() <../../api_document/mario.Database.add_extensions>`
for accepted inputs and other extension blocks.
