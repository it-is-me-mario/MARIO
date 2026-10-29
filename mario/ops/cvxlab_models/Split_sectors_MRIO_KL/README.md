# Split_sectors_MRIO_KL

## Optional numerical result cleanup

Use `split_model_options.solution_cleanup = "postprocess"` to save an `optimal`
solver point after deterministic sign/zero projection. This mode has no dollar
cutoff on corrections or accounting/reaggregation residuals. All residuals are
reported using the original reference precision; they do not block export.
The output is marked `postprocessed_pending_review`, with raw and cleaned points
retained and economic review pending. Nonfinite data and incompatible axes still
fail reconstruction; other solver statuses remain distinct.

An explicit saved-point execution can restore a previous optimal point after
checking identical CSV inputs, templates, set tables and variable coordinates.
It uses the same MARIO/CVXLab reconstruction and evaluates constraints/objective
without calling an optimizer. Its separate provenance records the original solve.

### Earlier bounded experiment

`split_model_options.solution_cleanup` is disabled by default. When explicitly
selected, it contains `max_cell_adjustment`, `absolute_tolerance` in original
monetary units, and `relative_tolerance`. After MOSEK returns, MARIO projects
forbidden signs and structural zeros, rejecting the entire projection if any
single adjustment exceeds its limit. Legitimate negative Y and signed Tax/TTM
are retained. This adds no objective or optimization constraints and leaves
CVXLab unchanged.

MARIO archives both raw and cleaned points, a cell-level correction audit and
all constraint residuals. The KL objective is reevaluated at the cleaned point.
Approximate acceptance applies the declared tolerance to model constraints and
monetary reaggregation/accounting checks; fixed X and sign checks retain their
strict checks. The old strict residual count is still reported. An accepted
cleaned database is an approximate result, not a certificate of KL optimality.

The full formulation is in the model_settings workbooks here. See the [model catalogue](../README.md) for losses, factor domains, accounting profiles and numerical controls. The bridge copies the selected workbook without rewriting its formulas.

Preferred model for the first insertion group; use MOSEK first, with Clarabel/SCS as alternatives.

The KL operators use `maximum(reference, Entropy_floor)`, without adding the
floor to positive references. Signed Y is evaluated on its sign-adjusted
nonnegative magnitude. Tax/TTM use separate positive/negative components with
their own floored references; Capital/Labor remain nonnegative.

The optional `split_model_options["prior_zero_tolerance"]` enables the controlled
prior-filter experiment for this full KL template. In original monetary units,
only enabled objective priors with absolute value strictly below the threshold
are zeroed, then `Entropy_floor = prior_zero_tolerance * 1e-2`. Signed Y references
retain their original domain sign even below the threshold. V0 remains a signed
net reference; flooring occurs in its component losses. Baseline flows, targets,
accounting residuals and zero/sign masks are not modified. All processing occurs
before numerical unit scaling and is recorded in `prior_preparation.json/.csv`
and `entropy_support.json`. Without this option, support retains its minimum-prior
rule. The operator revision differs from historical additive-support checkpoints.

Example for databases in M USD: `prior_zero_tolerance=1e-6` removes sub-USD prior
magnitudes and supplies a `1e-8 M USD` (one-cent) reference floor. The floor is
not a lower bound on final flows. Independent finite-objective and physical
constraint validation remain necessary even when the native solver says optimal.
