

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    
.. image:: https://readthedocs.org/projects/mario-suite/badge/?version=latest
    :target: https://mario-suite.readthedocs.io/en/latest/index.html
    :alt: Documentation Status  
    
.. image:: https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png
    :target: https://creativecommons.org/licenses/by-nc-sa/4.0/ 
    
.. image:: https://github.com/SESAM-Polimi/MARIO/blob/main/doc/source/_static/images/polimi.svg?raw=true
   :width: 200
   :align: right

*******
MARIO
*******
Multifunctional Analysis of Regions through Input-Output 


What is it
-----------
**MARIO** is a python package for handling input-output tables and models.
MARIO aims to provide a *simple* & *intuitive* API for common IO tasks without
needing in-depth programming knowledge. MARIO supporst automatic parsing of different
structured tables such EXIOBASE, EORA, EUROSTAT in different formats namely:

* Single region 
* Multi region
* Hybrid tables
* Monetary tables
* Input-Output tables
* Supply-Use tables

When databases are not structured, MARIO supports parsing data from xlsx, csv, txt files
or pandas.DataFrames.

More than parsing data, MARIO includes some basic functionalities:

* Aggregation of databases
* SUT to IOT transformation
* Modifying database in terms of adding:
   * New sectors, activities or commodities to the database
   * Adding new extensions to the satellite account
* Scneario and shock analysis
* Backward and forward linkages analysis
* Extracting single region database from multi region databases
* Balance test 
* Productivity test
* Exporting the databases into different formats for scenarios analyzed
* Interactive visualization routines


Requirements
------------

MARIO has been tested on macOS and Windows.

To run MARIO, a couple of things are needed:

#. Being in love with Input-Output :-)
#. The Python programming language, version 3.7 or higher
#. A number of Python add-on modules (list)
#. For some functionalities a solver may needed (optional)
#. MARIO software itself

Recommended installation method
-------------------------------

The easiest way to make MARIO software working is to use the free
conda package manager which can install the current and future MARIO
depencies in an easy and user friendly way.

To get conda, `download and install "Anaconda Distribution" <https://www.anaconda.com/products/individual>`_ 
. Between differnet options for running python codes, we strongly suggest, `Spyder <https://www.spyder-ide.org/>`_, 
which is  a free and open source scientific environment written in Python, for Python, and designed by and for scientists,
engineers and data analysts.

When Anaconda and Spyder are installed, you have two options to install mario:

*Option.1: Creating mario environment*

create a new environment called "mario" with all the necessary modules,
by running the following command in a terminal or command-line window

.. code-block:: python

   conda create -c conda-forge -n mario mario

If you create a new environment for mario, to use it, you need to activate the mario environment each time by writing
the following line in *Anaconda Prompt*

.. code-block:: python

   conda activate mario

*Option.2: Installing mario package on base environment*

If you would prefer not to create new environment, you can install mario in your base environment in three different ways:

#. pip

   .. code-block:: python

      pip install mario

#. conda

   .. code-block:: python

      conda install -c conda-forge mario

#. installing from source code
           

Quickstart
----------
A simple test for Input-Output Table (IOT) and Supply-Use Table (SUT) is included in mario.

To use the IOT test, call

.. code-block:: python

   import mario
   test_iot = mario.load_test('IOT')

and to use the SUT test, call

.. code-block:: python

   test_sut = mario.load_test('SUT')

To see the configurations of the data, you can print them:

.. code-block:: python

   print(test_iot)
   print(test_sut)

To see specific sets of the tables like regions or value added,
get_index function can be used:

.. code-block:: python

   print(test_iot.get_index('Region'))
   print(test_sut.get_index('Factor of production'))

To visualize some data, various plot functions can be used:

.. code-block:: python

   test_iot.plot_matrix(....)

Specific modifications on the database can be done, such as
SUT to IOT transformation:

.. code-block:: python

   reformed_iot = test.sut_to_iot(method='B')

The changes can be tracked by metadata. The history can be checked by calling:

.. code-block:: python

   reformed_iot.meta_history

The new database can be saved into excel,txt or csv file:

.. code-block:: python

   reformed_iot.to_excel(path='a folder//database.xlsx')


Python module requirements
--------------------------
Some of the key packages the mario relies on are:

* `Pandas  <https://pandas.pydata.org/>`_ 
* `Numpy  <https://numpy.org/>`_ 
* `Plotly  <https://plotly.com/>`_ 
* `Tabulate  <https://pypi.org/project/tabulate/>`_ 
* `Cvxpy  <https://pypi.org/project/tabulate/>`_ (Optional in this version)



.. note::
   * This project is under active development. 
   * More examples will be uploaded through time to the gellery.
   * More parsers will be added to the next version.
   * The next version will cover some optimization models within the IO framework


License
-------

.. image:: https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png
    :target: https://creativecommons.org/licenses/by-nc-sa/4.0/


This work is licensed under a `Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) <https://creativecommons.org/licenses/by-nc-sa/4.0/>`_

