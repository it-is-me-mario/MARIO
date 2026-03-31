Advanced Tutorials
==================

This section is for workflows that assume you already know the basic MARIO
surface.

Current advanced topics
-----------------------

* layout-aware IOT and SUT parsing with ``matrix_layouts``;
* roundtrip testing across Excel, TXT and Parquet exports;
* workbook-driven ``add_sectors`` flows;
* `CVXLab <https://cvxlab.readthedocs.io/>`_-backed IOT split workflows.

The codebase also contains real-data regression fixtures under
``tests/fixtures/realdata``. These are useful when you want to validate parser,
export and aggregation behavior on small but realistic workbooks.

Recommended reading order
-------------------------

* :doc:`../concepts/matrix_layouts`
* :doc:`../reference/file_formats`
* :doc:`../contribute/testing_strategy`
