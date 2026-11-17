Research models
===============

See :doc:`../user_guide/configuration/model_setups` for the PV-HLCA workflow.

.. toctree::
   :maxdepth: 1

   ../api_document/mario.model_setup
   ../api_document/mario.models.install

A model is an installable Python project that registers a factory in the
``mario.models`` entry point group. The entry point name identifies the model.
The factory accepts the workspace through the ``workspace`` keyword argument
and returns the model's project object. It can expose its own configuration,
data retrieval, results and documentation.
