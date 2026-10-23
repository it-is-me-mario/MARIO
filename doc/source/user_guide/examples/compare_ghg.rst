:page-type: Worked example
:summary: Align indicator definitions, regional identities and units before comparing source estimates.

Compare GHG footprints across databases
=======================================

.. container:: mario-companion

   :download:`Download notebook <compare_ghg.ipynb>`

**Inputs** · Local EXIOBASE 3.10.2, Eora26 and ADB releases with their extensions.
The companion notebook lists the exact years and expected folder structure.

.. container:: mario-flow

   **Accounts** → **Characterization** → **Regional totals** → **Common units** → **Chart**

Indicator, geography and units
------------------------------

.. mario-cards::
   :columns: 3

   .. mario-card:: Indicator
      :icon: cloud

      The example requests AR5/GWP100. Already characterized source CO2eq
      totals keep their original factors.

   .. mario-card:: Geography
      :icon: pin

      Source-specific labels are reconciled to ISO3 before countries are selected.

   .. mario-card:: Units
      :icon: chart

      Regional totals are converted to a common magnitude before plotting.

Analysis steps
--------------

.. mario-steps::

   .. mario-step:: 1 · Check accounts

      Inspect the selected profiles and the gas rows actually present in
      each source. A supported profile does not imply identical coverage.

   .. mario-step:: 2 · Characterize

      .. code-block:: python

         db.calc_ghg(ipcc_report="AR5", time_horizon=100)
         ghg = "GHG AR5 GWP-100"
         db.calc_all(["F"])

      This block applies to a compatible IOT with the required gas accounts.
      See :doc:`../analysis/ghg_characterization` for source-total limitations.

   .. mario-step:: 3 · Build totals

      .. code-block:: python

         direct_fd = db.EY.loc[ghg].groupby(level=0).sum()
         pba = db.E.loc[ghg].groupby(level=0).sum() + direct_fd
         cba = db.F.loc[ghg].groupby(level=0).sum() + direct_fd

      The companion's harmonization step aligns regional labels and units.
      For partial numerical results, handle NaN explicitly before aggregating.

   .. mario-step:: 4 · Compare

      Plot the selected countries and years. Differences still reflect source
      coverage, accounts and modelling choices; a shared label alone does not
      make the estimates equivalent.

Start with :doc:`Calculate greenhouse gas emissions <../analysis/greenhouse_gases>`
for the single-database workflow.
