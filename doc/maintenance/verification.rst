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
For format/nomenclature changes, also verify IOT/SUT block selection, keyboard
activation and old Nomenclature/technology-assumption URLs with their fragments.

Run existing tests relevant to the change. For public APIs or notebook downloads::

   python -m pytest tests/docs/test_api_reference_docs.py
   python -m pytest tests/docs/test_downloads.py

For database profiles, concordances or aggregation, use the matching tests in
``tests/core/test_database_profiles.py``, ``tests/api/test_concordances.py`` and
``tests/api/test_classification_aggregation.py``. Explorer changes also have
Python and Node checks under ``tests/docs/``; select the affected component.
Do not rerun every real database for a wording-only edit.

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

Rendered review
---------------

Serve the built site locally::

   python doc/scripts/serve_preview.py /tmp/mario-docs-review --port 8765

Open ``http://127.0.0.1:8765``. For affected pages:

* Reach the feature through its topic menu, then follow its API/example links.
* Inspect desktop and narrow layouts. Check heading hierarchy, code overflow,
  tables, figures and the visibility of prerequisites and interpretation limits.
* Open disclosures with mouse and keyboard; test deep links into them.
* Download a companion and confirm it is the intended notebook. For changes to
  download cleaning, inspect code, source notices and removal of saved results.

A local build is not an online deployment. Report the preview location and
verification limits accurately; publishing is a separate task.
