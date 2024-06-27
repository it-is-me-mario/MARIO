Changing mario settings
=======================

mario has the capability of being flexible in the definition of some
definitions in an instance. This feature, allows the users to customize
mario, to their specfici nomenclature or naming convensions and
preferences.

For example, the dimenssion of regions in a table, by default, is called
**“Region”** in mario, but you might prefer to call it **“Country”**.
Or, the technical coefficient matrix in mario is called **“z”**, but as
in the literature, **“A”** is mainly used for the technical coefficient,
you might change this in mario, without impacting the performance of the
code.

This can be done thorugh mario settings module functionalities as
described below:

.. code:: ipython3

    from mario import upload_settings,download_settings,reset_settings



To change the default settings, you need to follow a specific structure,
that is represented as a nested python dict or a can be represented as a
yaml file. To access the default settings, you can use the
**‘download_settings’** function:

.. code:: ipython3

    settings = download_settings()

.. code:: ipython3

    settings




.. parsed-literal::

    {'index': {'a': 'Activity',
      'c': 'Commodity',
      'f': 'Factor of production',
      'k': 'Satellite account',
      'n': 'Consumption category',
      'r': 'Region',
      's': 'Sector'},
     'nomenclature': {'E': 'E',
      'EY': 'EY',
      'F': 'F',
      'M': 'M',
      'S': 'S',
      'U': 'U',
      'V': 'V',
      'X': 'X',
      'Y': 'Y',
      'Z': 'Z',
      'b': 'b',
      'e': 'e',
      'f': 'f',
      'g': 'g',
      'm': 'm',
      'p': 'p',
      's': 's',
      'u': 'u',
      'v': 'v',
      'w': 'w',
      'y': 'y',
      'z': 'z'}}



If you wish to download the yaml file and modify the yaml file, you can
path the directory where you want to download the yaml file like:

.. code:: ipython3

    settings = download_settings("path to download")

Now lets assume we want to implement two changes on the settings:

1. Changing “Region” to “Country” for indexing
2. Using “A” for the technical coefficient matrix instead of “z”

Chaning the index
-----------------

.. code:: ipython3

    # current setting
    settings["index"]["r"]




.. parsed-literal::

    'Region'



.. code:: ipython3

    # Changing setting
    settings["index"]["r"] = "Country"
    
    # new setting
    settings["index"]["r"]




.. parsed-literal::

    'Country'



Changing the matrix nomenclature
--------------------------------

