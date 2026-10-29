Sequential split verification
=============================

For changes to the sector-step controller or its public arguments, run::

   python -m pytest tests/ops/test_sector_step_failures.py tests/ops/test_add_sector_steps.py
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

For changes to pre-optimization output checks, also run::

   python -m pytest -q tests/ops/test_split_flow_scenario.py tests/ops/test_sector_step_failures.py

Cover a fully allocated parent after preceding sibling steps. The early
child-versus-parent check and the residual cleanup must use the same
floating-point error bound, including allocations from the checkpoint
history. Preserve the child observations exactly, remove only a residual
within that bound, and retain a regression for a substantive budget excess.
Do not edit a committed checkpoint or rewrite input targets to work around
an accumulated subtraction error. The observed sequential RBR case belongs
in the numerical regression fixture, rather than in public API examples.
