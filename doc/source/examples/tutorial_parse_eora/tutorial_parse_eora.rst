Parsing EORA
============

This tutorial shows how to parse the EORA database, showing an example
for both EORA26 multi-regional table and for a single-region table

Downloading the database
------------------------

The database is available at the following website:
https://worldmrio.com/. An account is necessary to download the data.
You can manually download the repository. In this example we are going
to show how the EORA26 database (https://worldmrio.com/eora26/) and a
single-region table (https://worldmrio.com/countrywise/). The example is
based on tables for 2016 but it works the same for any other year.

EORA26
~~~~~~

Let’s start with EORA26, which is a multi-regional database. The
targeted table file for this example is the one named
“Eora26_2016_bp.zip”, in basic prices. It is necessary to download the
file (but not to unzip it) and store it in any directory (‘EORA_folder’
in this example). For EORA26, an additional attribute (‘indices’) is
necessary, through which the path to “indices.zip” file need to be
passed. The indices can be downloaded from the same link as EORA26 (link
to the file:
https://worldmrio.com/ComputationsM/Phase199/Loop082/simplified/indices.zip)

Single-Region EORA
~~~~~~~~~~~~~~~~~~

As an example of single-region table, we downloaded the 2016 table for
Italy in purchaser’s prices (download link:
https://worldmrio.com/ComputationsM/Phase199/Loop082/XLSResults/byCountry/ITA/byYear/2016/IO_ITA_2016_PurchasersPrice.txt).

Parsing the downloaded EORA26 database
--------------------------------------

Once the EORA26 database files are stored in a given path, it is
possible to parse it into a mario.Database object. The ‘parse_eora’
method is suitable to parse both EORA26 and single-region versions. For
EORA26, the ‘multi_region’ attribute must be set to True, the ‘year’
attribute must refer to the reference year of the table, and the
‘indeces’ must be equal to the path where ‘indices.zip’ has been stored.

Make sure the data is downloaded with corresponding names/path given to
the function!

.. code:: ipython3

    import mario  # Import MARIO
    
    table_path = 'Eora26_2016_bp.zip'  # Define the desired path to the folder where Exiobase should be downloaded
    indices_path = 'indices.zip'
    
    eora26 = mario.parse_eora(
        path = table_path,
        multi_region = True, 
        table = 'IOT',
        year = 2016,
        indeces = indices_path
    )


::


    ---------------------------------------------------------------------------

    KeyError                                  Traceback (most recent call last)

    Cell In[1], line 6
          3 table_path = 'Eora26_2016_bp.zip'  # Define the desired path to the folder where Exiobase should be downloaded
          4 indices_path = 'indices.zip'
    ----> 6 eora26 = mario.parse_eora(
          7     path = table_path,
          8     multi_region = True, 
          9     table = 'IOT',
         10     year = 2016,
         11     indeces = indices_path
         12 )


    File ~/Documents/GitHub/MARIO/mario/tools/parsersclass.py:341, in parse_eora(path, multi_region, table, indeces, name_convention, aggregate_trade, year, name, calc_all, model, **kwargs)
        336     if table == "SUT":
        337         raise NotImplemented(
        338             "No handling of multiregional SUT from EORA is implemented yet"
        339         )
    --> 341     matrices, indeces, units = eora_multi_region(
        342         data_path=path, index_path=indeces, year=year, price="bp"
        343     )
        345     kwargs["notes"] = [
        346         "ROW deleted from database due to inconsistency.",
        347         "Intermediate imports from ROW added to VA matrix",
        348         "Intermediate exports to ROW added to Y matrix",
        349     ]
        351 else:


    File ~/Documents/GitHub/MARIO/mario/tools/tableparser.py:838, in eora_multi_region(data_path, index_path, year, price)
        835     for values in parser_ids[main_key].values():
        836         values["file_name"] = values["file_name"].format(year=year, price=price)
    --> 838 labels = all_file_reader(
        839     index_path, dict(labels=parser_ids["labels"]), sub_folder=False
        840 )
        842 # reading the files
        843 read = all_file_reader(
        844     data_path, dict(matrices=parser_ids["matrices"]), sub_folder=False
        845 )


    File ~/Documents/GitHub/MARIO/mario/tools/utilities.py:196, in all_file_reader(path, guide, sub_folder, sep, exceptions, engine)
        190             for inner_key, inner_value in value.items():
        191                 path = (
        192                     r"{}/{}".format(new_path, inner_value["file_name"])
        193                     if new_path
        194                     else r"{}".format(inner_value["file_name"])
        195                 )
    --> 196                 with folder.open(path) as file:
        197                     readers(inner_value["file_name"], file)
        199 else:


    File /opt/anaconda3/envs/mario_dev/lib/python3.11/zipfile.py:1563, in ZipFile.open(self, name, mode, pwd, force_zip64)
       1560     zinfo._compresslevel = self.compresslevel
       1561 else:
       1562     # Get info object for name
    -> 1563     zinfo = self.getinfo(name)
       1565 if mode == 'w':
       1566     return self._open_to_write(zinfo, force_zip64=force_zip64)


    File /opt/anaconda3/envs/mario_dev/lib/python3.11/zipfile.py:1492, in ZipFile.getinfo(self, name)
       1490 info = self.NameToInfo.get(name)
       1491 if info is None:
    -> 1492     raise KeyError(
       1493         'There is no item named %r in the archive' % name)
       1495 return info


    KeyError: "There is no item named 'labels_T.txt' in the archive"


Parsing the downloaded single-region EORA database
--------------------------------------------------

As for EORA26, the ‘parse_eora’ method can be adopted also for single
region tables, setting ‘multi_region’ as False. In this case, ‘indeces’
should not be defined.

.. code:: ipython3

    table_path = 'IO_ITA_2016_PurchasersPrice.txt'  # Define the desired path to the folder where Exiobase should be downloaded
    
    eora_IT = mario.parse_eora(
        path = table_path,
        multi_region = False, 
        table = 'IOT',
        year = 2016,
    )


.. parsed-literal::

    /Users/mohammadamintahavori/Documents/GitHub/MARIO/mario/tools/tableparser.py:688: DtypeWarning:
    
    Columns (0) have mixed types. Specify dtype option on import or set low_memory=False.
    
    /Users/mohammadamintahavori/Documents/GitHub/MARIO/mario/tools/tableparser.py:700: PerformanceWarning:
    
    dropping on a non-lexsorted multi-index without a level parameter may impact performance.
    


.. code:: ipython3

    eora_IT




.. parsed-literal::

    name = None
    table = IOT
    scenarios = ['baseline']
    Factor of production = 7
    Satellite account = 2692
    Consumption category = 7
    Region = 1
    Sector = 61



:download:`Link to the jupyter notebook file </../notebooks/tutorial_parse_eora.ipynb>`.
