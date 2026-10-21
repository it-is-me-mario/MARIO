Sequential IOT sector splits
============================

``intermediate_steps=True`` executes named sector groups in order. Every accepted
step becomes the baseline for the next one. This workflow currently supports
IOT workbooks whose Master rows are all marked ``Split``; each child needs a
parent present before its step. The ordinary single-call API is unchanged.

Create and edit a plan
----------------------

.. code-block:: python

   db.get_add_sectors_excel(
       path="add_sectors.xlsx",
       items=["Mining", "Refining"],
       intermediate_steps=True,
   )

Fill the inventories and split-support sheets as usual. In ``Intermediate
steps``, give each column a custom group name and list its sectors underneath.
Columns execute from left to right. Every Master sector must occur exactly
once. Several regions of the same sector belong to the same group.

.. code-block:: python

   db.add_sectors(
       "add_sectors.xlsx",
       split=True,
       intermediate_steps=True,
       save_intermediates="run/checkpoints",
       solver="CLARABEL",
   )

``save_intermediates`` is mandatory. ``eps`` must be zero: preceding flows must
be preserved, rather than relaxed as an observed target. ``delta`` retains the
ordinary split-model meaning. ``only_input_data_gen``, parent renaming and
``keep_all_split_steps=True`` cannot be combined with this workflow.

To execute only an initial part of the plan, pass ``stop_after_step="Mining"``
with the exact name of a pending group. MARIO saves that accepted checkpoint
and returns without starting subsequent groups. The complete original plan and
canonical inventories remain available, and ``remaining_add_sectors.xlsx``
retains the later groups for resumption. An unknown or already completed stop
name is rejected before starting a solve. Omitting the option executes every
pending group.

Inventory projection and preservation
-------------------------------------

The full workbook is the reference at the final sector classification. For a
step, references to future children are projected onto their current residual
parent. Newly coincident observations are summed. Partially overlapping
projected cluster constraints are rejected with an actionable error.

For previously added buyer sectors, canonical inventories are retained in the
checkpoint. When a new supplier is introduced, its finer input shares return
as conditional cross-entropy priors. The preceding parent-origin flow fixes
their total; it is not replaced by the original uncalibrated coefficient. The
conditional priors use the preceding origin distribution within an input-origin
cluster. These are estimation assumptions, not new observed bilateral flows.
Resolved nonnegative sector coefficients and the standard three-level IOT axes
are required for these deferred refinements. An aggregate inventory observation
does not identify shares within the group it denotes.

By default, each solved result is reaggregated to the preceding classification and checked
for Z, Y, V, E, X, EY and VY, with elementwise allowance
``1e-6 + 1e-8 * abs(reference)`` in each matrix's units. Supplied baseline
accounting residuals are preserved; they are not repaired. Order can affect the
final solution because earlier aggregates become binding constraints.
New child columns must also satisfy their own input/output accounting. Each
final-demand cell is split within its preceding sign domain: negative stock
changes remain permissible, while positive consumption cannot be offset by
negative child consumption. For nonnegative source Z/Y, new negative flows
below -1e-6 are rejected. Solver
statuses, including ``optimal_inaccurate``, are retained in the checkpoint;
acceptance also requires these independent numerical checks.

Experimental convex split options
---------------------------------

``split_model_options=None`` retains the packaged IOT model. Experimental
settings select explicit checked-in workbooks under ``mario/ops/cvxlab_models``;
objective and constraint formulas are not generated at runtime. Numerical weights
are input data. The supplied database and packaged workbooks are not rewritten. The same options work in a single IOT
split and in sequential groups. SUT experiments are not supported.

.. code-block:: python

   options = {
       "accounting": "inherit",
       "value_added_loss": "signed_kl",
       "final_demand_weight": 0.1,
       "complete_intermediate_priors": True,
       "check_feasibility": True,
       "scale": 1000.0,
   }
   db.add_sectors(
       "add_sectors.xlsx", split=True, intermediate_steps=True,
       save_intermediates="new_run/checkpoints", solver="CLARABEL",
       split_model_options=options,
   )

``accounting="inherit"`` replaces zero-discrepancy row/column equations with
explicit inherited targets. For each preceding sector, its row discrepancy
``sum(Z_row)+sum(Y_row)-X`` and column discrepancy ``sum(Z_col)+sum(V_col)-X``
are allocated to the child/residual-parent family by fixed output shares. A
zero-output family retains its discrepancy in the preceding parent. Their
aggregate is unchanged and no discrepancy is optimized. This is an explicit
allocation assumption, not a correction of the baseline. New discrepancies
are checked separately against ``1e-6 + 1e-8 * abs(X)``. Inherited accounting
requires ``eps=0`` and disables positive ``residue`` clipping.

``model="Split_sectors_MRIO_quadratic"`` or
``model="Split_sectors_MRIO_KL"`` selects a named packaged formulation.
The existing ``flow_loss``, ``value_added_loss`` and
``complete_intermediate_priors`` settings also resolve to explicit templates.
See ``mario/ops/cvxlab_models/README.md`` for the complete catalogue and workbook
selection. ``model_definition.json`` records the selected workbook and hashes.

In the MRIO templates, Capital and Labor (and other non-TTM/non-Tax factors)
are constrained nonnegative. TTM and Tax may take either sign, including
crossing a prior's sign, subject to aggregates and structural zeros. Quadratic
V penalises net deviations. Entropy V uses nonnegative positive/negative
components for TTM/Tax, while positive factors use ordinary nonnegative entropy.
The older prior-sign formulation remains in the historical reference template
selected by ``split_model_options=None``. Negative positive-factor priors are
rejected explicitly by entropy models; they are not silently converted.

