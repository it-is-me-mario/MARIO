pv_hlca.project.Project
=======================

The PV-HLCA project API prepares a photovoltaic supply chain model, applies
the study scenarios and returns its environmental and economic indicators.
Instantiate ``Project`` directly with released versions of ``mariopy``.
Use :func:`mario.model_setup` with a MARIO source build. The
`PV-HLCA guide in the Model Gallery`_ covers installation and the first run.

.. py:class:: pv_hlca.project.Project(workspace, *, cache_dir=None)

   :param workspace: Directory for editable inputs and run records. Opening a
      new project creates ``config.yaml`` and populates ``inputs/``.
   :param cache_dir: Directory for the background data cache. The default is
      ``MARIO_MODEL_CACHE`` if set, or ``~/.cache/mario/models``.

   With a MARIO source build, pass ``workspace`` and ``cache_dir`` to
   ``mario.model_setup("pv-hlca", workspace=..., cache_dir=...)``.

   .. py:method:: describe()

      Return a dictionary with model and publication identifiers, tags,
      current parameter values and descriptions, scenario names, indicator
      descriptions, background data provenance, and the documentation path.
      Parameter values reflect the workspace configuration and model defaults.

   .. py:method:: docs()

      Return the path to ``GUIDE.md`` shipped with the installed model.

   .. py:method:: fetch_data()

      Verify the required background files and return their directory as a
      ``pathlib.Path``. Download missing or invalid cache files and verify
      their SHA-256 checksums. A configured local ``data.path`` must already
      contain the expected files.

   .. py:method:: build(*, download=False, **overrides)

      Read the workspace configuration and return a ``mario.Database``
      containing the ``baseline``, ``domestic``, ``NZIA`` and
      ``baseline_2030`` scenarios.

      :param bool download: Fetch required background files if absent from
         the cache. The default uses files already available locally.
      :param overrides: Set any of the parameters listed below for this run.
         Arguments override values in ``config.yaml``. Unset fields inherit
         the model defaults.
      :raises FileNotFoundError: A required input or cached background file
         is missing.
      :raises ValueError: A configuration field, parameter value or supplied
         local background file fails validation.

      Each successful build saves the effective configuration, input files and
      provenance under the workspace's ``runs/`` directory. The preparation is
      reused in the same project object while the source data path, MARIO
      version and input file hashes match.

   .. py:method:: results(db, *, write=False)

      :param db: MARIO database built in this project's workspace.
      :param bool write: Save each table as a CSV under the run's
         ``results/`` directory.
      :returns: Dictionary of pandas DataFrames keyed by indicator name.
         See the result tables below for columns and units.

   .. py:method:: run_directory(db)

      Return the run directory as a ``pathlib.Path``. It contains
      ``config.yaml``, ``provenance.yaml`` and the input snapshot.
      The database must have been built in this project's workspace.

Parameters
----------

Set these fields in the ``parameters`` mapping in ``config.yaml`` or pass
them as keyword arguments to :meth:`~pv_hlca.project.Project.build`.

.. list-table::
   :header-rows: 1
   :widths: 25 18 57

   * - Parameter
     - Default
     - Accepted values
   * - ``capacity_factor``
     - ``OWID``
     - ``OWID`` or ``RN`` (Renewables Ninja).
   * - ``electricity_mix``
     - ``WEO_STEPS``
     - ``WEO_STEPS`` projects EU27 and China to 2030. ``EMBER`` changes EU27.
   * - ``module_efficiency``
     - ``0.195``
     - Fraction greater than 0 and at most 1.
   * - ``degradation_rate``
     - ``0.0``
     - Annual fraction from 0 up to, but excluding, 1.
   * - ``lci_variant``
     - ``IEA``
     - ``IEA`` or ``NREL`` upstream electricity inventory.
   * - ``upstream_reshoring``
     - ``null``
     - EU27 domestic share for upstream stages in NZIA, between 0 and 1
       inclusive. ``null`` in YAML or ``None`` in Python keeps the study shares.

The ``data.source`` field identifies the supported background
``exiobase-hybrid-green-steel-1.3.2``. Set ``data.path`` to use a verified
local copy. Paths in the ``inputs`` mapping can be absolute or relative to the
workspace. The ``pv_inventory`` and ``aggregation`` entries point to directories
of CSV tables. ``trade_shares`` and the two ``capacity_factor_multipliers_*``
entries point to CSV files. ``parameters``, ``mappings``, ``scenario_2030``
and ``capacity_factor_row`` point to supporting YAML files.

Result tables
-------------

For each scenario present in the database, result rows include its
``scenario`` and the six effective parameter values.

.. list-table::
   :header-rows: 1
   :widths: 21 29 50

   * - Table
     - Additional dimensions
     - Value columns
   * - ``footprints``
     - ``region``
     - ``footprint_gkwh``, solar electricity footprint in g CO₂eq/kWh.
   * - ``prices``
     - ``region``
     - ``price_eur_kwh``, solar electricity producer price in EUR/kWh.
   * - ``production``
     - ``region``, ``commodity``
     - ``production``, output in the unit of the corresponding commodity.
   * - ``value_added``
     - ``region``, ``factor``
     - ``value_added``, million EUR across activities.
   * - ``employment``
     - ``region``, ``activity``
     - ``employment``, thousands of people.
   * - ``headline``
     - One row per scenario
     - ``EU27_value_added_Meur`` in million EUR and ``global_co2eq`` in
       tonnes CO₂eq from the production satellite accounts.
