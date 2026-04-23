From pymrio
===========

MARIO can convert an in-memory ``pymrio.IOSystem`` directly into a
``mario.Database``.

This workflow is not file-based. It is a bridge between two Python libraries,
and it is practical when the upstream ingestion, balancing, or
extension handling already happened inside ``pymrio``.


Relevant Source Links
---------------------

* official pymrio documentation:
  `pymrio documentation <https://pymrio.readthedocs.io/en/latest/index.html>`_.


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
  dictionary assigning selected ``pymrio`` extensions to MARIO's factor side.
  As a shorthand, use ``"all"`` to assign every Extension not explicitly sent
  to satellites to the factor side;
* ``satellite_account``:
  dictionary assigning selected ``pymrio`` extensions to MARIO's satellite
  side. As a shorthand, use ``"all"`` to assign every Extension not
  explicitly sent to factors to the satellite side;
* ``include_meta``:
  when ``True``, MARIO records the ``pymrio`` metadata trail into the database
  notes.


Assignment Patterns
-------------------

``parse_from_pymrio(...)`` requires you to classify every available
``pymrio.Extension`` explicitly.

At the top level, both ``value_added`` and ``satellite_account`` can be:

* one ``dict`` mapping Extension names to selectors;
* the string ``"all"``.

Each dictionary value can be:

* ``"all"``, to assign the full extension to that side;
* one slicer, to split one extension between factors and satellites.

Common valid patterns are:

* explicit split:
  ``value_added={"factor_inputs": "all"}``,
  ``satellite_account={"air_emissions": "all", "water": "all"}``;
* complement shorthand:
  ``value_added="all"``,
  ``satellite_account={"air_emissions": "all"}``;
* full shorthand:
  ``value_added="all"``,
  ``satellite_account="all"``.

With the full shorthand, MARIO looks for exactly one factor-like Extension
such as ``factor_inputs``, ``factor_of_production``, ``value_added``, or
``primary_inputs`` and assigns all remaining Extensions to satellites.

To inspect the available Extension names in one ``pymrio.IOSystem``, use:

.. code-block:: python

   import pymrio

   [
       name
       for name in dir(io)
       if isinstance(getattr(io, name), pymrio.Extension)
   ]

The conversion is currently an ``IOT`` workflow.


Notebook Walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`pymrio parser walkthrough <../notebooks/parsers/custom_database/from_pymrio>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the pymrio notebook <../notebooks/parsers/custom_database/from_pymrio.ipynb>`

.. toctree::
   :hidden:

   ../notebooks/parsers/custom_database/from_pymrio

Caveats
-------

* every ``pymrio.Extension`` must be classified explicitly;
* the ``"all"`` / ``"all"`` shorthand works only when MARIO can infer one
  unique factor-like Extension;
* this is a conversion bridge, not a generic automatic harmonizer between the
  two libraries;
* the resulting MARIO database is an ``IOT`` database, not a ``SUT`` one.
