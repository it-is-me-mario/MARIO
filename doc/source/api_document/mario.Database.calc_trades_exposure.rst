mario.Database.calc\_trades\_exposure
=====================================

.. currentmodule:: mario

Using the contributor-region shares from
:doc:`calc_trades_concentration <mario.Database.calc_trades_concentration>`:

.. math::

   a_{rod} = \left|\sum_{j\in r}c_{od,j}\right|, \qquad
   s_{rod} = \frac{a_{rod}}{\sum_q a_{qod}}, \qquad
   \mathrm{Exposure}_{od}(A) = \sum_{r\in A}s_{rod}.

``exposed_to`` selects the set ``A`` of contributor Regions. Exposure is a
fraction between zero and one. A zero denominator produces zero shares and
zero exposure. Contributors are summed by Region before taking absolute
values. Region clusters affect the trade axes; ``exposed_to`` still selects
original contributor Regions.

All other selectors follow
:doc:`calc_trades_content <mario.Database.calc_trades_content>`. The result is a
Region-by-Region DataFrame of exposure fractions, or a dictionary of DataFrames
when multiple scenarios are requested.

.. automethod:: Database.calc_trades_exposure
