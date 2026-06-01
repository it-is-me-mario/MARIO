Country Coverage Workbook
=========================

MARIO uses the packaged Country_coverage workbook to reconcile source-specific
region labels with ISO3 country codes.

This workbook supports parser coverage checks and region aggregation workflows:

- parser and source coverage queries use it to align country labels across databases
- runtime region aggregation uses it before falling back to `country_converter <https://github.com/IndEcol/country_converter>`_
- workbook updates let you correct or extend source-specific country mappings without patching parser code

Download the :download:`Country_coverage workbook </_static/data/supporting_files/Country_coverage.xlsx>`.

For the runtime aggregation details, see :doc:`../../concepts/clusters`.

The parser coverage query remains available from :doc:`index`.
