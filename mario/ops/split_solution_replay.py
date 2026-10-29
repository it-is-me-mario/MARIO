"""Restore one saved optimal split point for post-processing, without solving.

The scoped context is an execution option, not a persisted model parameter.
Normal model runs never use this path. CSV inputs, template files, set tables
and variable coordinates must match the original numerical problem exactly.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput

_REPLAY = ContextVar('mario_saved_split_solution', default=None)


def _same_model_file(source, destination):
    if source.read_bytes() == destination.read_bytes():
        return True
    if source.suffix != '.xlsx':
        return False
    # MARIO updates Excel's document timestamps when preparing a model. Require
    # every other ZIP member (including all worksheet/formula XML) to be exact.
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(destination) as new:
        excluded = {'docProps/core.xml'}
        names = set(old.namelist()) - excluded
        return names == set(new.namelist()) - excluded and all(old.read(n) == new.read(n) for n in names)


@contextmanager
def replay_split_solution(directory):
    """Use exactly one existing raw solution inside a normal MARIO split call."""
    state = {'directory': Path(directory).resolve(), 'used': False}
    token = _REPLAY.set(state)
    try:
        yield state
        if not state['used']:
            raise WrongInput('The saved split solution was not consumed.')
    finally:
        _REPLAY.reset(token)


def restore_saved_solution(model, destination):
    state = _REPLAY.get()
    if state is None:
        return False
    if state['used']:
        raise WrongInput('A saved split point can be used for only one split step.')
    source, destination = state['directory'], Path(destination).resolve()
    if source == destination:
        raise WrongInput('Saved solution restoration requires a fresh destination.')
    report = source / 'raw_model_solution.json'
    if not report.is_file():
        report = source / 'model_solution.json'
    records = json.loads(report.read_text())
    numerical = [(key, scenario, row['problem'], frame)
                 for key, frame in model.core.problem.numerical_problems.items()
                 for scenario, row in frame.iterrows()]
    if len(records) != 1 or len(numerical) != 1 or records[0]['status'] != 'optimal':
        raise WrongInput('Restoration requires a single saved problem with optimal solver status.')
    names = {'model_settings.xlsx', 'mapping.xlsx', 'user_defined_operators.py', 'user_defined_constants.py'}
    old_inputs = {p.name for p in (source / 'input_data').glob('*.csv')}
    new_inputs = {p.name for p in (destination / 'input_data').glob('*.csv')}
    if not old_inputs or old_inputs != new_inputs:
        raise WrongInput('Saved solution CSV input tables differ.')
    files = [Path(n) for n in sorted(names)] + [Path('input_data') / n for n in sorted(old_inputs)]
    for name in files:
        if not _same_model_file(source / name, destination / name):
            raise WrongInput(f'Saved solution input or model file differs: {name}.')
    key, scenario, problem, frame = numerical[0]
    index_path = source / 'returned_solution_index.json'
    index = json.loads(index_path.read_text())
    saved = {item['name']: item for item in index}
    variables = {variable.name(): variable for variable in problem.variables()}
    if len(saved) != len(index) or saved.keys() != variables.keys():
        raise WrongInput('Saved solution variable names differ.')
    with sqlite3.connect((source / 'database.db').as_uri() + '?mode=ro', uri=True) as old_db, \
            sqlite3.connect((destination / 'database.db').as_uri() + '?mode=ro', uri=True) as new_db:
        sets = [row[0] for row in old_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_set_%'")]
        for name in [*sets, *variables]:
            old = pd.read_sql_query(f'SELECT * FROM "{name}" ORDER BY id', old_db).drop(columns='values', errors='ignore')
            new = pd.read_sql_query(f'SELECT * FROM "{name}" ORDER BY id', new_db).drop(columns='values', errors='ignore')
            if not old.equals(new):
                raise WrongInput(f'Saved solution coordinates differ: {name}.')
    arrays_path = source / 'returned_solution_scaled.npz'
    values = {}
    with np.load(arrays_path, allow_pickle=False) as arrays:
        for name, variable in variables.items():
            value = arrays[saved[name]['array']]
            if value.shape != variable.shape or not np.isfinite(value).all():
                raise WrongInput(f'Invalid saved point for {name}.')
            values[variable.id] = value.copy()
    from cvxpy.reductions.solution import Solution
    from cvxpy.problems.problem import SolverStats
    problem.unpack(Solution('optimal', None, values, {}, {}))
    # No optimizer runs in this execution. Keep the original time in provenance.
    problem._solver_stats = SolverStats.from_dict({'solve_time': 0.}, 'saved_solution')
    frame.at[scenario, 'status'] = 'optimal'
    model.core.problem.fetch_problem_status()
    audit = dict(execution='postprocess_saved_solution', optimization_rerun=False,
        source_directory=str(source), original_solver_status='optimal',
        original_solver_seconds=records[0].get('solver_seconds'),
        saved_point_sha256=hashlib.sha256(arrays_path.read_bytes()).hexdigest(),
        saved_index_sha256=hashlib.sha256(index_path.read_bytes()).hexdigest(),
        identical_input_tables=len(old_inputs), model_files_verified=sorted(names),
        coordinates_verified=True, excel_metadata_excluded=['docProps/core.xml'])
    (destination / 'solver_replay.json').write_text(json.dumps(audit, indent=2))
    state.update(used=True, provenance=audit)
    return True
