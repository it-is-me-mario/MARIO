mario.Database.calc\_trades\_exposure
======================================

.. currentmodule:: mario

``db.calc_trades_exposure(...)`` calculates embodied trade-content
exposure to one or more contributor Regions.

The method returns the share of absolute contributor-Region content attributable
to the Regions selected through ``exposed_to``. The output keeps the same trade
axes as ``db.calc_trades_content(...)`` after collapsing contributor detail:
rows are origin Regions and columns are destination Regions. When
``aggregate=False``, the output keeps the same ``Intermediate`` / ``Final``
column split.

``indicator``, ``item``, ``scenario``, ``method``, ``clusters``,
``clusters_direction``, ``intermediate``, ``final`` and ``aggregate`` behave
like they do in ``db.calc_trades_content(...)``.

The older name ``db.calc_trades_content_exposure(...)`` is still accepted as a
deprecated alias.

.. automethod:: Database.calc_trades_exposure