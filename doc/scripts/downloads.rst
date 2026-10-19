Public downloads
================

Keep three distinct things: native set inventories, fine classification lookups,
and the broad sector assignments used by the indicator browser. Fine lookups
are not numerical allocation weights. Archive years with identical sets can
share an inventory; counts alone are not sufficient to merge them.

The source notices come from ``database_licences.json`` and the selected release
metadata. Review these against the publisher terms when adding or updating a
release. Eora inventory downloads remain withheld; GTAP exports contain public
classification metadata only. Do not add economic coefficients or raw licensed
observations to public assets.

After updating a catalogue::

    python doc/scripts/build_download_metadata.py --jobs /private/tmp/mario-download-jobs.json
    node doc/scripts/prepare_download_workbooks.mjs /private/tmp/mario-download-jobs.json /private/tmp/mario-download-workbooks
    node doc/scripts/build_classification_concordances.mjs

Use the Artifact Tool runtime for the Node authoring commands. Preview and
check the generated files before copying them to the manifest's original paths.
The native-workbook serializer appends or replaces only the authored Read me
sheet; original worksheets, tables, strings and formula caches are copied
verbatim. This also preserves the legacy inventories the import engine cannot
handle efficiently.
The edited XML parts retain namespace declarations, including prefixes referenced
only by Excel compatibility attributes. Removing these declarations can trigger
Excel's repair prompt even when the ZIP and XML are otherwise readable.

Sphinx publishes code-only notebook copies, with source terms and portable
example links. It strips saved results, execution metadata and literal local
paths from downloads and source copies; the original guide notebooks stay
intact. Browser CSVs export selected MRIO results with one value/unit pair and
source notices. References stay in charts and publisher links. PNG/JPG exports
retain source credit. The electricity comparison exports credited figures rather than a mixed-licence
emission-factor CSV; its publication and source repository remain linked.

Before release, run ``tests/docs/test_downloads.py`` and
``tests/docs/test_download_export.cjs``, a strict Sphinx build, and real browser
download checks. Remove superseded assets from an incremental preview too:
Sphinx does not automatically delete every old static file.
