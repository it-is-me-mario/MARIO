Documentation maintenance KB
============================

This is the repository's internal guide for contributors and coding agents.
It is versioned with the code and is not part of the published user manual.
Start here when a change affects public behaviour or documentation.

Maintenance references
----------------------

* `Authoring rules <../AUTHORING.rst>`_: page types, writing, visual components
  and downloadable notebooks.
* `Change map <change-map.rst>`_: where a fact belongs and what must be reviewed
  together when it changes.
* `Verification <verification.rst>`_: build, link/download checks, example
  validation and visual review.

Update workflow
---------------

1. **Identify the change.** Locate the implementation or source metadata, then
   select the relevant rows in the change map. Search the repository for the
   affected API name, document name or database family to find additional uses.
2. **Choose the main page.** A task belongs in its topic guide; signatures and
   complete parameter definitions belong in the API reference. An example
   links to these pages and demonstrates their use.
3. **Update connected content.** Review the guide, API, notebook, topic index,
   navigation and generated assets listed in the map. Change only the affected
   items, but account for each one; do not add duplicate explanations.
4. **Verify the result.** Follow the verification checklist. Inspect rendered
   pages when layout or navigation changes. Verify downloads as well as pages.
5. **Record the outcome.** In the change report, name the updated entry point,
   checks run and any unverified examples. If the maintenance process changed,
   update this KB in the same change.

Use this small checklist in the task or review notes; do not commit a new copy
for each edit:

* Main guide and API reference reviewed.
* Existing examples and notebook companions reviewed.
* Topic index, sidebar, search and old URLs checked if affected.
* Shared metadata and generated assets reviewed if affected.
* Relevant examples, build and download/link checks completed.
* Visual review completed if affected; remaining limits stated.

Established decisions
---------------------

* Keep **Get started** focused on installation, first use and core concepts.
  Advanced features belong in Docs; do not expand onboarding into a catalogue.
* Organize Docs by user task, not by the historical location of a source file.
  Structural path analysis, for example, has an analysis guide as well as a
  separate worked example.
* Author web pages in **RST**. Keep database test/parser notebooks downloadable
  from the relevant guide and Downloadable material. Do not delete a notebook
  when replacing its rendered page.
* Put the minimal call, expected result and required inputs first. Use short,
  descriptive headings. Keep scientific limitations visible; optional detail
  may be collapsed. Do not turn every paragraph into a card.
* Use actual Sphinx links for API mentions, with concise code-style labels such
  as ``db.get_concordances()``. Let the theme supply their visual treatment.
* Preserve published document paths, or add a deliberate redirect. A move in
  the menu does not require a move on disk.

Keeping the KB current
----------------------

Maintain one authoring policy and one change map. Link to specialized generator
instructions instead of copying them here. Add a new map row when a new feature
has a different maintenance route; update existing rows when files move.

Do not store transient branch status, personal paths, credentials, source data,
database counts or current function signatures here. Read those from the
repository or the relevant data snapshot when working on them. Wording-only
edits do not need a KB entry unless they establish a reusable rule.
