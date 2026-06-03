mario.Database.calc\_ghg
========================

.. currentmodule:: mario

.. automethod:: Database.calc_ghg

.. note::

   ``time_horizon`` and ``ipcc_report`` are used only when
   ``Database.calc_ghg(...)`` resolves a built-in ``profile``. In the current
   built-in registry this affects gases such as ``CH4`` and ``N2O``; scalar
   entries such as ``CO2`` and total ``GHG`` remain unchanged. When a custom
   flat ``gwp={...}`` mapping is passed, the method keeps the previous
   behavior and ignores these two arguments.