These factor domains change the mathematical model. Historical checkpoints
remain readable, but cannot be resumed silently with the new experimental
formulation. Start a fresh controlled trial to use it.

``final_demand_weight`` (default 0) adds signed KL to a final-demand prior
constructed jointly from the preceding Y row and fixed output shares of the
child/residual-parent family. Each preceding Y cell is conserved in the prior,
independently of child order. A zero-output family retains its row in the parent.
This proportional allocation is not a new empirical observation.
``supply_weight`` (default 0) regularizes split-sector deliveries to stable
buyers using the same joint allocation of preceding Z rows. Reading these priors
from the legacy deterministic split would repeatedly reduce Y and duplicate
supplier rows when several children share a parent.
``complete_intermediate_priors=True`` additionally covers every free
intermediate-input cell once and uses supply weight 1 when none is specified.
Deferred supplier observations replace the corresponding supply priors instead
of adding a second loss on the same cells. Weights are modelling preferences,
not estimated sampling variances. Structural zeros are omitted from these KL
terms to avoid unnecessary exponential cones.

``flow_loss="quadratic"`` replaces KL on Z and Y with weighted squared
deviations and requires complete intermediate priors. Combined with quadratic
V it produces a QP, avoiding exponential cones. This is a different modelling
criterion, not an equivalent entropy reformulation. Each squared deviation is
divided by ``max(abs(prior), 1e-6*max(abs(prior)), 1e-8)`` within its free block,
with the numerical floor adjusted for ``scale``. Structural zeros and the
Y prior-sign domains and V factor-type domains are retained. The default ``flow_loss="kl"`` uses KL.

``check_feasibility=True`` first solves an LP with the same affine constraints
and all objective-implied domains. Its default solver is HiGHS, selected by
``feasibility_solver``. The HiGHS preflight applies an absolute band of
``1e-6`` in original monetary units to each canonical constraint row, matching
the absolute component of the final constraint audit. This avoids rejecting
accepted, serialized checkpoints because of sub-tolerance residuals. The final
optimization constraints and acceptance checks are unchanged. Other preflight
solvers retain their solver-specific numerical tolerances.

HiGHS is called directly without constructing a dual infeasibility certificate;
that certificate can be much more expensive than the feasibility decision.
An infeasible LP stops before optimization and writes ``feasibility.json``,
including native status, numerical band and measured residuals. A feasible
preflight establishes only feasibility within that band; the final solution
must independently pass all constraint and conservation checks.

``compact_constraints=True`` indexes structural/sign masks at their active
coordinates and replaces exact two-sided bands with single equalities. These
changes preserve the feasible set; nonzero empirical target bands remain bands.

``scale`` (default 1) divides monetary solver inputs and restores solved flows
before returning them. Numerical prior offsets scale with the flows. Baseline,
inventory and checkpoint units remain unchanged. ``model_solution.json`` reports
every explicit/domain constraint in original units. Nonfinite objective
evaluation at a numerical domain boundary is reported explicitly; independent
constraint and conservation checks still control acceptance. Solver status and
this warning must be considered when assessing optimality.

Checkpoint state retains the normalized options. Changing them after completed
groups requires an earlier starting point and a fresh checkpoint directory.

If satellite accounts will be rebuilt after the monetary split, set
``defer_satellite_recalculation=True``. Sequential acceptance then omits E
conservation; Z, Y, V, X, EY, VY and the accounting/sign checks remain enforced.
E is kept as provisional data in the checkpoint. Its preservation record has
``status="deferred"``, ``passed=None`` and ``requires_recalculation=True``;
``state.json`` lists ``pending_recalculations=["E"]``. This does not reconcile
or certify E. The default is False, retaining the strict E check.

Checkpoint and resume
---------------------

A successful group writes ``001_<group>/`` containing:

* ``database/flows/``: reloadable matrices and units;
* ``remaining_add_sectors.xlsx``: an editable plan for the remaining sectors;
* ``source_add_sectors.xlsx`` and ``step_add_sectors.xlsx``: the supplied and
  projected workbooks for this execution;
* ``state.json``: completed sectors, preserved canonical observations, runtime
  versions, conservation diagnostics and database checksums.

Shared-data publishers may place ``flows/`` directly in the checkpoint root.
Such copies set ``database_directory="."`` in ``state.json`` and rebase its
checksum keys to the same root. The loader verifies those files and retains
independent X targets exactly as for the default ``database/`` layout. A database
directory must be relative and stay within the checkpoint. Publishers can store
the workbooks separately; pass their actual paths explicitly when resuming.

Only after writing all files does the checkpoint directory become committed.
A failed group leaves a hidden partial directory with ``failure.json`` and
diagnostic inputs, while the preceding checkpoint and live database stay valid.

.. code-block:: python

   import mario

   db = mario.load_add_sectors_checkpoint("run/checkpoints/001_Mining")
   db.add_sectors(
       "revised_remaining.xlsx",
       split=True,
       intermediate_steps=True,
       save_intermediates="run/checkpoints",
       solver="CLARABEL",
   )

Use a copy of the remaining workbook for an edited revision, or resubmit the
original full workbook with its remaining groups rearranged. With the full
workbook, edits to completed sector observations are rejected. Parent
correspondences are fixed once a group has been committed. Changes to completed
results, parent correspondences or the geographic partition require rolling
back to an earlier appropriate baseline. Keep the preceding source files when
planning such a rollback. Existing committed checkpoint directories are never
overwritten. ``inplace=False`` returns a separate database while retaining the
same on-disk checkpoint behavior.
