mario.CoreModel.available_aggregations
======================================

.. currentmodule:: mario

.. autoproperty:: CoreModel.available_aggregations

For a GLORIA release 060 SUT::

    db.available_aggregations["Activity"]
    # {'NACE Rev. 2.1': ['section', 'division', 'group', 'class']}

These are supported hierarchy levels for this native variant. Some individual
items can remain unresolved. See
:doc:`the aggregation guide <../user_guide/transformations/classification_aggregation>`
for examples and :attr:`~mario.CoreModel.available_concordances` for target
editions usable by code lookup alone.
