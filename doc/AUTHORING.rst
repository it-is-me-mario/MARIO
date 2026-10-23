Writing MARIO documentation
===========================

Web pages and executable notebooks have different jobs. Author the web page in
RST; keep the notebook as a downloadable companion. Do not paste a notebook's
full cell sequence or cached tables into the page.

Page types
----------

* **Guide:** one operation, minimal call, expected result, choices, next step.
* **Explanation:** assumptions, equations, interpretation and limits.
* **Worked example:** question, exact inputs, selected figure or result, stages,
  and a notebook for the complete execution.
* **API reference:** full signature, arguments, returned objects and constraints.

A public feature needs a guide in its topic, even when a worked example also
uses it. Link the guide, example and API in both directions. Keep Get started
focused on the first successful workflow and core concepts.

Page structure
--------------

Put ``:page-type:`` and a one-sentence ``:summary:`` before the title. State any
prerequisite that determines whether the first call works. Show the useful
result early; avoid opening with a long argument inventory.

Use the existing components selectively:

* ``mario-recipe`` container: short code example with a nested ``mario-result``.
* ``mario-cards``: independent choices or different questions, not paragraphs
  arbitrarily split into boxes.
* ``mario-steps``: actions that must happen in order.
* ``mario-details``: optional variants and technical explanations. Keep required
  inputs, material limitations and interpretation cautions visible.
* ``mario-switch``: mutually exclusive workflows such as IOT versus SUT.

Use short, descriptive headings that name the operation or information.
Avoid slogans, metaphors and rhetorical labels. Prefer two or three decisions
to an exhaustive option table. Name the units and axes when explaining a result.
Use figures to explain an actual result, with captions describing its scope.

Executable companions
---------------------

RST pages keep the existing document names to preserve published URLs. Some
legacy names therefore still live under ``notebooks/parsers`` or ``advanced``.
The topic navigation in ``source/conf.py`` determines where they appear.

Place the matching ``.ipynb`` beside its ``.rst`` page and add a download link
inside a ``mario-companion`` container. The paired file is registered
in Downloadable material automatically. Sphinx excludes notebooks as web
sources; ``mario_downloads.clean_notebook`` removes cached results and local
paths and retains source attribution in published downloads.

Maintain the page and its companion together when changing a call or scientific
assumption. Short guides can omit optional steps, but must not contradict the
complete notebook. Examples need defined selectors and explicit source inputs.

Verification
------------

Build with warnings treated as errors::

   python -m sphinx -b html -W --keep-going doc/source /tmp/mario-docs

Run the relevant ``tests/docs`` checks and execute small guide examples on the
packaged tables. Source-specific examples require their stated external files;
do not imply they were rerun when only their API signatures were checked.
Check internal links, companion downloads and source notices. Inspect the
rendered layout on desktop and a narrow viewport, including disclosures and
navigation. Keep existing source/licence notices with database documentation.
