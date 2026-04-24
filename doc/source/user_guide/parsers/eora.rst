EORA
=====

.. important::

   **EORA 2** has been released. 
   Dedicated parser for EORA 2 will be available soon.

Regarding EORA 1 database, MARIO supports parsing of:

* ``Eora26``
* single-region national tables.

There is currently **no** parser for the full Eora multi-regional release.
The multi-region parser is restricted to ``Eora26`` only.


Relevant source links
---------------------

* official Eora website:
  `Eora MRIO portal <https://www.worldmrio.com/>`_.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_eora(...) <../../api_document/mario.parse_eora>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one Eora file or one directory containing the local dataset
* ``multi_region``:
  use ``True`` for ``Eora26`` and ``False`` for local single-region files
* ``table``:
  relevant mainly for single-region parsing (some countries are IOTs, some are SUTs).
  For multi-region parsing use ``IOT`` only
* ``indeces``:
  optional path to the ``Eora26`` label files. If omitted, MARIO looks for
  ``labels_*.txt`` files next to the dataset files;
* ``name_convention``:
  use ``full_name`` or ``abbreviation`` for region labels in the single-region
  workflow;
* ``aggregate_trade``:
  single-region helper that collapses detailed import/export rows into total
  imports and exports;
* ``country``:
  single-region selector when the input path points to a directory containing
  multiple country files;
* ``price``:
  optional single-region selector when the local directory contains multiple
  price variants.

Expected path structure
-----------------------

For ``Eora26``, ``path`` points to the directory containing the numeric files,
and ``indeces`` points to the label files if they are not colocated:

.. code-block:: text

   EORA/
   ├── Eora26_2017_bp/
   │   ├── Eora26_2017_bp_T.txt
   │   ├── Eora26_2017_bp_FD.txt
   │   ├── Eora26_2017_bp_VA.txt
   │   ├── Eora26_2017_bp_Q.txt
   │   └── Eora26_2017_bp_QY.txt
   └── indices/
       ├── labels_T.txt
       ├── labels_FD.txt
       ├── labels_VA.txt
       └── labels_Q.txt

For single-region tables, ``path`` can point to one file or to a directory
with files named like:

.. code-block:: text

   IO_All_2017/
   └── IO_ITA_2017_BasicPrice.txt

When using a directory of single-region files, pass ``country=`` and, if the
directory contains several variants, ``year=`` or ``price=``.


Notebook walkthrough
--------------------

Since no automatic Eora download is supported natively in MARIO,
you should work from local Eora files that you already downloaded.

Use the notebook below as the main parser guide:

* :doc:`Eora parser walkthrough <../../notebooks/parsers/eora/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the Eora notebook <../../notebooks/parsers/eora/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/eora/walkthrough


Caveats
-------

* There is no parser here for the full Eora MRIO release. Multi-region parsing means ``Eora26`` only
* ``Eora26`` parsing requires the path to the *indices* files in addition to the numeric data files
* Single-region parsing can infer ``IOT`` versus ``SUT`` automatically from the local file structure.
