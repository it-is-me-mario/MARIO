"""Transactional, resumable IOT splits at successive sector resolutions."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
from importlib.metadata import version
import json
import logging
from pathlib import Path
import re
import tempfile
import traceback
from uuid import uuid4

import numpy as np
import pandas as pd
from pandas.io.excel._openpyxl import OpenpyxlWriter

from mario.log_exc.exceptions import WrongInput
from mario.ops.add_sector_workbook import (
    _copy_add_sector_workbook, build_db_units_sheet, derive_add_sector_sets,
    group_inventories_by_target, load_add_sector_workbook_input,
)

ATOL, RTOL = 1e-6, 1e-8
logger = logging.getLogger(__name__)


def _recoverable_step_failure(exc):
    """Recognise failed optimisation without hiding schema or code errors."""
    from mario.ops.split_model import solver_failure
    if not isinstance(exc, ImportError) and solver_failure(exc):
        return True
    return isinstance(exc, WrongInput) and any(message in str(exc) for message in (
        'CVXLab split optimization did not solve optimally',
        'Linear split feasibility check returned',
        'split constraint cells exceed numerical precision',
        'Nonfinite model solution constraint residual', 'Nonfinite model solution objective',
        'Step does not preserve preceding', 'Step introduced row-accounting discrepancies',
        'New-sector columns are not balanced', 'Step introduced negative',
        'Step changed the sign domain',
    ))


def _write_run_report(root, report):
    """Keep each call's journal and a convenient latest copy, atomically."""
    content = json.dumps(report, indent=2, allow_nan=False)
    for name in (f"run_report_{report['run_id']}.json", 'run_report.json'):
        temporary = root / f'.{name}.tmp'
        temporary.write_text(content)
        temporary.replace(root / name)


class _SectorWorkbookWriter(OpenpyxlWriter):
    @property
    def sheets(self):
        # Pandas looks up every worksheet by name here; openpyxl scans all
        # worksheets per lookup. Iterating directly keeps this mapping linear.
        return {sheet.title: sheet for sheet in self.book.worksheets}


def write_workbook_payload(workbook, path, *, instance=None):
    """Write a normalized payload, including the editable global step plan."""
    def cluster_frame(mapping):
        return pd.DataFrame({name: pd.Series(values, dtype=object) for name, values in mapping.items()})

    with _SectorWorkbookWriter(path) as writer:
        workbook.master_sheet.to_excel(writer, sheet_name="Master", index=False)
        for name, mapping in (("Regions Clusters", workbook.regions_clusters),
                              ("Sectors Clusters", workbook.item_clusters),
                              ("Factors Clusters", workbook.factors_clusters)):
            cluster_frame(mapping).to_excel(writer, sheet_name=name, index=False)
        for name, frame in workbook.inventories_by_sheet.items():
            frame.to_excel(writer, sheet_name=name, index=False)
        for name, frame in (workbook.split_info or {}).items():
            frame.to_excel(writer, sheet_name=name, index=False)
        if workbook.uncertainty_values:
            pd.DataFrame({"Inventory data categories": workbook.uncertainty_values.keys(),
                          "New uncertainty values": workbook.uncertainty_values.values()}).to_excel(
                writer, sheet_name="Uncertainties", index=False)
        if workbook.intermediate_steps is not None:
            cluster_frame(workbook.intermediate_steps).to_excel(writer, sheet_name="Intermediate steps", index=False)
        if instance is not None:
            build_db_units_sheet(instance).to_excel(writer, sheet_name="DB units", index=False)


def validate_plan(workbook, existing, *, completed=()):
    plan = workbook.intermediate_steps
    if not plan:
        raise WrongInput("intermediate_steps=True requires a populated 'Intermediate steps' sheet.")
    if any(not isinstance(name, str) or not name.strip() or not isinstance(group, list)
           or any(not isinstance(s, str) or not s.strip() for s in group)
           for name, group in plan.items()):
        raise WrongInput("Intermediate steps require non-empty names and lists of sector names.")
    sectors = set(workbook.master_sheet["Sector"].dropna().astype(str))
    duplicates = sectors & set(existing) - set(completed)
    if duplicates:
        raise WrongInput(f"Workbook sectors already exist outside this checkpoint history: {sorted(duplicates)}")
    flattened = [sector for group in plan.values() for sector in group]
    counts = Counter(flattened)
    if set(counts) - sectors or sectors - set(counts) or any(n != 1 for n in counts.values()):
        raise WrongInput("Each Master sector must appear exactly once in Intermediate steps; "
                         f"missing={sorted(sectors - counts.keys())}, unknown={sorted(counts.keys() - sectors)}, "
                         f"duplicates={sorted(s for s, n in counts.items() if n != 1)}")
    modes = workbook.master_sheet["Add or Split"].fillna("").astype(str).str.lower()
    if not modes.eq("split").all():
        raise WrongInput("Intermediate IOT steps currently require every Master row to be marked Split.")
    parents = {}
    for sector, rows in workbook.master_sheet.groupby("Sector", sort=False):
        values = rows["Parent Sector"].dropna().astype(str).str.strip().unique()
        if len(values) != 1 or not values[0]:
            raise WrongInput(f"Sector {sector!r} needs one consistent parent in all regions.")
        parents[sector] = values[0]
    return [(name, [s for s in group if s not in existing]) for name, group in plan.items()
            if any(s not in existing for s in group)], parents


