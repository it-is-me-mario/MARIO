From pymrio
===========

MARIO can convert an in-memory ``pymrio.IOSystem`` directly into a
``mario.Database``.

This workflow is not file-based. It is a bridge between two Python-side data
models, and it is practical when the upstream ingestion, balancing, or
extension handling already happened inside ``pymrio``.

Recommended Entry Point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_from_pymrio(...) <../api_document/mario.parse_from_pymrio>`

Key arguments
-------------

The key public arguments are:

* ``io``:
  the ``pymrio.IOSystem`` to convert;
* ``value_added``:
  dictionary assigning selected ``pymrio`` extensions to MARIO's factor side;
* ``satellite_account``:
  dictionary assigning selected ``pymrio`` extensions to MARIO's satellite
  side;
* ``include_meta``:
  when ``True``, MARIO records the ``pymrio`` metadata trail into the database
  notes.

How the mapping works
---------------------

``parse_from_pymrio(...)`` requires you to classify every available
``pymrio.Extension`` explicitly.

For each extension, you decide whether it belongs to:

* ``value_added``
* ``satellite_account``

Each dictionary value can be:

* ``"all"``, to assign the full extension to that side;
* one slicer, to split one extension between factors and satellites.

The conversion is currently an ``IOT`` workflow.

Typical usage
-------------

Convert one ``pymrio`` object and send one extension entirely to satellites:

.. code-block:: python

   import mario

   db = mario.parse_from_pymrio(
       io=io,
       value_added={"factor_inputs": "all"},
       satellite_account={"emissions": "all"},
   )

Split one extension by row selection:

.. code-block:: python

   import mario

   db = mario.parse_from_pymrio(
       io=io,
       value_added={"accounts": ["compensation", "taxes"]},
       satellite_account={"accounts": ["co2", "ch4"]},
   )

Caveats
-------

* every ``pymrio.Extension`` must be classified explicitly;
* this is a conversion bridge, not a generic automatic harmonizer between the
  two libraries;
* the resulting MARIO database is an ``IOT`` database, not a ``SUT`` one.
