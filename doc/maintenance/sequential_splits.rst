Sequential split verification
=============================

For changes to the sector-step controller or its public arguments, run::

   python -m pytest tests/ops/test_add_sector_plan.py tests/ops/test_sector_step_failures.py tests/ops/test_add_sector_steps.py
   python -m pytest tests/docs/test_api_reference_docs.py

Use portable synthetic flows. Verify a failure before the first accepted
step, a failure after the last accepted step, an all-failed pass, group
atomicity, dependent-parent blocking and a resumed deferred supplier.
Check exact source/input preservation and prior refinement as well as the
attempt count. Unknown/schema/export errors must not become skipped solves.
Failure journals must not modify committed checkpoint files.

The public guide is
``doc/source/user_guide/transformations/intermediate_sector_steps.rst``;
the parameter contract is owned by ``Database.add_sectors`` and its API
reference page. Keep the ordinary stop-on-failure default covered. Solver
fixtures may be optional; report skipped solver checks explicitly. Review
the guide and API in a warnings-as-errors Sphinx build. This check requires
no project database or large MRIO run.

For intermediate-prior construction changes, also run::

   python -m pytest -q tests/ops/test_conservative_split_priors.py tests/ops/test_split_model.py

Verify family-block conservation across origins/destinations and multiple
siblings, retention of compatible fine recipe references, zero-output/support
cases and unchanged signed accounts, targets and masks. Use an explicit legacy
control for a real-data comparison with identical objective, solver and prepared
inputs. Prior revision changes must not silently resume older completed steps.

For inventory-driven planning, verify chains in both directions, weighted cycle
breaking, strict user precedences, joint groups and parent dependencies. Compare
uncompressed XLSX archive parts before and after: replacing an existing plan
must change only its worksheet part; adding the sheet may also change the three
workbook relationship/content-type parts. Preserve formulas and unrelated user
sheets exactly. Test atomic-write failure and concurrent edits. Execution must
honour a manually revised sheet without recalculating the plan. None of these
planning checks requires CVXLab or an optimisation solve.

For changes to pre-optimization output checks, also run::

   python -m pytest -q tests/ops/test_split_flow_scenario.py tests/ops/test_sector_step_failures.py

Cover a fully allocated parent after preceding sibling steps. The early
child-versus-parent check and the residual cleanup must use the same
numerical bound, including allocations from the checkpoint history. Named
models also use their existing absolute diagnostic tolerance as a floor;
aggregation of external targets need not agree to machine precision with
the residual subtraction. Preserve the child observations exactly, report
each residual removed in ``output_roundoff.json``, and retain regressions
for a substantive excess and the unchanged legacy zero-tolerance default.
Do not edit a committed checkpoint or rewrite input targets to work around
an accumulated subtraction error. The observed sequential RBR case belongs
in the numerical regression fixture, rather than in public API examples.
The PLSR aggregate-boundary fixture additionally verifies that a sub-dollar
target difference cannot stop a named-model run before the solver.

For optional LP preflight changes on resume, the solver-free checks are::

   python -m pytest tests/ops/test_resume_preflight_options.py

Keep mathematical controls protected when allowing a different preflight
switch or LP solver. Record those diagnostic changes separately from an
objective transition, including in the run report when no step is accepted.
Do not weaken model-definition fingerprints or modify committed checkpoints.