for this, you need to change the var of the specific key in
nomenclature. Please refer to mario’s terminology
(https://mario-suite.readthedocs.io/en/latest/terminology.html)

.. code:: ipython3

    # current settings
    settings["nomenclature"]["z"]




.. parsed-literal::

    'z'



.. code:: ipython3

    # Changing settings
    settings["nomenclature"]["z"] = "A"
    
    # New settings
    settings["nomenclature"]["z"]




.. parsed-literal::

    'A'



Once your changes are ready, you can upload them to mario settings using
the **“upload_settings”** function. You can pass the python dictionary
or the path to the yaml file:

.. code:: ipython3

    upload_settings(settings)

Now your changes are implemented into the settings. To make sure, you
can download the settings again and check the status:

.. code:: ipython3

    download_settings()




.. parsed-literal::

    {'index': {'a': 'Activity',
      'c': 'Commodity',
      'f': 'Factor of production',
      'k': 'Satellite account',
      'n': 'Consumption category',
      'r': 'Country',
      's': 'Sector'},
     'nomenclature': {'E': 'E',
      'EY': 'EY',
      'F': 'F',
      'M': 'M',
      'S': 'S',
      'U': 'U',
      'V': 'V',
      'X': 'X',
      'Y': 'Y',
      'Z': 'Z',
      'b': 'b',
      'e': 'e',
      'f': 'f',
      'g': 'g',
      'm': 'm',
      'p': 'p',
      's': 's',
      'u': 'u',
      'v': 'v',
      'w': 'w',
      'y': 'y',
      'z': 'A'}}



**Warning:**

mario needs to reload some of its modules to force the software to use
the new settings everywhere. in some cases, the changes might not be
syncronized everywhere. To secure the full syncronization, it is advised
to close your interactive session and reload mario after you implemented
your changes.

Now we can check how things are changed. Let’s import a mario example:

.. code:: ipython3

    from mario import load_test

.. code:: ipython3

    example = load_test("IOT")

.. code:: ipython3

    example




.. parsed-literal::

    name = IOT test
    table = IOT
    scenarios = ['baseline']
    Factor of production = 3
    Satellite account = 4
    Consumption category = 1
    Country = 2
    Sector = 6



At first, you can notice that, the regions are now represent with
**“Country”** keyword in the database. that can be also seen when using
the **get_index** funciton:

.. code:: ipython3

    example.get_index("Country")




.. parsed-literal::

    ['RoW', 'Italy']



Now if you need to take the technical coefficient matrix, you need to
request **“A”** instead of **“z”**:

.. code:: ipython3

    example.A




.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }
    
        .dataframe tbody tr th {
            vertical-align: top;
        }
    
        .dataframe thead tr th {
            text-align: left;
        }
    
        .dataframe thead tr:last-of-type th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr>
          <th></th>
          <th></th>
          <th>Country</th>
          <th colspan="6" halign="left">Italy</th>
          <th colspan="6" halign="left">RoW</th>
        </tr>
        <tr>
          <th></th>
          <th></th>
          <th>Level</th>
          <th colspan="6" halign="left">Sector</th>
          <th colspan="6" halign="left">Sector</th>
        </tr>
        <tr>
          <th></th>
          <th></th>
          <th>Item</th>
          <th>Agriculture</th>
          <th>Construction</th>
          <th>Manufacturing</th>
          <th>Mining</th>
          <th>Services</th>
          <th>Transport</th>
          <th>Agriculture</th>
          <th>Construction</th>
          <th>Manufacturing</th>
          <th>Mining</th>
          <th>Services</th>
          <th>Transport</th>
        </tr>
        <tr>
          <th>Country</th>
          <th>Level</th>
          <th>Item</th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th rowspan="6" valign="top">Italy</th>
          <th rowspan="6" valign="top">Sector</th>
          <th>Agriculture</th>
          <td>0.035106</td>
          <td>0.000653</td>
          <td>0.021014</td>
          <td>0.000083</td>
          <td>0.001676</td>
          <td>0.000288</td>
          <td>5.048324e-05</td>
          <td>0.000002</td>
          <td>0.000024</td>
          <td>0.000001</td>
          <td>0.000005</td>
          <td>0.000002</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>0.012325</td>
          <td>0.194778</td>
          <td>0.004384</td>
          <td>0.005575</td>
          <td>0.008825</td>
          <td>0.002324</td>
          <td>7.457826e-07</td>
          <td>0.000019</td>
          <td>0.000001</td>
          <td>0.000002</td>
          <td>0.000004</td>
          <td>0.000002</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>0.132174</td>
          <td>0.237906</td>
          <td>0.240282</td>
          <td>0.072057</td>
          <td>0.049447</td>
          <td>0.055996</td>
          <td>5.809324e-04</td>
          <td>0.001911</td>
          <td>0.002514</td>
          <td>0.000878</td>
          <td>0.000415</td>
          <td>0.000788</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>0.000580</td>
          <td>0.007814</td>
          <td>0.004607</td>
          <td>0.043918</td>
          <td>0.001428</td>
          <td>0.000343</td>
          <td>2.853587e-06</td>
          <td>0.000019</td>
          <td>0.000025</td>
          <td>0.000021</td>
          <td>0.000002</td>
          <td>0.000001</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>0.137336</td>
          <td>0.133450</td>
          <td>0.206065</td>
          <td>0.248969</td>
          <td>0.231043</td>
          <td>0.183065</td>
          <td>1.207210e-04</td>
          <td>0.000200</td>
          <td>0.000249</td>
          <td>0.000153</td>
          <td>0.000322</td>
          <td>0.000281</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>0.027626</td>
          <td>0.016173</td>
          <td>0.050787</td>
          <td>0.108437</td>
          <td>0.034471</td>
          <td>0.248808</td>
          <td>2.007685e-05</td>
          <td>0.000028</td>
          <td>0.000043</td>
          <td>0.000034</td>
          <td>0.000035</td>
          <td>0.000319</td>
        </tr>
        <tr>
          <th rowspan="6" valign="top">RoW</th>
          <th rowspan="6" valign="top">Sector</th>
          <th>Agriculture</th>
          <td>0.029250</td>
          <td>0.001083</td>
          <td>0.004822</td>
          <td>0.000277</td>
          <td>0.000723</td>
          <td>0.000153</td>
          <td>1.081939e-01</td>
          <td>0.006410</td>
          <td>0.053775</td>
          <td>0.003453</td>
          <td>0.005811</td>
          <td>0.008671</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>0.000110</td>
          <td>0.003467</td>
          <td>0.000326</td>
          <td>0.000257</td>
          <td>0.000102</td>
          <td>0.000055</td>
          <td>3.635630e-03</td>
          <td>0.068389</td>
          <td>0.002878</td>
          <td>0.012448</td>
          <td>0.011287</td>
          <td>0.004867</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>0.018519</td>
          <td>0.025394</td>
          <td>0.112831</td>
          <td>0.013736</td>
          <td>0.011612</td>
          <td>0.009333</td>
          <td>1.190623e-01</td>
          <td>0.312903</td>
          <td>0.431001</td>
          <td>0.101473</td>
          <td>0.068652</td>
          <td>0.112907</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>0.000631</td>
          <td>0.000609</td>
          <td>0.037504</td>
          <td>0.027916</td>
          <td>0.004308</td>
          <td>0.000780</td>
          <td>2.203056e-03</td>
          <td>0.011217</td>
          <td>0.047095</td>
          <td>0.060872</td>
          <td>0.003256</td>
          <td>0.002639</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>0.011629</td>
          <td>0.010859</td>
          <td>0.019097</td>
          <td>0.023009</td>
          <td>0.019389</td>
          <td>0.012611</td>
          <td>1.565488e-01</td>
          <td>0.151628</td>
          <td>0.154824</td>
          <td>0.156603</td>
          <td>0.258929</td>
          <td>0.162667</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>0.001366</td>
          <td>0.000667</td>
          <td>0.003838</td>
          <td>0.008621</td>
          <td>0.003904</td>
          <td>0.024286</td>
          <td>2.019775e-02</td>
          <td>0.042909</td>
          <td>0.025625</td>
          <td>0.037014</td>
          <td>0.023152</td>
          <td>0.163810</td>
        </tr>
      </tbody>
    </table>
    </div>