def compile_step(workbook, sectors, existing, parents):
    """Project final input coordinates onto the current sector partition.

The original payload remains immutable. Future children project onto their
current residual parent; newly coincident singleton observations are summed.
Projected overlapping multi-sector observations are rejected, never guessed.
"""
    existing, active = set(existing), set(sectors)
    available = existing | active
    for sector in active:
        if parents[sector] not in existing:
            raise WrongInput(f"Parent {parents[sector]!r} of {sector!r} must be introduced in an earlier step.")

    def project(item, visited=()):
        if item in available:
            return item
        if item in visited or item not in parents:
            raise WrongInput(f"No current parent representation for input sector {item!r}.")
        return project(parents[item], (*visited, item))

    def members(item, visited=()):
        if item in available or item in parents:
            return {project(item)}
        if item in visited or item not in workbook.item_clusters:
            raise WrongInput(f"Unknown or cyclic input-sector cluster: {item!r}")
        return set().union(*(members(v, (*visited, item)) for v in workbook.item_clusters[item]))

    clusters, aliases, by_signature = {}, {}, {}
    for name in workbook.item_clusters:
        resolved = sorted(members(name))
        if not resolved:
            raise WrongInput(f"Empty sector cluster {name!r}.")
        if len(resolved) == 1:
            aliases[name] = resolved[0]
        else:
            signature = tuple(resolved)
            aliases[name] = by_signature.setdefault(signature, name)
            clusters[aliases[name]] = resolved

    master = workbook.master_sheet.loc[workbook.master_sheet["Sector"].isin(active)].copy()
    inventories = {}
    for name in master["Inventory sheet"].dropna().unique():
        frame = workbook.inventories_by_sheet[name].copy(deep=True)
        sector_rows = frame["Item type"].eq("Sector")
        frame.loc[sector_rows, "DB Item"] = frame.loc[sector_rows, "DB Item"].map(
            lambda value: aliases[value] if value in aliases else project(value))
        # Disjoint final observations can overlap after projection. Exact
        # singleton collisions are additive; partial cluster overlaps are not.
        observations = {}
        for _, row in frame.loc[sector_rows].iterrows():
            key = (row.get("DB Region"), row.get("Change type"))
            item = row["DB Item"]
            resolved = set(clusters.get(item, [item]))
            for previous, previous_set in observations.get(key, []):
                if previous != item and previous_set & resolved:
                    raise WrongInput(f"Step projects overlapping input constraints {previous!r} and {item!r} "
                                     f"in {name!r}; introduce the affected sectors together or revise the observations.")
            observations.setdefault(key, []).append((item, resolved))
        keys = [c for c in ("Unit", "Item type", "DB Item", "DB Region", "Change type") if c in frame]
        aggregations = {c: ("sum" if c == "Quantity" else "first") for c in frame.columns if c not in keys}
        if frame["Quantity"].isna().any():
            raise WrongInput(f"Missing inventory quantities in {name!r}.")
        frame["Quantity"] = pd.to_numeric(frame["Quantity"], errors="raise")
        if not np.isfinite(frame["Quantity"].to_numpy(dtype=float)).all():
            raise WrongInput(f"Non-finite inventory quantities in {name!r}.")
        frame = frame.groupby(keys, dropna=False, sort=False, as_index=False).agg(aggregations)
        inventories[name] = frame.reindex(columns=workbook.inventories_by_sheet[name].columns)
    support = {name: frame.copy(deep=True) for name, frame in (workbook.split_info or {}).items()}
    for name, column in (("Total outputs", "Sector"), ("Trades", "Sector_from")):
        if name in support:
            support[name] = support[name].loc[support[name][column].isin(active)].copy()
    if "Exclusions" in support:
        frame = support["Exclusions"]
        mask = pd.Series(True, index=frame.index)
        for column in ("Sector_from", "Sector_to"):
            mask &= frame[column].isin(available) | frame[column].isna()
        support["Exclusions"] = frame.loc[mask].copy()
    tolerances = support.get("Tolerances")
    if tolerances is not None:
        eps = tolerances.loc[tolerances["tol_Name"].eq("eps"), "values"]
        if eps.empty or not pd.to_numeric(eps, errors="raise").eq(0).all():
            raise WrongInput("Sequential preservation requires eps=0 in Tolerances.")
    return replace(workbook, master_sheet=master, item_clusters=clusters,
                   inventories_by_sheet=inventories, split_info=support, intermediate_steps=None)


