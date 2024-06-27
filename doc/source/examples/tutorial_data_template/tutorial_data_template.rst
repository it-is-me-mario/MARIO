Creating an Empty Database, from tabular information
====================================================

This example shows how you can create a data template from tabular info,
(namely the list of regions, sectors, …).

.. code:: ipython3

    from mario import DataTemplate

At first you need to identify what kind of table you want to buid. Lets
go with a IOT table

.. code:: ipython3

    template = DataTemplate("IOT")

Now you can create a template file where you can fill your information

.. code:: ipython3

    template.get_template_excel("iot_template.xlsx")

The template looks like:

.. figure:: empty_template.PNG
   :alt: Alt text

   Alt text

Now you can fill the data,

Lets assume you want to build a table with:

**Regions:** - Italy

**Sectors:** - Primary - Secondary

**Consumption Categories:** - Final Demand

**Factors of production:** - Labor

**Satellite accounts:** - CO2

The filled template should look like:

.. figure:: filled_template.PNG
   :alt: Alt text

   Alt text

Let’s call the new filled excel file as iot_template_filled.xlsx.

Now we can read back the file!

.. code:: ipython3

    template.read_template("iot_template_filled.xlsx")

Now you can transfrom the template into a mario.Database, that can be
later filled using other mario functionalities. Or you can save the
template database into an excel file, which follows the mario excel
parser standards!

.. code:: ipython3

    database = template.to_Database()

.. code:: ipython3

    database




.. parsed-literal::

    name = unknow
    table = IOT
    scenarios = ['baseline']
    Factor of production = 1
    Satellite account = 1
    Consumption category = 1
    Region = 1
    Sector = 2



.. code:: ipython3

    database.X




.. raw:: html

    <div>
    <style scoped>
        .dataframe tbody tr th:only-of-type {
            vertical-align: middle;
        }
    
        .dataframe tbody tr th {
            vertical-align: top;
        }
    
        .dataframe thead th {
            text-align: right;
        }
    </style>
    <table border="1" class="dataframe">
      <thead>
        <tr style="text-align: right;">
          <th></th>
          <th></th>
          <th>Item</th>
          <th>production</th>
        </tr>
        <tr>
          <th>Region</th>
          <th>Level</th>
          <th>Item</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th rowspan="2" valign="top">Italy</th>
          <th rowspan="2" valign="top">Sector</th>
          <th>Primary</th>
          <td>0</td>
        </tr>
        <tr>
          <th>Secondary</th>
          <td>0</td>
        </tr>
      </tbody>
    </table>
    </div>



.. code:: ipython3

    database.to_excel("new_data.xlsx")

:download:`Link to the jupyter notebook file </../notebooks/tutorial_data_template.ipynb>`.
