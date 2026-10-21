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
| `Split_sectors_MRIO_KL` | Complete KL on Z; prior-sign KL on Y | KL on nonnegative factors; positive/negative components for TTM/Tax | Regularised entropy model |
| `Split_sectors_MRIO_quadratic` | Complete weighted squared differences on Z/Y | Weighted squared differences, with factor-type domains | QP used for the next monetary experiments |

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
    "add_sectors.xlsx", split=True,
    split_model_options={
        "model": "Split_sectors_MRIO_quadratic",
        "accounting": "inherit",
        "final_demand_weight": 0.1,
        "compact_constraints": True,
        "scale": 1000.0,
    },
)
```

The old `flow_loss`, `value_added_loss`, `complete_intermediate_priors` options
still select the corresponding explicit folder. A named model plus conflicting
loss settings is rejected. Weights, the scale-covariant numerical support floor
and tolerances are data, stored in input tables (`Model_controls`, `tol`), not
substitutions into objective strings. A zero loss weight omits that term and its
implicit entropy domain; it does not impose a zero target.

`model_definition.json` in the generated run directory records the selected
folder/workbook, formulation revision and hashes. Checkpoint state carries this
definition and revision. Historical checkpoints remain readable; resuming an
old experimental checkpoint with the new V domains is rejected rather than
silently changing the problem midway through a staged split.

## Maintaining these models

`split_operators.py` implements the named numerical operators used by the
workbooks. `build_split_templates.py` is a **developer-only authoring tool** for
the checked-in workbooks. Run it explicitly after editing its specification,
inspect the resulting workbook changes and run the template/model tests. The
solver/bridge never invokes it. This keeps every supported formulation visible
in this folder, including its strict/inherited/compact constraint profile.
