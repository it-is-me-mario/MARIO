:page-type: Guide
:summary: Convert annual IAMC production series into physical or monetary MARIO supply mixes.

Apply an IAM production mix
===========================

Read a public or custom annual IAMC dataset with :func:`mario.read_iamc`.
Model, scenario, region and variable names are taken from the file. Select
the worksheet by name for a research workbook with a cover page.

From a MARIO checkout, download the two public NGFS runs and their identifiers
with ``python scripts/download_ngfs_gcam.py .``.

The following example expects a GCAM 6.0 NGFS Net Zero 2050 export and a
hybrid EXIOBASE SUT named ``db``. Its generating commodities have already
been pooled into a single TJ commodity called ``Electricity (generation)``.
The companion notebook includes that preparation.

.. code-block:: python

   import mario

   iam = mario.read_iamc("Net_Zero_2050.xlsx")
   select = dict(model="GCAM 6.0 NGFS", scenario="Net Zero 2050",
                 year=2050, regions={"US": "GCAM 6.0 NGFS|USA"}, unit="EJ/yr")
   shares = iam.supply_mix(**select, basis="physical")
   db.update_supply_mix(shares, level="Activity", commodities="Electricity (generation)",
                        scenario="US power 2050", clone_from="baseline")

The electricity preset uses disjoint generation variables, including separate
solar PV and CSP. It checks coverage against reported total generation for
each source region before calculating shares. US wind accounts for 44.98%
of this GCAM scenario's generation in 2050. MARIO applies the mix within the
generation activities. Other activities may also supply electricity as a
co-product. Inspect the solved ``S`` block to measure their contribution.

Monetary valuation
------------------

For a monetary SUT, use ``basis="value"`` and pass regional prices per unit of
production for each mapped technology. The share is quantity times price
divided by total valued production. Any common price factor cancels. To use
base-year prices, divide regional generation receipts by physical generation
for the same technology, year and accounting boundary. To use scenario prices,
the companion applies Peng et al.'s relative cost assumptions in Table S6 and
anchors the prices to the reported US electricity price. These relative costs
are a modelling assumption. An electricity mix shock alone sets neither total
future generation nor total expenditure.

.. code-block:: python

   value_shares = iam.supply_mix(**select, basis="value", prices={"US": prices_by_activity})

Custom variables and geographic coverage
----------------------------------------

Use ``variables={native_label: series_name}`` for custom routes, including
steel. Multiple series can contribute to one native label. The optional
``total`` names a separately reported control series. Source regions mapped
to one MRIO region are summed in physical units before valuation. For a
downscaled geography, prepare country-level quantities using an explicit
allocation rule first. A database with one steel activity needs distinct route
activities or a separate recipe model to represent a steel route mix.

.. container:: mario-companion

   :download:`Download the GCAM–EXIOBASE notebook <iam_scenarios.ipynb>`

See :doc:`supply_mix` for the effects on IOT and SUT blocks and
:doc:`../../api_document/mario.read_iamc` for the full interface.
Scenario data are available from the
`NGFS Phase V Scenario Explorer <https://data.ene.iiasa.ac.at/ngfs/#/downloads>`_.
The valuation assumptions come from
`Peng et al., Supporting Information 1 <https://doi.org/10.1021/acs.est.6c10592>`_.
