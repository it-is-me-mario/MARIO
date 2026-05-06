MARIO Documentation
===================

**MARIO** (*Multifunctional Analysis of Regions through Input-Output*) is a
Python package for handling Input-Output Tables (IOT) and Supply and Use
Tables (SUT). It is designed to make common IO workflows accessible without
requiring deep programming expertise, while still exposing the full flexibility
needed for research and applied analysis.

.. warning::

   This documentation currently tracks the code in the ``main`` branch.
   The corresponding PyPI release is not available yet and is expected by
   June 2026.

   If you want to start using this version before the PyPI release, follow
   the temporary installation steps in :doc:`setup/installation`.

What MARIO supports
-------------------

MARIO can parse tables from many well-known sources out of the box, including
EXIOBASE, EORA, EUROSTAT, FIGARO, WIOD, OECD, and more. When data are not
already structured for a known format, MARIO also accepts custom databases
through Excel, CSV, text files, or pandas DataFrames.

Supported table types include single-region and multi-region systems, monetary
and hybrid tables, Input-Output Tables, and Supply and Use Tables.

What you can do with it
-----------------------

Beyond parsing, MARIO provides a set of analytical and transformation tools:

* aggregation of sectors, regions, and extensions;
* SUT-to-IOT transformation;
* adding new sectors, activities, commodities, and satellite extensions;
* scenario and shock analysis;
* backward and forward linkage analysis;
* extraction of single-region tables from multi-region databases;
* balance and productivity checks;
* export to Excel, text, and Parquet formats.

Quickstart
----------

A minimal IOT and SUT test database is included in MARIO:

.. code-block:: python

   import mario

   iot = mario.load_test("IOT")
   print(iot)
   print(iot.get_index("Region"))

   iot.calc_all()
   iot.to_excel(path="output_folder")

For SUT workflows:

.. code-block:: python

   sut = mario.load_test("SUT")
   print(sut)
   print(sut.get_index("Sector"))

   sut.calc_all()
   sut.to_txt(path="output_folder", coefficients=True)

Citation
--------

If you use MARIO in academic work, please cite:

.. container:: publications-primary-citation

   .. bibliography:: publications/mario.bib
      :filter: False
      :style: mario_abbr
      :keyprefix: index-

      Tahavori2023

The full list of publications using MARIO is in the :doc:`resources/publications` page.

Supporting institutions
-----------------------

MARIO grows across two complementary settings.

.. raw:: html

    <table>
       <tr>
          <td valign="top" width="180">
             <a href="https://www.polimi.it" target="_blank" rel="noopener">
                <img src="https://www.polimi.it/_assets/4b51f00386267395f41e0940abbcd656/Images/logo.svg" alt="Politecnico di Milano" width="120" />
             </a>
          </td>
          <td valign="top">
             <strong>Politecnico di Milano</strong>. Development stays closer to the academic side: research methods, modelling choices, scientific validation, and documentation-oriented workflows.
          </td>
       </tr>
       <tr>
          <td valign="top" width="180">
             <a href="https://enextgen.it" target="_blank" rel="noopener">
                <img src="https://enextgen.it/img/eNextGen_logo_transparent_black.png" alt="eNextGen" width="160" />
             </a>
          </td>
          <td valign="top">
             <strong>eNextGen</strong>. As a spin-off of Politecnico di Milano, eNextGen brings MARIO into applied settings for companies and organisations, where the same analytical core supports real decarbonisation, sustainability, and decision-support cases.
          </td>
       </tr>
    </table>

.. toctree::
   :maxdepth: 1
   :caption: Setup
   :hidden:

   setup/index

.. toctree::
   :maxdepth: 1
   :caption: Concepts
   :hidden:

   concepts/index

.. toctree::
   :maxdepth: 1
   :caption: User Guide
   :hidden:

   user_guide/index

.. toctree::
   :maxdepth: 1
   :caption: Dev guide
   :hidden:

   contribute/index

.. toctree::
   :maxdepth: 1
   :caption: API reference
   :hidden:

   reference/api_library

.. toctree::
   :maxdepth: 1
   :caption: Research
   :hidden:

   resources/publications
