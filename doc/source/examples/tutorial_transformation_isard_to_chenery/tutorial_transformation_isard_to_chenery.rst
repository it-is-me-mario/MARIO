Transforming a SUT table from Isard to Chenery-Moses model
==========================================================

This tutorial shows how to switch a SUT table from Isard to
Chenery-Moses

Background
----------

In the case of a multi-regional SUT, the Isard and Chenery-Moses are two
possible models that differentiate mainly in how traded commodity flows
are accounted.

While an Isard model shows how each commodity is imported by or exported
towards each foreign industrial activity in the USE table, the
Chenery-Moses model assumes a fixed shares of imports/exports for each
commodity independently on activity-specific consumption patterns.

In practical terms, the regional extradiagonal blocks of the SUPPLY
matrix (S) of the Isard model are null, while the regional extradiagonal
blocks of the USE matrix (U) are null in the Chenery-Moses model, as
shown in the following example

.. figure:: example.jpg
   :alt: Alt text

   Alt text

Perform the transformation
--------------------------

From version 0.3.0 onwards, MARIO has a built-in method to perform the
transormation from Isard to Chenery-Moses. Note the opposite cannot be
done since the Chenery-Moses model loses information regarding the
activity-specific consumption patterns of each imported commodity in a
given region.

First, we need to import a SUT table into MARIO. To do so, we can load
the test SUT using the “load_test” method.

.. code:: ipython3

    import mario
    
    test_SUT = mario.load_test(table='SUT')

It is possible to check if the table is in Isard or Chenery-Moses format

.. code:: ipython3

    test_SUT.is_isard()




.. parsed-literal::

    True



.. code:: ipython3

    test_SUT.is_chenerymoses()




.. parsed-literal::

    False



It is also possible to check the ‘S’ or ‘U’ matrices to check which of
the two models shown in the Figure above the parsed table resembles

.. code:: ipython3

    test_SUT.S




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
          <th>Region</th>
          <th colspan="6" halign="left">Italy</th>
          <th colspan="6" halign="left">RoW</th>
        </tr>
        <tr>
          <th></th>
          <th></th>
          <th>Level</th>
          <th colspan="6" halign="left">Commodity</th>
          <th colspan="6" halign="left">Commodity</th>
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
          <th>Region</th>
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
          <th rowspan="6" valign="top">Activity</th>
          <th>Agriculture</th>
          <td>6.414041e+10</td>
          <td>0.000000e+00</td>
          <td>8.476744e+08</td>
          <td>0.000000e+00</td>
          <td>1.268921e+09</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>0.000000e+00</td>
          <td>2.052262e+11</td>
          <td>8.890008e+06</td>
          <td>0.000000e+00</td>
          <td>5.602012e+09</td>
          <td>1.517120e+07</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>0.000000e+00</td>
          <td>1.581203e+09</td>
          <td>1.161939e+12</td>
          <td>2.616691e+09</td>
          <td>2.876029e+10</td>
          <td>7.861768e+08</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>0.000000e+00</td>
          <td>1.745479e+07</td>
          <td>1.271582e+09</td>
          <td>9.838438e+09</td>
          <td>2.453322e+09</td>
          <td>1.185310e+07</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>2.456823e+09</td>
          <td>5.639194e+09</td>
          <td>6.655796e+10</td>
          <td>0.000000e+00</td>
          <td>1.837665e+12</td>
          <td>2.160879e+10</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>0.000000e+00</td>
          <td>1.567515e+09</td>
          <td>1.752820e+09</td>
          <td>0.000000e+00</td>
          <td>9.178747e+09</td>
          <td>2.613827e+11</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th rowspan="6" valign="top">RoW</th>
          <th rowspan="6" valign="top">Activity</th>
          <th>Agriculture</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>5.969584e+12</td>
          <td>1.117362e+10</td>
          <td>2.223620e+11</td>
          <td>4.305393e+09</td>
          <td>7.087351e+10</td>
          <td>3.325944e+09</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>3.479551e+08</td>
          <td>1.256801e+13</td>
          <td>3.825648e+10</td>
          <td>3.405690e+09</td>
          <td>5.886374e+10</td>
          <td>1.964438e+09</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>1.079269e+10</td>
          <td>1.698351e+10</td>
          <td>5.259731e+13</td>
          <td>2.664999e+10</td>
          <td>4.536109e+11</td>
          <td>1.015322e+10</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>5.145630e+08</td>
          <td>1.285635e+10</td>
          <td>1.869789e+11</td>
          <td>3.418478e+12</td>
          <td>6.750145e+10</td>
          <td>4.215670e+09</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>8.931201e+09</td>
          <td>1.683406e+11</td>
          <td>4.937088e+11</td>
          <td>1.401294e+10</td>
          <td>8.244055e+13</td>
          <td>6.142484e+10</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>4.692799e+08</td>
          <td>1.974234e+10</td>
          <td>2.833988e+10</td>
          <td>3.321611e+09</td>
          <td>1.741595e+11</td>
          <td>8.411313e+12</td>
        </tr>
      </tbody>
    </table>
    </div>



