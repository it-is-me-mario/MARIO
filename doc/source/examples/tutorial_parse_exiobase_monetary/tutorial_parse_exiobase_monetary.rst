Parsing Exiobase v3.8.2 (Monetary units)
========================================

This tutorial shows how to parse the Exiobase v3.8.2 database in
supply-use (SUT) and input-output (IOT) format.

Downloading the database
------------------------

The database is available at the following Zenodo repository:
https://zenodo.org/records/5589597. You can manually download the
repository. In this example we are going to show how to parse a SUT and
a IOT both for 2019

Parsing the downloaded SUT database
-----------------------------------

Once the Exiobase database is stored in a given path (‘SUT_path’ in this
example, where we target the SUT for 2019), it is possible to parse it
into a mario.Database object. The ‘parse_exiobase’ function is suitable
to parse any version of Exiobase, providing the type of table (‘SUT’ or
‘IOT), the type of unit (’Hybrid’ or ‘Monetary’) and the directory where
the database is stored.

It is not necessary to unzip the downloaded file

.. code:: ipython3

    import mario  # Import MARIO
    
    SUT_path = 'MRSUT_2019.zip'  # Define the desired path to the folder where Exiobase should be downloaded
    
    exiobase = mario.parse_exiobase(
        table = 'SUT',
        unit = 'Monetary',
        path = SUT_path,
    )

Exploring the database
----------------------

Once the database is parsed, MARIO offers useful methods to explore and
navigate the database.

Searching for activities
~~~~~~~~~~~~~~~~~~~~~~~~

Adopting the ‘search’ method of the Database class, MARIO allows the
user to extract a list out of a given database set which contain a
desired string. For instance, it is possible to extract all the
activities containing the “gas” string.

.. code:: ipython3

    exiobase.search('Activity','gas') 




.. parsed-literal::

    ['Manure treatment (biogas), storage and land application',
     'Extraction of natural gas and services related to natural gas extraction, excluding surveying',
     'Extraction, liquefaction, and regasification of other petroleum and gaseous materials',
     'Production of electricity by gas',
     'Manufacture of gas; distribution of gaseous fuels through mains',
     'Biogasification of food waste, incl. land application',
     'Biogasification of paper, incl. land application',
     'Biogasification of sewage slugde, incl. land application']



The easy rule is to always refer to the database sets using the singular
and the first capital letter (e.g. ‘Satellite account’, ‘Commodity’,…)

Getting set list
~~~~~~~~~~~~~~~~

In case the objective is to get the full list of labels contained in a
set, the ‘get_index’ method allows to do so. Again, use the singular and
capital letter.

.. code:: ipython3

    exiobase.get_index('Region')




.. parsed-literal::

    ['AT',
     'BE',
     'BG',
     'CY',
     'CZ',
     'DE',
     'DK',
     'EE',
     'ES',
     'FI',
     'FR',
     'GR',
     'HR',
     'HU',
     'IE',
     'IT',
     'LT',
     'LU',
     'LV',
     'MT',
     'NL',
     'PL',
     'PT',
     'RO',
     'SE',
     'SI',
     'SK',
     'GB',
     'US',
     'JP',
     'CN',
     'CA',
     'KR',
     'BR',
     'IN',
     'MX',
     'RU',
     'AU',
     'CH',
     'TR',
     'TW',
     'NO',
     'ID',
     'ZA',
     'WA',
     'WL',
     'WE',
     'WF',
     'WM']



.. code:: ipython3

    exiobase.get_index('Factor of production')




.. parsed-literal::

    ['Taxes less subsidies on products purchased: Total',
     'Taxes on products purchased',
     'Subsidies on products purchased',
     'Other net taxes on production',
     "Compensation of employees; wages, salaries, & employers' social contributions: Total",
     "Compensation of employees; wages, salaries, & employers' social contributions: Low-skilled",
     "Compensation of employees; wages, salaries, & employers' social contributions: Medium-skilled",
     "Compensation of employees; wages, salaries, & employers' social contributions: High-skilled",
     'Operating surplus: Consumption of fixed capital',
     'Operating surplus: Rents on land',
     'Operating surplus: Royalties on resources',
     'Operating surplus: Remaining net operating surplus']



Parsing the downloaded IOT database
-----------------------------------

Moving to the IOT database, once it is downloaded and stored in a given
path (‘IOT_path’ in this example, where we target the
industry-by-industry IOT for 2019), it is possible to parse it into a
mario.Database object. Again, the ‘parse_exiobase’ function is suitable
to parse this version of Exiobase, providing the type of table (‘IOT’ in
this case), the type of unit (again, ‘Monetary’) and the directory where
the database is stored.

.. code:: ipython3

    
    # Download the exiobase IOT 2019 ixi
    info = mario.download_exiobase3(".",years=[2019],system="ixi")
    
    IOT_path = 'IOT_2019_ixi.zip'  # Define the desired path to the folder where Exiobase should be downloaded
    
    exiobase = mario.parse_exiobase(
        table = 'IOT',
        unit = 'Monetary',
        path = IOT_path,
    )

Note that there is no need to specify whether the database is defined as
industry-by-industry or as product-by-product. MARIO will deal with any
IOT in the same manner: unlike for SUTs, which distinguish “Activity”
and “Commodity” among their sets, the IOTs presents the “Sector” set.

This can be tested just by calling the ‘exiobase’ object, to show the
sets of the parsed database, noticing the database has 163 items within
the “Sector” set.

.. code:: ipython3

    exiobase




.. parsed-literal::

    name = None
    table = IOT
    scenarios = ['baseline']
    Factor of production = 9
    Satellite account = 1104
    Consumption category = 7
    Region = 49
    Sector = 163



The ‘search’ and ‘get_index’ methods can be applied to the IOT in the
same way as for the SUT.

:download:`Link to the jupyter notebook file </../notebooks/tutorial_parse_exiobase_monetary.ipynb>`.
