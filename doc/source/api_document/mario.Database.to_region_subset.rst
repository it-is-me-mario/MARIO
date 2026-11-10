mario.Database.to_region_subset
===============================

.. currentmodule:: mario

Keep a selected subset of regions explicit while treating the remaining
regions as exogenous imports and exports. This generalizes
``Database.to_single_region(...)`` to the case where more than one region must
remain endogenous.

See :doc:`Extract a region or subset <../user_guide/transformations/mrio_to_srio>`
for SUT product/producer import classification and the native accounting blocks.

.. automethod:: Database.to_region_subset
