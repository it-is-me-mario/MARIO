"""Opt-in convex IOT split experiments and explicit inherited accounting.

The supplied baseline is never closed or edited. With accounting='inherit',
each preceding row/column discrepancy is distributed within its split family
by fixed output shares, including the residual parent. A zero-output family
retains its discrepancy in the parent. No discrepancy is a decision variable.
"""
from __future__ import annotations

import json
import hashlib
from decimal import Decimal
from importlib import resources
from pathlib import Path
import time

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput


MODEL_REVISION = 'constant-reference-kl-v3'
DEFAULTS = dict(model=None, accounting='strict', value_added_loss='legacy', flow_loss='kl', final_demand_weight=0.,
                supply_weight=0., complete_intermediate_priors=False,
                check_feasibility=False, feasibility_solver='HIGHS', scale=1.,compact_constraints=False,
                defer_satellite_recalculation=False, require_finite_objective=False)
FLOW_TABLES = {'Z0','V0','X','Trade','Zold','Yold','Vold','Z_refine',
               'RowResidual','ColumnResidual','Y0','Z_use0','Z_supply0'}


def normalize_options(options):
    if options is None:
        return None
    if not isinstance(options, dict) or set(options)-DEFAULTS.keys():
        raise WrongInput(f'split_model_options must be a dict with keys {sorted(DEFAULTS)}.')
    result = {**DEFAULTS, **options}
    catalogue = model_catalogue()
    requested = options.get('model')
    if requested is not None:
        if not isinstance(requested, str) or requested not in catalogue:
            raise WrongInput(f'Unknown explicit split model {requested!r}; choose {sorted(catalogue)}.')
        for key, value in catalogue[requested].items():
            if key in options and options[key] != value:
                raise WrongInput(f'{requested} requires {key}={value!r}.')
            result[key] = value
    if result['accounting'] not in ('strict','inherit'):
        raise WrongInput("accounting must be 'strict' or 'inherit'.")
    if result['value_added_loss'] not in ('legacy','signed_kl','quadratic'):
        raise WrongInput("value_added_loss must be 'legacy', 'signed_kl' or 'quadratic'.")
    if result['flow_loss'] not in ('kl','quadratic'):
        raise WrongInput("flow_loss must be 'kl' or 'quadratic'.")
    if result['flow_loss']=='quadratic' and not result['complete_intermediate_priors']:
        raise WrongInput('Quadratic flow loss requires complete_intermediate_priors=True.')
    for key in ('final_demand_weight','supply_weight','scale'):
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not np.isfinite(value) or value < 0 or (key=='scale' and value==0):
            raise WrongInput(f'{key} must be finite and {"positive" if key=="scale" else "nonnegative"}.')
    for key in ('complete_intermediate_priors','check_feasibility','compact_constraints',
                'defer_satellite_recalculation', 'require_finite_objective'):
        if not isinstance(result[key], bool):
            raise WrongInput(f'{key} must be boolean.')
    solvers = result['feasibility_solver']
    if isinstance(solvers, str):
        solvers = [solvers]
    if (not isinstance(solvers, list) or not solvers or
            any(not isinstance(s, str) or not s for s in solvers) or len(set(solvers)) != len(solvers)):
        raise WrongInput('feasibility_solver must name an LP solver or an ordered list of distinct LP solvers.')
    matches = [name for name, specification in catalogue.items()
               if all(result[key] == value for key, value in specification.items())]
    if len(matches) != 1:
        raise WrongInput('No packaged model matches these objective options.')
    result['model'] = matches[0]
    return result


def model_catalogue():
    resource = resources.files('mario.ops.cvxlab_models') / 'split_models.json'
    return json.loads(resource.read_text())


def select_model_template(options, *, staged=False):
    if options is None:
        return ('Split_sectors_staged' if staged else 'Split_sectors'), 'model_settings.xlsx'
    options = normalize_options(options)
    suffix = '_strict' if options['accounting'] == 'strict' else ''
    if options['compact_constraints']:
        suffix += '_compact'
    return options['model'], f'model_settings{suffix}.xlsx'


