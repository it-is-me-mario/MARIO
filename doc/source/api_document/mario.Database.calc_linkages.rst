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

Sparse flow blocks use sparse coefficient systems and actual production nodes,
including unequal regional Activity/Commodity classifications. Regional totals
are obtained by solving against regional indicator vectors, without requesting
full Leontief or Ghosh inverse views. The result keeps the existing index,
columns, normalization and amplification/share definitions.

``cut_diag=True`` excludes self effects exactly. Sparse arrays are not modified
in place: direct diagonal terms are subtracted from the sums, and inverse
diagonal terms use selected inversion when suitable sparse factors are
available, or streamed unit-vector solves otherwise. Acyclic single-node
components have a direct diagonal formula. Exact diagonal extraction can still
be expensive for large strongly connected systems. The selected-inversion
recursion follows `Jacquelin, Lin and Yang (2017)
<https://arxiv.org/abs/1708.04539>`_.

Detected singular production components raise ``WrongInput`` before an inverse
is requested. The error identifies the system and its component nodes. MARIO
does not remove those nodes, change source values or replace the diagnosed
singular system with a pseudoinverse. This also applies when ``cut_diag=False``:
including self effects does not restore invertibility.

.. automethod:: Database.calc_linkages
