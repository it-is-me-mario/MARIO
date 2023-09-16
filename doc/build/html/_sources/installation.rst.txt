
Download and installation
=================================

Requirements
------------

MARIO has been tested on macOS and Windows.

To run MARIO, a couple of things are needed:

#. Being in love with Input-Output :-)
#. The Python programming language, version 3.7 or higher
#. A number of Python adds-on packages
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

You can install mario using pip or from source code. It is suggested to create a new environment by running the following command in the anaconda prompt

.. code-block:: python

   conda create -n mario python=3.8

If you create a new environment for mario, to use it, you need to activate the mario environment each time by writing
the following line in *Anaconda Prompt*

.. code-block:: python

   conda activate mario

Now you can use pip to install mario on your environment as follow:

.. code-block:: python

  pip install mariopy

You can also install from the source code!


IMPORTANT NOTE: Pandas version 2.0 has recently been released, presenting major changes conflicting with MARIO. To overcome these issue, just install a previous version of Pandas as follows:

.. code-block:: python

  pip install pandas==1.3.5

           