def _attach(instance, workbook):
    instance.add_sectors_workbook = workbook
    instance.add_sectors_master = workbook.master_sheet
    instance.regions_clusters = workbook.regions_clusters
    instance.sectors_clusters = workbook.item_clusters
    instance.factors_clusters = workbook.factors_clusters
    instance.uncertainty_values = workbook.uncertainty_values
    instance.split_info = workbook.split_info or {}
    instance.inventories = group_inventories_by_target(workbook)
    for key, value in derive_add_sector_sets(workbook, existing_sectors=instance.get_index("Sector")).items():
        setattr(instance, key, value)


def _collapse(frame, parents):
    frame = frame.copy()
    for axis in (0, 1):
        labels = frame.index if axis == 0 else frame.columns
        if not isinstance(labels, pd.MultiIndex):
            continue
        if "Sector" in labels.names:
            position = labels.names.index("Sector")
        elif "Level" in labels.names and set(labels.get_level_values("Level")) == {"Sector"}:
            position = labels.names.index("Item")
        else:
            continue
        arrays = [labels.get_level_values(i) if i != position else
                  labels.get_level_values(i).map(lambda v: parents.get(v, v)) for i in range(labels.nlevels)]
        mapped = pd.MultiIndex.from_arrays(arrays, names=labels.names)
        if axis == 0:
            frame.index = mapped
            frame = frame.groupby(level=list(range(mapped.nlevels)), sort=False).sum()
        else:
            frame.columns = mapped
            frame = frame.T.groupby(level=list(range(mapped.nlevels)), sort=False).sum().T
    return frame


