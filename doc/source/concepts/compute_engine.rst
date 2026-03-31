Compute Engine
==============

MARIO no longer treats every derived matrix as a one-off special case.

The compute layer is organized around:

* a catalog of known matrices;
* a planner that chooses how to derive a requested block;
* a resolver that executes the chosen steps;
* formula and primitive modules that perform the actual math.

This makes it easier to:

* add new standard blocks;
* explain how a derived matrix is computed;
* keep IOT and SUT formulas separated where needed.
