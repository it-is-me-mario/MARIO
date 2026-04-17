File Formats
============

MARIO works with two broad families of input data:

* source-specific parser layouts, such as EXIOBASE or FIGARO distributions;
* generic custom database formats, such as Excel, TXT and Parquet.

Custom database formats
-----------------------

For generic custom databases, the most important formats are:

* Excel workbooks;
* TXT exports;
* Parquet exports.

These formats are meant to represent MARIO matrices directly. They are useful
for roundtrips, custom datasets and testing.

Depending on the workflow, a custom database may be imported from:

* flow matrices;
* coefficient matrices;
* or a mixture of both when the remaining side can be rebuilt.

Excel workbooks
---------------

Excel is the most user-facing custom format. It is convenient for:

* hand-built databases;
* validation;
* controlled editing of small and medium tables;
* templates such as aggregation, add-sectors and shock workbooks.

The main design choice in recent documentation is that workbook structure
should be explicit. When matrix structure is richer than the classical generic
layout, ``matrix_layouts`` should be used instead of forcing everything through
``Region / Level / Item``.

TXT and Parquet
---------------

TXT and Parquet are better suited to scripted workflows and roundtrips.

In practice:

* TXT is simple and transparent;
* Parquet is better for larger data and repeated machine use;
* both are less convenient than Excel for manual editing, but often better for
  reproducibility.

Shock workbooks
---------------

The shock workbook structure deserves separate attention because it has evolved.

For IOT databases, shocks now use flat-style columns that directly name the
relevant origin and destination sets instead of generic ``Level`` columns.

For SUT databases, the preferred shock format is split-native. This means
separate sheets such as:

* ``u`` and ``s``;
* ``Ya`` and ``Yc``;
* ``va`` and ``vc``;
* ``ea`` and ``ec``.

This is more faithful to SUT structure than a single large ``z``-style sheet.
Legacy shock files are still supported for compatibility.

Choosing the right format
-------------------------

As a rough rule:

* use dedicated parser layouts when you are importing a public database as
  released by its provider;
* use custom Excel when humans need to inspect or edit the data;
* use TXT or Parquet when the priority is scripted roundtrips or reproducible
  machine workflows.
