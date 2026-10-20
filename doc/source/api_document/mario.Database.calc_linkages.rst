mario.Database.calc\_linkages
=============================

.. currentmodule:: mario

For IOT, let :math:`w=(I-z)^{-1}` and :math:`g=(I-b)^{-1}`.
The four linkage measures are:

.. math::

   \begin{aligned}
   \mathrm{DB}_j &= \sum_i \widetilde{z}_{ij}, &
   \mathrm{TB}_j &= \sum_i \widetilde{w}_{ij}, \\
   \mathrm{DF}_i &= \sum_j \widetilde{b}_{ij}, &
   \mathrm{TF}_i &= \sum_j \widetilde{g}_{ij}.
   \end{aligned}

``DB`` / ``TB`` are direct / total backward linkages; ``DF`` / ``TF``
are direct / total forward linkages. The tilde means that diagonal entries
are excluded when ``cut_diag=True``. SUT uses the corresponding unified
activity/commodity systems.

With ``multi_mode=False`` and ``normalized=True``, each measure is divided
by its mean:

.. math::

   \ell_i^{\mathrm{norm}} = \frac{\ell_i}{n^{-1}\sum_j\ell_j}.

Amplifications use the raw values: :math:`\mathrm{TB}/\mathrm{DB}` and
:math:`\mathrm{TF}/\mathrm{DF}`. With ``multi_mode=True``, each sum is split
into Local and Foreign contributors; each share is its component divided by
their sum. Normalization is not applied in that mode. Zero denominators in
amplifications and regional shares give NaN.

``db.calc_linkages(...)`` returns the standard backward and forward linkages.

When ``multi_mode=False``, the dataframe also includes ``Forward Amplification``
and ``Backward Amplification`` ratios, defined as ``Total / Direct`` on the raw
linkage values.

When ``multi_mode=True``, the dataframe keeps the ``Local`` and ``Foreign``
components and adds their ``Local Share`` and ``Foreign Share`` for each
linkage measure.

.. automethod:: Database.calc_linkages