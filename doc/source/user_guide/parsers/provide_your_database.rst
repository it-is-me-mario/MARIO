:page-type: Guide
:summary: Create a structured Excel template, fill its tables and units, then parse it.

Import your own tables
======================

.. container:: mario-companion

   :download:`Download notebook <provide_your_database.ipynb>`

.. container:: mario-flow

   **Define labels** → **Generate template** → **Fill values** → **Parse**

Create an IOT template
----------------------

.. code-block:: python

   import mario

   mario.write_parse_template(
       "custom_iot.xlsx", table="IOT",
       sets={
           "regions": ["Reg1", "Reg2"],
           "sectors": ["Agriculture", "Services"],
           "final demand": ["Final demand"],
           "factors": ["Taxes", "Wages"], "satellites": ["CO2"],
       },
       units={"sectors": "M EUR", "factors": "M EUR", "satellites": "kg"},
   )

Fill the generated blocks and units before parsing. The template defines the
layout; it does not provide economic data.

Read the completed file
-----------------------

.. code-block:: python

   db = mario.parse_from_excel(path="custom_iot.xlsx", table="IOT", mode="flows")
   db.get_index("all")
   db.Z

.. mario-details:: SUT templates

   Use ``table="SUT"`` and provide ``activities`` and ``commodities`` instead
   of ``sectors``, with units for both. The companion notebook includes a
   complete SUT template example.

Create a NAM template
---------------------

NAM uses explicit memberships for each reporting economy and a monetary
currency, scale and reference period:

.. code-block:: python

   mario.write_parse_template(
       "custom_nam.xlsx", table="NAM",
       sets={"IT": {"commodity": ["Goods", "Services"],
                     "activity": ["Industry", "Services"]}},
       units={"currency": "EUR", "scale": 1_000_000, "period": 2023},
       representation="use_imports",
   )
   nam = mario.parse_from_excel("custom_nam.xlsx", table="NAM", mode="flows")
   nam.get_index("all")

This minimal template declares only products and activities; add other sets
and their actual members when your NAM contains them. Initial blocks are
``unavailable``. Fill a whole block numerically, including zeros, and change
its presence to ``observed`` in ``matrix_layouts``. A known all-zero block
can instead be ``declared_zero``. Parsing an unfilled template preserves
unknowns; it does not make ``T`` or its coefficients calculable.

Account names and native layouts are embedded in the workbook. Keep the
registry ranges consistent when editing it; Excel formulas are not accepted
as observed flow values. See :doc:`the NAM format guide
</get_started/table_formats/nam>` for all sets, item metadata and import
representations, and :func:`mario.write_parse_template` for arguments.

.. mario-cards::
   :columns: 3
   :links:

   .. mario-card:: :doc:`Excel layouts <../../notebooks/parsers/custom_database/from_excel>`

      Flow or coefficient workbooks.

   .. mario-card:: :doc:`CSV and Parquet <../../notebooks/parsers/custom_database/from_txt>`

      Matrix files or a flat representation.

   .. mario-card:: :doc:`pymrio objects <../../notebooks/parsers/custom_database/from_pymrio>`

      Import an existing IOSystem.
