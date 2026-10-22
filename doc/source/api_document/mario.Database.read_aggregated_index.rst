mario.Database.read\_aggregated\_index
======================================

.. currentmodule:: mario

Both historical workbooks and grouped regional sheets produced by
:meth:`Database.get_aggregation_excel` are accepted. In-memory grouped sheets
use the same ``Regions``, ``Item``, ``Aggregation`` columns; their first column
may also be the DataFrame index after an Excel read with ``index_col=0``.

Regional rows expand only to existing ``(Region, Item)`` pairs. Regions sharing
a row must have the same entire classification for that set. Unknown pairs,
duplicate sources and invalid region groups are rejected before stored mappings
are changed. Omitted sources retain their labels. Blank targets require
``ignore_nan=True`` to retain the original item label.

Stored regional mappings have a ``(Region, Item)`` MultiIndex and one
``Aggregation`` column. A historical flat item mapping on a regional set is
treated as a common rule applied wherever that item actually exists; it never
creates missing regional nodes.

Geographic targets are checked across all regional sets, including regional
consumption categories. Regions with different original label sets cannot share
a target, and simultaneous item mappings must also leave matching label sets
in the regions being merged. These checks also cover collisions with regions
omitted from the input, which otherwise retain their original names.

.. automethod:: Database.read_aggregated_index
