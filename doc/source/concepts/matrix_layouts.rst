Matrix Layouts
==============

Historical MARIO workbooks often used the public axes ``Region / Level / Item``.
Newer workflows also support explicit layouts where the public axes directly
expose the real MARIO sets carried by a matrix.

Examples
--------

Classical extension matrix
   ``E`` rows may be just ``Satellite account``.

Regionalized extension matrix
   ``E`` rows may be ``Region`` plus ``Satellite account``.

Regionalized and sectorized factor matrix
   ``V`` rows may be ``Region`` plus ``Sector`` plus ``Factor of production``.

The ``matrix_layouts`` parser argument
--------------------------------------

``matrix_layouts`` lets you declare richer row layouts for matrices such as
``V``, ``E``, ``v``, ``e``, ``VY`` and ``EY``.

This is the mechanism used by MARIO to parse newer explicit workbooks while
remaining compatible with legacy files.
