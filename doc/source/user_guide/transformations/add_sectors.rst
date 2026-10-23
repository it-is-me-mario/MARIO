:page-type: Guide
:summary: Describe new production inventories, then insert them into the model.

Add and split sectors
=====================

.. container:: mario-companion

   :download:`Run the notebook <add_sectors.ipynb>`

.. mario-cards::
   :columns: 2

   .. mario-card:: Add
      :icon: add-rows

      Introduce new productive items and their inputs. Available for IOT and SUT.

   .. mario-card:: Split
      :icon: split

      Extract a new sector from a parent through constrained disaggregation.
      Currently **IOT only**, using the CVXLab model.

Prepare the workbook in two passes
----------------------------------

Use the :download:`source IOT <../../_static/data/supporting_files/add_sector_iot_table.xlsx>`
with the companion example files.

.. mario-steps::

   .. mario-step:: 1 · Structure

      .. code-block:: python

         import mario

         db = mario.parse_from_excel(
             path="add_sector_iot_table.xlsx", table="IOT", mode="flows",
         )
         db.get_add_sectors_excel(path="new_sectors.xlsx")

      Fill **Master** with region, new sector, inventory sheet, output unit
      and parent sector. Optional cluster sheets reuse labels across regions.

   .. mario-step:: 2 · Inventories

      .. code-block:: python

         db.read_add_sectors_excel(path="new_sectors.xlsx", get_inventories=True)

      Fill the generated sheets with input coefficients and their native
      database labels. Use **DB units** to check units. For splitting, also
      provide **Total outputs**, **Trades** and **Tolerances**.

   .. mario-step:: 3 · Apply

      .. code-block:: python

         db.read_add_sectors_excel(path="new_sectors.xlsx", read_inventories=True)
         expanded = db.add_sectors(inplace=False)
         expanded.get_index("Sector")

      This inserts the inventories. A split additionally needs the
      disaggregation step described in the companion notebook.

.. mario-details:: Workbook examples and sheet layout

   * :download:`Empty template <../../_static/data/supporting_files/add_sector_iot_template.xlsx>`
   * :download:`Filled Master <../../_static/data/supporting_files/add_sector_iot_master_filled.xlsx>`
   * :download:`Completed inventories <../../_static/data/supporting_files/add_sector_iot_inventories_filled.xlsx>`

   .. figure:: ../../_static/images/add_sector_master.png
      :alt: Add-sector Master sheet with region, sector and inventory identifiers.

      The IOT Master sheet. In a SUT it uses Activity and Commodity, includes
      Market share and does not expose Add or Split.

.. mario-details:: Splitting and solver requirements

   The split model uses a nonlinear optimization problem. Large problems may
   need a suitable external solver such as MOSEK and its licence. Follow the
   companion notebook for the CVXLab assets, solve and balancing sequence.
   Inspect feasibility and the resulting balance before using the new sectors.

See :doc:`db.add_sectors() <../../api_document/mario.Database.add_sectors>` for
validation options, including parent value-added completion and inventory sums.