.. code:: ipython3

    test_SUT.U




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
          <th>Region</th>
          <th colspan="6" halign="left">Italy</th>
          <th colspan="6" halign="left">RoW</th>
        </tr>
        <tr>
          <th></th>
          <th></th>
          <th>Level</th>
          <th colspan="6" halign="left">Activity</th>
          <th colspan="6" halign="left">Activity</th>
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
          <th>Region</th>
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
          <th rowspan="6" valign="top">Commodity</th>
          <th>Agriculture</th>
          <td>2.613081e+09</td>
          <td>1.359344e+08</td>
          <td>2.540695e+10</td>
          <td>1.208340e+05</td>
          <td>3.196519e+09</td>
          <td>6.463362e+07</td>
          <td>5.040894e+08</td>
          <td>3.136392e+07</td>
          <td>1.499590e+09</td>
          <td>4.977875e+06</td>
          <td>3.137667e+08</td>
          <td>4.489841e+06</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>8.234773e+08</td>
          <td>4.263157e+10</td>
          <td>4.051235e+09</td>
          <td>6.623822e+07</td>
          <td>1.511442e+10</td>
          <td>4.531470e+08</td>
          <td>3.427462e+06</td>
          <td>2.349299e+08</td>
          <td>2.980236e+07</td>
          <td>5.437685e+06</td>
          <td>1.925330e+08</td>
          <td>1.005801e+07</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>8.971053e+09</td>
          <td>5.105912e+10</td>
          <td>2.892146e+11</td>
          <td>6.912651e+08</td>
          <td>9.336397e+10</td>
          <td>1.438189e+10</td>
          <td>3.772554e+09</td>
          <td>2.488904e+10</td>
          <td>1.381512e+11</td>
          <td>3.299075e+09</td>
          <td>3.641855e+10</td>
          <td>6.963659e+09</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>1.747090e+07</td>
          <td>1.737138e+09</td>
          <td>5.761244e+09</td>
          <td>8.144308e+08</td>
          <td>1.826550e+09</td>
          <td>9.785732e+06</td>
          <td>2.190015e+07</td>
          <td>2.286785e+08</td>
          <td>1.458622e+09</td>
          <td>8.452581e+07</td>
          <td>9.789548e+07</td>
          <td>5.874072e+06</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>8.610745e+09</td>
          <td>2.599288e+10</td>
          <td>2.440182e+11</td>
          <td>3.419365e+09</td>
          <td>4.507979e+11</td>
          <td>4.406078e+10</td>
          <td>4.470008e+08</td>
          <td>1.903031e+09</td>
          <td>8.410499e+09</td>
          <td>5.091172e+08</td>
          <td>2.542143e+10</td>
          <td>2.150222e+09</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>1.832589e+09</td>
          <td>3.009282e+09</td>
          <td>6.183923e+10</td>
          <td>1.519988e+09</td>
          <td>6.788441e+10</td>
          <td>7.545770e+10</td>
          <td>1.243929e+08</td>
          <td>3.185796e+08</td>
          <td>2.116153e+09</td>
          <td>1.214371e+08</td>
          <td>2.758496e+09</td>
          <td>2.895771e+09</td>
        </tr>
        <tr>
          <th rowspan="6" valign="top">RoW</th>
          <th rowspan="6" valign="top">Commodity</th>
          <th>Agriculture</th>
          <td>1.928423e+09</td>
          <td>2.035605e+08</td>
          <td>4.978912e+09</td>
          <td>2.809890e+05</td>
          <td>1.183583e+09</td>
          <td>1.357204e+07</td>
          <td>6.741444e+11</td>
          <td>7.024518e+10</td>
          <td>2.809955e+12</td>
          <td>9.928531e+09</td>
          <td>4.367480e+11</td>
          <td>7.074663e+10</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>3.291576e+06</td>
          <td>7.186756e+08</td>
          <td>3.417940e+07</td>
          <td>7.828606e+05</td>
          <td>9.880545e+07</td>
          <td>5.576916e+06</td>
          <td>2.234087e+10</td>
          <td>8.923503e+11</td>
          <td>1.381588e+11</td>
          <td>4.529305e+10</td>
          <td>9.396325e+11</td>
          <td>4.069810e+10</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>1.310490e+09</td>
          <td>5.517221e+09</td>
          <td>1.391664e+11</td>
          <td>1.830207e+08</td>
          <td>2.300338e+10</td>
          <td>2.655409e+09</td>
          <td>7.645405e+11</td>
          <td>3.996884e+12</td>
          <td>2.305268e+13</td>
          <td>3.743792e+11</td>
          <td>5.655872e+12</td>
          <td>9.891854e+11</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>2.160979e+07</td>
          <td>1.109156e+08</td>
          <td>4.427849e+10</td>
          <td>3.946190e+08</td>
          <td>8.211453e+09</td>
          <td>1.007717e+08</td>
          <td>7.696685e+09</td>
          <td>1.255249e+11</td>
          <td>2.468205e+12</td>
          <td>2.247546e+11</td>
          <td>2.181119e+11</td>
          <td>7.827661e+09</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>7.253485e+08</td>
          <td>2.201842e+09</td>
          <td>2.048522e+10</td>
          <td>3.076060e+08</td>
          <td>3.749654e+10</td>
          <td>3.386092e+09</td>
          <td>9.795698e+11</td>
          <td>1.902371e+12</td>
          <td>8.172955e+12</td>
          <td>5.826631e+11</td>
          <td>2.173693e+13</td>
          <td>1.397942e+12</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>8.591924e+07</td>
          <td>1.201545e+08</td>
          <td>4.389120e+09</td>
          <td>1.170603e+08</td>
          <td>7.436268e+09</td>
          <td>6.770691e+09</td>
          <td>1.261775e+11</td>
          <td>5.322208e+11</td>
          <td>1.346195e+12</td>
          <td>1.353592e+11</td>
          <td>1.882357e+12</td>
          <td>1.428436e+12</td>
        </tr>
      </tbody>
    </table>
    </div>



