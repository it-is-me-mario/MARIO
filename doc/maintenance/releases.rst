Releases and publication
========================

Use this checklist for a package release or a public documentation deployment.
Read the actual repository configuration first: this page describes the checks,
not a permanent version number, branch state or credential location.

Confirm the release scope
--------------------------

1. Fetch remote branches and tags. Check the working tree, branch and open PRs;
   preserve unrelated work and use an isolated checkout when needed.
2. Compare the requested version with ``mario/version.py``, GitHub releases and
   the ``mariopy`` versions on PyPI. A published version cannot be reused for a
   new artifact. Resolve a conflicting requested number before tagging or
   publishing; continue independent preparation while awaiting clarification.
3. Review changes from the **previous published tag**, including changes already
   merged into main since that release. A diff against main alone can miss
   changes that belong in the new release notes.
4. Check main's current protection rules and required checks. Release
   authorization covers the normal publication workflow; a prior exception
   for a named PR is not a standing exception for future PRs. If a review
   bypass is needed and is not already authorized for this operation, prepare
   the verified PR and release artifacts first, then ask about that concrete PR.

Prepare source and notes
-------------------------

* Update ``mario/version.py``; packaging and Sphinx read it as their version
  source. Convert the relevant Unreleased entry in ``CHANGELOG.rst`` into the
  chosen release, with its actual publication date.
* Organize notes by user-facing importance: public capabilities first, then
  behaviour changes, documentation and compatibility. Review previous release
  boundaries so existing features are not presented as newly implemented.
* Use the documentation change map to check the guide, API, examples, notebook
  companions and generated metadata affected by each public change.
* Record newly learned **repeatable** release steps in this KB in the same
  change. Keep transient run logs, local paths, credentials and artifacts out
  of the KB. Extend an existing rule instead of adding duplicate checklists.

Verify before publication
--------------------------

* Run the test suite in a supported Python environment with the declared
  runtime dependencies. Investigate failures; distinguish code regressions,
  obsolete expectations and optional/external prerequisites with evidence.
  Do not silently deselect a failing required check.
  Preview-server tests need permission to bind loopback sockets. Reuse valid
  local data for optional integration tests where possible; do not trigger
  large downloads just to repair a missing fixture path. Sparse numerical
  fixtures must state their fill value explicitly, so pandas version defaults
  cannot turn structural zeros into NaNs in a reference calculation.
* Build Sphinx with ``-W --keep-going`` into a fresh directory and run
  ``doc/scripts/check_documentation.py``. Review representative desktop/mobile
  pages, navigation, old redirects and downloadable notebooks. Execute changed
  examples where their inputs are available; distinguish those runs from
  source inspection in the release report.
* Build a wheel and source distribution from a clean, identified source commit
  (for example, a ``git archive`` extraction). Validate both with
  ``python -m twine check --strict``. Build isolation is preferred; if using
  ``--no-isolation``, record and verify the build environment.
* Inspect **both** archives for required runtime data and unintended content.
  Concordances need the manifest and every referenced compressed bundle; test
  fixtures and other packaged resources must remain available. Exclude local
  API-key files and private source datasets. Never print credential contents.
* Install the wheel into an isolated destination and run from outside the
  checkout. Confirm the imported path and version; exercise public metadata
  lookups, bundled classifications, aggregation proposals and a packaged test
  database. Repository imports can otherwise hide missing package data.
* Generate SHA-256 checksums for the exact artifacts to publish. Keep release
  notes and PR bodies in UTF-8 files or structured arguments so shell quoting
  cannot alter their content.

Merge, publish and verify
--------------------------

1. Push the reviewed branch and create or update its PR with the final scope
   and validation. Check that the head SHA is the one reviewed and tested.
   Satisfy the repository's checks and review requirements, using any explicitly
   authorized exception only within its stated scope.
2. After merge, fetch main and verify its commit and tree. Tag the intended
   commit. Never silently retarget or overwrite a published tag. If the merged
   tree differs from the tested candidate, rebuild and rerun affected checks.
3. Prepare the GitHub release and attach the wheel, source archive and checksum
   file. Publish the same validated bytes to PyPI through the configured
   authenticated mechanism; keep tokens out of arguments, logs and committed
   files. A tag or GitHub release alone does not prove a PyPI upload succeeded.
4. Verify PyPI's version metadata, filenames and SHA-256 digests against local
   artifacts, and verify the GitHub release is public with the correct tag and
   assets. Report partial publication accurately if any destination fails.
5. Read the current documentation workflow and canonical URL. At present,
   ``.github/workflows/docs-pages.yml`` deploys main to GitHub Pages at
   ``https://www.marioproject.com/en/latest/``. Check the workflow run for the
   **merged commit**, wait for deployment success, and open representative
   public pages. Read the Docs and a local preview are separate build targets;
   do not assume either proves the canonical site has been updated.
6. Report the release, package and documentation links, verification results
   and any remaining limits. Clean up task branches/worktrees only when their
   work is safely integrated and cleanup is authorized.

Documentation-only publication uses the same source, link, deployment-commit
and live-page checks, without inventing a package-version bump or PyPI upload.
