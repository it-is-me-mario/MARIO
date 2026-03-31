Troubleshooting
===============

Typical sources of confusion
----------------------------

Parser errors
   Usually come from missing labels, invalid set definitions, ambiguous layouts
   or workbook structures that do not match the expected file format.

Export/re-import mismatches
   Usually come from mixing legacy ``Level``-based workbooks with explicit
   layout-aware workbooks in the same roundtrip.

``add_sectors`` workbook issues
   Often come from incomplete master rows, missing inventory tabs, wrong unit
   definitions or inconsistent parent mappings.

CVXLab split issues
   ``split=True`` is stricter than the normal ``add_sectors`` workflow and
   currently expects the classical IOT layout for extension and factor rows.
   See the `CVXLab documentation <https://cvxlab.readthedocs.io/>`_ when the
   issue is related to model setup or solver configuration.

Recommended references
----------------------

* :doc:`../concepts/matrix_layouts`
* :doc:`../concepts/add_sectors_model`
* :doc:`../reference/file_formats`
* `CVXLab documentation <https://cvxlab.readthedocs.io/>`_
