API Reference
=============

.. currentmodule:: mario

******************
Analyzing database
******************

.. autosummary::
    :toctree: api_document/

    CoreModel.is_balanced
    CoreModel.is_productive
    CoreModel.is_multi_region
    CoreModel.is_hybrid
    CoreModel.sets
    CoreModel.scenarios
    CoreModel.table_type
    CoreModel.get_index
    CoreModel.is_chenerymoses
    CoreModel.is_isard

*********************
Database modification
*********************

.. autosummary::
    :toctree: api_document/

    Database.aggregate
    Database.add_sectors
    Database.to_single_region
    Database.to_iot
    Database.add_extensions
    Database.update_scenarios
    Database.reset_to_flows
    Database.reset_to_coefficients
    Database.clone_scenario
    Database.copy
    Database.backup
    Database.reset_to_backup
    Database.to_chenery_moses


**************
Shock analysis
**************

.. autosummary::
    :toctree: api_document/

    Database.shock_calc

******************
Data visualization
******************

.. autosummary::
    :toctree: api_document/

    mario.set_palette
    Database.plot_gdp
    Database.plot_bubble
    Database.plot_linkages
    Database.plot_matrix

**********
Get excels
**********
mario has some functions providing automatic excel file generations for easing some of
the functionalities such as aggrgeaton and adding sectors.

.. autosummary::
    :toctree: api_document/

    Database.get_aggregation_excel
    Database.get_extensions_excel
    Database.get_add_sectors_excel
    Database.get_shock_excel

*********
Save data
*********

.. autosummary::
    :toctree: api_document/

    Database.to_excel
    Database.to_txt
    Database.to_pymrio


****************
Database parsers
****************

Structured Databases
--------------------
mario supports automatic parsing of following database:

* Exiobase
* Eora26
* Eora single region

.. autosummary::
    :toctree: api_document/

    mario.parse_exiobase_3
    mario.parse_exiobase_sut
    mario.parse_eora
    mario.parse_from_pymrio
    mario.parse
    mario.hybrid_sut_exiobase
    mario.parse_exiobase
    mario.parse_oecd


Non-Structured Databases
------------------------
When databases are not structured (coming from abovementioned sources),
excel or text parsers can be used. The databases in this case, should follow
specific rules:

.. autosummary::
    :toctree: api_document/

    mario.parse_from_excel
    mario.parse_from_txt


************
Calculations
************

High level matrix calculations
-------------------------------
This function can be called inside a mario.Database object
to call missing matrices for different scenarios.

.. autosummary::
    :toctree: api_document/

    CoreModel.calc_all
    CoreModel.GDP
    Database.calc_linkages

Low level matrix calculations
------------------------------

This functions are used to calculate the matrices in mario.Database while they
can be used independently outside a mario.Databases object.

.. autosummary::
    :toctree: api_document/

    calc_X
    calc_X_from_w
    calc_X_from_z
    calc_Z
    calc_E
    calc_V
    calc_M
    calc_F
    calc_z
    calc_v
    calc_e
    calc_m
    calc_f
    calc_w
    calc_g
    calc_b
    calc_p
    calc_y

********
Metadata
********

.. autosummary::
    :toctree: api_document/

    CoreModel.save_meta
    CoreModel.meta_history
    CoreModel.add_note

****
Test
****

For having a simple exmaple of mario, load_test can be used.

.. autosummary::
    :toctree: api_document/

    mario.load_test

*********
Directory
*********

When mario needs to save an output of the model, if no path is given,
files wil be saved in a default directory with subfolders based on
the type of the output. By default, the directory is the working directory
but user can change the default directory.

.. autosummary::
    :toctree: api_document/

    CoreModel.directory

*********
Utilities
*********
There are some useful functions in mario that may help the user for different purposes.

.. autosummary::
    :toctree: api_document/

    CoreModel.search
    mario.slicer


*******
Logging
*******
In case that logging is useful for the user, the following function can be used to set the level of verbosity.

.. autosummary::
    :toctree: api_document/

    mario.set_log_verbosity


********
Settings
********
To customize the mario settings for naming convensions, the following functions can be used: 

.. autosummary::
    :toctree: api_document/

    mario.upload_settings
    mario.download_settings
    mario.reset_settings