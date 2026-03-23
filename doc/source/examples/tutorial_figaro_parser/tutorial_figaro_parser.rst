Figaro Parser
=============

In this example we will see how to parse locally downloaded FIGARO
Supply and Use Tables with MARIO.

As of March 23, 2026, the public CIRCABC folders for the flat files are:

- supply:
  `https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/651e74b4-ff35-445b-9427-5b3ed9ec5ca9?p=1&n=10&sort=name_ASC`
- use:
  `https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/library/093bfbed-142f-47c8-a151-d9fd3f95a507?p=1&n=10&sort=name_ASC`

Download the files manually and place the resulting ``.zip`` bundles or
extracted ``.csv`` files in one local directory. The current version of
MARIO supports parsing FIGARO Supply and Use Tables from those local
files.

.. code:: ipython3

    import mario
    
    figaro = mario.parse_figaro(
        path="database",
        table="SUT",
    )

Now you can work with the parsed database directly.

.. code:: ipython3

    figaro.GDP()




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
          <th>GDP</th>
        </tr>
        <tr>
          <th>Region</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>Argentina</th>
          <td>3.697371e+05</td>
        </tr>
        <tr>
          <th>Austria</th>
          <td>3.732273e+05</td>
        </tr>
        <tr>
          <th>Australia</th>
          <td>1.399327e+06</td>
        </tr>
        <tr>
          <th>Belgium</th>
          <td>4.639288e+05</td>
        </tr>
        <tr>
          <th>Bulgaria</th>
          <td>6.415996e+04</td>
        </tr>
        <tr>
          <th>Brazil</th>
          <td>1.261838e+06</td>
        </tr>
        <tr>
          <th>Canada</th>
          <td>1.620007e+06</td>
        </tr>
        <tr>
          <th>Switzerland</th>
          <td>6.631132e+05</td>
        </tr>
        <tr>
          <th>China</th>
          <td>1.506498e+07</td>
        </tr>
        <tr>
          <th>Cyprus</th>
          <td>2.192730e+04</td>
        </tr>
        <tr>
          <th>Czech Republic</th>
          <td>2.229991e+05</td>
        </tr>
        <tr>
          <th>Germany</th>
          <td>3.333184e+06</td>
        </tr>
        <tr>
          <th>Denmark</th>
          <td>3.032576e+05</td>
        </tr>
        <tr>
          <th>Estonia</th>
          <td>2.853506e+04</td>
        </tr>
        <tr>
          <th>Spain</th>
          <td>1.112071e+06</td>
        </tr>
        <tr>
          <th>Finland</th>
          <td>2.257000e+05</td>
        </tr>
        <tr>
          <th>Rest of the world</th>
          <td>9.869251e+06</td>
        </tr>
        <tr>
          <th>France</th>
          <td>2.295100e+06</td>
        </tr>
        <tr>
          <th>Great Britain</th>
          <td>2.479909e+06</td>
        </tr>
        <tr>
          <th>Greece</th>
          <td>1.653957e+05</td>
        </tr>
        <tr>
          <th>Croatia</th>
          <td>5.094699e+04</td>
        </tr>
        <tr>
          <th>Hungary</th>
          <td>1.364844e+05</td>
        </tr>
        <tr>
          <th>Indonesia</th>
          <td>9.760802e+05</td>
        </tr>
        <tr>
          <th>Ireland</th>
          <td>4.139783e+05</td>
        </tr>
        <tr>
          <th>India</th>
          <td>2.529599e+06</td>
        </tr>
        <tr>
          <th>Italy</th>
          <td>1.645424e+06</td>
        </tr>
        <tr>
          <th>Japan</th>
          <td>4.216607e+06</td>
        </tr>
        <tr>
          <th>South Korea</th>
          <td>1.525140e+06</td>
        </tr>
        <tr>
          <th>Lithuania</th>
          <td>5.095433e+04</td>
        </tr>
        <tr>
          <th>Luxembourg</th>
          <td>6.871203e+04</td>
        </tr>
        <tr>
          <th>Latvia</th>
          <td>3.052740e+04</td>
        </tr>
        <tr>
          <th>Malta</th>
          <td>1.405615e+04</td>
        </tr>
        <tr>
          <th>Mexico</th>
          <td>1.023775e+06</td>
        </tr>
        <tr>
          <th>Netherlands</th>
          <td>7.856965e+05</td>
        </tr>
        <tr>
          <th>Norway</th>
          <td>3.799912e+05</td>
        </tr>
        <tr>
          <th>Poland</th>
          <td>5.243482e+05</td>
        </tr>
        <tr>
          <th>Portugal</th>
          <td>1.928892e+05</td>
        </tr>
        <tr>
          <th>Romania</th>
          <td>2.290875e+05</td>
        </tr>
        <tr>
          <th>Russia</th>
          <td>1.402765e+06</td>
        </tr>
        <tr>
          <th>Saudi Arabia</th>
          <td>6.778487e+05</td>
        </tr>
        <tr>
          <th>Sweden</th>
          <td>4.964872e+05</td>
        </tr>
        <tr>
          <th>Slovenia</th>
          <td>4.745088e+04</td>
        </tr>
        <tr>
          <th>Slovakia</th>
          <td>9.250391e+04</td>
        </tr>
        <tr>
          <th>Turkey</th>
          <td>6.526885e+05</td>
        </tr>
        <tr>
          <th>United States</th>
          <td>1.925363e+07</td>
        </tr>
        <tr>
          <th>South Africa</th>
          <td>3.331388e+05</td>
        </tr>
      </tbody>
    </table>
    </div>



:download:`Link to the jupyter notebook file </../notebooks/tutorial_figaro_parser.ipynb>`.