The method to perform the transofrmation is called “to_chenery_moses”.

.. code:: ipython3

    test_SUT.to_chenery_moses()


.. parsed-literal::

    Database: to calculate s following matrices are need.
    ['z'].Trying to calculate dependencies.


Again, it is possible to check the model of the table after the
transformation or to show the S and U matrices as done previosly

.. code:: ipython3

    test_SUT.is_isard()




.. parsed-literal::

    False



.. code:: ipython3

    test_SUT.is_chenerymoses()




.. parsed-literal::

    True



.. code:: ipython3

    test_SUT.S




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
          <th>Region</th>
          <th colspan="6" halign="left">Italy</th>
          <th colspan="6" halign="left">RoW</th>
        </tr>
        <tr>
          <th></th>
          <th></th>
          <th>Level</th>
          <th colspan="6" halign="left">Commodity</th>
          <th colspan="6" halign="left">Commodity</th>
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
          <th>Region</th>
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
          <th rowspan="6" valign="top">Activity</th>
          <th>Agriculture</th>
          <td>5.709680e+10</td>
          <td>0.000000e+00</td>
          <td>5.329008e+08</td>
          <td>0.000000e+00</td>
          <td>1.216672e+09</td>
          <td>0.000000e+00</td>
          <td>7.043617e+09</td>
          <td>0.000000e+00</td>
          <td>3.147736e+08</td>
          <td>0.000000e+00</td>
          <td>5.224878e+07</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>0.000000e+00</td>
          <td>2.043568e+11</td>
          <td>5.588811e+06</td>
          <td>0.000000e+00</td>
          <td>5.371345e+09</td>
          <td>1.444179e+07</td>
          <td>0.000000e+00</td>
          <td>8.694767e+08</td>
          <td>3.301197e+06</td>
          <td>0.000000e+00</td>
          <td>2.306671e+08</td>
          <td>7.294106e+05</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>0.000000e+00</td>
          <td>1.574504e+09</td>
          <td>7.304668e+11</td>
          <td>2.201047e+09</td>
          <td>2.757607e+10</td>
          <td>7.483785e+08</td>
          <td>0.000000e+00</td>
          <td>6.699043e+06</td>
          <td>4.314718e+11</td>
          <td>4.156436e+08</td>
          <td>1.184227e+09</td>
          <td>3.779831e+07</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>0.000000e+00</td>
          <td>1.738084e+07</td>
          <td>7.993953e+08</td>
          <td>8.275669e+09</td>
          <td>2.352305e+09</td>
          <td>1.128322e+07</td>
          <td>0.000000e+00</td>
          <td>7.395026e+04</td>
          <td>4.721865e+08</td>
          <td>1.562769e+09</td>
          <td>1.010174e+08</td>
          <td>5.698811e+05</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>2.187026e+09</td>
          <td>5.615303e+09</td>
          <td>4.184247e+10</td>
          <td>0.000000e+00</td>
          <td>1.761998e+12</td>
          <td>2.056987e+10</td>
          <td>2.697975e+08</td>
          <td>2.389143e+07</td>
          <td>2.471549e+10</td>
          <td>0.000000e+00</td>
          <td>7.566728e+10</td>
          <td>1.038921e+09</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>0.000000e+00</td>
          <td>1.560874e+09</td>
          <td>1.101931e+09</td>
          <td>0.000000e+00</td>
          <td>8.800805e+09</td>
          <td>2.488158e+11</td>
          <td>0.000000e+00</td>
          <td>6.641049e+06</td>
          <td>6.508884e+08</td>
          <td>0.000000e+00</td>
          <td>3.779420e+08</td>
          <td>1.256693e+10</td>
        </tr>
        <tr>
          <th rowspan="6" valign="top">RoW</th>
          <th rowspan="6" valign="top">Activity</th>
          <th>Agriculture</th>
          <td>1.883560e+10</td>
          <td>1.483250e+06</td>
          <td>1.233132e+09</td>
          <td>6.596405e+07</td>
          <td>8.987178e+07</td>
          <td>1.069405e+07</td>
          <td>5.950748e+12</td>
          <td>1.117214e+10</td>
          <td>2.211289e+11</td>
          <td>4.239429e+09</td>
          <td>7.078364e+10</td>
          <td>3.315250e+09</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>1.097890e+06</td>
          <td>1.668350e+09</td>
          <td>2.121553e+08</td>
          <td>5.217947e+07</td>
          <td>7.464268e+07</td>
          <td>6.316343e+06</td>
          <td>3.468572e+08</td>
          <td>1.256635e+13</td>
          <td>3.804432e+10</td>
          <td>3.353511e+09</td>
          <td>5.878910e+10</td>
          <td>1.958122e+09</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>3.405376e+07</td>
          <td>2.254489e+06</td>
          <td>2.916839e+11</td>
          <td>4.083114e+08</td>
          <td>5.752053e+08</td>
          <td>3.264608e+07</td>
          <td>1.075863e+10</td>
          <td>1.698126e+10</td>
          <td>5.230563e+13</td>
          <td>2.624168e+10</td>
          <td>4.530357e+11</td>
          <td>1.012057e+10</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>1.623581e+06</td>
          <td>1.706626e+06</td>
          <td>1.036911e+09</td>
          <td>5.237539e+10</td>
          <td>8.559581e+07</td>
          <td>1.355482e+07</td>
          <td>5.129395e+08</td>
          <td>1.285465e+10</td>
          <td>1.859420e+11</td>
          <td>3.366102e+12</td>
          <td>6.741586e+10</td>
          <td>4.202115e+09</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>2.818028e+07</td>
          <td>2.234649e+07</td>
          <td>2.737914e+09</td>
          <td>2.146958e+08</td>
          <td>1.045395e+11</td>
          <td>1.975019e+08</td>
          <td>8.903021e+09</td>
          <td>1.683182e+11</td>
          <td>4.909709e+11</td>
          <td>1.379824e+10</td>
          <td>8.233601e+13</td>
          <td>6.122733e+10</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>1.480701e+06</td>
          <td>2.620712e+06</td>
          <td>1.571618e+08</td>
          <td>5.089126e+07</td>
          <td>2.208445e+08</td>
          <td>2.704525e+10</td>
          <td>4.677992e+08</td>
          <td>1.973972e+10</td>
          <td>2.818272e+10</td>
          <td>3.270719e+09</td>
          <td>1.739387e+11</td>
          <td>8.384268e+12</td>
        </tr>
      </tbody>
    </table>
    </div>



