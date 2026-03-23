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
EORA26, the ‘multi_region’ attribute must be set to True. When the
standard label files (``labels_T.txt``, ``labels_FD.txt``,
``labels_VA.txt`` and ``labels_Q.txt``) are stored in the same folder as
the numeric files, the parser detects the layout directly and the
‘indeces’ argument is not needed.

.. code:: ipython3

    import mario  # Import MARIO
    
    table_path = 'Eora26_2016_bp'  # Folder containing Eora26_2016_bp_*.txt and labels_*.txt
    
    eora26 = mario.parse_eora(
        path = table_path,
        multi_region = True, 
        table = 'IOT',
        calc_all = False,
    )


Parsing the downloaded single-region EORA database
--------------------------------------------------

As for EORA26, the ‘parse_eora’ method can be adopted also for single
region tables, setting ‘multi_region’ as False. When ``path`` points to
a folder such as ``IO_All_2016``, a ``country`` code should be provided
to select the right file. If both Basic Price and Purchasers Price files
are present, the ``price`` argument should also be provided.

.. code:: ipython3

    table_path = 'IO_All_2016'
    
    eora_IT = mario.parse_eora(
        path = table_path,
        multi_region = False, 
        table = 'SUT',
        country = 'ITA',
        price = 'PurchasersPrice',
        year = 2016,
        calc_all = False,
    )


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
