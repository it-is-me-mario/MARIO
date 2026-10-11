Electricity carbon footprint
============================

:doc:`← Analyses <analyses>`

How much greenhouse gas is associated with one kilowatt-hour of electricity?
The answer depends on the source, the system boundary and the method. This
benchmark brings monetary input–output estimates and physical-unit sources
onto a common basis, **g CO₂eq/kWh**.

The comparison follows Citterio et al. (2026),
`Carbon intensity of electricity: a systematic methodological and quantitative
review <https://doi.org/10.1007/s44498-026-00148-3>`_, and the accompanying
`eNextGen analysis <https://enextgen.it/en/analyses/electricity-carbon-footprint/>`_.
The charts use the blogpost snapshot, which includes updates beyond the article,
including **nxsut 3.0**.

By country and data source
~~~~~~~~~~~~~~~~~~~~~~~~~~

Each marker is an estimate for one country from one source. Colour distinguishes
natively monetary and natively physical factors; marker shape identifies the
source. Change the year and scope, select countries, or use the legend to hide
sources. The table and CSV export follow the active filters.

.. container:: benchmark-wide

   .. raw:: html
      :file: _generated/electricity-country.html

.. raw:: html

   <details class="benchmark-methods">
     <summary>Assumptions behind the country comparison</summary>
     <dl>
       <dt>Direct and life-cycle</dt>
       <dd>Direct intensity counts emissions associated with electricity generation.
       Life-cycle footprints also trace upstream supply-chain contributions within
       each model's boundary. Different sources do not necessarily include the same
       processes, capital goods or transmission and distribution losses.</dd>
       <dt>Monetary to physical</dt>
       <dd>A monetary factor is multiplied by a country-year electricity price:
       <span class="benchmark-equation">g CO₂eq/EUR × EUR/kWh = g CO₂eq/kWh</span>.
       Currency scales and exchange rates must be consistent. The snapshot pipeline
       uses country-year prices and ECB exchange rates where required. The chosen
       price is part of the estimate, rather than a universal unit conversion.</dd>
       <dt>Generation and electricity delivered</dt>
       <dd>Production-based factors and consumption-based factors answer different
       questions. Electricity imports, exports and losses can change the delivered
       mix; matching units does not remove these differences in system boundary.
       nxsut's national comparison uses its electricity-need commodity.</dd>
       <dt>Years and missing observations</dt>
       <dd>The year filter selects the comparison year represented in the snapshot.
       The underlying source release and reference-factor vintage may differ.
       Only available observations are shown; an absent point does not mean zero.
       The country sample contains 24 EU countries and the United States; Cyprus,
       Luxembourg and Malta are omitted, following the country comparison.</dd>
       <dt>GHG characterisation</dt>
       <dd>The nxsut results use GWP100 characterisation with IPCC AR5 factors in the
       snapshot pipeline. Other sources retain the characterisation and gas coverage
       of their published estimates. A common CO₂-equivalent unit does not guarantee
       identical gas coverage or characterisation.</dd>
     </dl>
   </details>

By generation technology
~~~~~~~~~~~~~~~~~~~~~~~~

National averages conceal the differences between generation technologies.
These distributions pool country × technology estimates from **nxsut 3.0** and
**EXIOBASE Hybrid**, together with the article's literature references. Select
sources to see how each contributes to the distribution.

.. container:: benchmark-wide

   .. raw:: html
      :file: _generated/electricity-technology.html

.. raw:: html

   <details class="benchmark-methods">
     <summary>Assumptions behind the technology distributions</summary>
     <dl>
       <dt>What the boxes represent</dt>
       <dd>Each box summarises the observations currently selected: the middle 50%
       of values, median, mean and whiskers up to 1.5 times the interquartile range.
       Sources contribute different numbers of observations. The sample is not
       weighted by electricity generation or balanced to give every source equal
       weight, and the boxes are not statistical confidence intervals.</dd>
       <dt>Physical output</dt>
       <dd>The model estimates use activity-side direct intensity and life-cycle
       footprint, converted from t CO₂eq/TJ to g CO₂eq/kWh. A national average
       electricity price is not used to convert individual generation technologies:
       their specific prices may differ substantially.</dd>
       <dt>Technology groups and biomass</dt>
       <dd>Technology labels follow the blogpost aggregation. “Other technologies”
       includes nuclear, hydro, wind, solar, geothermal, tide and wave, and biomass
       and waste. This grouping does not imply that every included technology has
       a low or zero footprint. The model characterisation gives biogenic CO₂ a
       factor of zero; other emissions and upstream contributions can remain.</dd>
       <dt>Sample and display limits</dt>
       <dd>The chart uses the pooled blogpost sample, rather than a common
       country-year panel across every source. Values outside the plotted range
       are drawn at the edge. The table reports uncapped statistics; the CSV retains the individual
       observations. Categories with fewer than three observations appear as
       individual points.</dd>
     </dl>
   </details>


Sources and reproducibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The input–output calculations are performed with MARIO; nxbase brings the
resulting indicators and external reference factors into a common structure.
The charts on this page are **fixed snapshots** of that analysis. They work
without an account or a live API connection.

.. raw:: html

   <div class="benchmark-links">
     <a href="https://doi.org/10.1007/s44498-026-00148-3">Read the article ↗</a>
     <a href="https://enextgen.it/en/analyses/electricity-carbon-footprint/">Read the eNextGen analysis ↗</a>
     <a href="https://github.com/eNextHub/electricity-carbon-footprint/tree/enextgen_blogpost">Code and data ↗</a>
   </div>

Charts and author-derived comparison data are adapted from the eNextGen
analysis and its accompanying repository, with attribution under **CC BY 4.0**.
Third-party observations remain subject to their source terms; this page
includes the comparison snapshot, rather than complete source databases.
See the source repository and blogpost for source-specific licences and
redistribution limits.

.. raw:: html

   <noscript><p>The interactive charts require JavaScript. The article, eNextGen
   analysis and code repository provide the figures and underlying comparison
   material.</p></noscript>
