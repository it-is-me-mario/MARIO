GTAP
====

MARIO currently supports the GTAP Power MRIO bundle as a local-file ``IOT``
workflow.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_gtap(...) <../api_document/mario.parse_gtap>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  GTAP bundle directory, or one file inside that directory;
* ``table``:
  currently only ``"IOT"`` is supported;
* ``variant``:
  currently only ``"power"`` is supported;
* ``layout``:
  currently only ``"MRIO"`` is supported;
* ``input_format``:
  use ``"auto"``, ``"csv"`` or ``"gdx"``.

Supported variants
------------------

The current implementation supports only:

* ``variant="power"``
* ``layout="MRIO"``
* ``table="IOT"``

Input formats can be:

* ``input_format="csv"``
* ``input_format="gdx"``
* ``input_format="auto"``

With ``auto``, MARIO prefers the CSV bundle when both CSV and GDX are present.

Download workflow
-----------------

Automatic GTAP download is not part of the current MARIO workflow.

You should point the parser to one local GTAP bundle directory, or to one file
inside that directory.

Tutorial
--------

If you prefer to run the walkthrough locally, you can also download the source
notebook:

* :download:`Download the GTAP notebook <../notebooks/parsers/gtap/tutorial.ipynb>`

Load MARIO first:

.. code-block:: python

   import mario

Parse a CSV GTAP Power MRIO bundle:

.. code-block:: python

   db = mario.parse_gtap(
       path="/path/to/gtap_bundle",
       table="IOT",
       variant="power",
       layout="MRIO",
       input_format="csv",
   )

Let MARIO auto-detect the available payload:

.. code-block:: python

   db = mario.parse_gtap(
       path="/path/to/gtap_bundle",
       table="IOT",
       input_format="auto",
   )

Use the GDX workflow explicitly:

.. code-block:: python

   db = mario.parse_gtap(
       path="/path/to/gtap_bundle",
       table="IOT",
       input_format="gdx",
   )

Caveats
-------

* GTAP parsing currently supports only GTAP Power MRIO ``IOT`` bundles;
* the GDX workflow requires the GAMS Python API because MARIO relies on
  ``gams.transfer``;
* ``auto`` is the most practical choice unless you explicitly want to force
  CSV or GDX.
