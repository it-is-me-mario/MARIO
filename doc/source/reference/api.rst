API Reference
=============

.. currentmodule:: mario

Database and model
------------------

.. autosummary::
   :toctree: ../api_document/

   CoreModel.is_balanced
   CoreModel.is_multi_region
   CoreModel.is_hybrid
   CoreModel.is_chenerymoses
   CoreModel.is_isard
   CoreModel.sets
   CoreModel.scenarios
   CoreModel.table_type
   CoreModel.get_index
   CoreModel.calc_all
   CoreModel.GDP
   CoreModel.search
   CoreModel.directory
   Database.aggregate
   Database.add_extensions
   Database.add_sectors
   Database.clone_scenario
   Database.copy
   Database.backup
   Database.reset_to_flows
   Database.reset_to_coefficients
   Database.to_iot
   Database.to_chenery_moses
   Database.to_single_region
   Database.update_scenarios

Metadata
--------

.. autosummary::
   :toctree: ../api_document/

   CoreModel.save_meta
   CoreModel.meta_history
   CoreModel.add_note

Templates and exports
---------------------

.. autosummary::
   :toctree: ../api_document/

   Database.get_aggregation_excel
   Database.get_extensions_excel
   Database.get_add_sectors_excel
   Database.get_shock_excel
   Database.to_excel
   Database.to_txt
   Database.to_parquet
   Database.to_pymrio

Shocks and visualisation
------------------------

.. autosummary::
   :toctree: ../api_document/

   Database.shock_calc
   Database.calc_linkages
   Database.plot_gdp
   Database.plot_bubble
   Database.plot_linkages
   Database.plot_matrix

Parsers
-------

.. autosummary::
   :toctree: ../api_document/

   parse_from_excel
   parse_from_txt
   parse_from_parquet
   parse_from_pymrio
   parse_eurostat
   parse_figaro
   parse_exiobase
   parse_exiobase_3
   parse_exiobase_sut
   hybrid_iot_exiobase
   hybrid_sut_exiobase
   parse_eora
   parse_oecd
   parse_wiod
   parse_adb
   parse_gtap
   parse_gloria
   parse_istat
   parse_statcan
   parse_emerging

Compute primitives
------------------

.. autosummary::
   :toctree: ../api_document/

   calc_X
   calc_X_from_w
   calc_X_from_z
   calc_Z
   calc_E
   calc_V
   calc_M
   calc_F
   calc_w
   calc_g
   calc_b
   calc_p
   calc_y

Utilities and settings
----------------------

.. autosummary::
   :toctree: ../api_document/

   load_test
   slicer
   set_log_verbosity
   set_palette
   upload_settings
   download_settings
   reset_settings
