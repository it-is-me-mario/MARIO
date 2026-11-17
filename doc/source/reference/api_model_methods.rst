Research models
===============

See `Research model setups`_ to install a model and open a workspace. The
`PV-HLCA guide in the Model Gallery`_ covers its data, scenarios and results.
The MARIO installation and setup functions are available in source builds.
The PV-HLCA project class works with compatible releases of ``mariopy``.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.model_setup
   ../api_document/mario.models.install
   PV-HLCA project <../api_document/pv_hlca.project.Project>

A model is an installable Python project that registers a factory in the
``mario.models`` entry point group. The entry point name identifies the model.
The factory accepts the workspace through the ``workspace`` keyword argument
and returns the model's project object. It can expose its own configuration,
data retrieval, results and documentation.
