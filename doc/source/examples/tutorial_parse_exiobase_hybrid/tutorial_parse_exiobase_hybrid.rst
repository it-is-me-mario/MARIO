Parsing Exiobase v3.3.18 (supply-use hybrid-units)
==================================================

This tutorial shows how to parse the Exiobase v3.3.18 database in
supply-use (SUT) format.

Downloading the database
------------------------

The database is available at the following Zenodo repository:
https://zenodo.org/doi/10.5281/zenodo.7244918. You can manually download
the repository or use the automatic download function available in
MARIO, as shown here below.

.. code:: ipython3

    import mario  # Import MARIO
    
    exiobase_path = 'Exiobase v3.3.18'  # Define the desired path to the folder where Exiobase should be downloaded
    mario.download_hybrid_exiobase(exiobase_path)  # Download the hybrid Exiobase into the desired folder

Parsing the downloaded database
-------------------------------

Once the Exiobase database is stored in a given path (‘exiobase_path’ in
this example), it is possible to parse it into a mario.Database object.
The ‘parse_exiobase’ function is suitable to parse any version of
Exiobase, providing the type of table (‘SUT’ or ‘IOT), the type of unit
(’Hybrid’ or ‘Monetary’) and the directory where the database is stored.

The ‘extensions’ attribute allows to select which environmental
transactions should be parsed. Options must be provided in a list and
are: ‘resource’, ‘Land’, ‘Emiss’, ‘Emis_unreg_w’, ‘waste_sup’,
‘waste_use’, ‘pack_sup_waste’, ‘pack_use_waste’, ‘mach_sup_waste’,
‘mach_use_waste’, ‘stock_addition’, ‘crop_res’, ‘Unreg_w’

.. code:: ipython3

    exiobase = mario.parse_exiobase(
        table = 'SUT',
        unit = 'Hybrid',
        path = exiobase_path,
        extensions = 'all',   # Include all satellite accounts. By default is "" (None)
    )

Exploring the database
----------------------

Once the database is parsed, MARIO offers useful methods to explore and
navigate the database.

Checking units of measure
~~~~~~~~~~~~~~~~~~~~~~~~~

In a hybrid-units database it may be interesting to check the unit of
measure of the database’s sets.

.. code:: ipython3

    exiobase.units['Commodity'] 




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
          <th>unit</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>Paddy rice</th>
          <td>tonnes</td>
        </tr>
        <tr>
          <th>Wheat</th>
          <td>tonnes</td>
        </tr>
        <tr>
          <th>Cereal grains nec</th>
          <td>tonnes</td>
        </tr>
        <tr>
          <th>Vegetables; fruit; nuts</th>
          <td>tonnes</td>
        </tr>
        <tr>
          <th>Oil seeds</th>
          <td>tonnes</td>
        </tr>
        <tr>
          <th>...</th>
          <td>...</td>
        </tr>
        <tr>
          <th>Membership organisation services n.e.c. (91)</th>
          <td>Meuro</td>
        </tr>
        <tr>
          <th>Recreational; cultural and sporting services (92)</th>
          <td>Meuro</td>
        </tr>
        <tr>
          <th>Other services (93)</th>
          <td>Meuro</td>
        </tr>
        <tr>
          <th>Private households with employed persons (95)</th>
          <td>Meuro</td>
        </tr>
        <tr>
          <th>Extra-territorial organizations and bodies</th>
          <td>Meuro</td>
        </tr>
      </tbody>
    </table>
    <p>200 rows × 1 columns</p>
    </div>



.. code:: ipython3

    exiobase.units['Satellite account'] 




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
          <th>unit</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>Aquatic plants (resource)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>Bauxite and aluminium ores (resource)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>Building stones (resource)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>Chemical and fertilizer minerals (resource)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>Clays and kaolin (resource)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>...</th>
          <td>...</td>
        </tr>
        <tr>
          <th>Construction materials and mining waste (excl. unused mining material) (Unreg_w)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>Oils and hazardous materials (Unreg_w)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>Sewage (Unreg_w)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>Mining waste (Unreg_w)</th>
          <td>tonne</td>
        </tr>
        <tr>
          <th>Unused waste (Unreg_w)</th>
          <td>tonne</td>
        </tr>
      </tbody>
    </table>
    <p>336 rows × 1 columns</p>
    </div>



Note that the “Activity” set, in hybrid databases, do not have unit of
measure since each activity may supply heterogeneus commodities as
output

.. code:: ipython3

    exiobase.units['Activity']




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
          <th>unit</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>Cultivation of paddy rice</th>
          <td>None</td>
        </tr>
        <tr>
          <th>Cultivation of wheat</th>
          <td>None</td>
        </tr>
        <tr>
          <th>Cultivation of cereal grains nec</th>
          <td>None</td>
        </tr>
        <tr>
          <th>Cultivation of vegetables, fruit, nuts</th>
          <td>None</td>
        </tr>
        <tr>
          <th>Cultivation of oil seeds</th>
          <td>None</td>
        </tr>
        <tr>
          <th>...</th>
          <td>...</td>
        </tr>
        <tr>
          <th>Activities of membership organisation n.e.c. (91)</th>
          <td>None</td>
        </tr>
        <tr>
          <th>Recreational, cultural and sporting activities (92)</th>
          <td>None</td>
        </tr>
        <tr>
          <th>Other service activities (93)</th>
          <td>None</td>
        </tr>
        <tr>
          <th>Private households with employed persons (95)</th>
          <td>None</td>
        </tr>
        <tr>
          <th>Extra-territorial organizations and bodies</th>
          <td>None</td>
        </tr>
      </tbody>
    </table>
    <p>164 rows × 1 columns</p>
    </div>



:download:`Link to the jupyter notebook file </../notebooks/tutorial_parse_exiobase_hybrid.ipynb>`.
