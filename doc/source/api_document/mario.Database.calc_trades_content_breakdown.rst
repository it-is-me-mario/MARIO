mario.Database.calc\_trades\_content\_breakdown
===============================================

.. currentmodule:: mario

The contributor entries :math:`c_{od,j}` reconstruct the collapsed content:

.. math::

   C_{od} = \sum_j c_{od,j}.

See :doc:`calc_trades_content <mario.Database.calc_trades_content>` for the
direct, total and upstream vector formulas and the IOT/SUT conventions.

``db.calc_trades_content_breakdown(...)`` is a convenience wrapper around
``db.calc_trades_content(..., breakdown=True)``.

.. automethod:: Database.calc_trades_content_breakdown
