:page-type: API reference
:summary: Canonical set names, accepted aliases and default matrix-axis conventions.

Sets and indices
================

For diagrams and format-specific nomenclature, see :doc:`Table formats
</get_started/table_formats>` and its :doc:`IOT </get_started/table_formats/iot>`
and :doc:`SUT </get_started/table_formats/sut>` guides.

Canonical names and aliases
---------------------------

.. raw:: html
   :file: ../get_started/_generated/indices_table.html

These are the default aliases. :doc:`Custom labels
</user_guide/inspection/custom_labels_and_aliases>` describes settings overrides.
Economic axes in the pandas representation use ``Region``, ``Level`` and
``Item``: the Level value identifies the set (Sector, Activity or Commodity),
and Item carries its native member label. The :doc:`matrix catalogue
<api_resolvable_matrices>` lists the semantic row and column sets for each block.

.. _regional-classifications:

Regional classifications
------------------------

Most sources use the same labels in every region, so ``db.get_index(...)``
returns a list. For a set whose members vary by region, it returns
``{region: [members]}``. BONSAI is an example. Each set is evaluated independently;
common/global sets still return lists. Equal counts do not imply equal members.

Use ``region=...`` for one region or ``flat=True`` for the union of distinct
labels. A union does not imply that every label exists in every region.
See :doc:`db.get_index() </api_document/mario.CoreModel.get_index>` and
:doc:`inspection examples </user_guide/inspection/basic_inspections>`.

The :download:`nomenclature and formulas workbook
</_static/data/supporting_files/Nomenclature_and_formulas.xlsx>` supplies the
shared index and matrix descriptions used by these pages.
