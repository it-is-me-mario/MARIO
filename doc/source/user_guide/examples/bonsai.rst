:page-type: Worked example
:summary: Check regional membership, product units and import diagnostics in HSUT and HIOT models.

Inspect BONSAI after import
===========================

.. container:: mario-companion

   :download:`Run the notebook <bonsai.ipynb>`

**Inputs** · Local BONSAI Balanced HSUT and native b2 HIOT bundles.
The companion uses the checked ``20260615`` directory and reference year 2016;
record the actual files because a directory's contents can be updated.

.. mario-steps::

   .. mario-step:: 1 · Import

      .. code-block:: python

         import mario

         sut = mario.parse_bonsai(path="/path/to/Balanced/20260615.zip")
         iot = mario.parse_bonsai(path="/path/to/HIOT/20260615", table="IOT")

      Use the :doc:`BONSAI guide <../parsers/bonsai>` for required files and
      optional UMFPACK installation before full-database calculations.

   .. mario-step:: 2 · Inspect one region

      .. code-block:: python

         region = iot.get_index("Region")[0]
         local_sectors = iot.get_index("Sector", region=region)
         iot.units["Sector"].head()

      Classifications vary by region. A global union of labels is not a list
      of sectors present in every region.

   .. mario-step:: 3 · Review the import

      .. code-block:: python

         iot.info["bonsai"]
         iot.info["bonsai"]["reference_products"]

      Review unmatched final demand and elementary flows. Value-added inputs
      are unavailable; zero placeholders are not observed GDP or value added.

.. mario-details:: Continue with footprint coefficients

   Request ``sut.fc`` for HSUT commodities or ``iot.f`` for HIOT sectors.
   Their denominators are the native product units. Use
   :doc:`../analysis/greenhouse_gases` for a combined GHG indicator.

   BONSAI's solve/partial preset can return NaN where coefficients are not
   independently determined. Preserve them when summing with ``skipna=False``.
