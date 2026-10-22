.. raw:: html

   <nav class="explorer-tabs" aria-label="Database explorer">
     <a href="scope.html">Classifications</a>
     <a href="compare.html" aria-current="page">Compare databases</a>
     <a href="analyses.html">Analyses</a>
   </nav>

.. _compare-databases:

Compare databases
=================

.. container:: explorer-intro

   Compare GDP, value added and GHG emissions across MRIO databases.
   Choose databases, versions, countries, years and sectors, and download results.

   .. container:: explorer-feedback

      Found an error, or know a database we should add? Tell us on `GitHub Issues <https://github.com/it-is-me-mario/MARIO/issues>`_.

.. raw:: html

   <div class="economy-browser" data-economy-browser data-root="../../" aria-busy="true">
     <p>Loading the data browser…</p>
     <noscript>Enable JavaScript to explore the data. Sources and methods are documented below.</noscript>
   </div>

.. raw:: html

   <div data-browser-methods hidden>
   <p><strong>Available years and classifications.</strong> Missing years,
   extensions, population or exchange rates remain unavailable. No other year
   is substituted. World sums every native database region once, including RoW;
   it is unavailable where the table lacks a complete global total. World per-capita values use the
   published World Bank WLD population, not a sum of country ratios.
   Selecting several years shows separate observations for each year;
   the map is available for one version and year. Sector aggregates follow the
   source classification and its revision. Combined native categories remain
   combined. The Excel correspondence lists the native labels, section and
   weight; every mapped category enters once. Sector aggregates apply to value
   added and GHG emissions; GDP is whole-economy only. Comparisons without a verified
   common classification use whole-economy totals.</p>
   <p><strong>Value added and GDP.</strong> Value added sums the explicitly
   selected factor rows, preserving signed subsidies and excluding imports,
   balancing adjustments and product taxes. GDP adds net product taxes on
   intermediate and final uses. Some parsers omit final-demand taxes, so the
   bridge is recovered from the source. GDP remains unavailable where this
   bridge has not been verified. EXIOBASE Hybrid publishes net product taxes
   only as a row on activities and has no final-use tax row, so its GDP adds
   that row alone. EXIOBASE readings with zero product-tax blocks
   are labelled as estimates. WIOD uses the published VA and TXSP rows; international SUT final-use taxes
   are retained in VY. Its ROW imports are external factors, so international
   SUTs do not provide a complete World total. FIGARO reconstructs the income total from D1, D29X39 and B2A3G and adds
   D21X31 on intermediate and final uses, excluding residence-purchase adjustments.
   Its compilation already uses national-accounts aggregates and World Bank world
   GDP, so the WDI comparison is not an independent validation. GDP is available only for the whole economy.</p>
   <p><strong>World Bank.</strong> Current-price monetary values use current US dollars and
   same-year official exchange rates. WIOD PYP retains previous-year prices and
   previous-year US dollars; its values are not compared with current-price WDI
   GDP, and the chart reference is omitted whenever PYP is selected. From 1999, EUR values use the rate reported for
   Germany. For 1995–1998, the published Eurostat EUR/ECU annual series is used;
   German DEM/USD values are never interpreted as EUR/USD. Per-capita MRIO totals use the country and year's population;
   World Bank GDP per capita uses its published series. Sector and aggregate
   region per-capita values are unavailable. Differences are
   (database GDP / World Bank GDP − 1) × 100. Source vintages, balancing,
   projections and accounting boundaries affect the comparison; it is not an
   accuracy score. Current-dollar time series also reflect prices and exchange
   rates. Monetary IOT inputs are in million EUR; monetary SUT 3.8.2 income
   components are in EUR. Each reading retains its own scale.</p>
   <p><strong>GHG scope.</strong> Industry or activity emissions use E
   or Ea. Whole-economy totals also include directly emitted final-demand
   accounts from EY where supplied. EY is not allocated to producer sectors:
   with sector aggregates it appears separately as Households, so all sectors
   plus Households equal the whole-economy total. Unavailable EY is not
   estimated or treated as an observed zero. Each
   reading has an explicit gas selection. EXIOBASE monetary includes available
   combustion, process, agriculture and waste rows. Mass-reported gases use
   EDGAR-compatible AR5 GWP100: CO₂ 1, CH₄ 28, N₂O 265, SF₆ 23,500 and,
   where reported, NF₃ 16,100. Biogenic CO₂ is excluded; HFC/PFC already
   expressed in CO₂-equivalent retain the source characterisation, whose GWP
   basis is unverified. EXIOBASE Hybrid shows an AR5-characterised three-gas subtotal (CO₂, CH₄,
   N₂O), including separate unregistered-waste source accounts; it omits F-gases
   and their overlap is not independently verified. EMERGING uses native <em>va</em> as a GDP proxy,
   without a verified market-price bridge; its seven fossil CO₂ fuel accounts
   are a CO₂-only proxy under GHG, excluding CH₄, N₂O and F-gases.
   These caveats are visible beneath the graph and retained in CSV exports.
   EMERGING-E uses the same-year EMERGING 2.2 CO₂ companion projected
   onto its native sectors, with electricity split by fuel; these are
   modelled emissions rather than a separate observed extension. ADB retains its source
   AR5 GWP100 totals, converted from Gg to tonnes once. No common IPCC
   basis is claimed: EXIOBASE retains the source characterisation of
   pre-characterised HFC/PFC mixtures, whose original basis is unverified. Country total GHG units are Gg CO₂eq and World totals use Mt CO₂eq; per-capita MRIO units
   are tonnes CO₂eq per person.</p>
   <p><strong>GLORIA.</strong> The v060 source series covers 1990–2029; 2024–2029
   are forecast tables. The 1990–2029 readings currently available here expose value added from six
   native factor rows and the source EDGAR-consistent GHG total, including
   directly emitted final-demand accounts. Native kilotonnes CO₂eq are converted
   to tonnes once. Detailed gas rows and the separate OECD-consistent inventory
   are not added again. Checks against the native gas rows recover AR5 GWP100
   factors for CO₂, CH₄, N₂O, SF₆ and NF₃; individual F-gas factors remain
   unverified, so the source total is retained. Economic tables are dated
   January 2026 and satellites April 2024. GDP adds signed product taxes and
   subsidies on intermediate and final commodity uses; independent world
   income/expenditure checks retain the source residuals. Value-added and GHG sectors use the README’s
   ISIC Rev. 4 concordance; Other services remains combined S+T.</p>
   <p><strong>BONSAI.</strong> The native b2 HIOT has reference year 2016,
   with frozen inputs updated on 21 October 2026. GDP and value added are
   unavailable: MARIO's factor placeholders are not source observations.
   GHG shows characterised producer emissions from the native elementary
   flows with EDGAR-compatible AR5 GWP100 (CO2 1, both methane origins 28,
   N2O 265). Supplied iLUC contributions to these gases are retained.
   Accelerated CO2 is excluded because no AR5 factor has been verified;
   F-gases are not characterised. This is a three-gas subtotal, with producer
   and land-use boundaries that differ from EDGAR. Separate direct final-demand
   emissions are unavailable. Whole-economy values are available; the
   Classifications page provides the qualified NACE/CPA concordances.
   The native Global block contains global processes, not a
   World total; the World aggregate sums every native region once.</p>
   <p><strong>EDGAR.</strong> References appear automatically where available,
   as separate dash markers. The country reference uses unchanged
   cells from EDGAR 2026's <em>TOTALS BY COUNTRY</em> worksheet, in Gg CO₂eq
   with AR5 GWP100. It includes households and excludes LULUCF. International
   aviation/shipping are reported separately from national totals;
   published World totals include the reference’s original geographic boundary.
   Some source territories are grouped, and those values are not split.
   World totals and country/World per-capita references use unchanged published
   cells from the 2026 report workbook, in Mt CO₂eq and t CO₂eq per person.
   MRIO world totals use Mt to match that published reference. EDGAR is not
   recalculated by sector, summed across countries or interpolated. Its territorial boundary and GWP basis differ from MRIO
   production accounts; no percentage accuracy score is calculated.</p>
   <p>© European Union 2026, European Commission JRC, EDGAR Community GHG
   database, comprising IEA–EDGAR CO₂, EDGAR CH₄, EDGAR N₂O and EDGAR F-gases.
   EU-owned material is generally CC BY 4.0; IEA–EDGAR CO₂ is
   <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">CC BY-NC-ND 4.0</a>.
   Retain attribution and component-specific conditions; use here is
   non-commercial. Crippa et al. (2026), <em>GHG emissions of all world
   countries – 2026 Report</em>,
   <a href="https://doi.org/10.2760/7717504">doi:10.2760/7717504</a>.
   Data are supplied as-is, without warranties from the EU or IEA.</p>
   <p><strong>Downloads.</strong> The CSV contains the current chart or table
   observations and source attribution. The MARIO-only Python example parses
   one local reading and calculates the result; comments explain the remaining
   aggregation, filtering and conversion. It is a starting point for working
   with MARIO. Source matrices and coefficients are not distributed here.</p>
   <p><strong>Database availability and licences.</strong> The indicator browser
   currently includes EXIOBASE, ADB, OECD ICIO, EMERGING, WIOD, FIGARO, GLORIA and BONSAI.
   The Environmentally extended filter selects readings with loaded emission
   accounts; years and versions without them are excluded.
   Current <a href="https://www.gtap.agecon.purdue.edu/resources/faqs/faqs_display.asp?F_ID=198">GTAP releases require a licence</a>;
   the licence conditions apply to use and redistribution. Older releases
   may have different access terms. Eora1, Eora2 and Open CEDA provide scope
   metadata only; Eora1 retains its MARIO parsing guide.
   GLORIA v060 is included for non-commercial research under
   <a href="https://creativecommons.org/licenses/by-nc/3.0/au/">CC BY-NC 3.0 Australia</a>,
   with attribution retained in downloads. Each published reading links to its
   own source licence.</p>
   <p>Additional sources:
   <a href="https://github.com/EXIOBASE/00-class/blob/main/class/exio3class.xlsx">EXIOBASE classification</a>,
   <a href="https://ghgprotocol.org/sites/default/files/2024-08/Global-Warming-Potential-Values%20%28August%202024%29.pdf">IPCC AR5 GWP100 factors</a>,
   World Bank <a href="https://data.worldbank.org/indicator/NY.GDP.MKTP.CD">GDP</a>,
   <a href="https://data.worldbank.org/indicator/NY.GDP.PCAP.CD">GDP per capita</a>,
   <a href="https://data.worldbank.org/indicator/SP.POP.TOTL">population</a> and
   <a href="https://data.worldbank.org/indicator/PA.NUS.FCRF">exchange rate</a>.</p>
   </div>

.. raw:: html

   <script>
   function followExplorerAnchor() {
   if (["#database-coverage", "#geographical-coverage"].includes(location.hash)) {
     location.replace("scope.html#geographical-coverage");
   } else if (location.hash === "#analyses") {
     location.replace("analyses.html");
   } else if (["#electricity-carbon-footprint", "#by-country-and-data-source",
               "#by-generation-technology", "#sources-and-reproducibility"].includes(location.hash)) {
     location.replace("electricity_carbon_footprint.html" + location.hash);
   }
   }
   followExplorerAnchor();
   window.addEventListener("hashchange", followExplorerAnchor);
   </script>
