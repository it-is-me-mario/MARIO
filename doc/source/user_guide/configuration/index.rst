:summary: Control calculation settings and customize the current Python session.

Configuration
=============

MARIO settings apply to the Python session. A parser can select compute
preferences for its database; inspect the active settings after importing.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - I want to
     - Guide
   * - Choose inverse or solve, a solver, and singular-system handling
     - :doc:`Computation settings <../advanced/compute_settings>`
   * - Customize matrix names and set aliases, or save settings
     - :doc:`Custom names and aliases <../inspection/custom_labels_and_aliases>`

:doc:`Database profiles <../advanced/database_profiles>` describe the
preferences bundled for a source. Active session settings are inspected
separately. See the :doc:`settings API <../../reference/api_settings_methods>`
for all configuration functions.

Provider credentials for electricity data are described beside the
:doc:`supply and trade mix workflow <../advanced/electricity_mix>` that uses them.

.. toctree::
   :hidden:

   ../advanced/compute_settings
   ../inspection/custom_labels_and_aliases
