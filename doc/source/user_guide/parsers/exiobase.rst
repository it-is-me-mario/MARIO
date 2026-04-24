EXIOBASE
========

MARIO supports the main EXIOBASE parser families:

* monetary IOT and SUT
* hybrid-unit IOT and SUT


Relevant releases
-----------------

* `3.10.1 (monetary, IOT) <https://doi.org/10.5281/zenodo.18937492>`_
* `3.9.6 (monetary, IOT) <https://doi.org/10.5281/zenodo.15689391>`_
* `3.9.5 (monetary, IOT) <https://doi.org/10.5281/zenodo.14869924>`_
* `3.9.4 (monetary, IOT) <https://doi.org/10.5281/zenodo.14614930>`_
* `3.8.2 (monetary, IOT and SUT) <https://doi.org/10.5281/zenodo.5589597>`_
* `3.3.18 (hybrid-units, IOT and SUT) <https://doi.org/10.5281/zenodo.7244919>`_


Recommended entry point
-----------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_exiobase(...) <../../api_document/mario.parse_exiobase>`

This method covers all EXIOBASE variants listed above, if properly configured.


Key arguments
-------------

The core public arguments are:

* ``path``:
  local directory or bundle to parse. When ``download=True`` in
  ``mario.parse_exiobase(...)``, this is instead the destination directory
  used for the download/cache step.
* ``table``:
  choose ``"IOT"`` or ``"SUT"``
* ``unit``:
  choose ``"Monetary"`` or ``"Hybrid"``
* ``download``:
  when ``True``, MARIO downloads the requested EXIOBASE package and then
  parses it locally. Monetary downloads require ``year=...``.


In addition, the dispatcher forwards parser-specific keyword arguments:

* monetary SUT:
  ``add_extensions=...`` lets you import extensions from a given matching monetary IOT
* hybrid SUT and hybrid IOT:
  ``extensions=...`` filters the imported extension set

For hybrid EXIOBASE, ``extensions`` accepts:

* ``None`` or ``[]`` to skip extension import;
* ``"all"`` to import every supported extension;
* one explicit list of extension groups.

Valid hybrid ``HSUT`` extension groups are:

* ``resource``
* ``Land``
* ``Emiss``
* ``Emis_unreg_w``
* ``Unreg_w``
* ``waste_sup``
* ``waste_use``
* ``pack_sup_waste``
* ``pack_use_waste``
* ``mach_sup_waste``
* ``mach_use_waste``
* ``stock_addition``
* ``crop_res``

Valid hybrid ``HIOT`` extension groups are the same, except that ``Unreg_w``
is not available:

* ``resource``
* ``Land``
* ``Emiss``
* ``Emis_unreg_w``
* ``waste_sup``
* ``waste_use``
* ``pack_sup_waste``
* ``pack_use_waste``
* ``mach_sup_waste``
* ``mach_use_waste``
* ``stock_addition``
* ``crop_res``

Expected path structure
-----------------------

For monetary IOTs, ``path`` points to an extracted EXIOBASE IOT directory:

.. code-block:: text

   EXIOBASE/3.9.4/
   ├── IOT_2013_ixi/
   └── IOT_2013_pxp/

For monetary SUTs, ``path`` points to an extracted monetary SUT directory:

.. code-block:: text

   EXIOBASE/3.8.2/
   └── MRSUT_2011/

For hybrid EXIOBASE, ``path`` can point to the extracted Zenodo release root.
That root may contain the hybrid SUT files, hybrid IOT files and extension
files together; MARIO detects the relevant pieces from the selected
``table=`` and ``extensions=`` arguments:

.. code-block:: text

   EXIOBASE/3.3.18/
   ├── MR_HSUT_*.txt
   ├── MR_HIOT_*.txt
   ├── Land_*.txt
   ├── Emiss_*.txt
   ├── waste_sup_*.txt
   └── waste_use_*.txt

You do not need to split the hybrid release into separate ``SUT``, ``IOT`` and
``extensions`` directories. The parser also accepts more organized extracted
folders when the same files are present under subdirectories.

When ``download=True``, ``path`` is the destination/cache directory where
MARIO downloads the requested release before parsing it.


**Download methods** are also available:

* ``mario.download_exiobase3(...)`` for supported monetary releases;
* ``mario.download_hybrid_exiobase(...)`` for the hybrid bundle.

Notebook walkthroughs
---------------------

Use the notebooks below as the main parser guides:

* :doc:`Monetary EXIOBASE parser walkthrough <../../notebooks/parsers/exiobase/monetary>`
* :doc:`Hybrid-units EXIOBASE parser walkthrough <../../notebooks/parsers/exiobase/hybrid>`

If you prefer to run them locally, you can also download the source notebooks:

* :download:`Download the monetary notebook <../../notebooks/parsers/exiobase/monetary.ipynb>`
* :download:`Download the hybrid notebook <../../notebooks/parsers/exiobase/hybrid.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/exiobase/monetary
   ../../notebooks/parsers/exiobase/hybrid


Caveats
-------

* The monetary SUT parser is currently available only for EXIOBASE ``3.8.2``: more recent releases are IOT-only
* The current hybrid parser targets EXIOBASE hybrid ``3.3.18`` and does not
  include the later consequential database released separately on Zenodo.
* Exiobase 1 and 2 versions are not supported. In principle, you could use pymrio and then :doc:`import them into MARIO <from_pymrio>`
