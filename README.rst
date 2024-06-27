
.. image:: https://avatars.githubusercontent.com/u/121170888?s=400&u=4cec21e036afea744bef6886998fa302fca02ce0&v=4
   :width: 100
   :align: right

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    
.. image:: https://readthedocs.org/projects/mario-suite/badge/?version=latest
    :target: https://mario-suite.readthedocs.io/en/latest/index.html
    :alt: Documentation Status  
    
.. image:: https://badge.fury.io/py/mariopy.svg
    :target: https://badge.fury.io/py/mariopy
    

   
.. image:: https://zenodo.org/badge/421900437.svg
   :target: https://zenodo.org/badge/latestdoi/421900437

*******
MARIO
*******

Multifunctional Analysis of Regions through Input-Output.  (`Documents <https://mario-suite.readthedocs.io/en/latest/intro.html>`_)


What is it
-----------
**MARIO** is a python package for handling input-output tables and models inspired by `Pymrio  <https://github.com/IndEcol/pymrio>`_ .
MARIO aims to provide a *simple* & *intuitive* API for common IO tasks without
needing in-depth programming knowledge. MARIO supporst automatic parsing of different
structured tables such EXIOBASE, EORA, EUROSTAT, and FIGARO in different formats namely:

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
#. The Python programming language
#. A number of Python adds-on packages
#. MARIO software itself

************
Installation
************

The easiest way to make MARIO software working is to use the free
conda package manager which can install the current and future MARIO
depencies in an easy and user friendly way.

To get conda, `download and install "Anaconda Distribution" <https://www.anaconda.com/products/individual>`_ 
. Between differnet options for running python codes, we strongly suggest, `Spyder <https://www.spyder-ide.org/>`_, 
which is  a free and open source scientific environment written in Python, for Python, and designed by and for scientists,
engineers and data analysts.

You can install mario using pip or from source code. It is suggested to create a new environment by running the following command in the anaconda prompt

.. code-block:: python

   conda create -n mario python=3.10

If you create a new environment for mario, to use it, you need to activate the mario environment each time by writing
the following line in *Anaconda Prompt*

.. code-block:: python

   conda activate mario

Now you can use pip to install mario on your environment as follow:

.. code-block:: python

  pip install mariopy

You can also install from the source code!
     
**********
Quickstart
**********

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

   reformed_iot = test.to_iot(method='B')

The changes can be tracked by metadata. The history can be checked by calling:

.. code-block:: python

   reformed_iot.meta_history

The new database can be saved into excel,txt or csv file:

.. code-block:: python

   reformed_iot.to_excel(path='a folder//database.xlsx')

********
Citation
********

In case you use mario, you should use our peer reviewed publication (`Tahavori, Golinucci, Rinaldi, et al. <https://openresearchsoftware.metajnl.com/articles/10.5334/jors.473>`_) for citiation!


.. _RST pckgs:


*********
Read more
*********

Testing MARIO
-------------
The current version of Mario has achieved a test coverage of 49%. This coverage includes a comprehensive 100% assessment of the fundamental mathematical engine. 
Additional tests are currently in active development to enhance the package's reliability. 
Mario utilizes `pytest <https://docs.pytest.org/en/7.4.x/>`_  as its primary tool for conducting unit tests. For a more detailed analysis of the test coverage pertaining to mario's unit tests, 
you can execute the following command:

.. code-block:: python

   pytest --cov=mario tests/ 

.. note::
   * This project is under active development. 
   * More examples will be uploaded through time to the gallery.
   * More parsers will be added to the next version.


Publications
------------

* Assessing environmental and market implications of steel decarbonisation strategies: a hybrid input-output model for the European Union (`Rinaldi et al, Environmental Research Letters, 2024  <https://doi.org/10.1088/1748-9326/ad5bf1>`_ )
* Assessing critical materials demand in global energy transition scenarios based on the Dynamic Extraction and Recycling Input-Output framework (DYNERIO) (`Rinaldi et al, Resources Conservation adn Recycling, 2023  <https://www.sciencedirect.com/science/article/pii/S092134492300037X?via%3Dihub>`_ )
* Three different directions in which the European Union could replace Russian natural gas (`Nikas et al, Energy, 2024 <https://www.sciencedirect.com/science/article/pii/S0360544224000252?via%3Dihub>`_ )
* Investigating the economic and environmental impacts of a technological shift towards hydrogen-based solutions for steel manufacture in high-renewable electricity mix scenarios for Italy (`Marco Conte et al, IOP Conf. Ser.: Earth Environ. Sci., 2022 <https://iopscience.iop.org/article/10.1088/1755-1315/1106/1/012008>`_)


Support Materials
-----------------

* `Input-Output analysis and modelling with MARIO Open University Course  <https://www.open.edu/openlearncreate/course/view.php?id=11723>`_ 
  


License
-------

.. image:: https://www.gnu.org/graphics/gplv3-or-later.png
    :target: https://www.gnu.org/licenses/gpl-3.0.en.html


This work is licensed under a `GNU GENERAL PUBLIC LICENSE <https://www.gnu.org/licenses/gpl-3.0.en.html>`_


Supporting Institutions
-----------------------

.. image:: https://github.com/it-is-me-mario/MARIO/blob/pre-releasev0.3.0/doc/source/_static/images/enextgen.png?raw=true
   :width: 120
   :align: left
   :target: https://www.enextgen.it/

.. image:: https://raw.githubusercontent.com/it-is-me-mario/MARIO/7cc701e2e0f23d2cdc0f01c05d6c6e33b30b682e/doc/source/_static/images/polimi.svg
   :width: 200
   :align: left
   :target: https://polimi.it/
   
