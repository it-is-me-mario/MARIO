:page-type: Guide
:summary: Extract an open national SUT from FIGARO-NAM and optionally convert it to an IOT.

Convert a NAM to a SUT or IOT
================================

Start from a local FIGARO-NAM ledger with ``use_imports``. The conversion
returns a new national database and preserves every scenario; the source NAM
remains available with its institutional accounts and native import detail.
Other NAM sources and supply-side import representations need their own
projection rules and currently raise an explicit error.

.. code-block:: python

   import mario

   nam = mario.parse_figaro("FIGARO_NAM_2023.csv", table="NAM", countries="IT")
   sut = nam.to_sut()
   sut.resolve_many(["Xa", "Xc", "u"])

For an IOT, select an explicit Eurostat conversion method:

.. code-block:: python

   iot = nam.to_iot(method="B")
   iot.resolve("z")

``B`` gives a product-by-product IOT; ``D`` gives an industry-by-industry IOT.
``A`` and ``C`` additionally require square, invertible supply and zero
activity final demand. :meth:`nam.to_iot() <mario.api.nam.NAMDatabase.to_iot>`
calls :meth:`nam.to_sut() <mario.api.nam.NAMDatabase.to_sut>` and the existing
SUT-to-IOT implementation for each scenario. The
:doc:`SUT-to-IOT guide <sut_to_iot>` explains these assumptions. Both NAM
methods always return a new object and have no ``inplace`` option.

Choose one economy and keep scenarios
--------------------------------------

A NAM containing several reporting economies stores independent national
ledgers. Select one explicitly:

.. code-block:: python

   sut = nam.to_sut(region="IT")
   iot = nam.to_iot(method="D", region="IT")

The output has that economy as its sole Region. Foreign origins of imports
do not become endogenous regions, and the operation does not create an
interregional system. Scenario names are retained in both outputs. An edited,
unbalanced scenario retains its values: conversion performs no balancing or
shock propagation.

Flows retained in the SUT
-------------------------

The SUT uses the NAM's source codes, monetary scale and valuation.
``S`` and domestic ``U`` are copied. Final demand uses the FIGARO categories
``P3_S13`` / ``P3_S14`` / ``P3_S15``, ``P51G`` (fixed capital formation),
``P5M`` (inventories and valuables) and ``P6`` (exports).

.. list-table:: FIGARO projection
   :header-rows: 1
   :widths: 35 65

   * - NAM flows
     - SUT destination
   * - ``Yc_c`` / ``Ya_c``
     - Product/activity final consumption in ``Yc`` / ``Ya``.
   * - ``C_o`` / ``A_o`` paid by the fixed-investment demand pool
     - ``P51G`` final demand; internal ``B8_S1`` routing is not added again.
   * - ``Yc_cap_d`` / ``Yc_cap_f`` and activity counterparts
     - FIGARO's direct inventory/valuable product demand in ``P5M``.
   * - Direct nonfinancial-asset demand
     - Typed fixed assets go to ``P51G``; inventories/valuables to ``P5M``.
       Nonzero unclassified or nonproduced-asset product demand is rejected.
   * - Product/activity exports
     - ``P6`` final demand.
   * - Primary factors and taxes
     - ``Va`` / ``Vc`` or direct final-demand accounts in ``VY``.
   * - Imports by user
     - ``Imports P7`` and ``Purchases abroad P33`` rows in ``Va`` / ``VY``.
   * - Non-product external settlements
     - Separate ``External settlement P7`` / ``External settlement P33`` rows
       in ``VY`` at ``P6``, without a product or partner allocation.

Imports are aggregated by trade account in the output. Their original
origin/product descriptors remain in ``nam.MU``, ``nam.MY`` and the other
native import blocks. Import and settlement rows are exogenous accounts,
not domestic value added. Saving, institutional transfers, financial
transactions and statistical discrepancies stay outside SUT demand.
The empty satellite account ``-`` is a placeholder, not measured environmental
data. Required missing flows and unsupported nonzero routing raise an error;
they are never silently replaced by zero.

Inspect provenance and balances
--------------------------------

.. code-block:: python

   conversion = sut.info["nam_to_sut"]
   conversion["checks"]                 # production-account imbalances by scenario
   conversion["input_blocks"]           # presence and provenance of projected inputs
   conversion["source_audit"]           # original FIGARO import audit

The current projection checks and the original import audit describe different
states. An audit imported with the NAM does not certify later scenario edits.
The output retains metadata, units and input provenance, including direct
account updates. ``info["nam_to_iot"]`` additionally records the IOT method.

An internally balanced projection need not equal a newer FIGARO SUT release.
Compare the same country, reference year, publication edition and revision.
This operation retains the NAM's values without applying a price bridge or
replacing them with a current API release. It supplies the production and
final-demand system; it does not choose a behavioural closure for the NAM.

See the :doc:`NAM format guide </get_started/table_formats/nam>`,
:doc:`FIGARO source guide </notebooks/parsers/figaro/walkthrough_figaro>` and
:doc:`NAM API reference </reference/api_nam_database>` for source inputs and
complete method signatures.
