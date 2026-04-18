WIOD
====

MARIO supports the WIOD 2016 multiregional Excel workbooks in both ``IOT`` and
``SUT`` form.

Relevant source links
---------------------

* official WIOD 2016 release page:
  `GGDC WIOD 2016 release <https://www.rug.nl/ggdc/valuechain/wiod/wiod-2016-release?lang=en>`_;
* direct IOT file:
  `Dataverse 199104 <https://dataverse.nl/api/access/datafile/199104>`_;
* direct SUT file:
  `Dataverse 199100 <https://dataverse.nl/api/access/datafile/199100>`_.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_wiod(...) <../api_document/mario.parse_wiod>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one WIOD workbook or one directory containing multiple WIOD workbooks;
* ``table``:
  choose ``"IOT"`` or ``"SUT"``;
* ``year``:
  use it when the selected directory contains more than one WIOD year;
* ``name``:
  optional metadata label override;
* ``calc_all``:
  optional eager computation of derived matrices after parsing.

Download workflow
-----------------

Automatic download is available:

* ``mario.download_wiod2016(...)``

Typical usage:

.. code-block:: python

   import mario

   mario.download_wiod2016(
       path="/path/to/wiod",
       table="IOT",
   )

You can also work entirely from already downloaded local workbooks.

Supported local inputs
----------------------

MARIO currently supports only the multiregional WIOD 2016 ``.xlsb`` workbooks,
for example:

* ``WIOT2014_Nov16_ROW.xlsb``
* ``intsut14_nov16.xlsb``

The parser does not target the national WIOD IO tables.

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the WIOD notebook <../notebooks/parsers/wiod/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse one WIOD IOT workbook:

.. code-block:: python

   db = mario.parse_wiod(
       path="/path/to/WIOT2014_Nov16_ROW.xlsb",
       table="IOT",
   )

Parse one WIOD SUT workbook:

.. code-block:: python

   db = mario.parse_wiod(
       path="/path/to/intsut14_nov16.xlsb",
       table="SUT",
   )

Parse from a directory containing multiple yearly workbooks:

.. code-block:: python

   db = mario.parse_wiod(
       path="/path/to/wiod_directory",
       table="IOT",
       year=2014,
   )

Caveats
-------

* only the multiregional WIOD 2016 ``.xlsb`` workbooks are supported;
* both ``IOT`` and ``SUT`` are supported, but they use different source files;
* if ``path`` points to a directory that contains multiple candidate years,
  pass ``year=`` explicitly.
