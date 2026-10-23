:page-type: Database guide
:summary: Import a Balanced hybrid supply-use table or BONSAI's native b2 hybrid input-output table.

BONSAI
======

.. container:: mario-guide-facts

   **Inputs:** a local ZIP or extracted directory from BONSAI's shared storage.
   MARIO does not download the source automatically.

   **Classification:** activities, commodities and sectors vary by region.
   Query an individual region to see its actual membership and size.

   **Coverage checked:** the ``20260615`` directory, with reference year **2016**.
   Files within this directory can be updated; its name is not an immutable
   snapshot identifier. Record the actual input files used for your analysis.

Choose your input
------------------

Use the Balanced bundle for a supply-use model. Use the HIOT bundle to import
BONSAI's final Stone/iLUC/capital model directly. Monetary SUT exports are not
supported by this parser.

.. mario-switch::
   :label: BONSAI input format
   :hint: Choose the bundle you have to see its files and import call.

   .. mario-switch-option:: bonsai-hiot
      :badge: IOT
      :title: Native HIOT
      :text: Import the final b2 product model.

   .. mario-switch-option:: bonsai-hsut
      :badge: SUT
      :title: Balanced HSUT
      :text: Retain separate activities and commodities.

.. _bonsai-hiot:

Import the HIOT
---------------

Obtain one export under ``_b Next version/HIOT``. The directory must contain:

.. code-block:: text

   20260615/
   ├── extended_size_hiot.b2.pkl
   ├── final_demand.b2.csv
   └── total_elementary_flow_w_iLUC.csv

The last file is required when ``extensions=True`` (the default). Use a trusted
BONSAI pickle export.

.. code-block:: python

    import mario

    db = mario.parse_bonsai(
        path="/path/to/HIOT/20260615",
        table="IOT",
    )

**Result:** an IOT with native product codes in the ``Sector`` set, original
units and the sectors actually present in each region. A ZIP containing the
same export can be passed as ``path``.

The year is inferred from elementary-flow ``time`` values. Pass ``year=2016``
for this export if those values are unavailable.

.. _bonsai-hsut:

Import the HSUT
---------------

Obtain one export under ``_b Next version/Balanced``. The ZIP or directory must
contain:

.. code-block:: text

   20260615/
   ├── classification.csv
   ├── hybrid_supply_w_characteristic_unit.csv
   ├── hybrid_use_w_characteristic_unit.csv
   └── all_elementary_flows_AB_and_BB.csv

The last file is required when ``extensions=True`` (the default).

.. code-block:: python

    import mario

    db = mario.parse_bonsai(
        path="/path/to/Balanced/20260615.zip",
        table="SUT",
    )

**Result:** a SUT with separate ``Activity`` and ``Commodity`` sets and native
commodity units. The extracted directory can also be passed as ``path``.

Inspect the imported model
---------------------------

For either format, inspect the source year, regions and metadata:

.. code-block:: python

    db.meta.year
    db.get_index("Region")
    db.database_profile
    db.info["bonsai"]

For the HIOT, inspect a region's sectors and their units:

.. code-block:: python

    db.get_index("Sector", region="IT")
    db.units["Sector"].head()

For the HSUT, use ``"Activity"`` or ``"Commodity"`` instead of ``"Sector"``.
The classification can vary in both membership and size between regions.
See :doc:`classification concordances <../inspection/concordances>` to find
external codes for the native items.

Prepare calculations
---------------------

For calculations on a full BONSAI model, install the optional UMFPACK solver.
With conda:

.. code-block:: bash

   conda install -c conda-forge scikit-umfpack

With pip, first install SuiteSparse through your system package manager, then
install ``mariopy[umfpack]``. Pip does not install SuiteSparse.

The parser selects ``solve`` / ``direct``, preferring UMFPACK and falling back
to SciPy when it is unavailable. These preferences affect the Python session.
Inspect the active selection after parsing:

.. code-block:: python

    mario.download_settings()["compute"]

Keep the default ``calc_all=False`` at import and request the quantities you
need. BONSAI uses ``singular_policy="partial"``: affected coefficients are
reported as NaN with a warning. See :doc:`computation settings
<../advanced/compute_settings>` for the meaning of these options.

To characterize the available gas accounts, follow
:doc:`Calculate greenhouse gas emissions <../analysis/greenhouse_gases>`.
HIOT per-unit footprints use ``f``; HSUT commodity footprints use ``fc``.
Both retain the native product units.

Interpretation and import diagnostics
--------------------------------------

* **Value added and GDP:** these inputs do not provide value-added accounts.
  MARIO's zero placeholders must not be interpreted as observed value added.
* **Environmental accounts:** labels use ``name | compartment``; IDs
  disambiguate homonyms. Original identities are retained in
  ``db.info["bonsai"]["satellites"]``.
* **Unmatched rows:** import diagnostics are in ``db.info["bonsai"]``.
  Set ``unmatched_extensions="raise"`` to reject unmatched elementary flows;
  ``unmatched_final_demand`` controls the corresponding HIOT policy.
* **HIOT representation:** the parser retains the native net-supply system,
  including substitution credits. The activity-to-reference-product mapping
  is in ``db.info["bonsai"]["reference_products"]``.

Continue with the :doc:`runnable BONSAI example <../examples/bonsai>`, or consult
:doc:`mario.parse_bonsai() <../../api_document/mario.parse_bonsai>` for the full
parameter list and representation details.

Source information: `BONSAI project <https://bonsai.uno/>`_ and
`BONSAI repository <https://gitlab.com/bonsamurais/bonsai>`_.
