Database parsers
================

Each guide is a notebook about one source: the parser workflow, the expected
inputs, the supported versions, the local layout and the common caveats. Every
guide also offers its notebook as a download at the bottom of the page.

The cards show regions and economic dimensions for versions with available set
lists. Explore :ref:`Classifications <database-scopes>`
for geographical and sectoral coverage, or download all sets from :doc:`Downloadable material
<../../resources/material>`.


Environmentally-extended databases
----------------------------------

.. mario-cards::
   :columns: 2
   :links:

   .. mario-card:: :doc:`EXIOBASE, monetary <../../notebooks/parsers/exiobase/monetary>`
      :kicker: mario.parse_exiobase
      :database: exiobase-monetary
      :logo: /_static/images/logos/exiobase.png

      Monetary IOT and SUT releases of EXIOBASE 3, with a downloader for the
      Zenodo records.

   .. mario-card:: :doc:`EXIOBASE, hybrid <../../notebooks/parsers/exiobase/hybrid>`
      :kicker: mario.parse_exiobase
      :database: exiobase-hybrid
      :logo: /_static/images/logos/exiobase.png

      The hybrid EXIOBASE bundle, as supply-use and input-output tables, with a
      choice of extensions.

   .. mario-card:: :doc:`EORA <../../notebooks/parsers/eora/walkthrough_eora>`
      :kicker: mario.parse_eora
      :database: eora

      Eora26 and single-region local files from EORA1.

   .. mario-card:: :doc:`GLORIA <../../notebooks/parsers/gloria/walkthrough_gloria>`
      :kicker: mario.parse_gloria
      :database: gloria

      GLORIA monetary SUT releases, from a local copy of the IELab material.

   .. mario-card:: :doc:`GTAP <../../notebooks/parsers/gtap/walkthrough_gtap>`
      :kicker: mario.parse_gtap
      :database: gtap
      :logo: /_static/images/logos/gtap.png

      GTAP Power MRIO bundles, from CSV or GDX files.

   .. mario-card:: :doc:`EMERGING <../../notebooks/parsers/emerging/walkthrough_emerging>`
      :kicker: mario.parse_emerging
      :database: emerging

      EMERGING MATLAB bundles, versions 1.0, 2.x and the E variant, downloadable
      from Zenodo.

   .. mario-card:: :doc:`WIOD <../../notebooks/parsers/wiod/walkthrough_wiod>`
      :kicker: mario.parse_wiod
      :database: wiod
      :logo: /_static/images/logos/wiod.png

      WIOD 2016 workbooks: the multi-regional IOT and the national IOT and SUT.

   .. mario-card:: :doc:`Asian Development Bank <../../notebooks/parsers/adb/walkthrough_adb>`
      :kicker: mario.parse_adb
      :database: adb
      :logo: /_static/images/logos/adb.svg

      ADB multi-regional and single-region workbooks, with the air-emissions
      extensions.

   .. mario-card:: :doc:`USEEIO v2.5 <../../notebooks/parsers/useeio/walkthrough_useeio>`
      :kicker: mario.parse_useeio
      :database: useeio
      :logo: /_static/images/logos/useeio.png

      USEEIO v2.5 model workbooks published by the US EPA.

   .. mario-card:: :doc:`CEADS <../../notebooks/parsers/ceads/walkthrough_ceads>`
      :kicker: mario.parse_ceads
      :database: ceads
      :logo: /_static/images/logos/ceads.png

      China's provincial multi-regional tables from CEADS, with an optional CO2
      row.

.. toctree::
   :hidden:

   EXIOBASE, monetary <../../notebooks/parsers/exiobase/monetary>
   EXIOBASE, hybrid <../../notebooks/parsers/exiobase/hybrid>
   EORA <../../notebooks/parsers/eora/walkthrough_eora>
   GLORIA <../../notebooks/parsers/gloria/walkthrough_gloria>
   GTAP <../../notebooks/parsers/gtap/walkthrough_gtap>
   EMERGING <../../notebooks/parsers/emerging/walkthrough_emerging>
   WIOD <../../notebooks/parsers/wiod/walkthrough_wiod>
   Asian Development Bank <../../notebooks/parsers/adb/walkthrough_adb>
   USEEIO v2.5 <../../notebooks/parsers/useeio/walkthrough_useeio>
   CEADS <../../notebooks/parsers/ceads/walkthrough_ceads>


Other MRIO and SRIO databases
-----------------------------

