:page-type: worked example
:summary: Transfer regional GCAM steel production by route to EXIOBASE Hybrid and verify the shares in solved supply flows.

GCAM–MARIO · Steel production routes
====================================

How much EU steel comes from scrap-based electric arc furnaces in 2050?
Under the GCAM 7.0 scenario ``NDC_LTT_CBAM``, these furnaces supply **71.16%
of mapped steel production in EU-12** and **71.17% in EU-15**. The notebook
reproduces both shares in MARIO and checks the other production routes against
GCAM's regional output.

.. container:: mario-companion

   :download:`Download the steel mix notebook <gcam-mario-steel.ipynb>`

Study inputs
------------

The regional export from the study by `Ghezzi et al.
<https://doi.org/10.1021/acs.est.5c15099>`_ reports annual production in Mt/yr
for 21 steelmaking series. Four scrap-EAF finishing variants supply the same
EXIOBASE activity. The concordance therefore represents 18 production routes.
The `regional files and provenance
<https://github.com/SESAM-Polimi/ExioSteel/tree/be43497a18302f7c2ad0df13a3cb6b6536355839/examples/gcam-output>`_
document how EU-12 and EU-15 sum to the EU27 figures in the
`published supplement <https://doi.org/10.1021/acs.est.5c15099.s001>`_.

The study's prepared SUT aggregates
`EXIOBASE Hybrid Green Steel 1.3.0 <https://zenodo.org/records/16779787>`_
to 23 regions. Its steel commodity is measured in tonnes and its activities
distinguish production routes, including scrap EAF and hydrogen-based DRI-EAF.

Run the notebook
----------------

#. Use the `pinned ExioSteel checkout
   <https://github.com/SESAM-Polimi/ExioSteel/tree/be43497a18302f7c2ad0df13a3cb6b6536355839>`_.
   Reuse its ``models/prepared/`` directory if available. For a first
   preparation, follow the `Python 3.12 setup
   <https://github.com/SESAM-Polimi/ExioSteel/blob/be43497a18302f7c2ad0df13a3cb6b6536355839/docs/installation.md>`_
   and run ``gcam-mario prepare`` in the checkout. The source download is 1.78 GB.
#. Open the notebook in a separate kernel with MARIO installed from the
   ``link-iam-mrio`` branch. Set ``EXIOSTEEL_ROOT`` to the ExioSteel checkout
   or set ``root`` in the first code cell.
#. Run all cells. To explore another case, choose a scenario printed by the
   notebook and a reporting year from the CSV, then rerun from the top.

The notebook reads the CSV with ``mario.read_iamc`` and creates a MARIO scenario
with ``db.shock_from_iam(..., shock="steel_mix")``. It checks the regional shares
in the solved supply matrix ``S`` and compares them with the baseline. The
shock sets the production mix. Absolute production follows the MRIO demand
and technology coefficients, so a combined EU27 share uses each model's own
regional production weights.
