Matrix Layouts
==============

Historical MARIO workbooks often used the public axes ``Region / Level / Item``.
Newer workflows also support explicit layouts where the public axes directly
expose the real MARIO sets carried by a matrix.

The goal of ``matrix_layouts`` is not to invent new matrix semantics. It is to
make the workbook tell MARIO exactly which set is present on each axis, instead
of forcing all files into a single generic ``Level / Item`` convention.

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

Why this matters
----------------

Explicit layouts solve two recurring problems:

* they make workbook structure easier to read and validate;
* they remove ambiguity for blocks that may carry more than one meaningful row
  structure.

Without explicit layouts, two files may both look like valid ``E`` matrices
while actually representing different row semantics.

When to use them
----------------

Use ``matrix_layouts`` when:

* your workbook exposes real set names directly;
* extension rows include regionalized or sectorized structure;
* you want the file format to stay close to what MARIO will expose after
  parsing.

Legacy workbooks without explicit layouts are still supported, but new custom
database templates should prefer explicit layouts whenever the matrix structure
is richer than the classical generic convention.
