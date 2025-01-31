Using MARIO and Pymrio Handshake Protocols
==========================================

Since version 3 of mario, user can exchange data between mario and
pymrio to be able to cover parsers that are missed in mario or pymrio or
use some of the two library functionalities.

In this example, we will look at how this function can be used.

OECD
----

Assuem you want to parse the oecd tables , and the oecd parser does not
exist natively in mario. At the first step, let’s download and load the
OECD data for 2011 using pymrio.

.. code:: ipython3

    import mario
    import pymrio
    from pathlib import Path
    
    
    oecd_storage = Path("temp_folder")
    meta_2018_download = pymrio.download_oecd(storage_folder=oecd_storage, years=[2011])
    
    data = pymrio.parse_oecd(path=oecd_storage, year=2011)

Lets’ take a look to the objects in pymrio parser output.

.. code:: ipython3

    dir(data)




.. parsed-literal::

    ['A',
     'As',
     'G',
     'L',
     'Y',
     'Z',
     '__basic__',
     '__class__',
     '__coefficients__',
     '__delattr__',
     '__dict__',
     '__dir__',
     '__doc__',
     '__eq__',
     '__format__',
     '__ge__',
     '__getattribute__',
     '__getstate__',
     '__gt__',
     '__hash__',
     '__init__',
     '__init_subclass__',
     '__le__',
     '__lt__',
     '__module__',
     '__ne__',
     '__new__',
     '__non_agg_attributes__',
     '__reduce__',
     '__reduce_ex__',
     '__repr__',
     '__setattr__',
     '__sizeof__',
     '__str__',
     '__subclasshook__',
     '__weakref__',
     'aggregate',
     'aggregate_duplicates',
     'calc_all',
     'calc_extensions',
     'calc_system',
     'copy',
     'factor_inputs',
     'get_DataFrame',
     'get_Y_categories',
     'get_extensions',
     'get_gross_trade',
     'get_index',
     'get_regions',
     'get_sectors',
     'meta',
     'name',
     'population',
     'remove_extension',
     'rename_Y_categories',
     'rename_regions',
     'rename_sectors',
     'report_accounts',
     'reset_all_full',
     'reset_all_to_coefficients',
     'reset_all_to_flows',
     'reset_extensions',
     'reset_full',
     'reset_to_coefficients',
     'reset_to_flows',
     'save',
     'save_all',
     'set_index',
     'unit',
     'x']



Unlike mario approach that all the satellite accounts and factors of
production are concatnated into one object, pymrio follows the strucutre
of the database and assing each account to a different object. So the
only piece of puzzle needs to be solved to transform a pymrio object to
mario object is to map those accounts. In this case for example, OECD
has no satellite accounts and it has only factors of production, stored
in factor_inputs object:

.. code:: ipython3

    data.factor_inputs.get_index()




.. parsed-literal::

    Index(['TLS', 'VA'], dtype='object', name='inputtype')



now using parse_from_pymrio function in mario, we can transfer pymrio
object to mario object. When doing so, you can take specific values from
an account, or take all the rows!

.. code:: ipython3

    oecd_by_mario = mario.parse_from_pymrio(
        io = data, # pymrio object
        value_added = {"factor_inputs":"all"}, # mapping of pymrio extensions using a dict.
        satellite_account= {} # there is no satellite account for the database
    )


.. parsed-literal::

    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    WARNING:mario.core.CoreIO:Database: to calculate v following matrices are need.
    ['X'].Trying to calculate dependencies.


now lets take a look to the mario data!

.. code:: ipython3

    print(oecd_by_mario)


.. parsed-literal::

    name = OECD-ICIO
    table = IOT
    scenarios = ['baseline']
    Factor of production = 2
    Satellite account = 1
    Consumption category = 7
    Region = 77
    Sector = 45
    


⚠️ NOTE: You can alternatively use the parse_oecd function of mario
which does this intermediate steps for you!

Exiobase 3.9.4
--------------

Another example we can look at is the latest release of exiobase. This
version is not compatible with the older versions of mario due to its
structure. But via the parse_from_pymrio, the data can be parsed easily.
Let’s repeat the exercise:

.. code:: ipython3

    
    pymrio.download_exiobase3(
        storage_folder = "temp_folder",
        years = 2020,
        system = "ixi",
        )




.. parsed-literal::

    Description: Download log of EXIOBASE3
    MRIO Name: EXIO3
    System: ixi
    Version: 10.5281/zenodo.3583070
    File: temp_folder/download_log.json
    History:
    20250129 19:20:40 - FILEIO -  Downloaded https://zenodo.org/records/14614930/files/IOT_2020_ixi.zip to IOT_2020_ixi.zip
    20250129 19:20:23 - NOTE -  Download log created
    20250129 19:20:23 - NOTE -  python_version: 3.11.10
    20250129 19:20:23 - NOTE -  pymrio_version: 0.5.4
    20250129 19:20:23 - NOTE -  os: Darwin
    20250129 19:20:23 - NOTE -  hostname: Mohammads-MacBook-Pro.local
    20250129 19:20:23 - NOTE -  username: mohammadamintahavori
    20250129 19:20:23 - METADATA_CHANGE -  Changed parameter "version" from "v2023" to "10.5281/zenodo.3583070"
    20250129 19:20:23 - METADATA_CHANGE -  Changed parameter "system" from "IxI" to "ixi"
    20250129 19:20:23 - METADATA_CHANGE -  Changed parameter "name" from "OECD-ICIO" to "EXIO3"
     ... (more lines in history)



.. code:: ipython3

    exio_by_pymrio = pymrio.parse_exiobase3("temp_folder/IOT_2020_ixi.zip")

The satellite accounts in this version of EXIOBASE are splitted into
multiple categories:

::

   - material
   - water
   - employment
   - air_emissions
   - energy
   - land
   - nutrients

and the factor of production is named as factor_inputs. The puzzle is
solved then!

.. code:: ipython3

    sat_acc = {  # In this way we are assigning all the indicators in the extensions that we want to map as Satellite Accounts
        'material': 'all',
        'water': 'all',
        'employment': 'all',
        'air_emissions': 'all',
        'energy': 'all',
        'land': 'all',
        'nutrients': 'all'
    } 
    
    value_added = {'factor_inputs': 'all'} # In this way we are assigning all the indicators in the extensions that we want to map as Value Added
    
    exio_by_mario = mario.parse_from_pymrio(exio_by_pymrio, satellite_account=sat_acc, value_added=value_added)



.. parsed-literal::

    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:900: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:956: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:984: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:993: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1001: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    /opt/anaconda3/envs/mariov3.4/lib/python3.11/site-packages/pymrio/core/mriosystem.py:1007: FutureWarning:
    
    DataFrame.groupby with axis=1 is deprecated. Do `frame.T.groupby(...)` without axis instead.
    
    WARNING:mario.core.CoreIO:Database: to calculate v following matrices are need.
    ['X'].Trying to calculate dependencies.


.. code:: ipython3

    print(exio_by_mario)


.. parsed-literal::

    name = EXIO_IOT_2020_ixi
    table = IOT
    scenarios = ['baseline']
    Factor of production = 9
    Satellite account = 726
    Consumption category = 7
    Region = 49
    Sector = 163
    


⚠️ NOTE: You can alternatively use the prase_exiobase function of mario
which does this intermediate steps for you! You just need to pass the
version of the database you need to parse

:download:`Link to the jupyter notebook file </../notebooks/tutorial_hand_shakes.ipynb>`.
