
Download and installation
=================================

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

.. code-block:: bash

   conda create -c conda-forge -n mario mario

If you create a new environment for mario, to use it, you need to activate the mario environment each time by writing
the following line in *Anaconda Prompt*

.. code-block:: bash

   conda activate mario

*Option.2: Installing mario package on base environment*

If you would prefer not to create new environment, you can install mario in your base environment in three different ways:

#. pip

   .. code-block:: bash

      pip install mario

#. conda

   .. code-block:: bash

      conda install -c conda-forge mario

#. installing from source code
           
