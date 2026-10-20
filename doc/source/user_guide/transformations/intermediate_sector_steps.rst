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

Each solved result is reaggregated to the preceding classification and checked
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

Checkpoint and resume
---------------------

A successful group writes ``001_<group>/`` containing:

* ``database/flows/``: reloadable matrices and units;
* ``remaining_add_sectors.xlsx``: an editable plan for the remaining sectors;
* ``source_add_sectors.xlsx`` and ``step_add_sectors.xlsx``: the supplied and
  projected workbooks for this execution;
* ``state.json``: completed sectors, preserved canonical observations, runtime
  versions, conservation diagnostics and database checksums.

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
