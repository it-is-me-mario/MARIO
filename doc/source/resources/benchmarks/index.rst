Analyses & benchmarks
=====================

Applied analyses and reproducible comparisons built with MARIO. Each benchmark
explores how database choices and modelling assumptions affect a real analysis.

.. mario-cards::
   :columns: 1
   :links:

   .. mario-card:: :doc:`Electricity carbon footprint <electricity_carbon_footprint>`
      :icon: bolt

      Compare direct and life-cycle emission factors across databases, countries
      and generation technologies. Explore the charts and the assumptions behind
      the Journal of Industrial Ecology article and the eNextGen analysis.

.. toctree::
   :hidden:

   electricity_carbon_footprint

.. raw:: html

   <script>
   if (window.location.hash === "#database-coverage") {
     window.location.replace("../database_coverage.html");
   } else if (["#electricity-carbon-footprint", "#by-country-and-data-source",
               "#by-generation-technology", "#sources-and-reproducibility"].includes(window.location.hash)) {
     window.location.replace("electricity_carbon_footprint.html" + window.location.hash);
   }
   </script>