def describe_model(options, *, staged=False):
    template, filename = select_model_template(options, staged=staged)
    source = resources.files('mario.ops.cvxlab_models') / template
    return dict(template=template, workbook=filename,
                revision=MODEL_REVISION if options is not None else 'historical-prior-sign',
                source_sha256={n: hashlib.sha256((source / n).read_bytes()).hexdigest()
                               for n in (filename, 'mapping.xlsx', 'user_defined_operators.py', 'user_defined_constants.py')},
                shared_operators_sha256={
                    'split_operators.py': hashlib.sha256((resources.files('mario.ops.cvxlab_models') / 'split_operators.py').read_bytes()).hexdigest(),
                    'Split_sectors/user_defined_operators.py': hashlib.sha256((resources.files('mario.ops.cvxlab_models') / 'Split_sectors/user_defined_operators.py').read_bytes()).hexdigest(),
                    'split_model.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                })


def record_model_configuration(directory, options, template, filename):
    directory = Path(directory)
    definition = describe_model(options, staged=template == 'Split_sectors_staged')
    if (template, filename) != (definition['template'], definition['workbook']):
        raise WrongInput('Selected workbook differs from the recorded model options.')
    (directory / 'model_definition.json').write_text(json.dumps(definition, indent=2))
    if options is not None:
        (directory / 'split_model_options.json').write_text(json.dumps(options, indent=2, allow_nan=False))
    return definition


def inherited_accounting(before, after_x, parents, scenario='baseline'):
    """Return row/column discrepancy targets aligned with the refined X index."""
    z, y, v, x = (before.resolve(name, scenario=scenario) for name in ('Z','Y','V','X'))
    original_x = x.iloc[:,0]
    original_row = z.sum(axis=1)+y.sum(axis=1)-original_x.reindex(z.index)
    original_col = z.sum(axis=0)+v.sum(axis=0)-original_x.reindex(z.columns)
    quantities = after_x.iloc[:,0]
    row, col = [], []
    for label, output in quantities.items():
        source = (*label[:-1], parents.get(label[-1],label[-1]))
        if source not in original_x.index:
            raise WrongInput(f'No preceding output/accounting reference for {label!r}.')
        denominator = float(original_x.loc[source])
        if denominator < 0 or output < -1e-10:
            raise WrongInput('Inherited accounting requires nonnegative outputs.')
        share = float(output)/denominator if denominator>0 else float(label==source)
        row.append(share*float(original_row.loc[source]))
        col.append(share*float(original_col.loc[source]))
    return pd.DataFrame({'row':row,'column':col}, index=quantities.index)


def _values(prior):
    value = prior.value
    if value is None:
        raise ValueError('A split prior must have a value before model construction.')
    if hasattr(value,'toarray'):
        value = value.toarray()
    result = np.asarray(value,dtype=float)
    if not np.isfinite(result).all():
        raise ValueError('Nonfinite split prior.')
    return result


def _array(value):
    return np.asarray(value.toarray() if hasattr(value,'toarray') else value,dtype=float)


def entropy_support(arrays):
    """Four decades below the smallest nonzero absolute monetary prior.

    Zeros have no decimal order. Signs are domains of the model, not a reason
    to ignore small signed observations. No arbitrary constant is substituted
    when every supplied reference is zero.
    """
    minima = []
    for values in arrays:
        values = _array(values)
        if not np.isfinite(values).all():
            raise WrongInput('Entropy support requires finite monetary priors.')
        nonzero = np.abs(values[values != 0])
        if nonzero.size:
            minima.append(float(nonzero.min()))
    if not minima:
        raise WrongInput('Cannot infer entropy support from all-zero priors; supply a nonzero monetary reference.')
    minimum = min(minima)
    # Decimal's adjusted exponent avoids rounding log10 at decade boundaries.
    exponent = Decimal(str(minimum)).adjusted()
    coefficient = 10. ** (exponent - 4)
    if not np.isfinite(coefficient) or coefficient <= 0:
        raise WrongInput('The data-derived entropy support is outside floating-point range.')
    return dict(minimum_nonzero_absolute=minimum, magnitude_exponent=exponent,
                orders_below=4, coefficient=coefficient)


def _entropy_floor(prior, reference_floor):
    floor = entropy_support([prior])['coefficient'] if reference_floor is None else float(reference_floor)
    if not np.isfinite(floor) or floor <= 0:
        raise WrongInput('Entropy support must be finite and strictly positive.')
    return floor


def model_constant_kl(a, reference):
    """Elementwise KL for a fixed, strictly positive numerical reference.

    x*log(x/q)-x+q = -entr(x)-(log(q)+1)*x+q, including x=0.
    Computing log(q) before canonicalisation keeps tiny prior values out of
    exponential-cone coordinates. This is the same objective and closed domain,
    not clipping, a new support floor or a relaxation. It must not be used for
    an endogenous or dynamically changing reference.
    """
    import cvxpy as cp
    if isinstance(reference, cp.Expression) and not reference.is_constant():
        raise WrongInput('Constant-reference KL cannot use an endogenous reference.')
    q = np.asarray(reference.value if hasattr(reference, 'value') else reference, dtype=float)
    if not np.isfinite(q).all() or (q <= 0).any():
        raise WrongInput('Constant-reference KL requires finite, strictly positive references.')
    return -cp.entr(a) - cp.multiply(np.log(q) + 1., a) + q


def model_active_kl(a, prior, zero_mask=None, signed=False, reference_floor=None):
    """KL on allowed cells; structural zeros create no exponential cones."""
    import cvxpy as cp
    q = _values(prior)
    allowed = np.ones(q.size,dtype=bool) if zero_mask is None else _values(zero_mask).reshape(-1)==0
    if not allowed.any():
        return cp.Constant(0.)
    q = q.reshape(-1)[allowed]
    if not signed and (q<0).any():
        raise ValueError('Intermediate-input priors must be nonnegative.')
    vector = cp.reshape(a,(a.size,),order='C')[np.flatnonzero(allowed)]
    if signed:
        vector = cp.multiply(np.where(q<0,-1.,1.),vector)
    # The floor is numerical support, not a source observation. Structural
    # exclusions remain fixed independently of the objective.
    return cp.sum(model_constant_kl(vector,np.abs(q)+_entropy_floor(q, reference_floor)))


def model_signed_kl(a, prior, zero_mask=None, reference_floor=None):
    return model_active_kl(a,prior,zero_mask,signed=True,reference_floor=reference_floor)


def model_quadratic(a, prior, zero_mask=None, reference_floor=1e-8):
    import cvxpy as cp
    q = _values(prior)
    allowed = np.ones(q.size,dtype=bool) if zero_mask is None else _values(zero_mask).reshape(-1)==0
    if not allowed.any():
        return cp.Constant(0.)
    vector = cp.reshape(a,(a.size,),order='C')[np.flatnonzero(allowed)]
    q = q.reshape(-1)[allowed]
    scale = np.maximum(np.abs(q),max(float(np.max(np.abs(q),initial=0.))*1e-6,reference_floor))
    return cp.sum_squares(cp.multiply(1/np.sqrt(scale),vector-q))


def model_prior_signed_values(a, prior, zero_mask=None):
    """Explicit prior-sign domain, also available without entropy atoms."""
    import cvxpy as cp
    q = _values(prior).reshape(-1)
    allowed = np.ones(q.size,dtype=bool) if zero_mask is None else _values(zero_mask).reshape(-1)==0
    if not allowed.any():
        return cp.Constant(0.)
    vector = cp.reshape(a,(a.size,),order='C')[np.flatnonzero(allowed)]
    return cp.multiply(np.where(q[allowed]<0,-1.,1.),vector)


def model_legacy_entropy(a, prior, *, signed=False, reference_floor=None):
    """Original matrix-valued loss, with a scale-covariant numerical offset."""
    import cvxpy as cp
    q = _values(prior)
    reference_floor = _entropy_floor(q, reference_floor)
    return cp.rel_entr(cp.multiply(np.where(q<0,-1.,1.),a) if signed else a,
                       np.abs(q)+reference_floor if signed else prior+reference_floor)


def model_masked_values(a, mask):
    """Keep constrained coordinates only; omit identities such as 0 == 0."""
    import cvxpy as cp
    positions = np.flatnonzero(_values(mask).reshape(-1)!=0)
    return cp.reshape(a,(a.size,),order='C')[positions] if positions.size else cp.Constant(0.)


def proportional_row_reference(table, original, outputs, previous_outputs, parents):
    """Joint output-share prior for Y or deliveries to unchanged buyers.

    Always read the preceding parent row, never a row already reduced by an
    earlier child. This makes the reference independent of child ordering and
    conserves each preceding cell across the child/residual-parent family.
    """
    keys = [column for column in table.columns if column not in ('id','values')]
    source = table[keys].copy()
    source['sector_from_Name'] = source['sector_from_Name'].map(lambda name:parents.get(name,name))
    values = original.set_index(keys)['values'].reindex(pd.MultiIndex.from_frame(source)).to_numpy()

    def output_series(frame):
        return pd.Series(frame.iloc[:,0].to_numpy(),index=pd.MultiIndex.from_tuples(
            [(label[0],label[-1]) for label in frame.index]))

    target_index = pd.MultiIndex.from_frame(table[['region_from_Name','sector_from_Name']])
    source_index = pd.MultiIndex.from_frame(source[['region_from_Name','sector_from_Name']])
    numerator = output_series(outputs).reindex(target_index).to_numpy(dtype=float)
    denominator = output_series(previous_outputs).reindex(source_index).to_numpy(dtype=float)
    share = np.divide(numerator,denominator,
                      out=table['sector_from_Name'].eq(source['sector_from_Name']).to_numpy(dtype=float),
                      where=denominator>0)
    if (not np.isfinite(values).all() or not np.isfinite(numerator).all()
            or not np.isfinite(denominator).all() or (numerator<0).any() or (denominator<0).any()):
        raise WrongInput('Incomplete or invalid preceding row/output reference for split priors.')
    return table.assign(values=values*share)


def fill_model_inputs(instance, input_data, flat_matrices, set_map, scenario_label, options):
    if options is None:
        return
    for name, signed in [('V_nonnegative_mask', False), ('V_signed_mask', True)]:
        if name in input_data:
            table = input_data[name]
            factor = 'fact_prod_Name' if 'fact_prod_Name' in table else 'factor_Name'
            free = table[factor].astype(str).str.strip().str.casefold().isin(['tax', 'ttm'])
            table['values'] = (free if signed else ~free).astype(float)
    if options['accounting']=='inherit' and (input_data['tol'].loc[input_data['tol']['scalar_Name'].eq('eps'),'values']!=0).any():
        raise WrongInput('Inherited accounting requires exact preceding aggregates (eps=0).')
    from mario.ops.cvxlab_bridge import _rename_flat_columns, _split_parent_lookup, _merge_cvxlab_input_table
    split = f'split_{scenario_label}'
    for name,matrix in [('Y0','Y'),('Z_use0','Z'),('Z_supply0','Z')]:
        if name in input_data:
            if name=='Z_use0':
                values = flat_matrices[matrix].query('Scenario == @split').drop(columns=['Scenario'])
                input_data[name] = _merge_cvxlab_input_table(input_data[name],_rename_flat_columns(values,set_map),table_name=name)
            else:
                original = flat_matrices[matrix].query("Scenario == 'original'").drop(columns=['Scenario'])
                input_data[name] = proportional_row_reference(
                    input_data[name],_rename_flat_columns(original,set_map),instance.matrices[split]['X'],
                    instance.resolve('X',scenario='original'),_split_parent_lookup(instance))
    refinement = getattr(instance,'_intermediate_refinement',None)
    if 'Z_supply0' in input_data and refinement is not None and not refinement.empty:
        keys = ['region_from_Name','sector_from_Name','region_to_Name','sector_to_Name']
        current = input_data['Z_supply0'].set_index(keys)
        updates = refinement.set_index(keys)['values']
        hit = current.index.intersection(updates.index)
        current.loc[hit,'values'] = updates.reindex(hit)
        input_data['Z_supply0'] = current.reset_index()
    if options['accounting']=='inherit':
        target = inherited_accounting(instance,instance.matrices[split]['X'],_split_parent_lookup(instance),scenario='original')
        for table,column,keys in [('RowResidual','row',['region_from_Name','sector_from_Name']),
                                  ('ColumnResidual','column',['region_to_Name','sector_to_Name'])]:
            series = pd.Series(target[column].to_numpy(),index=pd.MultiIndex.from_tuples(
                [(label[0],label[-1]) for label in target.index],names=keys))
            index = pd.MultiIndex.from_frame(input_data[table][keys])
            input_data[table]['values'] = series.reindex(index).to_numpy()
    for name in ('RowResidual','ColumnResidual','Y0','Z_use0','Z_supply0'):
        if name in input_data and not np.isfinite(input_data[name]['values'].to_numpy(dtype=float)).all():
            raise WrongInput(f'Incomplete or nonfinite {name} model inputs.')


def fill_numerical_controls(input_data, options, destination):
    """Compute support after input preparation/clipping and before unit scaling.

    Use one common coefficient for the monetary references in enabled entropy
    terms. Masks, targets, tolerances, residuals and disabled losses are excluded.
    Quadratic normalisation deliberately retains its separate historical floor.
    """
    if options is None or 'Model_controls' not in input_data:
        return
    supply = options['supply_weight'] or (1. if options['complete_intermediate_priors'] else 0.)
    names = []
    if options['flow_loss'] == 'kl':
        names += ['Z_use0'] if options['complete_intermediate_priors'] else ['Z0']
        if not options['complete_intermediate_priors'] and not supply and 'Refine_selector' in input_data:
            if input_data['Refine_selector']['values'].fillna(0).gt(0).any():
                names.append('Z_refine')
        if options['final_demand_weight']:
            names.append('Y0')
        if supply:
            names.append('Z_supply0')
    if options['value_added_loss'] != 'quadratic':
        names.append('V0')
    names = [name for name in names if name in input_data]
    record = dict(enabled=bool(names), monetary_prior_tables=names,
                  rule='10 ** (floor(log10(min(abs(nonzero prior)))) - 4)',
                  scale=options['scale'], revision=MODEL_REVISION)
    if names:
        record.update(entropy_support(input_data[name]['values'].to_numpy(dtype=float) for name in names))
        record['coefficient_scaled'] = record['coefficient'] / options['scale']
        _entropy_floor([], record['coefficient_scaled'])
    controls = dict(y_weight=options['final_demand_weight'], supply_weight=supply,
                    reference_floor=1e-8 / options['scale'],
                    entropy_floor=record.get('coefficient_scaled', 0.))
    table = input_data['Model_controls']
    table['values'] = table['model_control_Name'].map(controls)
    if not np.isfinite(table['values']).all():
        raise WrongInput('Unknown or nonfinite model control.')
    (Path(destination) / 'entropy_support.json').write_text(json.dumps(record, indent=2, allow_nan=False))


def _highs_feasibility(problem, absolute_tolerance):
    """Check the audited numerical envelope without requesting a dual ray.

    Equalities in a serialized accepted checkpoint need not be algebraically
    exact. Explicit bands use only the absolute tolerance already enforced by
    verify_model_solution; the final optimization problem is not modified.
    """
    import cvxpy as cp
    import cvxpy.settings as settings
    import highspy

    data, _, _ = problem.get_problem_data(cp.HIGHS, ignore_dpp=True)
    matrix = data[settings.A].tocsc()
    rhs = data[settings.B]
    equalities = data[settings.DIMS].zero
    lp = highspy.HighsLp()
    lp.num_col_, lp.num_row_ = matrix.shape[1], matrix.shape[0]
    lp.col_cost_ = data[settings.C]
    lower, upper = data[settings.LOWER_BOUNDS], data[settings.UPPER_BOUNDS]
    lp.col_lower_ = np.full(lp.num_col_, -highspy.kHighsInf) if lower is None else lower
    lp.col_upper_ = np.full(lp.num_col_, highspy.kHighsInf) if upper is None else upper
    lp.row_lower_ = np.r_[rhs[:equalities] - absolute_tolerance,
                         np.full(len(rhs) - equalities, -highspy.kHighsInf)]
    lp.row_upper_ = rhs + absolute_tolerance
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_, lp.a_matrix_.index_, lp.a_matrix_.value_ = matrix.indptr, matrix.indices, matrix.data
    solver = highspy.Highs()
    for key, value in dict(threads=1, primal_feasibility_tolerance=1e-10,
                           dual_feasibility_tolerance=1e-9, output_flag=False).items():
        solver.setOptionValue(key, value)
    solver.passModel(lp)
    solver.run()
    native_status = solver.getModelStatus()
    status = {highspy.HighsModelStatus.kOptimal: 'optimal',
              highspy.HighsModelStatus.kInfeasible: 'infeasible'}.get(native_status, native_status.name)
    record = dict(status=status, native_status=native_status.name,
                  variables=lp.num_col_, constraints=lp.num_row_,
                  absolute_feasibility_band_scaled=absolute_tolerance,
                  solver_seconds=solver.getRunTime(), dual_certificate_requested=False)
    if status == 'optimal':
        residual = matrix @ np.asarray(solver.getSolution().col_value) - rhs
        record['max_constraint_violation_scaled'] = float(max(
            np.abs(residual[:equalities]).max(initial=0.), residual[equalities:].max(initial=0.)))
    return record


def _gurobi_feasibility(problem, absolute_tolerance):
    """Use the same affine numerical envelope as the HiGHS probe."""
    import cvxpy as cp
    import cvxpy.settings as settings
    import gurobipy as gp

    data, _, _ = problem.get_problem_data(
        cp.GUROBI, solver_opts={'use_quad_obj': False}, ignore_dpp=True)
    matrix, rhs = data[settings.A].tocsc(), data[settings.B]
    equalities = data[settings.DIMS].zero
    lower, upper = data[settings.LOWER_BOUNDS], data[settings.UPPER_BOUNDS]
    with gp.Env(empty=True) as environment:
        environment.setParam('OutputFlag', 0)
        environment.start()
        with gp.Model(env=environment) as probe:
            probe.Params.Threads = 2
            probe.Params.TimeLimit = 1800.
            probe.Params.Method = 1
            probe.Params.FeasibilityTol = 1e-9
            probe.Params.OptimalityTol = 1e-9
            probe.Params.NumericFocus = 1
            probe.Params.DualReductions = 0
            variables = probe.addMVar(matrix.shape[1],
                lb=-gp.GRB.INFINITY if lower is None else lower,
                ub=gp.GRB.INFINITY if upper is None else upper)
            if equalities:
                probe.addMConstr(matrix[:equalities], variables, gp.GRB.LESS_EQUAL,
                                 rhs[:equalities] + absolute_tolerance)
                probe.addMConstr(matrix[:equalities], variables, gp.GRB.GREATER_EQUAL,
                                 rhs[:equalities] - absolute_tolerance)
            if equalities < len(rhs):
                probe.addMConstr(matrix[equalities:], variables, gp.GRB.LESS_EQUAL,
                                 rhs[equalities:] + absolute_tolerance)
            probe.optimize()
            status = {gp.GRB.OPTIMAL: 'optimal', gp.GRB.INFEASIBLE: 'infeasible'}.get(
                probe.Status, f'gurobi_status_{probe.Status}')
            record = dict(status=status, native_status=int(probe.Status),
                variables=matrix.shape[1], constraints=matrix.shape[0], native_rows=probe.NumConstrs,
                absolute_feasibility_band_scaled=absolute_tolerance,
                native_feasibility_tolerance_scaled=probe.Params.FeasibilityTol,
                solver_seconds=probe.Runtime, dual_certificate_requested=False)
            if status == 'optimal':
                residual = matrix @ variables.X - rhs
                record['max_constraint_violation_scaled'] = float(max(
                    np.abs(residual[:equalities]).max(initial=0.), residual[equalities:].max(initial=0.)))
    return record


def _affine_constraint_violation(constraint):
    """Evaluate cell residuals after converting sparse values, before NumPy ops.

    CVXPY's residual properties can apply np.maximum directly to a SciPy sparse
    matrix. That raises instead of checking otherwise valid constant domains.
    """
    from cvxpy.constraints.zero import Equality, Zero
    from cvxpy.constraints.nonpos import Inequality, NonPos, NonNeg

    value = _array(constraint.expr.value)
    if isinstance(constraint, (Equality, Zero)):
        return np.abs(value)
    if isinstance(constraint, (Inequality, NonPos)):
        return np.maximum(value, 0.)
    if isinstance(constraint, NonNeg):
        return np.maximum(-value, 0.)
    raise WrongInput(f'Unsupported split constraint for affine verification: {type(constraint).__name__}')


def check_feasibility(model, destination, options):
    if not options or not options['check_feasibility']:
        return
    import cvxpy as cp
    solvers = options['feasibility_solver']
    if isinstance(solvers, str):
        solvers = [solvers]
    records = []
    try:
        for key,frame in model.core.problem.numerical_problems.items():
            for scenario,row in frame.iterrows():
                original = row['problem']
                # Objective atoms can impose sign/domain constraints absent
                # from Problem.constraints. Dropping those changes feasibility.
                constraints = original.constraints+original.objective.expr.domain
                if not all(c.expr.is_affine() for c in constraints):
                    raise WrongInput('The feasibility stage requires affine split constraints/domains.')
                feasible = cp.Problem(cp.Minimize(0),constraints)
                solved = False
                for solver in solvers:
                    started = time.monotonic()
                    if solver not in cp.installed_solvers():
                        record = dict(status='not_installed')
                    else:
                        try:
                            if solver == 'HIGHS':
                                record = _highs_feasibility(feasible, 1e-6 / options['scale'])
                            elif solver == 'GUROBI':
                                record = _gurobi_feasibility(feasible, 1e-6 / options['scale'])
                            else:
                                feasible.solve(solver=solver, ignore_dpp=True)
                                record = dict(status=feasible.status, variables=sum(v.size for v in feasible.variables()),
                                              constraints=sum(c.size for c in constraints))
                                if feasible.status in ('optimal','optimal_inaccurate'):
                                    record['max_constraint_violation_scaled'] = max(
                                        (float(_affine_constraint_violation(c).max(initial=0.)) for c in constraints),default=0.)
                        except Exception as exc:
                            if not solver_failure(exc):
                                raise
                            record = dict(status='solver_error', error=str(exc), error_type=type(exc).__name__)
                    record.update(problem=str(key), scenario=str(scenario), solver=solver, seconds=time.monotonic()-started)
                    records.append(record)
                    if record['status'] in ('optimal','optimal_inaccurate'):
                        solved = True
                        break
                    if record['status'] in ('infeasible', 'infeasible_inaccurate'):
                        # A mathematical infeasibility is not a missing licence.
                        break
                if not solved:
                    raise WrongInput(f"Linear split feasibility check returned {record['status']}; see feasibility.json.")
    finally:
        (Path(destination)/'feasibility.json').write_text(json.dumps(records,indent=2,allow_nan=False))


def solver_failure(exc):
    """Recognise solver/installation failures without swallowing programming errors."""
    import cvxpy as cp
    return isinstance(exc, (cp.error.SolverError, ImportError)) or type(exc).__module__.startswith(('mosek', 'gurobipy'))


def verify_model_solution(model, destination, options):
    """Report and validate every affine constraint/domain in original units."""
    if options is None:
        return
    records = []
    failures = 0
    nonfinite_objectives = 0
    for key,frame in model.core.problem.numerical_problems.items():
        for scenario,row in frame.iterrows():
            problem = row['problem']
            bad, worst = 0, 0.
            for constraint in problem.constraints+problem.objective.expr.domain:
                violation = _affine_constraint_violation(constraint)
                if not np.isfinite(violation).all():
                    raise WrongInput('Nonfinite model solution constraint residual.')
                reference = np.abs(_array(constraint.args[0].value))
                if len(constraint.args) == 2:
                    reference = np.maximum(reference, np.abs(_array(constraint.args[1].value)))
                bad += int(np.count_nonzero(violation > 1e-6/options['scale']+1e-8*reference))
                worst = max(worst,float(violation.max(initial=0.))*options['scale'])
            stats = problem.solver_stats
            objective = float(problem.value)*options['scale']
            records.append(dict(problem=str(key),scenario=str(scenario),status=problem.status,
                                objective=objective if np.isfinite(objective) else None,
                                objective_finite=bool(np.isfinite(objective)),failed_constraint_cells=bad,
                                objective_required_finite=options['require_finite_objective'],
                                max_constraint_violation=worst,solver_seconds=stats.solve_time))
            if not np.isfinite(objective):
                records[-1]['warning'] = ('Objective evaluation is nonfinite at the returned point; '
                                          'all explicit and implicit domain residuals are checked independently.')
                nonfinite_objectives += 1
            failures += bad
    (Path(destination)/'model_solution.json').write_text(json.dumps(records,indent=2,allow_nan=False))
    if nonfinite_objectives and options['require_finite_objective']:
        raise WrongInput('Nonfinite model solution objective; see model_solution.json. Try another solver without clipping the solution.')
    if failures:
        raise WrongInput(f'{failures} split constraint cells exceed numerical precision; see model_solution.json.')
