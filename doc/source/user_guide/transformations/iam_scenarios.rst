:page-type: Guide
:summary: Convert annual IAMC production series into physical or monetary MARIO supply mixes.

Apply an IAM production mix
===========================

Select a model and one or more scenarios from the public NGFS Phase V
catalogue. :func:`mario.download_ngfs` returns one :class:`mario.IamData` with
the complete annual series for the selected runs. Use
:func:`mario.list_ngfs_runs` to find the model and scenario names.

.. code-block:: python

   import mario

   model = "GCAM 6.0 NGFS"
   available = mario.list_ngfs_runs(model=model)
   iam = mario.download_ngfs(model=model, scenarios=["Current Policies", "Net Zero 2050"])
   iam.frame.groupby("Scenario").size()

The downloader uses the current default run of each scenario. Inspect
``iam.frame.attrs["ngfs_runs"]`` for the identifiers and versions used. To read
an archived export or study-specific data, use :func:`mario.read_iamc`, for
example ``mario.read_iamc("study.xlsx", sheet_name="Results")``. Both paths
preserve the source labels and support the same supply-mix calculation.

:meth:`mario.Database.shock_from_iam` creates a MARIO scenario and returns
its name. For the two EXIOBASE SUTs in the companion notebook, select the
same IAM run and year. The generation commodity is measured in TJ on the
hybrid table and in EUR on the monetary table.

.. code-block:: python

   select = dict(model=model, scenario="Net Zero 2050", year=2050,
                 regions={"US": "GCAM 6.0 NGFS|USA"})
   hybrid_case = physical_db.shock_from_iam(iam, **select)
   money_case = monetary_db.shock_from_iam(iam, **select, prices="peng-2026")
   supply = monetary_db.query("S", scenarios=money_case)

On an original EXIOBASE SUT with separate generation commodities, pass
``pool=True`` in the same call to build the common electricity market. This
changes the commodity classification for every scenario, including the baseline.
On a prepared SUT, the method detects the shared generation commodity.
Pass ``commodity=...`` if it has a custom name. To download a single public
NGFS run and apply it directly, omit ``iam`` from either call.

The electricity preset uses disjoint generation variables, including separate
solar PV and CSP. It checks coverage against reported total generation for
each source region before calculating shares. US wind accounts for 44.98%
of this GCAM scenario's generation in 2050. MARIO applies the mix within the
generation activities. Other activities may also supply electricity as a
co-product. Inspect the solved ``S`` block to measure their contribution.

Monetary valuation
------------------

For a monetary SUT, choose regional prices per unit of production for each
mapped technology. The share is quantity times price
divided by total valued production. Any common price factor cancels. To use
base-year prices, divide regional generation receipts by physical generation
for the same technology, year and accounting boundary. To use scenario prices,
the ``"peng-2026"`` option applies the relative generation costs in Table S6
to each selected region. The notebook also scales them to GCAM's reported
regional mean and verifies the same shares. The relative costs are a modelling
assumption. In this example wind accounts for 34.52% of US generation value.
To use your own prices keyed by EXIOBASE activity, pass the regional mapping.

.. code-block:: python

   case = monetary_db.shock_from_iam(iam, **select, prices={"US": prices_by_activity},
                                     target_scenario="US power at base-year prices")

Custom variables and geographic coverage
----------------------------------------

For a SUT with a shared steel commodity and distinct route activities, use
``shock="production_mix"`` with ``commodity``, the IAM ``unit``, and
``variables={native_label: series_name}``. Multiple series can contribute
to one native label. The optional
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
