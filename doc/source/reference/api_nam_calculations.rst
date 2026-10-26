:page-type: API reference
:summary: NAM account totals and coefficients use full paying-account expenditure, with native detail retained.

NAM account totals and coefficients
===================================

**Table format: NAM.** Request these blocks through
:meth:`db.resolve() <mario.CoreModel.resolve>`, dotted access or
:meth:`db.resolve_many() <mario.CoreModel.resolve_many>`.
The :doc:`NAM format guide </get_started/table_formats/nam>` explains the sets
and diagram switch. :doc:`api_nam_database` gives the exact resolver and
scenario signatures. The :doc:`FIGARO source guide
</notebooks/parsers/figaro/walkthrough_figaro>` supplies a local-data example.

.. code-block:: python

   nam = mario.parse_figaro("FIGARO_NAM_2023.csv", table="NAM", countries="IT")
   nam.Xa
   nam.Xsi_d
   nam.cf_d
   nam.resolve_many(["u", "ri_d", "rs_dd"])
   nam.explain("cf_d")

Account totals
--------------

For every accounting node, total expenditure is

.. math::

   X_j=\sum_i T_{ij}.

``X`` contains all nodes; ``X`` plus a set's short name selects that set.
Examples are ``Xc``, ``Xa``, ``Xf``, ``Xsi_d``, ``Xsi_f``, ``Xsc_d``,
``Xsc_f``, ``Xnf``, ``Xfi``, ``Xtr`` and ``Xo``. The full mapping is below.
Vectors have ``Region / Set / Item`` rows and one ``production`` column.
For nonproduction accounts, this column contains account expenditure.
Receipts equal expenditure only when the ledger is balanced. Summing ``X``
over different account stages does not calculate GDP.

.. raw:: html
   :file: ../get_started/_generated/nam_indices.html

A set total sums every authoritative outgoing block for that set and reporting
economy, including tax, transfer and financial payments where present.
Only the selected import authority contributes. Each required input must be
observed or explicitly declared zero; another set's missing outgoing blocks
do not prevent an independently covered total.

Coefficient names and denominator
---------------------------------

For every native flow, the coefficient name is its lowercase spelling,
retaining underscores: ``CF_d`` becomes ``cf_d``, ``MU`` becomes ``mu``.
The coefficient has exactly the native flow's row/column layout and descriptors.

.. math::

   f_{ij}=F_{ij}/X_j,
   \qquad f=F\operatorname{diag}(X_{\mathrm{column\ set}})^{-1}.

``cf_d`` depends on ``CF_d`` and ``Xsi_d``; ``u`` depends on ``U`` and ``Xa``;
``s`` depends on ``S`` and ``Xc``. ``t`` uses complete ``T`` and ``X``.
No denominator is a block subtotal or grand total. Unlike SUT ``s``, NAM ``s``
does not use an IT/PT technology assumption. Coefficients are dimensionless;
vectors and flows retain the database's currency, scale and reference period.

For example, if one income account pays 70 to consumption, 20 in taxes and
10 to saving, its total is 100. The corresponding consumption coefficient
is 0.70, even if consumption has just one row. Dividing by the consumption
block's own column sum would instead give 1 and lose its share in the account.

Inactive and signed accounts
----------------------------

An account with zero expenditure and no nonzero outgoing payments has zero
coefficients. If signed payments cancel to a zero total, normalization is
undefined: the resolver raises an error naming the accounts, including when
the requested block happens to be zero in those columns. Negative nonzero
totals are retained, and coefficients need not lie between zero and one.
No epsilon, least-squares substitution or closure rule is inferred.

Updates and persistence
-----------------------

Changing native flows invalidates totals, coefficients and other derived
results across affected scenarios. Inputs and returned frames are independent
copies. Native Excel export retains authoritative flows and schema metadata;
derived caches are recomputed after reload and are not additional workbook
payments. Flow reconstruction from coefficients and a NAM inverse are not
registered operations.

The complete catalogue, including roles, sets and denominator descriptions,
is in :doc:`api_resolvable_matrices`.