def verify_preservation(before, after, parents, *, scenario="baseline", split_model_options=None):
    report = {}
    cleanup = (split_model_options or {}).get('solution_cleanup')
    report_only = bool(cleanup and cleanup.get('validation') == 'report_only')
    atol = cleanup.get('absolute_tolerance', ATOL) if cleanup else ATOL
    rtol = cleanup.get('relative_tolerance', RTOL) if cleanup else RTOL
    if cleanup:
        report['numerical_validation'] = dict(status='postprocessed_pending_review' if report_only else 'approximate_after_cleanup',
            residuals_enforced=not report_only, economic_review='pending',
            absolute_tolerance_original_units=atol, relative_tolerance=rtol,
            strict_absolute_tolerance=ATOL, strict_relative_tolerance=RTOL)
    defer_e = bool((split_model_options or {}).get('defer_satellite_recalculation'))
    for name in ("Z", "Y", "V", "E", "X", "EY", "VY"):
        if name == 'E' and defer_e:
            report[name] = {'passed':None,'enforced':False,'status':'deferred',
                            'requires_recalculation':True}
            continue
        expected = before.resolve(name, scenario=scenario)
        actual = _collapse(after.resolve(name, scenario="baseline"), parents)
        if set(actual.index) != set(expected.index) or set(actual.columns) != set(expected.columns):
            raise WrongInput(f"Step changed the preceding {name} coordinate set after reaggregation.")
        actual = actual.reindex(index=expected.index, columns=expected.columns).to_numpy(dtype=float)
        reference = expected.to_numpy(dtype=float)
        difference = np.abs(actual - reference)
        matrix_atol, matrix_rtol = (atol, rtol) if name in ('Z', 'Y', 'V') else (ATOL, RTOL)
        passed = np.isfinite(actual).all() and np.isfinite(reference).all() and (
            difference <= matrix_atol + matrix_rtol * np.abs(reference)).all()
        report[name] = {"passed": bool(passed), "max_absolute_difference": float(difference.max(initial=0))}
        if report_only and name in ('Z', 'Y', 'V', 'X', 'VY'):
            report[name]['enforced'] = False
        if cleanup and name in ('Z', 'Y', 'V'):
            report[name]['strict_passed'] = bool((difference <= ATOL + RTOL * np.abs(reference)).all())
        if not np.isfinite(actual).all() or not np.isfinite(reference).all():
            raise WrongInput(f'Nonfinite values in reconstructed {name}.')
        if not passed and not (report_only and name in ('Z', 'Y', 'V', 'X', 'VY')):
            raise WrongInput(f"Step does not preserve preceding {name}: {report[name]}")
    z, v, x = (after.resolve(name) for name in ("Z", "V", "X"))
    sector_level = "Sector" if "Sector" in z.columns.names else "Item"
    inherit = split_model_options and split_model_options['accounting'] == 'inherit'
    selected = z.columns.get_level_values(sector_level).isin(
        set(parents) | set(parents.values()) if inherit else parents)
    production = x.iloc[:, 0].reindex(z.columns[selected]).to_numpy(dtype=float)
    residual = (z.loc[:, selected].sum(axis=0) + v.loc[:, selected].sum(axis=0)).to_numpy(dtype=float) - production
    expected = np.zeros(len(production))
    if inherit:
        from mario.ops.split_model import inherited_accounting
        targets = inherited_accounting(before,x,parents,scenario=scenario)
        expected = targets['column'].reindex(z.columns[selected]).to_numpy(dtype=float)
        row_residual = after.resolve('Z').sum(axis=1)+after.resolve('Y').sum(axis=1)-x.iloc[:,0]
        row_difference = row_residual-targets['row']
        row_passed = np.isfinite(row_difference).all() and (
            row_difference.abs() <= atol+rtol*x.iloc[:,0].abs()).all()
        report['inherited_row_accounting'] = {
            'passed':bool(row_passed),'max_absolute_difference':float(row_difference.abs().max()),
            'max_absolute_inherited_residual':float(targets['row'].abs().max())}
        if not np.isfinite(row_difference).all():
            raise WrongInput('Nonfinite row-accounting discrepancies.')
        if not row_passed and not report_only:
            raise WrongInput(f"Step introduced row-accounting discrepancies: {report['inherited_row_accounting']}")
    difference = residual-expected
    passed = np.isfinite(difference).all() and (np.abs(difference) <= atol + rtol * np.abs(production)).all()
    report["new_sector_column_accounting"] = {"passed": bool(passed),
        "max_absolute_difference": float(np.abs(difference).max(initial=0)),
        "max_absolute_inherited_residual": float(np.abs(expected).max(initial=0))}
    if not np.isfinite(difference).all():
        raise WrongInput('Nonfinite column-accounting discrepancies.')
    if not passed and not report_only:
        raise WrongInput(f"New-sector columns are not balanced: {report['new_sector_column_accounting']}")
    for name in ("Z", "Y"):
        baseline = before.resolve(name, scenario=scenario).to_numpy(dtype=float)
        result = after.resolve(name).to_numpy(dtype=float)
        if (baseline >= 0).all() and (result < -ATOL).any():
            raise WrongInput(f"Step introduced negative {name} flows beyond the numerical tolerance.")
    y = after.resolve("Y")
    source_index = pd.MultiIndex.from_tuples(
        [(*label[:-1], parents.get(label[-1], label[-1])) for label in y.index], names=y.index.names)
    preceding = before.resolve("Y", scenario=scenario).reindex(index=source_index, columns=y.columns).to_numpy(dtype=float)
    result = y.to_numpy(dtype=float)
    invalid = ((preceding > 0) & (result < -ATOL)) | ((preceding < 0) & (result > ATOL))
    invalid |= (preceding == 0) & (np.abs(result) > ATOL)
    if invalid.any():
        raise WrongInput("Step changed the sign domain of a preceding final-demand cell.")
    return report


