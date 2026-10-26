Documentation verification
==========================

Run commands from the repository root, using an environment with MARIO and
``doc/docs-requirements.txt`` installed. Use the supported Python version in
the project's packaging configuration. No real database is needed for a
documentation build or the structural checks below.

Build and structural checks
---------------------------

Build with warnings treated as errors, then check the built guides::

   python -m sphinx -b html -W --keep-going doc/source /tmp/mario-docs-review
   python doc/scripts/check_documentation.py /tmp/mario-docs-review

Use a new output directory after moving/removing pages or assets. ``-E -a``
rebuilds Sphinx documents but does not delete obsolete published files.

The checker discovers Get started, guide/parser pages and notebook companions from the
source tree. It checks built pages, sidebar membership, local links and anchors,
guide downloads, the shared download list, output-free notebook copies with
source notices, and absence of raw notebook sources. It does not execute examples,
check external URLs or assess scientific correctness and visual quality.
For format/nomenclature changes, also verify IOT/SUT/NAM block selection, keyboard
activation, flow/coefficient switching and old Nomenclature/technology-assumption URLs with their fragments.
Check NAM diagram links against the runtime domains and ensure that derived
views/results and alternative import authorities are not presented as additive
flow blocks (``tests/docs/test_table_formats.py``). Check lowercase coefficient
deep links, the muted palette, native descriptors and unsupported final-demand
coefficient cells. Verify API table-format filters and badges on both shared
block names and format-specific standalone functions.
For NAM, follow a generic inspection/scenario/template/export link as well as
the format page. Check actual facade signatures, available versus registered
blocks, fixed baseline naming and guarded IOT/SUT operations. API filtering
must include supported NAM parser/template entry points without advertising
guarded query, transformation or export methods.
Classify API index entries by their canonical document/symbol identity, not
their displayed heading: some function-page titles omit the module prefix.
Check that template generation remains visible under the NAM filter.

Run existing tests relevant to the change. For public APIs or notebook downloads::

   python -m pytest tests/docs/test_api_reference_docs.py
   python -m pytest tests/docs/test_downloads.py

For database profiles, concordances or aggregation, use the matching tests in
``tests/core/test_database_profiles.py``, ``tests/api/test_concordances.py`` and
``tests/api/test_classification_aggregation.py``. Explorer changes also have
Python and Node checks under ``tests/docs/``; select the affected component.
Do not rerun every real database for a wording-only edit.

Internal NAM proposal
---------------------

For changes to ``doc/development/nam/catalogue.json``, regenerate and check
the internal matrix list::

   python doc/scripts/check_nam_spec.py --write
   python doc/scripts/check_nam_spec.py

``mario/model/nam_schema.json`` owns the implemented block domains, roles and
import authority. The development JSON retains conversion proposals;
the checker requires its structural definitions to match the runtime contract.
Do not edit its generated ``catalogue.rst`` by hand. The checker uses
the standard library and does not import MARIO. It checks structural
consistency, including duplicate ownership of accounting cells, but does not
execute a NAM parser or validate real-source balances. Run the internal core
checks and affected IOT/SUT regressions with a working MARIO environment::

   python -m pytest tests/core/test_nam_core.py tests/parsers/test_nam.py tests/compute/test_compute_catalog.py tests/compute/test_resolver.py tests/api/test_dataset_model.py
   python -m pytest tests/parsers/test_figaro_parser.py tests/parsers/test_write_parse_template.py

The core tests use portable synthetic flows and require no source workbook.
They check set-scoped identity, explicit missing/zero states, native layouts,
exclusive import authority, separate resident/nonresident financial results
and scenario cache invalidation. For account-normalization changes, check full
paying-account denominators across blocks, retained native descriptors,
inactive versus signed-cancelling zero accounts, both import authorities,
per-set missing-data coverage and scenario cache invalidation. A balanced
source must give equal receipt and expenditure totals; an unbalanced fixture
must retain the documented expenditure convention. The version 2 workbook also preserves typed
item metadata and explicitly rejects version 1; check this migration message
when changing the native contract. Imports stay in their dedicated trade set,
including when a payment passes through an investment routing pool in Other.
The NAM parser tests use small, synthetic T02 sources, including routing and
adjustment accounts, and test native template/export round trips. Bulk CSV
checks must separate the selected national ledger from foreign import origins,
reject duplicate keys even across chunks, retain wholly zero accounts from the
packaged source classification, and reject a missing/multiple-country selection.
For a matching national workbook and bulk release, compare every native block
and ``T``; align omitted zero origin/product rows before comparing native import
frames. Export totals already present in the national square must not be counted
again from outgoing bilateral rows. A real-source
check still needs a local FIGARO-NAM file. ``parse_figaro(..., table="NAM")``
compares every normalized national-square cell with the source and reports
the reconciliation in ``nam.info["figaro_nam"]``. This does not certify a SUT
valuation bridge or financial/nonfinancial reconciliation. Check retained
origin/product attribution, external settlements and source controls, then
export/reload and compare the native flows as well as ``T``.

