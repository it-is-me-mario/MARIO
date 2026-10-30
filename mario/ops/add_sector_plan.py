"""Plan sequential IOT splits without constructing or solving a CVXLab model."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import math
import os
from pathlib import Path
import posixpath
import re
import shutil
import stat
import tempfile
from xml.dom import minidom
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pandas as pd
import pint
from openpyxl.utils import get_column_letter

from mario.log_exc.exceptions import WrongInput
from mario.ops.add_sector_workbook import load_add_sector_workbook_input


@dataclass
class AddSectorsIntermediateStepsPlan:
    """Inspectable plan already written to ``path``; edit that workbook to revise it."""

    steps: dict[str, list[str]]
    summary: pd.DataFrame
    diagnostics: dict
    path: Path


def _pairs(values, sectors):
    result = set()
    for pair in values or []:
        if (not isinstance(pair, (tuple, list)) or len(pair) != 2
                or any(not isinstance(s, str) or s not in sectors for s in pair)):
            raise WrongInput("before requires pairs of sector names from Master.")
        if pair[0] == pair[1]:
            raise WrongInput("A sector cannot be before itself.")
        result.add(tuple(pair))
    return result


def _units(sectors, together, maximum):
    roots = {s: s for s in sectors}

    def root(s):
        while roots[s] != s:
            s = roots[s]
        return s

    for group in together or []:
        if (not isinstance(group, (tuple, list)) or not group
                or any(not isinstance(s, str) or s not in sectors for s in group)):
            raise WrongInput("together requires non-empty groups of sector names from Master.")
        members = {root(s) for s in group}
        first = min(members)
        for member in members:
            roots[member] = first
    groups = defaultdict(list)
    for s in sorted(sectors):
        groups[root(s)].append(s)
    if any(len(group) > maximum for group in groups.values()):
        raise WrongInput("A together group exceeds max_sectors_per_step.")
    groups = {tuple(group): group for group in groups.values()}
    return groups, {s: key for key, group in groups.items() for s in group}


def _hard_order(groups, hard):
    remaining, ordered = set(groups), []
    while remaining:
        ready = [v for v in remaining if not any(b == v and a in remaining for a, b in hard)]
        if not ready:
            raise WrongInput("Contradictory before/parent precedences: no valid step order exists.")
        chosen = min(ready)
        ordered.append(chosen)
        remaining.remove(chosen)
    return ordered


def _weighted_order(groups, hard, weights):
    """Kahn ordering on acyclic preferences, weighted greedy cycle breaking."""
    _hard_order(groups, hard)
    remaining, ordered = set(groups), []
    while remaining:
        ready = [v for v in remaining if not any(b == v and a in remaining for a, b in hard)]

        def incoming(v):
            return math.fsum(w for (a, b), w in weights.items() if b == v and a in remaining)

        def outgoing(v):
            return math.fsum(w for (a, b), w in weights.items() if a == v and b in remaining)

        unblocked = [v for v in ready if incoming(v) == 0]
        chosen = min(unblocked, key=lambda v: (-outgoing(v), v)) if unblocked else min(
            ready, key=lambda v: (incoming(v) - outgoing(v), incoming(v), v))
        ordered.append(chosen)
        remaining.remove(chosen)
    return ordered


def _cycles(groups, edges):
    # Reachability is small here (one node per sector group, not per MRIO cell).
    reachable = {v: {b for a, b in edges if a == v} for v in groups}
    for middle in sorted(groups):
        for node in sorted(groups):
            if middle in reachable[node]:
                reachable[node].update(reachable[middle])
    seen, cycles = set(), []
    for node in sorted(groups):
        if node in seen:
            continue
        component = {v for v in groups if v in reachable[node] and node in reachable[v]}
        if len(component) > 1:
            seen.update(component)
            cycles.append(sorted(s for group in component for s in group))
    return cycles


def _dependencies(database, workbook, sectors):
    """Economic weights: fixed regional output times positive input coefficient.

    Only resolved singleton observations identify a supplier. Multi-item
    clusters remain ambiguous; no equal allocation or confidence is invented.
    """
    master = workbook.master_sheet
    region_names = set(database.get_index("Region"))
    existing = set(database.get_index("Sector"))
    reference_unit = master.loc[master.Sector.eq(min(sectors)), "Unit"].iloc[0]
    if not isinstance(reference_unit, str) or not reference_unit.strip():
        raise WrongInput("Fill sector units in Master before planning.")
    ureg = pint.UnitRegistry()

    def money(unit):
        match = re.fullmatch(r"(?:(k|M|G|thousand|million|billion)\s*)?([A-Z]{3})", str(unit).strip())
        if match:
            prefix, currency = match.groups()
            return currency, {None:1., 'k':1e3, 'M':1e6, 'G':1e9,
                              'thousand':1e3, 'million':1e6, 'billion':1e9}[prefix]
        return None

    def convert(value, unit):
        try:
            value = float(value)
            if not math.isfinite(value) or value < 0:
                raise ValueError()
            if unit != reference_unit:
                source_money, reference_money = money(unit), money(reference_unit)
                if source_money and reference_money:
                    if source_money[0] != reference_money[0]:
                        raise ValueError("Currency conversion requires an explicit external exchange rate.")
                    value *= source_money[1] / reference_money[1]
                else:
                    value *= ureg(str(unit)).to(reference_unit).magnitude
            if not math.isfinite(value):
                raise ValueError()
            return value
        except (ValueError, TypeError, pint.errors.PintError) as exc:
            raise WrongInput("Planning requires finite nonnegative quantities and comparable "
                             f"sector monetary units (reference {reference_unit!r}).") from exc

    outputs = {}
    output_table = (workbook.split_info or {}).get("Total outputs", pd.DataFrame())
    for row in output_table.to_dict("records"):
        if row["Sector"] not in sectors:
            continue
        key = (row["Sector"], row["Region"])
        if key in outputs:
            raise WrongInput(f"Duplicate Total outputs observation for {key}.")
        outputs[key] = convert(row["Quantity"], row["Unit"])

    def resolve(item, trail=()):
        if item in sectors or item in existing:
            return {item}
        if item in trail or item not in workbook.item_clusters:
            raise WrongInput(f"Unknown or cyclic inventory sector/cluster: {item!r}.")
        return set().union(*(resolve(v, (*trail, item)) for v in workbook.item_clusters[item]))

    weights, ambiguous, no_detail, ignored = defaultdict(float), [], [], []
    covered = set()
    for record in master.to_dict("records"):
        buyer, region = record["Sector"], record["Region"]
        if buyer not in sectors:
            continue
        regions = [region] if region in region_names else workbook.regions_clusters.get(region, [])
        if not regions or not set(regions) <= region_names:
            raise WrongInput(f"Unknown Master region/cluster: {region!r}.")
        keys = {(buyer, r) for r in regions}
        if covered & keys:
            raise WrongInput(f"Overlapping Master inventory coverage for {buyer!r}.")
        covered.update(keys)
        if not keys <= outputs.keys():
            raise WrongInput(f"Fill Total outputs for every planned sector/region before planning: {buyer!r}.")
        output = math.fsum(outputs[k] for k in sorted(keys))
        output_basis = convert(1., record['Unit'])
        sheet = record["Inventory sheet"]
        empty = record.get("Leave empty")
        if empty is True or (isinstance(empty, (int, float)) and empty == 1):
            no_detail.append(dict(sector=buyer, region=region, reason="leave_empty"))
            continue
        fine = False
        for observation in workbook.inventories_by_sheet[sheet].to_dict("records"):
            if observation.get("Item type") != "Sector":
                continue
            change = observation.get("Change type")
            if change != "Update":
                ignored.append(dict(sector=buyer, region=region, item=observation.get("DB Item"),
                                    reason="non_update_observation"))
                continue
            q = convert(observation["Quantity"], observation["Unit"])
            members = resolve(observation["DB Item"])
            if len(members) != 1:
                if members & sectors and q > 0:
                    ambiguous.append(dict(sector=buyer, region=region, item=observation["DB Item"],
                                          members=sorted(members)))
                continue
            supplier = next(iter(members))
            if supplier in sectors and supplier != buyer and q > 0:
                fine = True
                weights[(supplier, buyer)] += output * q / output_basis
        if not fine:
            no_detail.append(dict(sector=buyer, region=region, reason="no_explicit_new_supplier"))
    if not all(math.isfinite(w) for w in weights.values()):
        raise WrongInput("Nonfinite dependency weight; check inventory quantities and output units.")
    return dict(weights), dict(weight_unit=reference_unit, ambiguous_clusters=ambiguous,
                               profiles_without_explicit_dependencies=no_detail, ignored_observations=ignored)


def _sheet_xml(steps):
    root = ET.Element("worksheet", xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    data = ET.SubElement(root, "sheetData")
    for i in range(1 + max(map(len, steps.values()))):
        row = ET.SubElement(data, "row", r=str(i + 1))
        for j, (name, sectors) in enumerate(steps.items(), 1):
            if i and len(sectors) < i:
                continue
            cell = ET.SubElement(row, "c", r=f"{get_column_letter(j)}{i + 1}", t="inlineStr")
            text = ET.SubElement(ET.SubElement(cell, "is"), "t")
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            text.text = name if i == 0 else sectors[i - 1]
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _write_steps(path, steps, signature):
    """Replace one XLSX part atomically; copy every other part byte for byte."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package = "http://schemas.openxmlformats.org/package/2006/relationships"
    content = "http://schemas.openxmlformats.org/package/2006/content-types"

    def element(document, parent, namespace, name, attrs):
        tag = f"{parent.prefix}:{name}" if parent.prefix else name
        node = document.createElementNS(namespace, tag)
        for key, value in attrs.items():
            node.setAttribute(key, str(value))
        parent.appendChild(node)
        return node

    fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}-steps-", suffix=".xlsx", dir=path.parent)
    os.close(fd)
    try:
        with ZipFile(path) as source:
            if len(source.namelist()) != len(set(source.namelist())):
                raise WrongInput("Duplicate XLSX archive entries; cannot safely update the plan.")
            book = minidom.parseString(source.read("xl/workbook.xml"))
            relationships = minidom.parseString(source.read("xl/_rels/workbook.xml.rels"))
            sheets = book.getElementsByTagNameNS(ns, "sheets")[0]
            matches = [s for s in sheets.getElementsByTagNameNS(ns, "sheet")
                       if s.getAttribute("name") == "Intermediate steps"]
            replacements = {}
            if matches:
                rid = matches[0].getAttributeNS(rel, "id")
                target = next(r.getAttribute("Target") for r in relationships.documentElement.childNodes
                              if r.nodeType == r.ELEMENT_NODE and r.getAttribute("Id") == rid)
                part = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            else:
                number = 1
                while f"xl/worksheets/sheet{number}.xml" in source.namelist():
                    number += 1
                part = f"xl/worksheets/sheet{number}.xml"
                used_ids = {r.getAttribute("Id") for r in relationships.documentElement.childNodes
                            if r.nodeType == r.ELEMENT_NODE}
                number = 1
                while f"rId{number}" in used_ids:
                    number += 1
                rid = f"rId{number}"
                sheet_id = 1 + max(int(s.getAttribute("sheetId"))
                                   for s in sheets.getElementsByTagNameNS(ns, "sheet"))
                sheet = element(book, sheets, ns, "sheet", dict(name="Intermediate steps", sheetId=sheet_id))
                sheet.setAttribute("xmlns:r", rel)
                sheet.setAttributeNS(rel, "r:id", rid)
                element(relationships, relationships.documentElement, package, "Relationship",
                        dict(Id=rid, Type=rel + "/worksheet", Target="/" + part))
                types = minidom.parseString(source.read("[Content_Types].xml"))
                element(types, types.documentElement, content, "Override", dict(
                    PartName="/" + part,
                    ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"))
                replacements.update({"xl/workbook.xml": book.toxml(encoding="utf-8"),
                                     "xl/_rels/workbook.xml.rels": relationships.toxml(encoding="utf-8"),
                                     "[Content_Types].xml": types.toxml(encoding="utf-8")})
            replacements[part] = _sheet_xml(steps)
            with ZipFile(temporary, "w") as destination:
                destination.comment = source.comment
                for info in source.infolist():
                    if info.filename in replacements:
                        destination.writestr(info, replacements.pop(info.filename))
                    else:
                        with source.open(info) as src, destination.open(info, "w") as dst:
                            shutil.copyfileobj(src, dst, length=1024 * 1024)
                for name, value in replacements.items():
                    destination.writestr(name, value)
        current = path.stat()
        if (current.st_mtime_ns, current.st_size, current.st_ino) != signature:
            raise WrongInput("The workbook changed during planning; no plan was written. Retry on the current file.")
        os.chmod(temporary, stat.S_IMODE(current.st_mode))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def get_intermediate_steps_plan(database, io, *, max_sectors_per_step, ordering, before, together):
    from mario.ops.add_sector_steps import _attach, compile_step, validate_plan

    if database.table_type != "IOT":
        raise WrongInput("Intermediate-step planning currently supports IOT sector splits only.")
    if (isinstance(max_sectors_per_step, bool) or not isinstance(max_sectors_per_step, int)
            or max_sectors_per_step < 1):
        raise WrongInput("max_sectors_per_step must be a positive integer.")
    if ordering not in ("suppliers_first", "buyers_first"):
        raise WrongInput("ordering must be 'suppliers_first' or 'buyers_first'.")
    if io == "inventories":
        io = getattr(database, "add_sectors_workbook_path", None)
    if not isinstance(io, (str, os.PathLike)):
        raise WrongInput("Provide one add_sectors.xlsx file, or first load it with read_add_sectors_excel.")
    path = Path(io).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".xlsx":
        raise WrongInput("Planning requires one existing .xlsx workbook, not a directory.")
    # A new plan must never invalidate an immutable, hashed checkpoint.
    for directory in path.parents:
        state_path = directory / "state.json"
        if state_path.is_file():
            import json
            state = json.loads(state_path.read_text())
            if (state.get("format") == "mario-sector-steps-v1"
                    and str(path.relative_to(directory)) in state.get("files", {})):
                raise WrongInput("Copy the workbook outside its committed checkpoint before replanning.")
    info = path.stat()
    signature = (info.st_mtime_ns, info.st_size, info.st_ino)
    workbook, _ = load_add_sector_workbook_input(path, table="IOT", read_inventories=True, split=True)
    sectors = set(workbook.master_sheet.Sector)
    if not sectors:
        raise WrongInput("Fill Master and its inventories before planning intermediate steps.")
    # Reuse the execution validator without depending on an old/absent plan.
    proposal = replace(workbook, intermediate_steps={"Planned sectors": sorted(sectors)})
    _, parents = validate_plan(proposal, database.get_index("Sector"))
    missing = set(parents.values()) - sectors - set(database.get_index("Sector"))
    if missing:
        raise WrongInput(f"Unknown split parent sectors: {sorted(missing)}")
    groups, membership = _units(sectors, together, max_sectors_per_step)
    precedences = _pairs(before, sectors) | {(p, s) for s, p in parents.items() if p in sectors}
    hard = set()
    for a, b in precedences:
        if membership[a] == membership[b]:
            raise WrongInput("A before/parent precedence conflicts with a together group.")
        hard.add((membership[a], membership[b]))
    _hard_order(groups, hard)
    dependencies, diagnostics = _dependencies(database, workbook, sectors)
    preferences = defaultdict(float)
    for (a, b), weight in dependencies.items():
        if ordering == "buyers_first":
            a, b = b, a
        if membership[a] != membership[b] and weight > 0:
            preferences[(membership[a], membership[b])] += weight
    ordered = _weighted_order(groups, hard, preferences)
    batches, batch, nodes = [], [], set()
    for node in ordered:
        if batch and (len(batch) + len(groups[node]) > max_sectors_per_step
                      or any((prior, node) in hard for prior in nodes)):
            batches.append(batch)
            batch, nodes = [], set()
        batch.extend(groups[node])
        nodes.add(node)
    if batch:
        batches.append(batch)
    steps = {f"Step {i}": group for i, group in enumerate(batches, 1)}
    if len(steps) > 16384 or max(map(len, steps.values())) > 1048575:
        raise WrongInput("The proposed plan exceeds Excel worksheet dimensions.")
    available = set(database.get_index("Sector"))
    for group in steps.values():
        compile_step(workbook, group, available, parents)
        available.update(group)
    step_of = {s: i for i, group in enumerate(batches, 1) for s in group}
    relations, violations = [], []
    for (a, b), weight in sorted(dependencies.items()):
        preferred_a, preferred_b = (a, b) if ordering == "suppliers_first" else (b, a)
        row = dict(supplier=a, buyer=b, weight=weight, supplier_step=step_of[a], buyer_step=step_of[b],
                   preference_satisfied=step_of[preferred_a] <= step_of[preferred_b])
        relations.append(row)
        if not row["preference_satisfied"] and weight > 0:
            violations.append(row)
    diagnostics.update(algorithm="deterministic_weighted_greedy", globally_optimal=False,
                       ordering=ordering, weight_basis="regional_output_times_positive_input_coefficient",
                       before=[list(pair) for pair in sorted(precedences)],
                       cycles=_cycles(groups, preferences), dependencies=relations,
                       unmet_preferences=violations,
                       unmet_preference_weight=math.fsum(r["weight"] for r in violations))
    summary = pd.DataFrame([dict(step=name, sectors=list(group), sector_count=len(group),
                                 unmet_preference_weight=math.fsum(
                                     r["weight"] for r in violations if
                                     (r["buyer"] if ordering == "suppliers_first" else r["supplier"]) in group))
                            for name, group in steps.items()])
    _write_steps(path, steps, signature)
    planned_workbook = replace(workbook, intermediate_steps={name:list(group) for name,group in steps.items()})
    _attach(database, planned_workbook)
    database.add_sectors_workbook_path = str(path)
    return AddSectorsIntermediateStepsPlan(steps, summary, diagnostics, path)
