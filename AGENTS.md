# Repository instructions

## Documentation maintenance

Before changing public APIs, parsers, database metadata, examples or the docs
site, read [the documentation maintenance KB](doc/maintenance/README.rst).
Use its change map to identify affected pages and downloads before editing.
Follow [the authoring rules](doc/AUTHORING.rst) for user-facing content.
For releases, merges and public deployments, also follow the
[release checklist](doc/maintenance/releases.rst). Record newly learned,
repeatable operational checks in the KB as part of the same change.

A feature must be discoverable from its topic guide and API reference; a worked
example alone is not sufficient. Keep database notebooks as downloadable
companions, with the web explanation in RST. Check the page, companion,
navigation and relevant generated assets together.

Use the KB's verification checklist before reporting completion. State which
examples were executed and which were only inspected. Update the KB in the same
change when page ownership, generators or verification commands change; keep
current values and API signatures in their canonical sources, not in the KB.
