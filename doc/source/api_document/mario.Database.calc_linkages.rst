mario.Database.calc\_linkages
=============================

.. currentmodule:: mario

``db.calc_linkages(...)`` returns the standard backward and forward linkages.

When ``multi_mode=False``, the dataframe also includes ``Forward Amplification``
and ``Backward Amplification`` ratios, defined as ``Total / Direct`` on the raw
linkage values.

When ``multi_mode=True``, the dataframe keeps the ``Local`` and ``Foreign``
components and adds their ``Local Share`` and ``Foreign Share`` for each
linkage measure.

.. automethod:: Database.calc_linkages