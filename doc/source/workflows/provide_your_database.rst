Provide your database
=====================

This workflow is the recommended way to load a custom database into MARIO when
you already know your own sets and only need a template to fill.

The idea is simple:

1. define the sets of your database;
2. define the units for the unit-bearing sets;
3. ask MARIO to generate one Excel template;
4. fill the numeric values in that workbook;
5. read it back with :doc:`/api_document/mario.parse_from_excel`.

Recommended helper
------------------

Use :doc:`/api_document/mario.write_parse_template` to scaffold the workbook.

It accepts:

* ``table="IOT"`` or ``table="SUT"``;
* ``sets=...`` with your regions, sectors or activities/commodities, factors,
  satellite accounts, and final-demand categories;
* ``units=...`` with the units of the unit-bearing sets;
* ``format="flat"`` or ``format="matrix"``.

The default is ``format="flat"``.

Alternative: define sets and units in Excel
-------------------------------------------

If you prefer not to pass Python dictionaries, you can define the sets and
units in a separate workbook first.

Generate the definition workbook:

.. code-block:: python

   import mario

   mario.write_template_definition(
       "custom_iot_definition.xlsx",
       table="IOT",
   )

Fill the ``definition`` sheet, then generate the real data-entry workbook:

.. code-block:: python

   import mario

   mario.write_parse_template(
       "custom_iot.xlsx",
       table="IOT",
       definition="custom_iot_definition.xlsx",
   )

This is equivalent to passing ``sets=...`` and ``units=...`` directly.

Why ``flat`` is the default
---------------------------

The flat template is easier to author manually:

* one ``data`` sheet for the numeric values;
* one ``units`` sheet for the units;
* one ``instructions`` sheet with the parse command.

It is also read back directly by
:doc:`/api_document/mario.parse_from_excel` without extra layout arguments.

Minimal IOT example
-------------------

.. code-block:: python

   import mario

   mario.write_parse_template(
       "custom_iot.xlsx",
       table="IOT",
       sets={
           "regions": ["Italy", "France"],
           "sectors": ["Agriculture", "Industry"],
           "final demand": ["Households", "Government"],
           "factors": ["Labor", "Capital"],
           "satellites": ["CO2"],
       },
       units={
           "sectors": "M EUR",
           "factors": "M EUR",
           "satellites": "kt",
       },
   )

After you fill the values:

.. code-block:: python

   import mario

   db = mario.parse_from_excel(
       path="custom_iot.xlsx",
       table="IOT",
       mode="flows",
   )

Minimal SUT example
-------------------

.. code-block:: python

   import mario

   mario.write_parse_template(
       "custom_sut.xlsx",
       table="SUT",
       sets={
           "regions": ["Italy"],
           "activities": ["Manufacturing", "Services"],
           "commodities": ["Goods", "Services"],
           "final demand": ["Households"],
           "factors": ["Labor"],
           "satellites": ["CO2"],
       },
       units={
           "activities": "M EUR",
           "commodities": "M EUR",
           "factors": "M EUR",
           "satellites": "kt",
       },
   )

Then parse it:

.. code-block:: python

   import mario

   db = mario.parse_from_excel(
       path="custom_sut.xlsx",
       table="SUT",
       mode="flows",
   )

Alternative: matrix template
----------------------------

If you prefer the historical matrix workbook layout, set:

.. code-block:: python

   mario.write_parse_template(
       "custom_iot_matrix.xlsx",
       table="IOT",
       sets=...,
       units=...,
       format="matrix",
   )

This is still valid, but the flat template is usually the better manual entry
point.

Note on ``DataTemplate``
------------------------

``DataTemplate`` is deprecated. Use
:doc:`/api_document/mario.write_parse_template` instead.
