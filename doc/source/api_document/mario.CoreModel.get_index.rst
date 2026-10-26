mario.CoreModel.get\_index
==========================

.. currentmodule:: mario

.. automethod:: CoreModel.get_index

The usual return value is an ordered list. For the
:ref:`special case of regional classifications <regional-classifications>`,
the result is a dictionary of lists::

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

Membership includes existing nodes with zero flows. Non-main levels, including
aggregation DataFrames, retain their existing representation.

NAM accepts its registered short names, set IDs and display labels with
``level="main"`` only. Its regional selectors follow the list/dictionary
convention above; aggregation levels are not available. See
:doc:`the NAM interface </reference/api_nam_database>` for its exact signature.
