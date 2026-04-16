SUT Split and Unified Blocks
============================

SUT databases in MARIO have two useful views of the same system:

* a split-native representation, which follows supply-use structure directly;
* a unified public view, which makes some workflows feel closer to IOT usage.

Split-native blocks
-------------------

The native SUT flow blocks are:

* ``U`` and ``S``;
* ``Ya`` and ``Yc``;
* ``Va`` and ``Vc``;
* ``Ea`` and ``Ec``;
* ``EY`` and ``VY``.

These are the blocks that preserve the original commodity/activity distinction.
They are usually the right level to reason about parsing, SUT assumptions and
SUT-specific transformations.

Unified views
-------------

MARIO can also expose:

* ``Z`` as a unified productive block;
* ``Y`` as a unified final-demand block;
* ``V`` and ``E`` as unified extension blocks.

These are views built from the split-native representation. They are convenient
for inspection, exports and some user-facing workflows, but they do not replace
the split blocks conceptually.

How MARIO moves between them
----------------------------

The compute catalog knows how to:

* concatenate split blocks into unified views;
* extract split blocks back out of unified views when the structure is known.

This is handled by the resolver in the same way as ordinary formulas. From the
user point of view, it means a SUT database can expose ``db.Z`` or ``db.U``
without forcing a single internal representation everywhere.

Why the distinction matters
---------------------------

The distinction is not just cosmetic.

It affects:

* which blocks should be treated as native during resets;
* how technology assumptions are applied;
* which exports are most faithful to the original SUT structure;
* which workflows are efficient on large tables.

For example, recent SUT resets in MARIO were made table-aware so that a reset
to flows keeps ``U``, ``S``, ``Ya``, ``Yc`` and the other split-native blocks,
instead of rebuilding everything first through a unified ``Z`` view.
