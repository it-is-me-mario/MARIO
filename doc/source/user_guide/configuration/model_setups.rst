:page-type: guide
:summary: Install a research model and open an editable project.

Research model setups
=====================

Each research model is maintained in its own repository. MARIO opens an
installed model through :func:`mario.model_setup`. The project's Python API,
input files and indicators are defined by that model.

Install PV-HLCA
---------------

The installation and setup functions below are available when running MARIO
from its current source. The :doc:`PV-HLCA project reference
<../../api_document/pv_hlca.project.Project>` describes the project class
available with released versions of ``mariopy``. Use a Python environment
with pip and Git.

.. code-block:: python

   import mario

   commit = mario.models.install("pv-hlca")

The installer selects a fixed commit and returns its SHA. To try a development
branch, use ``mario.models.install("pv-hlca", ref="branch-name")``. A tag or full
commit SHA also works. The installer keeps the installed MARIO version fixed.
Start a new Python session after installation or switching revisions. The model
repository also supports direct and editable installation.

Build a project
---------------

.. code-block:: python

   import mario

   model = mario.model_setup("pv-hlca", workspace="./pv-study")
   model.fetch_data()
   db = model.build()
   tables = model.results(db)
   print(tables["footprints"].query("region == 'EU27'"))

The workspace contains ``config.yaml`` and the editable YAML/CSV inputs.
``fetch_data()`` retrieves the versioned background database to a separate
cache. ``build()`` returns a MARIO SUT with the model's scenarios.

Change a hypothesis in the workspace YAML or pass an argument to the build:

.. code-block:: python

   alternative = model.build(module_efficiency=0.22)

The model saves the effective configuration and a copy of the input files for
each run. Use ``model.docs()`` to find the guide for your installed version and
``model.describe()`` to inspect the available parameters, scenarios and results.
See the `PV-HLCA repository <https://github.com/it-is-me-mario/pv-hlca-model>`_
for the publication and packaged guide.

:doc:`../../reference/api_model_methods` documents the common MARIO calls and
the PV-HLCA project API.
