EXIOBASE
========

MARIO supports the main EXIOBASE parser families:

* monetary IOT;
* monetary SUT;
* hybrid HIOT;
* hybrid HSUT.

Relevant Zenodo releases
------------------------

* monetary EXIOBASE 3.8.2: `Zenodo 5589597 <https://doi.org/10.5281/zenodo.5589597>`_;
* monetary EXIOBASE 3.9.4: `Zenodo 14614930 <https://doi.org/10.5281/zenodo.14614930>`_;
* monetary EXIOBASE 3.9.5: `Zenodo 14869924 <https://doi.org/10.5281/zenodo.14869924>`_;
* monetary EXIOBASE 3.9.6: `Zenodo 15689391 <https://doi.org/10.5281/zenodo.15689391>`_;
* monetary EXIOBASE 3.10.1: `Zenodo 18937492 <https://doi.org/10.5281/zenodo.18937492>`_;
* hybrid EXIOBASE 3.3.18: `Zenodo 7244919 <https://doi.org/10.5281/zenodo.7244919>`_;
* newer consequential release not yet covered by the current hybrid parser:
  `Zenodo 15421526 <https://zenodo.org/records/15421526>`_.

For this source, the most useful documentation format is a notebook-driven one:
short explanation on this landing page, then one practical notebook per parser
family.

Recommended Entry Points
------------------------

For normal user workflows, the public entry point should be:

* :doc:`mario.parse_exiobase(...) <../api_document/mario.parse_exiobase>`

This dispatcher is enough for the main EXIOBASE variants covered here. The
lower-level parser functions still exist, but they are not the recommended
surface for ordinary usage.

Key arguments
-------------

The core public arguments are:

* ``table``:
  choose ``"IOT"`` or ``"SUT"``;
* ``unit``:
  choose ``"Monetary"`` or ``"Hybrid"``;
* ``path``:
  local directory or bundle to parse;
* ``year``:
  optional metadata override. In most normal workflows the year is inferred
  from the EXIOBASE payload itself.

In addition, the dispatcher forwards parser-specific keyword arguments:

* monetary SUT:
  ``add_extensions=...`` lets you import extensions from a matching monetary
  IOT;
* hybrid SUT and hybrid IOT:
  ``extensions=...`` filters the imported extension set.

Typical usage
-------------

Monetary IOT:

.. code-block:: python

   import mario

   db = mario.parse_exiobase(
       table="IOT",
       unit="Monetary",
       path="/path/to/exiobase/iot_directory",
   )

Monetary SUT:

.. code-block:: python

   import mario

   db = mario.parse_exiobase(
       table="SUT",
       unit="Monetary",
       path="/path/to/exiobase/sut_directory",
   )

Hybrid SUT:

.. code-block:: python

   import mario

   db = mario.parse_exiobase(
       table="SUT",
       unit="Hybrid",
       path="/path/to/exiobase/hybrid_bundle",
       extensions="all",
   )

Download helpers are also available:

* ``mario.download_exiobase3(...)`` for supported monetary releases;
* ``mario.download_hybrid_exiobase(...)`` for the hybrid bundle.

Caveats
-------

* the monetary SUT parser is currently available only for EXIOBASE ``3.8.2``;
* the more recent monetary releases supported by MARIO are IOT-only;
* the current hybrid parser targets EXIOBASE hybrid ``3.3.18`` and does not
  yet include the later consequential developments released separately on
  Zenodo.

Notebook Walkthroughs
---------------------

Use the notebooks below as the main parser guides:

* :doc:`Monetary EXIOBASE <../notebooks/parsers/exiobase/monetary>`
* :doc:`Hybrid EXIOBASE <../notebooks/parsers/exiobase/hybrid>`

If you prefer to run them locally, you can also download the source notebooks:

* :download:`Download the monetary notebook <../notebooks/parsers/exiobase/monetary.ipynb>`
* :download:`Download the hybrid notebook <../notebooks/parsers/exiobase/hybrid.ipynb>`

