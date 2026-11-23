mario.Database.add\_sectors
===========================

.. currentmodule:: mario

For sequential IOT splits, checkpointing and numerical result handling, see
:doc:`../user_guide/transformations/intermediate_sector_steps`.

Prepare the editable worksheet with
:meth:`Database.get_add_sectors_intermediate_steps_plan`. Execution reads the
saved sheet and does not automatically regenerate its order.

With ``intermediate_steps=True``, ``on_step_failure="raise"`` stops at the
first failed optimisation. ``on_step_failure="continue"`` keeps its sectors
in their parents and attempts the following group, retaining the original
inventories and targets. Each group is attempted once per call.

On resume, the optional LP controls ``check_feasibility`` and
``feasibility_solver`` in ``split_model_options`` may change without
``allow_model_change=True``. Disabling the preliminary LP does not relax the
main optimization constraints or its result acceptance. The run report and
checkpoint history record preflight changes separately.

Named models default to ``intermediate_prior_policy="conservative"`` inside
``split_model_options``. This changes intermediate-flow references, while
retaining the selected objective and constraints. ``"legacy"`` is available
for controlled comparisons. The guide describes conservation, support conflicts
and the requirement to rebuild checkpoints after changing this policy.

For named models, the pre-solver output check uses the existing absolute
numerical tolerance (default ``1e-6`` in original monetary units) together
with the floating-point subtraction bound. A negative residual within that
band becomes zero while the supplied child target stays exact. Such cases
are recorded in ``output_roundoff.json`` and the reaggregation diagnostics;
the optimizer's constraints and tolerances are unchanged.

.. automethod:: Database.add_sectors
