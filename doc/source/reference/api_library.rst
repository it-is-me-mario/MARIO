API reference
=============

Public methods and standalone functions include their signatures and parameters.
Filter the table by name, category or table format, or open a category from
the sidebar. Calculation entries identify IOT, SUT and NAM explicitly.
The same block name can have different inputs in different table formats.

For NAM, start with :doc:`the supported database interface <api_nam_database>`
and :doc:`account totals and coefficients <api_nam_calculations>`. A shared
method name can have format-specific options; the NAM page shows its actual
signatures rather than inheriting unsupported IOT/SUT workflows.

Calculation helpers include native SUT functions such as :func:`~mario.calc_u`,
:func:`~mario.calc_s`, :func:`~mario.calc_U` and :func:`~mario.calc_S`,
with equations, inputs and returned axes. See :doc:`api_calculation_methods`
for the full formula overview.

.. mario-api-index::

.. toctree::
   :maxdepth: 1
   :hidden:

   api_parsing_methods
   api_download_methods
   api_inspection_methods
   api_indices
   api_calculation_methods
   api_transformation_methods
   api_export_methods
   api_template_methods
   api_visualization_methods
   api_settings_methods
