# CVXLab model catalogue

Each folder contains an inspectable formulation, including `model_settings.xlsx`,
operators, constants and mapping. MARIO **selects and copies a workbook**; it
does not construct or rewrite objective/constraint formulas during a run.
The compatibility adapter may remove an unsupported schema column for older
CVXLab versions; it does not select a different mathematical formulation.

## Main IOT / MRIO choices

| Folder | Intermediate flows / Y | Value added | Use |
|---|---|---|---|
| `Split_sectors` | Historical partial relative entropy | Historical prior-sign relative entropy | Unchanged reference when `split_model_options=None` |
| `Split_sectors_staged` | Historical model + explicit staged Y/refinement rules | Historical prior-sign relative entropy | Staged historical reference |
| `Split_sectors_MRIO_KL` | Complete KL on Z; prior-sign KL on Y | KL on nonnegative factors; positive/negative components for TTM/Tax | Preferred first insertion model |
| `Split_sectors_MRIO_quadratic` | Complete weighted squared differences on Z/Y | Weighted squared differences, with factor-type domains | Alternative after entropy attempts fail |

The `Split_sut*` folders retain their existing SUT formulations. The new factor
domains below apply to the **MRIO templates**, not to those SUT models or the
historical reference. Existing databases are never changed by selecting a model.

The remaining MRIO folders expose the previously available mixed-loss and
partial-prior combinations. `split_models.json` lists every combination and is
the runtime lookup, not a formula generator:

| Folder suffix after `Split_sectors_MRIO_` | Z/Y loss | V loss | Complete Z priors |
|---|---|---|---|
| `KL` | KL | KL components | Yes |
| `kl_V_legacy` | KL | Relative-entropy components | Yes |
| `kl_V_quadratic` | KL | Quadratic | Yes |
| `quadratic` | Quadratic | Quadratic | Yes |
| `quadratic_V_legacy` | Quadratic | Relative-entropy components | Yes |
| `quadratic_V_signed_kl` | Quadratic | KL components | Yes |
| `partial_entropy_V_legacy` | Historical partial entropy / signed Y KL | Relative-entropy components | No |
| `partial_entropy_V_signed_kl` | Historical partial entropy / signed Y KL | KL components | No |
| `partial_entropy_V_quadratic` | Historical partial entropy / signed Y KL | Quadratic | No |

`value_added_loss="legacy"` in an MRIO folder selects the relative-entropy
criterion, **with the new factor-type domains**. Exact historical sign behaviour
is available in the first two historical folders, not implied by that loss name.

## Workbooks within each MRIO folder

- `model_settings.xlsx`: inherited row/column accounting.
- `model_settings_strict.xlsx`: strict accounting with the original bands.
- `model_settings_compact.xlsx`: inherited accounting, compact structural-zero
  constraints and exact aggregate preservation (requires eps=0).
- `model_settings_strict_compact.xlsx`: strict accounting with compact zero masks.

All workbooks retain the two trade tolerance bands; at delta=0 they describe an
equality. There is no runtime replacement of those expressions with an equality.
Staged Y masks are explicit in the workbooks and filled only for staged runs.

`model_settings.xlsx` is the default **file within a chosen MRIO folder**.
The public `accounting` option still defaults to `strict`, and selects the
explicit `_strict` workbook. No default accounting policy has been changed.

## Recommended execution order

Prefer `Split_sectors_MRIO_KL` for the first insertion group, and
`Split_sectors_MRIO_partial_entropy_V_signed_kl` for subsequent insertions that
refine inventories from completed groups. Try `Split_sectors_MRIO_quadratic`
only after the preferred entropy formulation fails. These are distinct objectives.

MOSEK is the preferred entropy solver, with Clarabel and SCS available as open
alternatives. Gurobi is preferred for a pure quadratic objective; MOSEK, Clarabel
and OSQP remain alternatives. Gurobi cannot solve the exponential cones produced
by these entropy atoms through the current CVXPY interface. When `solver=None`,
MARIO selects the first installed compatible solver in these orders. Direct calls
use one formulation/solver; the Database disaggregation pipeline orchestrates
recorded retries and model fallback through its entropy-first policy.

## Factor-type domains

- **Capital and Labor:** V ≥ 0. Other non-Tax/non-TTM factors also default to a
  nonnegative domain, supporting custom aggregated value-added fixtures.
- **TTM and Tax:** net V is free to take either sign, including crossing the
  prior's sign. Existing aggregate-consistency and structural-zero constraints
  still apply. A structural zero is not an unconstrained missing observation.
- **Quadratic V:** penalise the net deviation from the supplied prior, with no
  sign-of-prior constraint on TTM/Tax.
