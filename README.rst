.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

.. image:: https://readthedocs.org/projects/mario-suite/badge/?version=latest
    :target: https://mario-suite.readthedocs.io/en/latest/index.html
    :alt: Documentation Status

.. image:: https://badge.fury.io/py/mariopy.svg
    :target: https://badge.fury.io/py/mariopy

.. image:: https://zenodo.org/badge/421900437.svg
   :target: https://doi.org/10.5281/zenodo.5879382

*******
MARIO
*******

**MARIO** stands for **Multifunctional Analysis of Regions through Input-Output**.
It is a Python package for working with Input-Output Tables (IOT) and Supply and
Use Tables (SUT). Once parsed, a table becomes a MARIO *database* that can be
inspected, computed, transformed, aggregated, shocked, and exported.

Documentation is available on `Read the Docs <https://mario-suite.readthedocs.io/en/latest/index.html>`_.


What MARIO Supports
-------------------

MARIO is designed around a practical IO workflow:

* parse a database from supported sources or load a packaged test table;
* inspect sets, scenarios, and available matrices;
* compute derived matrices and indicators on demand;
* transform, aggregate, or shock the database;
* export the results for roundtrip or downstream analysis.

The current documentation covers both standard parsers and custom database
ingestion. Supported workflows include:

* single-region and multi-region systems;
* monetary and hybrid tables where the parser supports them;
* standard sources such as EXIOBASE, EORA, EUROSTAT, FIGARO, WIOD, OECD, and more;
* custom databases from Excel, text, CSV, and pandas-based inputs;
* aggregation, SUT-to-IOT conversion, scenario analysis, and exports.


Installation
------------

The package name on PyPI is ``mariopy``, while the import name is ``mario``.

Preferably, create a clean Python environment first:

.. code-block:: bash

   conda create -n mario python=3.11
   conda activate mario

Install from PyPI:

.. code-block:: bash

   pip install mariopy

Parquet import and export support is included in the default installation.

Install from source:

.. code-block:: bash

   git clone https://github.com/it-is-me-mario/MARIO.git
   cd MARIO
   pip install -e .


Quickstart
----------

A minimal test database is bundled with MARIO:

.. code-block:: python

   import mario

   db = mario.load_test("IOT")

   print(db)
   print(db.get_index("Region"))

   db.calc_all()
   db.to_excel(path="output_folder")

For SUT workflows:

.. code-block:: python

   import mario

   sut = mario.load_test("SUT")
   iot = sut.to_iot(method="B")


Documentation Map
-----------------

The published documentation is organized into a few main sections:

* `Setup <https://mario-suite.readthedocs.io/en/latest/setup/index.html>`_ for installation and first checks;
* `Concepts <https://mario-suite.readthedocs.io/en/latest/concepts/index.html>`_ for MARIO terminology and conventions;
* `User guide <https://mario-suite.readthedocs.io/en/latest/user_guide/index.html>`_ for parsers, inspection, transformations, custom databases, and exports;
* `API reference <https://mario-suite.readthedocs.io/en/latest/reference/api_library.html>`_ for method-level documentation;
* `Publications <https://mario-suite.readthedocs.io/en/latest/resources/publications.html>`_ for the software paper and related research.


Citation
--------

Citation guidance and the up-to-date list of publications using MARIO are maintained in the
`Research section of the documentation <https://mario-suite.readthedocs.io/en/latest/resources/publications.html>`_.


License
-------

MARIO is distributed under the
`GNU General Public License v3.0 <https://www.gnu.org/licenses/gpl-3.0.en.html>`_.


Supporting institutions
-----------------------

MARIO grows across two complementary settings.

.. raw:: html

    <table>
       <tr>
          <td valign="top" width="180">
             <a href="https://www.polimi.it">
                <img src="https://www.polimi.it/_assets/4b51f00386267395f41e0940abbcd656/Images/logo.svg" alt="Politecnico di Milano" width="120" />
             </a>
          </td>
          <td valign="top">
             <strong>Politecnico di Milano</strong>. Development stays closer to the academic side: research methods, modelling choices, scientific validation, and documentation-oriented workflows.
          </td>
       </tr>
       <tr>
          <td valign="top" width="180">
             <a href="https://enextgen.it">
                <img src="https://enextgen.it/img/eNextGen_logo_transparent_black.png" alt="eNextGen" width="90" />
             </a>
          </td>
          <td valign="top">
             <strong>eNextGen</strong>. As a spin-off of Politecnico di Milano, eNextGen brings MARIO into applied settings for companies and organisations, where the same analytical core supports real decarbonisation, sustainability, and decision-support cases.
          </td>
       </tr>
    </table>
