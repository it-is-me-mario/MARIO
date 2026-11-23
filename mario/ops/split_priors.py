"""Conservative references for interactions between currently split families.

Only objective references are changed. Baseline matrices, production/trade
targets, sign domains and structural-zero masks are never modified here.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput

KEYS = ['region_from_Name', 'region_to_Name', 'sector_from_Name', 'sector_to_Name']


def conservative_family_prior(table, original_z, quantities, parents, zero_mask):
    """Keep child recipes where feasible and split each remaining parent budget.

The operation covers every origin/destination pair between active families,
including cross-family blocks. Stable suppliers/buyers are left untouched.
Structural support conflicts are reported, not converted into a monetary gate.
"""
    # The bridge lookup also contains identity entries for residual parents.
    # They are existing buyers, not newly inserted child columns.
    parents = {child: parent for child, parent in parents.items() if parent and child != parent}
    families = set(parents.values())
    members = families | set(parents)
    selected = table.sector_from_Name.isin(members) & table.sector_to_Name.isin(members)
    result = table.copy()
    work = table.loc[selected, KEYS + ['values']].copy()
    work['_position'] = np.flatnonzero(selected)
    if work.empty:
        return result, []
    work = work.merge(zero_mask[KEYS + ['values']].rename(columns={'values': '_zero'}),
                      on=KEYS, how='left', validate='one_to_one')
    if work['_zero'].isna().any() or not np.isfinite(work['values']).all():
        raise WrongInput('Incomplete/nonfinite intermediate prior coordinates or masks.')
    reference = original_z.loc[original_z.sector_from_Name.isin(families)
                              & original_z.sector_to_Name.isin(families), KEYS + ['values']]
    if reference.duplicated(KEYS).any():
        raise WrongInput('Duplicate baseline coordinates in intermediate prior construction.')
    reference = reference.set_index(KEYS)['values']
    x = {(label[0], label[-1]): float(value) for label, value in quantities.iloc[:, 0].items()}
    if not all(np.isfinite(v) and v >= 0 for v in x.values()):
        raise WrongInput('Conservative intermediate priors require finite nonnegative outputs.')
    work['_supplier'] = work.sector_from_Name.map(lambda s: parents.get(s, s))
    work['_buyer'] = work.sector_to_Name.map(lambda s: parents.get(s, s))
    grouped = ['region_from_Name', 'region_to_Name', '_supplier', '_buyer']
    records = []
    for (origin, destination, supplier, buyer), block in work.groupby(grouped, sort=False):
        key = (origin, destination, supplier, buyer)
        if key not in reference.index:
            raise WrongInput(f'Missing preceding intermediate-flow budget: {key}.')
        budget = float(reference.loc[key])
        if not np.isfinite(budget):
            raise WrongInput(f'Nonfinite preceding intermediate-flow budget: {key}.')
        raw = block['values'].to_numpy(dtype=float)
        allowed = block['_zero'].to_numpy() == 0
        child_column = block.sector_to_Name.isin(parents).to_numpy()
        values = np.zeros(len(block))
        mode = 'keep_child_recipes_split_residual'
        if budget > 0 and allowed.any():
            child = child_column & allowed
            values[child] = np.maximum(raw[child], 0.)
            child_total = float(values.sum())
            if child_total > budget:
                values *= budget / child_total
                mode = 'rescale_child_recipes_to_available_budget'
            else:
                remainder = max(budget - child_total, 0.)
                residual = ~child_column & allowed
                if residual.any():
                    weights = np.array([x[(origin, s)] for s in block.sector_from_Name])
                    weights[~residual] = 0.
                    if weights.sum() == 0:
                        weights = (residual & block.sector_from_Name.eq(supplier).to_numpy()).astype(float)
                        if weights.sum() == 0:
                            weights = residual.astype(float)
                    values += remainder * weights / weights.sum()
                elif child_total > 0:
                    values *= budget / child_total
                    mode = 'rescale_child_recipes_no_residual_column_support'
                else:
                    weights = np.array([x[(origin, s)] * x[(destination, t)]
                                        for s, t in zip(block.sector_from_Name, block.sector_to_Name)])
                    weights[~allowed] = 0.
                    if weights.sum() == 0:
                        weights = allowed.astype(float)
                    values = budget * weights / weights.sum()
                    mode = 'output_share_fallback_no_recipe_reference'
            # Remove allocation roundoff in an admissible positive cell only.
            largest = int(np.argmax(values))
            values[largest] += budget - float(values.sum())
        elif budget != 0:
            mode = 'baseline_budget_has_no_nonnegative_admissible_partition'
        positions = block['_position'].to_numpy(dtype=int)
        result.iloc[positions, result.columns.get_loc('values')] = values
        error = float(values.sum()) - budget
        if not np.array_equal(raw, values) or error != 0:
            records.append(dict(origin=origin, destination=destination,
                supplier_parent=supplier, buyer_parent=buyer, mode=mode,
                budget_original_units=budget, prior_before_original_units=float(raw.sum()),
                prior_after_original_units=float(values.sum()),
                child_columns_before_original_units=float(raw[child_column].sum()),
                child_columns_after_original_units=float(values[child_column].sum()),
                conservation_error_original_units=error,
                maximum_cell_change_original_units=float(np.abs(values-raw).max(initial=0.))))
    return result, records


def prepare_intermediate_priors(input_data, original_z, quantities, parents, policy, destination=None,
                                *, complete_reference=None):
    """Apply and audit a policy before entropy thresholding/floors and scaling."""
    records = []
    covered = []
    if policy == 'conservative':
        # Z0 can contain only selected legacy references, even when its axes
        # cover the whole block. Construct one complete reference, then expose
        # its family cells through both parameter tables; never normalize each
        # partial view as if it were a separate allocation of the whole budget.
        canonical = input_data.get('Z_use0', complete_reference)
        if canonical is None:
            raise WrongInput('Conservative intermediate priors need a complete split-flow reference.')
        corrected, changes = conservative_family_prior(
            canonical, original_z, quantities, parents, input_data['Zero_use_mask'])
        true_parents = {s:p for s,p in parents.items() if p and s!=p}
        members = set(true_parents) | set(true_parents.values())
        selected = corrected.sector_from_Name.isin(members) & corrected.sector_to_Name.isin(members)
        updates = corrected.loc[selected].set_index(KEYS)['values']
        for name in ('Z0','Z_use0'):
            if name in input_data:
                table = input_data[name].copy()
                values = updates.reindex(pd.MultiIndex.from_frame(table[KEYS])).to_numpy()
                hit = np.isfinite(values)
                table.iloc[np.flatnonzero(hit),table.columns.get_loc('values')] = values[hit]
                input_data[name] = table
                covered.append(name)
        records.extend(dict(table='complete_family_reference', **row) for row in changes)
    report = dict(policy=policy, stage='before_prior_threshold_and_entropy_floor',
        covered_tables=covered, changed_group_references=len(records),
        maximum_conservation_error_original_units=max(
            (abs(r['conservation_error_original_units']) for r in records), default=0.),
        unsupported_budget_groups=sum(r['mode']=='baseline_budget_has_no_nonnegative_admissible_partition'
                                      for r in records),
        child_recipe_rescaling_groups=sum(r['mode'].startswith('rescale_child') for r in records),
        baseline_changed=False, output_targets_changed=False, trade_targets_changed=False,
        masks_changed=False, monetary_rejection_threshold_applied=False)
    if destination is not None:
        destination = Path(destination)
        (destination/'intermediate_prior_preparation.json').write_text(json.dumps(report, indent=2, allow_nan=False))
        columns=['table','origin','destination','supplier_parent','buyer_parent','mode',
                 'budget_original_units','prior_before_original_units','prior_after_original_units',
                 'child_columns_before_original_units','child_columns_after_original_units',
                 'conservation_error_original_units','maximum_cell_change_original_units']
        pd.DataFrame(records,columns=columns).to_csv(destination/'intermediate_prior_preparation.csv', index=False)
    return report
