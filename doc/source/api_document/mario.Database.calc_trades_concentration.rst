mario.Database.calc\_trades\_concentration
==========================================

.. currentmodule:: mario

For contributor entries :math:`c_{od,j}` from
``calc_trades_content(..., breakdown=True)``, the method computes:

.. math::

   a_{rod} = \left|\sum_{j\in r}c_{od,j}\right|, \qquad
   s_{rod} = \frac{a_{rod}}{\sum_q a_{qod}}, \qquad
   \mathrm{HHI}_{od} = \sum_r s_{rod}^{2}.

Contributors are summed within each contributor Region ``r`` **before** taking
the absolute value, so positive and negative entries within that Region can
cancel. A zero denominator produces zero shares and HHI zero. Otherwise HHI
lies between :math:`1/R` and 1, where ``R`` is the number of contributor
Regions with nonzero magnitudes. Higher values mean more concentrated content.

All selectors follow
:doc:`calc_trades_content <mario.Database.calc_trades_content>`. The result is a
Region-by-Region DataFrame of dimensionless HHI values, or a dictionary of
DataFrames when multiple scenarios are requested.

.. automethod:: Database.calc_trades_concentration
