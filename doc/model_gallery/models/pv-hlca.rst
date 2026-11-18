:page-type: guide
:summary: Estimate the environmental and economic effects of photovoltaic reshoring.

PV-HLCA · Photovoltaic supply chains
====================================

Publication
-----------

**Environmental and socio-economic implications of solar photovoltaic reshoring
under the EU Net Zero Industry Act: a hybrid input–output assessment**

Lorenzo Rinaldi, Raffaele Merletti, Camilla Citterio, Nicolò Golinucci and
Matteo Vincenzo Rocco. *Journal of Industrial Ecology* (2026).
`Read the paper <https://doi.org/10.1007/s44498-026-00175-0>`_.

PV-HLCA represents stages from silicon processing to module assembly and
electricity generation. The study compares the footprint and economic effects
of shifting manufacturing to the EU under the Net Zero Industry Act.

Background database
-------------------

The model uses `EXIOBASE Hybrid Green Steel 1.3.2 <https://zenodo.org/records/18744457>`_,
which extends EXIOBASE Hybrid with steel and hydrogen technologies. PV-HLCA
aggregates the background to 22 regions and adds photovoltaic activities and
commodities. The installable workflow uses the background in the
`archived model repository <https://zenodo.org/records/20734983>`_. The original
reference results were generated with an earlier background edition.

Install and run
---------------

Use a Python environment with Git. Install MARIO and the version of PV-HLCA
used in this guide.

.. code-block:: shell

   pip install mariopy
   GIT_LFS_SKIP_SMUDGE=1 pip install "mario-pv-hlca @ git+https://github.com/it-is-me-mario/pv-hlca-model.git@6b458e1a0927f15c285ed9db88814c870621115d"

Open a project in Python and run the central case.

.. code-block:: python

   from pv_hlca.project import Project

   model = Project(workspace="./pv-study")
   model.fetch_data()
   db = model.build()
   tables = model.results(db, write=True)

See the :doc:`PV-HLCA API reference <../api_document/pv_hlca.project.Project>`
for methods, configuration and result tables.

The first data download is about 255 MB. To use an existing copy of the same
Parquet files, point ``data.path`` in ``pv-study/config.yaml`` to their directory.
The first build prepares the regional database and inserts the PV inventories.
Subsequent builds in the same session can reuse that preparation.

.. _install-through-mario:

If you run MARIO from its current source, see :doc:`Research model setups
<../user_guide/configuration/model_setups>` for the installation and workspace
commands.

Change an assumption
--------------------

Set ``module_efficiency: 0.22`` under ``parameters`` in ``config.yaml`` to use
22% module efficiency. The equivalent Python call is
``model.build(module_efficiency=0.22)``.

The YAML also controls the capacity-factor source, module degradation, upstream
inventory, 2030 electricity mix and NZIA upstream sourcing. The ``inputs/``
directory contains the CSV files for inventories, aggregations and trade shares.
Use ``model.describe()`` to see the options and ``model.docs()`` for the guide
shipped with the installed model.

For changes to the construction code, use an editable checkout of the
`PV-HLCA repository <https://github.com/it-is-me-mario/pv-hlca-model>`_.

Results
-------

``build()`` returns a MARIO supply and use table with four scenarios. The
result tables cover the footprint and producer price of solar electricity,
PV commodity output, value added, employment and aggregate effects.

.. code-block:: python

   tables["footprints"].query("region == 'EU27'")

In the central ``baseline`` case, the EU27 footprint is 51.25 g CO₂eq/kWh.
The 22% efficiency variant gives 46.91 g CO₂eq/kWh with the other assumptions
held fixed. Each run records its effective configuration, input files and
background database version.
