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

.. mario-cards::
   :columns: 3
   :links:

   .. mario-card:: :doc:`Excel layouts <../../notebooks/parsers/custom_database/from_excel>`

      Flow or coefficient workbooks.

   .. mario-card:: :doc:`CSV and Parquet <../../notebooks/parsers/custom_database/from_txt>`

      Matrix files or a flat representation.

   .. mario-card:: :doc:`pymrio objects <../../notebooks/parsers/custom_database/from_pymrio>`

      Import an existing IOSystem.