def _fingerprint(workbook, sector):
    master = workbook.master_sheet.loc[workbook.master_sheet["Sector"].eq(sector)]
    payload = {"master": master.to_json(orient="records", double_precision=15), "clusters": workbook.item_clusters,
               "regions": workbook.regions_clusters, "factors": workbook.factors_clusters,
               "inventories": {str(name): workbook.inventories_by_sheet[name].to_json(orient="records", double_precision=15)
                               for name in master["Inventory sheet"].dropna()}}
    for name, column in (("Total outputs", "Sector"), ("Trades", "Sector_from")):
        frame = (workbook.split_info or {}).get(name)
        if frame is not None:
            payload[name] = frame.loc[frame[column].eq(sector)].to_json(orient="records", double_precision=15)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _remaining(workbook, existing):
    master = workbook.master_sheet.loc[~workbook.master_sheet["Sector"].isin(existing)].copy()
    names = set(master["Inventory sheet"].dropna())
    pending = set(master["Sector"])
    support = {name: frame.copy() for name, frame in (workbook.split_info or {}).items()}
    for name, column in (("Total outputs", "Sector"), ("Trades", "Sector_from")):
        if name in support:
            support[name] = support[name].loc[support[name][column].isin(pending)].copy()
    plan = {name: [s for s in group if s in pending] for name, group in (workbook.intermediate_steps or {}).items()}
    return replace(workbook, master_sheet=master, inventories_by_sheet={
        name: frame for name, frame in workbook.inventories_by_sheet.items() if name in names},
        split_info=support, intermediate_steps={name: values for name, values in plan.items() if values})