It’s Awesome! Isn’t it?

Reseting to default settings
----------------------------

If you wish to comeback to the original mario settings, you need to use
the **reset_settings** funciton:

.. code:: ipython3

    reset_settings()

⚠️ **warning:**

if you make a mistake in your custom settings, mario will switch to the
default settings. Let’s take an example by removing one of the essential
index elements in the custom setting:

.. code:: ipython3

    del settings["index"]["a"]
    
    settings




.. parsed-literal::

    {'index': {'c': 'Commodity',
      'f': 'Factor of production',
      'k': 'Satellite account',
      'n': 'Consumption category',
      'r': 'Country',
      's': 'Sector'},
     'nomenclature': {'E': 'E',
      'EY': 'EY',
      'F': 'F',
      'M': 'M',
      'S': 'S',
      'U': 'U',
      'V': 'V',
      'X': 'X',
      'Y': 'Y',
      'Z': 'Z',
      'b': 'b',
      'e': 'e',
      'f': 'f',
      'g': 'g',
      'm': 'm',
      'p': 'p',
      's': 's',
      'u': 'u',
      'v': 'v',
      'w': 'w',
      'y': 'y',
      'z': 'A'}}



.. code:: ipython3

    upload_settings(settings)


.. parsed-literal::

    The user settings is not correctly build for index, so the original mario settings are used.


.. code:: ipython3

    # Lets get back to the original settings to continue with the tests
    reset_settings()

Advanced use cases of settings
------------------------------

If you wish to go through mario code and make some changes in the
software, you need to properly use the enums created for these naming
convensions. Everytime that mario is loaded, it is reading the
configuration file, and create two specific classes for naming
conventions using **Index** and **Nomenclature**:

.. code:: ipython3

    from mario import Index,Nomenclature

.. code:: ipython3

    idx = Index()
    nom = Nomenclature()

These two objects will carry on the naming convensions, so it can be
used when coding in mario, to encapsulate the coding and naming
convensions. Let’s take a look to these objects:

.. code:: ipython3

    idx.r




.. parsed-literal::

    'Region'



.. code:: ipython3

    idx.a




.. parsed-literal::

    'Activity'



.. code:: ipython3

    nom.z




.. parsed-literal::

    'z'



.. code:: ipython3

    nom.Z




.. parsed-literal::

    'Z'



As you can see, instead of using direct variables in mario, we rely on
these two clases to get the user the opprotunity to change the settings
wihtout any troubles. Inside mario, these two classes are extensively
used for these purpose. If you check the core code, in constants modlues
of mario, you will find two variabls called \**"_MASTER_INDEX"*\* and
\**"_ENUM"*\* which are instances of the **“Index”** and
**“Nomenclautre”** respectively:

.. code:: ipython3

    from mario.tools.constants import _MASTER_INDEX,_ENUM

.. code:: ipython3

    _MASTER_INDEX["r"] # This is equal to _MASTER_INDEX.r




.. parsed-literal::

    'Region'



Using these two instances, all over the software, we encapsulated the
code 👩‍💻 and the naming convensions.