For exploratory NAM-to-SUT checks, match publication/revision as well as
country and reference year; a current API cache may postdate the NAM release.
Identify an edition through a versioned source download and compare it with
the cache, rather than inferring the edition solely from an API update date.
Start with unchanged native supply/use blocks and compare raw source cells
before investigating final-demand or trade projection rules.
Compare domestic uses with domestic uses, normalize classification spellings,
and select activities from their declared classification (a code beginning
with ``P`` can still be an activity). Check product and activity balances,
full cells and component totals separately: similar national totals can hide
large differences in allocation. Keep import use, direct final-demand taxes
and non-product external settlements explicit. Regroup split primary-income
components without adding a parent aggregate twice. An internally balanced
projection does not establish equality with an independently revised SUT.

For the supported projection, run ``tests/ops/test_nam_to_sut.py``. Check
unchanged S/U, separate direct taxes/imports/settlements, typed investment
routing, source units and codes, required missing inputs, and native reloads.
Verify all scenarios through both national SUT output and explicit SUT-to-IOT
composition for A/B/C/D; preserve edits and source imbalance without balancing.
Exercise multi-ledger selection and unrelated missing financial accounts.
The original import audit must remain separate from current projection checks.
Do not infer support for other sources or import authorities from a successful
FIGARO run.

For NAM reference changes run ``python doc/scripts/generate_nomenclature_tables.py``
and inspect the generated NAM tables together with the format/source guides.
The JSON owns implemented structural metadata; the internal proposal stays
separate from the public manual.

Example verification
--------------------

* Execute changed minimal examples against packaged IOT/SUT fixtures where
  possible. Check outputs, units and axes, not just absence of exceptions.
* Source-specific calls need the stated release, files and options. When those
  inputs are unavailable, check signatures and data requirements and explicitly
  report that full execution was not performed.
* Check that notebook variables are defined in execution order and selectors
  match the intended source. Retain portable paths and input/licence guidance.
* After scientific changes, reconcile affected equations, examples, figures and
  captions. State characterization, allocation and numerical limits where relevant.
* For regional footprints, verify producer and consumer attribution on a small
  cross-border example; a conserved global total can hide incorrect geography.
  For chained scenario workflows, execute the sequence through transformations
  that consume only the baseline or discard other scenarios, and check that
  earlier updates survive.
  ``tests/docs/test_workflow_examples.py`` executes the affected RST recipes
  and notebook calculations on small accounting/scenario fixtures. Run it
  when changing those examples; source-database and live-provider runs remain
  separate checks.

NAM recipes in the same test module execute the published account-total,
scenario-edit, native-export and template code with portable inputs. Keep
web and notebook examples paired. In mixed FIGARO companions, execute the
local NAM section independently of IOT/SUT API sections when only NAM files
are available, and report the distinction. Compare native flows, descriptors,
metadata, scenarios and recomputed coefficients after Excel reload. Source
reconstruction, source account imbalance and balance of a manually edited
scenario are different checks; do not treat a preserved import audit as a
fresh certification of edited values.

Rendered review
---------------

Serve the built site locally::

   python doc/scripts/serve_preview.py /tmp/mario-docs-review --port 8765

Open ``http://127.0.0.1:8765``. For affected pages:

* Reach the feature through its topic menu, then follow its API/example links.
* Inspect desktop and narrow layouts. Check heading hierarchy, code overflow,
  tables, figures and the visibility of prerequisites and interpretation limits.
  For shared-width changes compare a format guide, a Docs task guide and the
  Database explorer; check both the page-menu and side-contents breakpoints.
  A wide NAM diagram may scroll within its frame, without widening the page.
* Open disclosures with mouse and keyboard; test deep links into them.
* Download a companion and confirm it is the intended notebook. For changes to
  download cleaning, inspect code, source notices and removal of saved results.

A local build is not an online deployment. Report the preview location and
verification limits accurately; publishing is a separate task.
