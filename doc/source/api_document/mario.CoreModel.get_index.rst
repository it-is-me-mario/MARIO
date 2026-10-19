mario.CoreModel.get\_index
==========================

.. currentmodule:: mario

.. automethod:: CoreModel.get_index

The default return value remains a list when the same members are present in
every region. If a regional set differs, the result is a dictionary of lists::

    db.get_index("Activity")
    # Common classification: ["A1", "A2", ...]
    # Regional classification: {"IT": ["A1"], "DE": ["A2", "A3"], ...}

Each set is checked independently. Equal counts alone do not imply a common
classification. Differences in axis order alone do not require a dictionary;
the common list retains the existing logical index order. Regions without
members appear with an empty list.

Select one region, or explicitly request the union of distinct labels::

    db.get_index("Activity", region="IT")  # Always a list.
    db.get_index("Activity", flat=True)    # Union, always a list.
    db.get_index("all")                    # Each set uses its own representation.

The union does not imply that all its members exist in every region. Use the
regional view when validating region-item pairs.

Regional membership is read from already materialized matrix axes, including
nodes with only zero flows. No matrices are computed and no Cartesian product
is added. The stored logical indexes and ``ModelState`` index API retain their
legacy representation in this first implementation. Non-main levels, including
aggregation DataFrames, retain their existing behavior.
