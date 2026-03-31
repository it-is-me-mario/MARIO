Architecture Overview
=====================

The current codebase is organized around a few main layers:

``mario.api``
   The public surface centered on ``Database`` and ``CoreModel``.

``mario.compute``
   The matrix catalog, planner, resolver and formulas.

``mario.parsers``
   Parser infrastructure and built-in dataset parsers.

``mario.ops``
   Structural operations, exports, aggregation, transforms, shocks and add-sectors.

``mario.views``
   Plotting and tabular views.

``mario.internal`` and ``mario.storage``
   Internal state and storage backends that support newer parser and backend work.
