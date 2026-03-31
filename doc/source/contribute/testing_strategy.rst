Testing Strategy
================

MARIO uses a mix of unit tests and small real-data regression tests.

Current priorities
------------------

* parser correctness on real but manageable workbooks;
* export and re-import roundtrips;
* aggregation behavior across legacy and explicit layouts;
* ``add_sectors`` workbook and engine behavior;
* source-specific parser stability.

Real-data fixtures
------------------

The repository now includes small real-data workbook fixtures under
``tests/fixtures/realdata``. These are intended to keep parser, export and
aggregation behavior grounded on realistic inputs instead of purely synthetic
tables.
