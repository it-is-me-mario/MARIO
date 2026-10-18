mario.CoreModel.matrices
========================

.. currentmodule:: mario

.. autoproperty:: CoreModel.matrices

Scenario mappings always store canonical matrix identifiers, regardless of
active nomenclature settings. For example, after configuring ``E`` as ``R``,
both ``db.matrices["baseline"]["E"]`` and ``db.matrices["baseline"]["R"]``
access the same block, while iterating over the mapping yields ``E``.

Assigning a block or a scenario also normalizes current aliases. Use
``query`` or ``get_data`` for calculated matrices and scenario comparisons;
direct mapping access only retrieves blocks already materialized in storage.
