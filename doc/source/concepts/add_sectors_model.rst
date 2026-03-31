Add Sectors Model
=================

``add_sectors(...)`` is now a workbook-driven workflow rather than a compact
one-shot helper.

The current public API revolves around:

* ``get_add_sectors_excel(...)`` to create the workbook template;
* ``read_add_sectors_excel(...)`` and ``get_inventory_sheets(...)`` to prepare
  and validate the workbook;
* ``add_sectors(...)`` to execute the structural update;
* optional ``split=True`` workflows backed by
  `CVXLab <https://cvxlab.readthedocs.io/>`_ for richer IOT split cases.

For a more detailed implementation note, see :doc:`../add_sector_refactor`.