.. mario-cards::
   :columns: 2
   :links:

   .. mario-card:: :doc:`OECD <../../notebooks/parsers/oecd/walkthrough_oecd>`
      :kicker: mario.parse_oecd
      :database: oecd
      :logo: /_static/images/logos/oecd.png

      OECD inter-country ICIO, national IOT and SUT tables.

   .. mario-card:: :doc:`FIGARO <../../notebooks/parsers/figaro/walkthrough_figaro>`
      :kicker: mario.parse_figaro
      :database: figaro
      :logo: /_static/images/logos/eurostat.png

      FIGARO SUT and IOT, downloaded directly from the Eurostat API.

   .. mario-card:: :doc:`EUROSTAT <../../notebooks/parsers/eurostat/walkthrough_eurostat>`
      :kicker: mario.parse_eurostat
      :database: eurostat
      :logo: /_static/images/logos/eurostat.png

      National SUT and IOT from the Eurostat SDMX API.

   .. mario-card:: :doc:`BEA <../../notebooks/parsers/bea/walkthrough_bea>`
      :kicker: mario.parse_bea
      :database: bea
      :logo: /_static/images/logos/bea.svg

      The official BEA supply-use workbooks for the United States.

   .. mario-card:: :doc:`ISTAT <../../notebooks/parsers/istat/walkthrough_istat>`
      :kicker: mario.parse_istat
      :database: istat
      :logo: /_static/images/logos/istat.svg

      Official ISTAT input-output releases for Italy, IOT and SUT.

   .. mario-card:: :doc:`StatCan <../../notebooks/parsers/statcan/walkthrough_statcan>`
      :kicker: mario.parse_statcan
      :database: statcan
      :logo: /_static/images/logos/statcan.svg

      Statistics Canada supply-use and symmetric input-output tables, read from
      the official API.

   .. mario-card:: :doc:`CEPALSTAT <../../notebooks/parsers/cepalstat/walkthrough_cepalstat>`
      :kicker: mario.parse_cepalstat
      :database: cepalstat
      :logo: /_static/images/logos/eclac.svg

      Supply-use and input-output tables for Latin America and the Caribbean,
      still in beta.

.. toctree::
   :hidden:

   OECD <../../notebooks/parsers/oecd/walkthrough_oecd>
   FIGARO <../../notebooks/parsers/figaro/walkthrough_figaro>
   EUROSTAT <../../notebooks/parsers/eurostat/walkthrough_eurostat>
   BEA <../../notebooks/parsers/bea/walkthrough_bea>
   ISTAT <../../notebooks/parsers/istat/walkthrough_istat>
   StatCan <../../notebooks/parsers/statcan/walkthrough_statcan>
   CEPALSTAT <../../notebooks/parsers/cepalstat/walkthrough_cepalstat>


Custom databases
----------------

.. mario-cards::
   :columns: 2
   :links:

   .. mario-card:: :doc:`Work with your custom database <provide_your_database>`
      :kicker: mario.write_parse_template
      :logo: /_static/images/mario-logo.png

      Create a MARIO-readable Excel template, fill it and parse it back into a
      database.

   .. mario-card:: :doc:`Excel custom parser <../../notebooks/parsers/custom_database/from_excel>`
      :kicker: mario.parse_from_excel
      :database: custom-database-from-excel
      :logo: /_static/images/logos/file-xlsx.svg

      Read a completed MARIO-readable Excel workbook, IOT or SUT.

   .. mario-card:: :doc:`TXT, CSV, and Parquet custom parser <../../notebooks/parsers/custom_database/from_txt>`
      :kicker: mario.parse_from_txt
      :database: custom-database-from-txt
      :logo: /_static/images/logos/file-txt.svg /_static/images/logos/file-csv.svg /_static/images/logos/file-parquet.svg

      Read directories of TXT, CSV or Parquet files, such as MARIO exports.

   .. mario-card:: :doc:`Pymrio bridge <../../notebooks/parsers/custom_database/from_pymrio>`
      :kicker: mario.parse_from_pymrio
      :database: custom-database-from-pymrio
      :logo: /_static/images/logos/pymrio.png

      Turn a pymrio ``IOSystem`` in memory into a MARIO database.

.. toctree::
   :hidden:

   provide_your_database
   Excel custom parser <../../notebooks/parsers/custom_database/from_excel>
   TXT, CSV, and Parquet custom parser <../../notebooks/parsers/custom_database/from_txt>
   Pymrio bridge <../../notebooks/parsers/custom_database/from_pymrio>
