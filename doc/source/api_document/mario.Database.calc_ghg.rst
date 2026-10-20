mario.Database.calc\_ghg
========================

.. currentmodule:: mario

The aggregate extension is a GWP-weighted sum of matched gas accounts:

.. math::

   E_{\mathrm{GHG},j} = \sum_{g\in G}\mathrm{GWP}_g\,E_{g,j}.

The GWP factors come from the selected profile or explicit ``gwp`` mapping.
The same weighted row sum is applied to final-demand emissions in ``EY``.
The aggregate rows are added to ``E`` and ``EY`` through ``add_extensions``.
Input gas rows
must share one unit. An explicit ``unit`` must match that unit; this operation
does not convert input magnitudes. Unmatched accounts are omitted; if no
accounts match, the calculation raises ``KeyError``.

.. automethod:: Database.calc_ghg

.. note::

   ``time_horizon`` and ``ipcc_report`` are used only when
   ``Database.calc_ghg(...)`` resolves a built-in ``profile``. In the current
   built-in registry this affects gases such as ``CH4`` and ``N2O``; scalar
   entries such as ``CO2`` and total ``GHG`` remain unchanged. When a custom
   flat ``gwp={...}`` mapping is passed, the method keeps the previous
   behavior and ignores these two arguments.