.. code:: ipython3

    test_SUT.U




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
          <th>Region</th>
          <th colspan="6" halign="left">Italy</th>
          <th colspan="6" halign="left">RoW</th>
        </tr>
        <tr>
          <th></th>
          <th></th>
          <th>Level</th>
          <th colspan="6" halign="left">Activity</th>
          <th colspan="6" halign="left">Activity</th>
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
          <th>Region</th>
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
          <th rowspan="6" valign="top">Commodity</th>
          <th>Agriculture</th>
          <td>4.541504e+09</td>
          <td>3.394949e+08</td>
          <td>3.038586e+10</td>
          <td>4.018230e+05</td>
          <td>4.380102e+09</td>
          <td>7.820566e+07</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>8.267689e+08</td>
          <td>4.335025e+10</td>
          <td>4.085415e+09</td>
          <td>6.702108e+07</td>
          <td>1.521323e+10</td>
          <td>4.587239e+08</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>1.028154e+10</td>
          <td>5.657634e+10</td>
          <td>4.283810e+11</td>
          <td>8.742859e+08</td>
          <td>1.163674e+11</td>
          <td>1.703730e+10</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>3.908070e+07</td>
          <td>1.848054e+09</td>
          <td>5.003973e+10</td>
          <td>1.209050e+09</td>
          <td>1.003800e+10</td>
          <td>1.105574e+08</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>9.336094e+09</td>
          <td>2.819472e+10</td>
          <td>2.645034e+11</td>
          <td>3.726971e+09</td>
          <td>4.882944e+11</td>
          <td>4.744687e+10</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>1.918508e+09</td>
          <td>3.129436e+09</td>
          <td>6.622835e+10</td>
          <td>1.637049e+09</td>
          <td>7.532068e+10</td>
          <td>8.222839e+10</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
        </tr>
        <tr>
          <th rowspan="6" valign="top">RoW</th>
          <th rowspan="6" valign="top">Commodity</th>
          <th>Agriculture</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>6.746485e+11</td>
          <td>7.027655e+10</td>
          <td>2.811455e+12</td>
          <td>9.933509e+09</td>
          <td>4.370617e+11</td>
          <td>7.075112e+10</td>
        </tr>
        <tr>
          <th>Construction</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>2.234430e+10</td>
          <td>8.925852e+11</td>
          <td>1.381886e+11</td>
          <td>4.529848e+10</td>
          <td>9.398250e+11</td>
          <td>4.070816e+10</td>
        </tr>
        <tr>
          <th>Manufacturing</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>7.683131e+11</td>
          <td>4.021773e+12</td>
          <td>2.319083e+13</td>
          <td>3.776783e+11</td>
          <td>5.692290e+12</td>
          <td>9.961491e+11</td>
        </tr>
        <tr>
          <th>Mining</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>7.718585e+09</td>
          <td>1.257536e+11</td>
          <td>2.469663e+12</td>
          <td>2.248392e+11</td>
          <td>2.182098e+11</td>
          <td>7.833536e+09</td>
        </tr>
        <tr>
          <th>Services</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>9.800168e+11</td>
          <td>1.904274e+12</td>
          <td>8.181366e+12</td>
          <td>5.831722e+11</td>
          <td>2.176235e+13</td>
          <td>1.400092e+12</td>
        </tr>
        <tr>
          <th>Transport</th>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>0.000000e+00</td>
          <td>1.263019e+11</td>
          <td>5.325394e+11</td>
          <td>1.348311e+12</td>
          <td>1.354806e+11</td>
          <td>1.885116e+12</td>
          <td>1.431332e+12</td>
        </tr>
      </tbody>
    </table>
    </div>



:download:`Link to the jupyter notebook file </../notebooks/tutorial_transformation_isard_to_chenery.ipynb>`.