def _digest(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def refinement_priors(database, canonical, active, parents):
    """Restore finer supplier priors for previously introduced buyer sectors.

    Canonical coefficients determine conditional supplier shares. The preceding
    flow fixes their total, including its origin distribution. These remain
    soft CE priors; all preceding aggregates remain hard constraints.
    """
    from collections import defaultdict
    import pint
    z = database.resolve("Z")
    regions = database.get_index("Region")
    available = set(database.get_index("Sector")) | set(active)
    families = {parent: [parent, *(s for s in active if parents[s] == parent)]
                for parent in {parents[s] for s in active}}
    rows = []
    for buyer, record in canonical.items():
        clusters = record["clusters"]

        def project(item, trail=()):
            if item in available:
                return {item}
            if item in trail:
                raise WrongInput(f"Cyclic deferred inventory reference: {item}")
            if item in parents:
                return project(parents[item], (*trail, item))
            if item in clusters:
                return set().union(*(project(v, (*trail, item)) for v in clusters[item]))
            raise WrongInput(f"Unresolved deferred input: {item}")

        for profile in record["profiles"]:
            dest = profile["region"]
            destinations = [dest] if dest in regions else record["regions"].get(dest, [])
            for destination in destinations:
                column = (destination, "Sector", buyer)
                if column not in z.columns:
                    raise WrongInput("Deferred refinements currently require the standard IOT row layout.")
                for parent, children in families.items():
                    if any(child not in record.get("planned_sectors", parents) for child in children[1:]):
                        # A later extension outside the original plan was not
                        # an observed zero in the earlier canonical inventory.
                        continue
                    totals = {r: float(z.loc[(r, "Sector", parent), column]) for r in regions}
                    shares = defaultdict(float)
                    has_fine_observation = False
                    for observation in profile["rows"]:
                        if observation.get("Item type") != "Sector":
                            continue
                        items = project(observation["DB Item"])
                        if len(items) != 1:
                            # An aggregate observation supplies no conditional
                            # information inside the group it denotes.
                            continue
                        item = next(iter(items))
                        if item not in children:
                            continue
                        origin = observation.get("DB Region")
                        origins = [origin] if origin in regions else record["regions"].get(origin, [])
                        if not origins:
                            raise WrongInput(f"Unresolved deferred input origin: {origin}")
                        q = float(observation["Quantity"])
                        source_unit = observation["Unit"]
                        target_unit = database.units["Sector"].loc[parent, "unit"]
                        if source_unit != target_unit:
                            q *= pint.UnitRegistry()(source_unit).to(target_unit).magnitude
                        if q < 0 or not np.isfinite(q):
                            raise WrongInput("Deferred sector input priors must be finite and nonnegative.")
                        total = sum(totals[r] for r in origins)
                        if total > 0:
                            for origin_region in origins:
                                shares[(origin_region, item)] += q * totals[origin_region] / total
                        has_fine_observation = True
                    if not has_fine_observation:
                        continue
                    for origin in regions:
                        total_share = sum(shares[(origin, child)] for child in children)
                        if total_share <= 0 or totals[origin] <= 0:
                            continue
                        for child in children:
                            rows.append({"region_from_Name": origin, "sector_from_Name": child,
                                         "region_to_Name": destination, "sector_to_Name": buyer,
                                         "values": totals[origin] * shares[(origin, child)] / total_share})
    return pd.DataFrame(rows)


def _canonical_record(workbook, sector, parents):
    master = workbook.master_sheet.loc[workbook.master_sheet["Sector"].eq(sector)]
    return {"profiles": [{"region": row["Region"], "rows": json.loads(
        workbook.inventories_by_sheet[row["Inventory sheet"]].to_json(orient="records", double_precision=15))}
                         for _, row in master.iterrows()],
            "clusters": workbook.item_clusters, "regions": workbook.regions_clusters,
            "planned_sectors": list(parents)}


def load_checkpoint(path):
    """Load a committed checkpoint; preserve history for editing the full plan."""
    import mario
    path = Path(path)
    state = json.loads((path / "state.json").read_text())
    if state.get("format") != "mario-sector-steps-v1" or state.get("status") != "complete":
        raise WrongInput("Not a completed MARIO sector-step checkpoint.")
    for relative, digest in state["files"].items():
        source = path / relative
        if source.resolve().is_relative_to(path.resolve()) is False or _digest(source) != digest:
            raise WrongInput(f"Checkpoint file changed or is incomplete: {relative}")
    relative = state.get('database_directory', 'database')
    if not isinstance(relative,str) or not relative.strip() or Path(relative).is_absolute():
        raise WrongInput('Invalid checkpoint database directory.')
    directory = (path / relative).resolve()
    if not directory.is_relative_to(path.resolve()):
        raise WrongInput('Checkpoint database directory must remain inside the checkpoint.')
    database = mario.parse_from_parquet(str(directory / "flows"), table="IOT", mode="flows")
    if (state.get('split_model_options') or {}).get('accounting') == 'inherit':
        # The generic flow parser treats X as derived. Here it is an audited
        # independent target, which must survive serialization and resume.
        output = pd.read_parquet(directory/'flows'/'X.parquet')
        if (not output.index.equals(database.Z.index) or output.shape[1]!=1
                or not np.isfinite(output.to_numpy()).all() or (output.to_numpy()<0).any()):
            raise WrongInput('Invalid independent output in inherited-accounting checkpoint.')
        database.reset_to_flows('baseline')
        database.matrices['baseline']['X'] = output
    database._intermediate_steps_state = state
    return database


def compatible_model_definition(recorded, current):
    """Compare the mathematical definition separately from export-policy code.

    Keep the complete source hashes in each checkpoint. Only the dedicated
    postprocessing module may change without invalidating the preceding solve;
    workbooks, operators, model construction and all other fields stay exact.
    """
    def mathematical(definition):
        if not isinstance(definition, dict):
            return definition
        shared = dict(definition.get('shared_operators_sha256', {}))
        shared.pop('split_solution.py', None)
        return {**definition, 'shared_operators_sha256': shared}
    return mathematical(recorded) == mathematical(current)


def run_intermediate_steps(instance, *, io, scenario, inplace, split, save_intermediates, options,
                           stop_after_step=None, allow_model_change=False, on_step_failure="raise"):
    if not save_intermediates:
        raise WrongInput("save_intermediates is mandatory when intermediate_steps=True.")
    if instance.table_type != "IOT" or not split:
        raise WrongInput("Intermediate sector steps currently require an IOT and split=True.")
    if options.get("only_input_data_gen") or options.get("parent_name") or options.get("parent_names"):
        raise WrongInput("Intermediate steps require solved outputs and stable parent labels; "
                         "only_input_data_gen and parent renaming are not supported.")
    if options.get("keep_all_split_steps"):
        raise WrongInput("Intermediate steps save the accepted baseline; keep_all_split_steps must be False.")
    instance._validate_scenario(scenario)
    target = instance if inplace else instance.copy()
    if io == "inventories":
        workbook = getattr(instance, "add_sectors_workbook", None)
        if workbook is None or not workbook.inventories_by_sheet:
            raise WrongInput("Read the workbook with read_inventories=True before running intermediate steps.")
        workbook = _copy_add_sector_workbook(workbook)
    else:
        workbook, _ = load_add_sector_workbook_input(io, table="IOT", read_inventories=True, split=True)
    state = getattr(instance, "_intermediate_steps_state", {})
    completed = state.get("completed_sectors", [])
    model_options = options.get('split_model_options')
    from mario.ops.split_model import normalize_options, describe_model, MODEL_REVISION
    if completed and model_options is not None and state.get('split_model_revision') != MODEL_REVISION:
        raise WrongInput('Split model factor domains changed or entropy support changed; restart before the completed steps. '
                         'Historical checkpoints remain readable but cannot silently use the new formulation.')
    preceding_options = normalize_options(state.get('split_model_options'))
    if completed and preceding_options != model_options:
        objective_keys = {'model', 'flow_loss', 'value_added_loss', 'complete_intermediate_priors'}
        if (not allow_model_change or preceding_options is None or model_options is None
                or any(preceding_options[k] != model_options[k] for k in model_options.keys() - objective_keys)):
            raise WrongInput('Split model options changed; only an explicit named-objective transition with '
                             'unchanged accounting, weights and numerical controls is allowed.')
    validation_code_transition = None
    if completed and preceding_options is not None:
        recorded_definition = state.get('model_definition')
        current_definition = describe_model(preceding_options, staged=True)
        if not compatible_model_definition(recorded_definition, current_definition):
            raise WrongInput('Packaged split model definition changed; restart before the completed steps.')
        if recorded_definition != current_definition:
            validation_code_transition = dict(
                module='split_solution.py', reason='postprocessing_policy_only',
                previous_sha256=recorded_definition.get('shared_operators_sha256', {}).get('split_solution.py'),
                current_sha256=current_definition['shared_operators_sha256'].get('split_solution.py'))
    plan, parents = validate_plan(workbook, target.get_index("Sector"), completed=completed)
    if stop_after_step is not None and stop_after_step not in [name for name, _ in plan]:
        raise WrongInput("stop_after_step must name a pending group in Intermediate steps.")
    previous_parents = state.get("sector_parents", {})
    if any(parents[s] != previous_parents[s] for s in parents.keys() & previous_parents.keys()):
        raise WrongInput("Parent correspondences changed; restart before the affected completed steps.")
    parents = {**previous_parents, **parents}
    canonical = dict(state.get("canonical_inventories", {}))
    fingerprints = dict(state.get("sector_fingerprints", {}))
    for sector in set(completed) & set(workbook.master_sheet["Sector"]):
        if fingerprints.get(sector) != _fingerprint(workbook, sector):
            raise WrongInput(f"Completed sector {sector!r} was edited; resume from an earlier checkpoint.")
    root = Path(save_intermediates)
    root.mkdir(parents=True, exist_ok=True)
    counter = state.get("step_index", 0)
    deferred = set(state.get('deferred_sectors', [])) - set(target.get_index('Sector'))
    report = dict(format='mario-sector-steps-report-v1', run_id=uuid4().hex,
                  status='running', on_step_failure=on_step_failure,
                  stop_after_step=stop_after_step, attempts=[], last_checkpoint_this_call=None)

    def save_report(status):
        pending = set(workbook.master_sheet['Sector']) - set(target.get_index('Sector'))
        report.update(status=status, completed_sectors=list(
            getattr(target, '_intermediate_steps_state', {}).get('completed_sectors', [])),
            pending_sectors=sorted(pending), deferred_sectors=sorted(deferred & pending))
        _write_run_report(root, report)
        target._intermediate_steps_report = json.loads(json.dumps(report))

    save_report('running')
    for name, sectors in plan:
        counter += 1
        slug = re.sub(r"[^\w-]+", "_", name, flags=re.UNICODE).strip("_")[:50] or "step"
        destination = root / f"{counter:03d}_{slug}"
        if destination.exists():
            report['error'] = f'Checkpoint already exists: {destination}'
            save_report('failed')
            raise FileExistsError(f"Checkpoint already exists: {destination}")
        staging = Path(tempfile.mkdtemp(prefix=f".{counter:03d}_{slug}_", dir=root))
        attempt = dict(step=name, step_index=counter, sectors=list(sectors),
                       status='running', directory=str(staging), phase='compile')
        report['attempts'].append(attempt)
        save_report('running')
        missing_parents = {parents[s] for s in sectors} - set(target.get_index('Sector'))
        blocked = bool(missing_parents) and missing_parents <= deferred
        try:
            if blocked:
                raise WrongInput(f'Step depends on deferred parent sectors: {sorted(missing_parents)}')
            compiled = compile_step(workbook, sectors, target.get_index("Sector"), parents)
            candidate = target.copy()
            _attach(candidate, compiled)
            candidate._intermediate_refinement = refinement_priors(target, canonical, sectors, parents)
            refinement_count = len(candidate._intermediate_refinement)
            write_workbook_payload(compiled, staging / "step_add_sectors.xlsx", instance=target)
            solve_options = dict(options)
            work_root = Path(solve_options.pop("cvxlab_path")) / destination.name if options.get("cvxlab_path") else staging / "cvxlab"
            work_root.mkdir(parents=True, exist_ok=True)
            solve_options["cvxlab_path"] = work_root
            attempt['phase'] = 'solve'
            try:
                candidate.add_sectors(io="inventories", scenario=scenario, split=True, **solve_options)
            finally:
                candidate.__dict__.pop("_intermediate_refinement", None)
            from mario.ops.split_solution import effective_validation_options
            attempt['phase'] = 'validate'
            validation_options = effective_validation_options(
                model_options, getattr(candidate, '_last_split_status', []))
            preservation = verify_preservation(target, candidate, {s: parents[s] for s in sectors}, scenario=scenario,
                                               split_model_options=validation_options)
            attempt['phase'] = 'export'
            candidate.to_parquet(path=staging / "database", flows=True, coefficients=False, include_meta=True)
            write_workbook_payload(_remaining(workbook, candidate.get_index("Sector")),
                                   staging / "remaining_add_sectors.xlsx", instance=candidate)
            write_workbook_payload(workbook, staging / "source_add_sectors.xlsx", instance=candidate)
            completed = list(dict.fromkeys([*completed, *sectors]))
            fingerprints.update({s: _fingerprint(workbook, s) for s in sectors})
            canonical.update({s: _canonical_record(workbook, s, parents) for s in sectors})
            deferred.difference_update(sectors)
            cleanup = (validation_options or {}).get('solution_cleanup')
            state = {"format": "mario-sector-steps-v1", "status": "complete", "step_index": counter,
                     "step_name": name, "step_sectors": sectors, "completed_sectors": completed,
                     "sector_fingerprints": fingerprints, "preservation": preservation,
                     "sector_parents": parents, "canonical_inventories": canonical,
                     "on_step_failure": on_step_failure, "deferred_sectors": sorted(deferred),
                     "refinement_prior_cells": refinement_count,
                     "runtime": {p: version(p) for p in ("mariopy", "cvxlab", "pandas", "cvxpy")},
                     "solver_status": getattr(candidate, "_last_split_status", []),
                     "solver_replay": getattr(candidate, '_last_split_solver_replay', None),
                     "split_model_options": model_options,
                     "numerical_validation_policy": cleanup,
                     "numerical_validation_code_transition": validation_code_transition,
                     "split_model_revision": MODEL_REVISION if model_options is not None else None,
                     "model_definition": getattr(candidate, '_last_split_model_definition', None),
                     "model_history": [*state.get('model_history', []), dict(
                         step_index=counter, step_name=name, sectors=sectors,
                         split_model_options=model_options,
                         model_definition=getattr(candidate, '_last_split_model_definition', None),
                         solver=getattr(candidate, '_last_split_solver', solve_options.get('solver')),
                         explicit_model_change=bool(state.get('completed_sectors') and
                             normalize_options(state.get('split_model_options')) != model_options))],
                     "pending_recalculations": ['E'] if preservation['E'].get('requires_recalculation') else [],
                     "tolerances": {"absolute": cleanup.get('absolute_tolerance', ATOL) if cleanup else ATOL,
                                    "relative": cleanup.get('relative_tolerance', RTOL) if cleanup else RTOL,
                                    "monetary_residuals_enforced": not bool(cleanup and cleanup.get('validation') == 'report_only')},
                     "files": {str(p.relative_to(staging)): _digest(p)
                               for p in (staging / "database").rglob("*") if p.is_file()}}
            (staging / "state.json").write_text(json.dumps(state, indent=2, allow_nan=False))
            staging.rename(destination)
        except Exception as exc:
            recoverable = blocked or (attempt['phase'] in ('solve', 'validate') and _recoverable_step_failure(exc))
            attempt.update(status='blocked' if blocked else 'failed', error=str(exc),
                           error_type=type(exc).__name__, recoverable=recoverable)
            (staging / "failure.json").write_text(json.dumps({"step": name, "sectors": sectors,
                "error": str(exc), "traceback": traceback.format_exc(),
                "status": attempt['status'], "completed_sectors": report['completed_sectors'],
                "phase": attempt['phase'], "recoverable": recoverable}, indent=2))
            if on_step_failure == 'continue' and recoverable:
                deferred.update(sectors)
                save_report('running')
                logger.warning('Step %r %s; retaining the preceding database and continuing: %s',
                               name, attempt['status'], exc)
                if name == stop_after_step:
                    break
                continue
            save_report('failed')
            raise
        candidate._intermediate_steps_state = state
        target.__dict__.clear()
        target.__dict__.update(candidate.__dict__)
        attempt.update(status='accepted', phase='complete', directory=str(destination))
        report['last_checkpoint_this_call'] = str(destination)
        save_report('running')
        validation_code_transition = None
        scenario = "baseline"
        if name == stop_after_step:
            break
    save_report('partial' if report['deferred_sectors'] else 'stopped' if report['pending_sectors'] else 'complete')
    return None if inplace else target
