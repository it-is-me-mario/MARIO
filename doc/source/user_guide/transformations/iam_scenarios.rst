:page-type: Guide
:summary: Choose an IAM-to-MRIO shock by its economic mechanism and apply production mixes to a SUT.

.. _apply-an-iam-production-mix:

Choose and apply an IAM shock
=============================

Choose the shock by the economic change you want to model. For example, a
switch to electric heating changes purchases of electricity and fuel. A switch
from coal-fired to wind generation changes who supplies that electricity.
The two operations can draw on the same IAM run and edit different MRIO blocks.

.. list-table:: IAM-to-MRIO shock families
   :header-rows: 1
   :widths: 24 30 46

   * - Family
     - Shock identifiers
     - Target and interpretation
   * - Production structure
     - ``electricity_mix``, ``steel_mix``, ``production_mix``
     - Change the shares of activities supplying a common product in SUT
       market shares ``s``. The electricity preset and user-mapped production
       routes use the same implemented operator.
   * - Input structure
     - ``fuel_switch``, ``electrification``
     - Change fuel or electricity inputs per unit of buyer output in SUT
       ``u`` or IOT ``z``. Direct purchases by households belong in final
       demand. Both shocks are specified for future implementation.
   * - Final demand
     - ``final_demand_change``, ``capacity_investment``
     - Change product purchases in a named final-use column of ``Yc`` (SUT)
       or ``Y`` (IOT). Investment uses the gross fixed capital formation
       (GFCF) column. Both shocks are specified for future implementation.

:func:`mario.list_iam_shocks` describes the IAM inputs, concordances,
valuation rules, target blocks and implementation status
for each identifier. The ``supported_tables`` column gives current execution
support.

.. code-block:: python

   import mario

   shocks = mario.list_iam_shocks()
   shocks[["family", "status", "supported_tables"]]
   shocks.loc["capacity_investment", ["iam_input", "physical_rule", "monetary_rule", "requires"]]
   mario.list_iam_shocks(implemented_only=True)

GCAM's US results in the two Phase V scenarios below illustrate three mapping decisions.

* ``Production|Steel`` gives total steel output. ``steel_mix`` needs output
  by production route, as in a study-specific export. A change in
  ``Final Energy|Industry|Steel|Electricity`` can inform an input shock once
  energy use is related to steel output.
* For fuel switching and electrification, specify the buyers, the fuels
  displaced and the output or useful service held fixed. Technology
  efficiencies determine how delivered energy changes at fixed service. In a
  monetary table, value the resulting inputs at carrier-specific prices.
  Applying both substitutions to the same fuel use needs a joint calculation.
* For wind investment, GCAM reports ``Investment|Energy Supply|Electricity|Wind``
  in billion US$2010/yr and ``Capacity Additions|Electricity|Wind`` in GW/yr.
  Use reported spending or reconstruct it from additions and cost per unit
  capacity. If only stocks are available, add retirements to the stock change
  before annualizing. Align currency and price year, then allocate expenditure
  to capital goods and construction by supplier. A GFCF increment is the
  difference from the investment already represented in the reference case.

The IAMC codelists provide reporting labels and model-region mappings.
Project-specific variable names can enter the same shock through an explicit
concordance. See the
`IAMC common definitions <https://github.com/IAMconsortium/common-definitions>`_.

Apply a production shock
------------------------

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
``shock="steel_mix"`` with ``commodity``, the IAM ``unit``, and
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
