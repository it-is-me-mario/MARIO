USEEIO
======

MARIO supports local parsing of ``USEEIO`` model workbooks exported as Excel
files.

The current backend is intentionally narrow:

* it parses only the workbook export, not the full ``useeior`` build framework;
* it currently supports only the verified ``v2.5`` workbook structure;
* it exposes an explicit ``format=`` argument so future workbook families can
  be added without changing the public API.

Relevant source links
---------------------

* official catalog page:
  `USEEIO v2.5 models on Data.gov <https://catalog.data.gov/dataset/useeio-v2-5-models>`_;
* EPA model page:
  `USEEIO models <https://www.epa.gov/land-research/us-environmentally-extended-input-output-useeio-models>`_;
* EPA technical page:
  `USEEIO technical content <https://www.epa.gov/land-research/us-environmentally-extended-input-output-useeio-technical-content>`_;
* framework and workbook-format reference:
  `USEPA/useeior <https://github.com/USEPA/useeior>`_.

Models, Aliases, and Parser Scope
---------------------------------

In ``USEEIO``, the model name in the filename, such as
``USEEIOv2.5-yellowthroat-22.xlsx``, mixes together three different things:

* the software/data version, for example ``v2.5``;
* the model alias, for example ``yellowthroat``;
* the release label or published year token, for example ``22``.

The alias is the important part if you want to understand what the model
actually contains. It identifies the economic schema and the source used for
import-related factors and extensions. It is not the same as MARIO's
``format=`` argument.

For the currently relevant national ``USEEIO`` families, the official
``USEPA/USEEIO`` model registry distinguishes the following aliases:

.. list-table::
   :header-rows: 1

   * - Alias
     - BEA schema
     - Import-factor source
     - Main extensions / indicators
   * - ``yellowthroat``
     - BEA Summary 2017
     - GLORIA v59a
     - GHG + material-footprint extensions
   * - ``waxwing``
     - BEA Detail 2017
     - GLORIA v59a
     - GHG + material-footprint extensions
   * - ``kingbird``
     - BEA Summary 2017
     - EXIOBASE v3.8.2
     - GHG
   * - ``kinglet``
     - BEA Detail 2017
     - EXIOBASE v3.8.2
     - GHG
   * - ``oriole``
     - BEA Summary 2017
     - CEDA 2024
     - GHG
   * - ``catbird``
     - BEA Detail 2017
     - CEDA 2024
     - GHG

This parser currently targets the national workbook exports only. It does not
cover the ``StateEEIO`` families listed in the same official registry.

What ``format`` Means
---------------------

``format=`` is a parser-side selector. It describes the file layout and matrix
semantics that MARIO knows how to read, not the scientific content of the
model.

So:

* ``yellowthroat`` and ``kingbird`` are different models, because they differ
  in schema detail and import-factor source;
* but they can still share the same parser ``format`` if the workbook tabs and
  block semantics are organized the same way.

At the moment, MARIO supports:

* ``format="auto"``:
  inspect the workbook and resolve the known layout automatically;
* ``format="v2.5_workbook"``:
  force the currently verified workbook export structure.

For this verified format, the parser assumes the workbook follows the
``useeior`` model-object export logic, in particular:

* ``V`` is the make matrix;
* ``U`` is the extended use matrix containing the intermediate-use block, final
  demand columns, and value-added rows;
* ``q`` is the commodity-output vector;
* ``B`` is the direct environmental coefficient matrix;
* metadata tabs such as ``commodities_meta``, ``final_demand_meta``, and
  ``value_added_meta`` identify the axes.

Recommended entry point
-----------------------

For normal user workflows, the public entry point is:

* :doc:`mario.parse_useeio(...) <../../api_document/mario.parse_useeio>`

Key arguments
-------------

The key public arguments are:

* ``path``:
  one local ``USEEIO*.xlsx`` workbook or one directory containing a single
  workbook;
* ``format``:
  workbook layout selector. ``auto`` is the default and currently resolves to
  ``"v2.5_workbook"``;
* ``table``:
  currently only ``"SUT"`` is supported.

Expected path structure
-----------------------

``path`` can point to one local ``USEEIO*.xlsx`` workbook or to a directory
containing one workbook:

.. code-block:: text

   USEEIO/
   ├── USEEIOv2.5-yellowthroat-22.xlsx
   ├── USEEIOv2.5-kingbird-22.xlsx
   └── USEEIOv2.5-catbird-22.xlsx

Inside the workbook, MARIO expects the ``useeior`` model export sheets such as
``V``, ``U``, ``B``, ``q``, ``commodities_meta``, ``final_demand_meta`` and
``value_added_meta``. If a directory contains more than one workbook, pass the
workbook path directly.

Notebook walkthrough
--------------------

Use the notebook below as the main parser guide:

* :doc:`USEEIO parser walkthrough <../../notebooks/parsers/useeio/walkthrough>`

If you prefer to run it locally, you can also download the source notebook:

* :download:`Download the USEEIO notebook <../../notebooks/parsers/useeio/walkthrough.ipynb>`

.. toctree::
   :hidden:

   ../../notebooks/parsers/useeio/walkthrough

Caveats
-------

* MARIO currently parses only the verified ``v2.5`` workbook export. Other
  USEEIO workbook families should still be treated as unsupported until they
  are checked explicitly.
* The official ``USEPA/USEEIO`` registry currently lists some newer entries,
  such as ``v2.5.1`` families, as pending or in draft. This parser has been
  verified only on the published ``v2.5`` workbook export family so far.
* The parser targets the Excel workbook export, not the full ``useeior``
  model-building framework. If you are working from the framework sources,
  export one workbook first and parse that workbook locally.
* ``USEEIO`` workbooks can expose a release year that differs from the
  internal IO year used by the model. MARIO stores the internal IO year in the
  parsed database metadata.
* In the official model registry, ``USEEIO v2.5-waxwing-22`` is marked as
  deprecated because it was published with an incorrect extension and replaced
  by ``USEEIO v2.5.1-waxwing-22``. Until the replacement workbook is checked
  explicitly, treat ``waxwing`` parsing with more caution than the other
  published ``v2.5`` aliases.
* For the verified ``v2.5`` workbook layout, the direct environmental
  coefficient matrix ``B`` is aligned with the commodity axis. MARIO therefore
  loads direct extensions into ``Ec`` through ``B * q``.
