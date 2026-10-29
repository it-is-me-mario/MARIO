"""Numerical post-processing of MRIO split results, outside CVXLab.

This projects sign domains and explicit zero masks only. It does not rebalance
flows, change targets, remove legitimate signed Y/V, or certify exact optimality.
The postprocess policy records corrections without imposing a monetary limit.
The earlier, explicit bounded policy remains readable for historical trials.
"""
import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput


def effective_validation_options(options, statuses):
    """Keep monetary residuals diagnostic for optimal named MRIO solutions.

    This is an export policy, separate from the normalized mathematical model
    settings. Nonoptimal states and historical/SUT formulations retain their
    existing handling. No amount of monetary discrepancy changes this policy;
    the measured discrepancies remain available for subsequent economic review.
    """
    if (options and str(options.get('model', '')).startswith('Split_sectors_MRIO_')
            and statuses and all(status == 'optimal' for status in statuses)):
        return {**options, 'solution_cleanup': {'validation': 'report_only'}}
    return options


def save_solution_snapshot(model, destination, prefix):
    arrays, index, seen = {}, [], set()
    for key, frame in model.core.problem.numerical_problems.items():
        for scenario, row in frame.iterrows():
            for variable in row['problem'].variables():
                if id(variable) in seen or variable.value is None:
                    continue
                seen.add(id(variable))
                label = f'variable_{len(index)}'
                value = variable.value
                arrays[label] = np.asarray(value.toarray() if hasattr(value, 'toarray') else value).copy()
                index.append(dict(array=label, name=variable.name(), shape=list(variable.shape),
                                  problem=str(key), scenario=str(scenario)))
    destination = Path(destination)
    np.savez_compressed(destination / f'{prefix}_scaled.npz', **arrays)
    (destination / f'{prefix}_index.json').write_text(json.dumps(index, indent=2))


def project_solution(model, destination, options):
    """Project only forbidden signs/zeros; record every correction for review."""
    problems = [row['problem'] for frame in model.core.problem.numerical_problems.values()
                for _, row in frame.iterrows()]
    if len(problems) != 1:
        raise WrongInput('Solution cleanup currently requires one numerical MRIO split problem.')
    variables = {variable.name(): variable for variable in problems[0].variables()}
    required = {'Z_use', 'Z_supply', 'Y', 'V'}
    if not required <= variables.keys():
        raise WrongInput('Solution cleanup requires the MRIO flow variables.')
    signed = {'V_signed_positive', 'V_signed_negative'} & variables.keys()
    if signed and len(signed) != 2:
        raise WrongInput('Solution cleanup requires both signed-V auxiliary variables when present.')
    required |= signed
    scale, policy = options['scale'], options['solution_cleanup']
    destination = Path(destination)
    plans, changes, blocks = [], [], {}
    with sqlite3.connect((destination / 'database.db').resolve().as_uri() + '?mode=ro', uri=True) as conn:
        def table(name):
            return pd.read_sql_query(f'SELECT * FROM "{name}" ORDER BY id', conn)

        def aligned(name, coordinates):
            data = table(name)
            columns = [c for c in coordinates if c != 'values']
            if not coordinates[columns].equals(data[columns]):
                raise WrongInput(f'Solution cleanup coordinate mismatch for {name}.')
            return data['values'].to_numpy(dtype=float)

        for name in sorted(required):
            variable = variables[name]
            data = table(name)
            raw = np.asarray(variable.value, dtype=float).reshape(-1)
            if len(raw) != len(data) or not np.isfinite(raw).all():
                raise WrongInput(f'Invalid returned solution values for {name}.')
            cleaned = raw.copy()
            if name in ('Z_use', 'Z_supply'):
                cleaned = np.maximum(cleaned, 0.)
                zero = aligned('Zero_use_mask' if name == 'Z_use' else 'Zero_supply_mask', data) != 0
            elif name == 'Y':
                prior = aligned('Y0', data)
                cleaned = np.where(prior < 0, np.minimum(cleaned, 0.), np.maximum(cleaned, 0.))
                zero = aligned('Zero_Y_mask', data) != 0
            else:
                zero = aligned('Zero_V_mask', data) != 0
                nonnegative = aligned('V_nonnegative_mask', data) != 0
                if name == 'V':
                    cleaned[nonnegative] = np.maximum(cleaned[nonnegative], 0.)
                else:
                    cleaned = np.maximum(cleaned, 0.)
                    zero |= nonnegative
            cleaned[zero] = 0.
            difference = (cleaned - raw) * scale
            maximum = float(np.abs(difference).max(initial=0.))
            blocks[name] = dict(changed_cells=int(np.count_nonzero(difference)),
                maximum_adjustment_original_units=maximum,
                total_absolute_adjustment_original_units=float(np.abs(difference).sum()))
            changed = data.loc[difference != 0].drop(columns='values').copy()
            changed.insert(0, 'table', name)
            changed['raw_original_units'] = raw[difference != 0] * scale
            changed['cleaned_original_units'] = cleaned[difference != 0] * scale
            changed['adjustment_original_units'] = difference[difference != 0]
            changes.append(changed)
            plans.append((variable, cleaned.reshape(variable.shape)))
    audit = dict(status='prepared', operation='project_sign_domains_and_structural_zeros',
                 policy=policy, scale=scale, blocks=blocks,
                 targets_changed=False, baseline_changed=False,
                 optimality_certified=False)
    pd.concat(changes, ignore_index=True).to_csv(destination / 'solution_cleanup.csv', index=False)
    if ('max_cell_adjustment' in policy and
            any(b['maximum_adjustment_original_units'] > policy['max_cell_adjustment'] for b in blocks.values())):
        audit.update(status='rejected_before_cleanup', error='Per-cell adjustment limit exceeded.')
        (destination / 'solution_cleanup.json').write_text(json.dumps(audit, indent=2))
        raise WrongInput('Solution cleanup exceeds max_cell_adjustment; the raw point was left unchanged.')
    for variable, values in plans:
        variable.value = values
    return audit
