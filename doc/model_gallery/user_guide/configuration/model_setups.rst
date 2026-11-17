:page-type: Guide
:summary: Install a catalogued research model and open its project workspace.

Research model setups
=====================

Each research model has its own repository, inputs and results. Install the
model package, then open a project in a workspace where you can edit its inputs.

Install a model
---------------

Install the current MARIO source checkout into your Python environment and
make sure Git and pip are available. Pass a model identifier from the
installation catalogue to :func:`mario.models.install`. This example installs
``pv-hlca``.

.. code-block:: python

   import mario

   commit = mario.models.install("pv-hlca")

MARIO installs the pinned model revision and returns its Git commit SHA. To
try a development version, pass a branch, tag or full commit SHA as ``ref``.

.. code-block:: python

   commit = mario.models.install("pv-hlca", ref="branch-name")

If you use the released ``mariopy`` package, follow the direct installation
instructions in the model's guide. For changes to the model code, use an
editable checkout of its repository.

Open a project
--------------

Start a new Python session after installing or updating a model. Pass its
registered name and a workspace directory to :func:`mario.model_setup`.

.. code-block:: python

   import mario

   model = mario.model_setup("pv-hlca", workspace="./pv-study")

Check the model's guide for data requirements, editable inputs, available
scenarios and results. For this example, continue with :doc:`../../models/pv-hlca`.