- **Entropy V:** TTM/Tax = `V_signed_positive − V_signed_negative`, both components
  nonnegative. Penalise each component against `max(prior,0)` / `max(-prior,0)`
  plus numerical support. This is convex and permits either net sign; it is
  different from the old fixed-prior-sign entropy. Positive and negative
  components are auxiliary accounting variables, not new observations.

Negative priors for nonnegative factors cause an explicit error in entropy
models, rather than silently taking an absolute value. Quadratic models can
retain such a reference in the objective while imposing V≥0. Source preparation
and its audit remain responsible for explaining a conflicting reference.

## Selection and numerical controls

```python
db.add_sectors(
    "add_sectors.xlsx", split=True, solver="MOSEK",
    split_model_options={
        "model": "Split_sectors_MRIO_KL",
        "accounting": "inherit",
        "final_demand_weight": 0.1,
        "compact_constraints": True,
        "scale": 1000.0,
    },
)
```

For all MRIO entropy/relative-entropy terms, `Entropy_floor` is derived from
the actual references in enabled losses. Let `m` be the smallest nonzero absolute
monetary prior before numerical scaling. The support is
`10 ** (floor(log10(m)) - 4)`: `m=0.03` yields `1e-6`. Signed priors contribute
their magnitude; zeros, masks, controls, targets and disabled losses are excluded.
One common coefficient is recomputed per step, then divided by `scale`.
`entropy_support.json` records the rule, participating tables, minimum, exponent
and both coefficients. All-zero references and unrepresentable/nonfinite support
raise explicit errors. The support is additive in references, not a weight or
lower bound on fitted values, and does not release structural zeros.

The quadratic normalisation retains its separate `Reference_floor` of
`1e-8/scale`; this change does not reweight the quadratic objective. The original
historical `Split_sectors` and SUT formulations retain their own numerical rules.

`require_finite_objective=True` rejects an infinite/NaN objective even when affine
residuals pass. The entropy-first pipeline enables it, so numerical negative
entropy operands trigger a solver retry without clipping values. The default
False retains the earlier residual-only compatibility behaviour for direct calls,
with the nonfinite objective still reported explicitly.

The old `flow_loss`, `value_added_loss`, `complete_intermediate_priors` options
still select the corresponding explicit folder. A named model plus conflicting
loss settings is rejected. Weights, the scale-covariant numerical support floor
and tolerances are data, stored in input tables (`Model_controls`, `tol`), not
substitutions into objective strings. A zero loss weight omits that term and its
implicit entropy domain; it does not impose a zero target.

`model_definition.json` in the generated run directory records the selected
folder/workbook, formulation revision and hashes. Checkpoint state carries this
definition and revision. Historical checkpoints remain readable; the new entropy-support revision
requires a fresh experiment or the exact recorded old code for replay.

For pending steps of a new experiment, `allow_model_change=True` on
`add_sectors(..., intermediate_steps=True)` explicitly permits changing only the
named objective. Accounting, weights, scale, feasibility policy, satellite policy
and completed inventory fingerprints must remain identical. The previous model
definition is verified, and `model_history` records the actual model and solver
per step. The flag defaults to False; ordinary model changes remain rejected.

## Maintaining these models

`split_operators.py` implements the named numerical operators used by the
workbooks. `build_split_templates.py` is a **developer-only authoring tool** for
the checked-in workbooks. Run it explicitly after editing its specification,
inspect the resulting workbook changes and run the template/model tests. The
solver/bridge never invokes it. This keeps every supported formulation visible
in this folder, including its strict/inherited/compact constraint profile.


### Fixed-prior KL numerical representation

The explicit MRIO KL operators evaluate fixed-prior KL as
`-entr(x) - (log(q) + 1)*x + q`, with `q` the strictly positive,
numerically supported reference. This is exactly
`x*log(x/q) - x + q`, including the continuous extension at `x=0`,
and preserves the domain `x >= 0`. Computing the constant `log(q)` before
canonicalisation avoids placing tiny prior values directly in exponential-cone
coordinates. No prior, adaptive-support coefficient, weight or physical constraint
is altered. Negative entropy operands remain outside the domain and are not
clipped during verification. Relative-entropy/legacy operators are unchanged.

This representation addresses a reproducible MOSEK `UNKNOWN` failure with
references as small as `1e-25` in scaled units; it does not guarantee convergence
on every dataset. Failed attempts must remain visible. The model revision is
`constant-reference-kl-v3`; earlier checkpoints retain their original model
fingerprints and cannot silently resume under changed operator sources.

See the [CVXPY atom definitions](https://www.cvxpy.org/functions/index.html)
and [MOSEK entropy and relative-entropy representations](https://docs.mosek.com/modeling-cookbook/expo.html).
