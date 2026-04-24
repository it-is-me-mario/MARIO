Global Trade Analysis Project (GTAP)
====================================

MARIO currently supports the GTAP Power MRIO bundle as a local-file ``IOT``
workflow.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_gtap(...) <../../api_document/mario.parse_gtap>`

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

Expected path structure
-----------------------

``path`` can point to the GTAP Power bundle directory or to one file inside
that directory:

.. code-block:: text

   GTAP/
   └── power_mrio/
       ├── *.csv
       └── *.gdx

With ``input_format="auto"``, MARIO uses the CSV files when both CSV and GDX
payloads are present. The GDX path requires the GAMS Python API.

Download workflow
-----------------

Automatic GTAP download is not part of the current MARIO workflow.

You should point the parser to one local GTAP bundle directory, or to one file
inside that directory.

Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`GTAP parser walkthrough <../../notebooks/parsers/gtap/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the GTAP notebook <../../notebooks/parsers/gtap/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/gtap/walkthrough

Caveats
-------

* GTAP parsing currently supports only GTAP Power MRIO ``IOT`` bundles;
* the GDX workflow requires the GAMS Python API because MARIO relies on
  ``gams.transfer``;
* ``auto`` is the most practical choice unless you explicitly want to force
  CSV or GDX.
