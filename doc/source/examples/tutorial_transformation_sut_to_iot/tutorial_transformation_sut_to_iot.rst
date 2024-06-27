Transforming a SUT into an IOT table
====================================

This tutorial shows how to transform a SUT table into an IOT table

Background
----------

IOT tables are obtained by transforming SUTs according to a
transformation model. The “Eurostat Manual of Supply, Use and
Input-Output Tables” was our reference in scripting the transfromation
methods.

Link to the manual here:
https://ec.europa.eu/eurostat/web/products-manuals-and-guidelines/-/ks-ra-07-013

Methods
-------

Four methods are exploitable to transform a SUT into an IOT. Each of
them will lead to a specific type of IOT and embeds intrisic
assumptions.

-  Method A. Commodity-by-commodity IOT based on the product-based
   technology assumption (possible negative values)
-  Method B. Commodity-by-commodity IOT based on the industry-based
   technology assumption
-  Method C. Activity-by-activity IOT based on fixed industry sales
   structure assumption (possible negative values)
-  Method D. Activity-by-activity IOT based on fixed product sales
   structure assumption

Perform the transformation
--------------------------

First, we need to import a SUT table into MARIO. To do so, we can load
the test SUT using the “load_test” method.

.. code:: ipython3

    import mario
    
    test_SUT = mario.load_test(table='SUT')


.. parsed-literal::

    cvxpy module is not installed in your system. This will raise problems in some of the abilities of MARIO


It is possible to show the properties of the table by calling its name.
It is a SUT table with 6 activities and 6 commodities

.. code:: ipython3

    test_SUT




.. parsed-literal::

    name = SUT test
    table = SUT
    scenarios = ['baseline']
    Activity = 6
    Commodity = 6
    Factor of production = 3
    Satellite account = 1
    Consumption category = 1
    Region = 2



To perform the transformation, it is enought to call the “to_iot”
method, passing one of the four transformation methods listed above
(‘A’, ‘B’, ‘C’ or ‘D’)

.. code:: ipython3

    test_SUT.to_iot(method='A') 


.. parsed-literal::

    baseline deleted from the database


After the transformation, the table transformed to an IOT of 6 sectors

.. code:: ipython3

    test_SUT




.. parsed-literal::

    name = SUT test
    table = IOT
    scenarios = ['baseline']
    Factor of production = 3
    Satellite account = 1
    Consumption category = 1
    Region = 2
    Sector = 6



:download:`Link to the jupyter notebook file </../notebooks/tutorial_transformation_sut_to_iot.ipynb>`.
