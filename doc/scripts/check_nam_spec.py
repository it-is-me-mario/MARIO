#!/usr/bin/env python3
"""Validate the internal NAM draft and check its generated matrix reference.

This is a documentation contract check, not a NAM parser or runtime catalogue.
It deliberately uses only the standard library and does not import MARIO.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOGUE = ROOT / "doc" / "development" / "nam" / "catalogue.json"
RUNTIME_CONTRACT = ROOT / "mario" / "model" / "nam_schema.json"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def read_catalogue(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def validate_catalogue(spec: dict) -> list[str]:
    """Return contract errors without evaluating formulas or reading source files."""
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    require(spec.get("schema_version") == 2, "Unsupported NAM draft schema version.")
    require(spec.get("status") == "design_draft", "This checker is for a design_draft.")
    require(spec.get("implemented") is False, "The draft must not claim runtime support.")
    require(spec.get("table_kind") == "NAM", "Expected the NAM table kind.")
    require(spec.get("account_index") == ["reference_region", "set", "item"],
            "The national account identity must be reference_region / set / item.")
    require(spec.get("orientation") == "column_pays_row_receives", "Unexpected flow orientation.")
    require(set(spec.get("presence_states", [])) ==
            {"observed", "declared_zero", "unavailable", "derived"},
            "Presence states must distinguish unavailable data from zero and derived values.")

    sets = spec.get("sets", {})
    domains = spec.get("domains", {})
    axis_roles = spec.get("axis_roles", {})
    policies = spec.get("coefficient_policies", {})
    projections = spec.get("sut_projections", {})
    matrices = spec.get("matrices", [])
    names = [m.get("name") for m in matrices]
    require(len(names) == len(set(names)), "Matrix names must be unique.")
    require(all(isinstance(n, str) and n for n in names), "Every matrix needs a nonempty name.")
    aliases = [s.get("short_name", "").casefold() for s in sets.values()]
    require(all(aliases) and len(set(aliases)) == len(aliases), "NAM short names must be nonempty and unique.")
    labels = [s.get("label") for s in sets.values()]
    require(len(labels) == len(set(labels)), "Set labels must be unique.")
    require(set(domains.get("all_accounts", {}).get("sets", [])) == sets.keys(),
            "The national T view must cover every declared monetary accounting set.")
    for name, definition in sets.items():
        require(bool(definition.get("label")) and bool(definition.get("classification")),
                f"{name}: a set needs a label and classification.")
        if definition.get("classification") == "institutional_sectors":
            require(definition.get("account_role") in {"income", "capital", "trade"},
                    f"{name}: missing institutional accounting role.")
            require(definition.get("residency") in {"resident", "nonresident"},
                    f"{name}: missing residency relative to the reference economy.")

    for name, domain in domains.items():
        members = domain.get("sets", [])
        require(len(members) == len(set(members)), f"{name}: duplicate set in a domain.")
        require(set(members) <= sets.keys(), f"{name}: unknown set in a domain.")
        require(bool(members) or domain.get("derived_only") is True,
                f"{name}: only a derived-only domain may have no native sets.")
    for name, axis in axis_roles.items():
        require(axis.get("base") == "region" or axis.get("base") in sets,
                f"{name}: unknown axis classification.")
    for name, policy in policies.items():
        require(policy.get("status") in {"proposed", "review_required", "not_applicable", "implemented"},
                f"{name}: invalid coefficient review state.")
        require(bool(policy.get("denominator")) or policy.get("status") == "not_applicable",
                f"{name}: a coefficient proposal needs a denominator description.")
    valid_targets = {"U", "S", "Ya", "Yc", "Va", "Vc", "VY"}
    for name, projection in projections.items():
        require(set(projection.get("targets", [])) <= valid_targets,
                f"{name}: unknown SUT projection target.")
        require(bool(projection.get("rule")), f"{name}: missing projection rule.")

    by_name = {m.get("name"): m for m in matrices}
    valid_presence = {"core", "source_dependent", "optional", "trade_mode", "derived"}
    for matrix in matrices:
        name = matrix.get("name")
        role = matrix.get("role")
        require(role in {"flow", "result", "view", "coefficient"}, f"{name}: invalid matrix role.")
        require(matrix.get("presence") in valid_presence, f"{name}: invalid presence rule.")
        require(matrix.get("coefficient") in policies, f"{name}: unknown coefficient policy.")
        require(matrix.get("sut") in projections, f"{name}: missing/unknown SUT projection.")
        require(bool(matrix.get("description_it")), f"{name}: missing readable description.")
        require(set(matrix.get("depends_on", [])) <= by_name.keys(),
                f"{name}: unknown dependency.")
        for side, layout_key in (("rows", "optional_row_axes"),
                                 ("columns", "optional_column_axes")):
            domain = matrix.get(side)
            require(domain in domains, f"{name}: unknown {side} domain.")
            if role == "flow" and domain in domains:
                require(not domains[domain].get("derived_only") and domain != "all_accounts",
                        f"{name}: a native flow needs specific accounting domains.")
            if name not in {"T", "t", "X"} and domain in domains and not domains[domain].get("derived_only"):
                require(len(domains[domain]["sets"]) == 1,
                        f"{name}.{side}: exactly one accounting set is required.")
            layout = matrix.get(layout_key)
            if layout is not None:
                require(isinstance(layout, list) and bool(layout), f"{name}: empty optional layout.")
                if isinstance(layout, list) and layout:
                    require(layout[-1] == domain, f"{name}: {layout_key} must end in its domain.")
                    require(set(layout[:-1]) <= axis_roles.keys(),
                            f"{name}: unknown descriptor in {layout_key}.")
                    require(len(layout) == len(set(layout)),
                            f"{name}: repeated semantic role in {layout_key}.")
        if name == "T":
            require(matrix["rows"] == matrix["columns"] == "all_accounts",
                    "T must have identical complete accounting sets on both axes.")
        if role in {"result", "view", "coefficient"}:
            require(matrix.get("presence") == "derived", f"{name}: derived blocks cannot be native flows.")
            require(matrix.get("coefficient") == "none", f"{name}: derived presentation is not a normalized payment.")
            require(matrix.get("sut") == "derived_only", f"{name}: a derived balance/view cannot add SUT flows.")
        elif role == "flow":
            require(matrix.get("presence") != "derived", f"{name}: native authority must be explicit.")
            require(matrix.get("sut") != "derived_only", f"{name}: flow incorrectly marked as derived-only.")

    modes = spec.get("representations", {})
    trade_blocks = {m["name"] for m in matrices if m.get("presence") == "trade_mode"}
    require(set(modes) == {"use_imports", "supply_imports"}, "Both import representations must be specified.")
    owners = []
    for mode, definition in modes.items():
        active = definition.get("authoritative_import_blocks", [])
        alternative = definition.get("alternative_import_blocks", [])
        require(len(active) == len(set(active)) and len(alternative) == len(set(alternative)),
                f"{mode}: duplicate import block.")
        require(set(active).isdisjoint(alternative), f"{mode}: one import block has two authority roles.")
        require(set(active) | set(alternative) == trade_blocks,
                f"{mode}: import authority must cover exactly the declared trade blocks.")
        owners.append(set(active))
        require(definition.get("use_coverage") ==
                ("domestic" if mode == "use_imports" else "total"),
                f"{mode}: inconsistent domestic/total use coverage.")
        # Two authoritative blocks must not claim the same cells in T.
        cell_owners = {}
        for matrix in matrices:
            if matrix.get("role") != "flow" or matrix["name"] in alternative:
                continue
            row_sets = domains.get(matrix.get("rows"), {}).get("sets", [])
            col_sets = domains.get(matrix.get("columns"), {}).get("sets", [])
            for row_set in row_sets:
                for col_set in col_sets:
                    pair = (row_set, col_set)
                    require(pair not in cell_owners,
                            f"{mode}: {matrix['name']} overlaps {cell_owners.get(pair)} in T at {pair}.")
                    cell_owners[pair] = matrix["name"]
    if len(owners) == 2:
        require(owners[0].isdisjoint(owners[1]), "The alternative import authorities must be exclusive.")

    def visit(name, ancestors):
        if name in ancestors:
            errors.append(f"Derived dependency cycle at {name}.")
            return
        for dependency in by_name.get(name, {}).get("depends_on", []):
            visit(dependency, ancestors | {name})

    for name in by_name:
        visit(name, set())
    decisions = spec.get("open_decisions", [])
    decision_ids = [d.get("id") for d in decisions]
    require(len(decision_ids) == len(set(decision_ids)), "Open-decision IDs must be unique.")
    for decision in decisions:
        require(bool(decision.get("decision")), "An open decision needs a description.")
        require(isinstance(decision.get("blocks_flow_core"), bool),
                "An open decision must state whether it blocks the flow core.")
    for matrix in matrices:
        if matrix.get("role") == "coefficient":
            source = by_name.get(matrix.get("source"), {})
            require(matrix["name"] == source.get("name", "").lower(), "Coefficient names must be lowercase source names.")
            require(all(matrix[axis] == source.get(axis) for axis in ("rows", "columns")), "Coefficient axes must match their flows.")
            require(matrix.get("denominator") == ("X" if source.get("name") == "T" else sets[source["columns"]]["total_vector"]),
                    f"{matrix['name']}: wrong account denominator.")
    return errors


def render_catalogue(spec: dict) -> str:
    """Generate the readable internal table from the JSON source of truth."""
    def domain_label(key):
        domain = spec["domains"][key]
        members = domain["sets"]
        if len(members) == 1:
            return spec["sets"][members[0]]["label"]
        return {"income": "Income sectors (resident + nonresident)",
                "capital": "Capital sectors (resident + nonresident)",
                "all_accounts": "All national accounts"}.get(key, domain.get("label", key))

    lines = [
        ".. Generated by doc/scripts/check_nam_spec.py --write; edit catalogue.json.",
        ".. Internal design draft; not a public runtime reference.", "",
        "Proposed NAM matrix catalogue", "=============================", "",
        "This list describes the NAM specification, including future conversion",
        "policies. Internal flow-core support is described in `the design contract",
        "<README.rst>`_ for geography, authority, units, signs and conversion rules.", "",
        "Domains carry their declared reference-economy scope. Extra partner and",
        "imported-product descriptors are specified in `catalogue.json",
        "<catalogue.json>`_. Account-total normalization and a source-specific FIGARO",
        "SUT projection are implemented; the general conversion policies below remain proposals.", "",
        ".. list-table:: Proposed blocks",
        "   :header-rows: 1", "   :widths: 10 17 17 8 12 36", "",
        "   * - Name", "     - Rows", "     - Columns", "     - Role",
        "     - SUT target", "     - Significato",]
    for matrix in spec["matrices"]:
        targets = spec["sut_projections"][matrix["sut"]]["targets"]
        lines.extend([
            f"   * - ``{matrix['name']}``",
            f"     - {domain_label(matrix['rows'])}",
            f"     - {domain_label(matrix['columns'])}",
            f"     - {matrix['role']}",
            f"     - {', '.join(f'``{t}``' for t in targets) if targets else 'Pending review' if matrix['sut'] == 'pending' else 'Outside SUT flows'}",
            f"     - {matrix['description_it']}",
        ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--write", action="store_true", help="Regenerate the readable internal catalogue.")
    args = parser.parse_args()
    try:
        spec = read_catalogue(args.catalogue)
        errors = validate_catalogue(spec)
        runtime = read_catalogue(RUNTIME_CONTRACT)
        for key in ("sets", "domains", "axis_roles", "representations"):
            if runtime[key] != spec[key]:
                errors.append(f"Draft {key} differs from the implemented runtime contract.")
        structural_blocks = [{key: m[key] for key in ("name", "rows", "columns", "role", "presence")}
                             for m in spec["matrices"]]
        if [{key: m[key] for key in ("name", "rows", "columns", "role", "presence")}
                for m in runtime["matrices"]] != structural_blocks:
            errors.append("Draft block domains/roles differ from the implemented runtime contract.")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        parser.exit(1, f"Invalid NAM draft: {exc}\n")
    if errors:
        parser.exit(1, "Invalid NAM draft:\n" + "\n".join(f"- {e}" for e in errors) + "\n")
    output = args.catalogue.with_suffix(".rst")
    expected = render_catalogue(spec)
    if args.write:
        output.write_text(expected, encoding="utf-8")
    elif not output.is_file() or output.read_text(encoding="utf-8") != expected:
        parser.exit(1, "Readable NAM catalogue is stale; run this command with --write.\n")
    counts = Counter(m["role"] for m in spec["matrices"])
    print(f"NAM draft valid: {len(spec['sets'])} sets; "
          f"{counts['flow']} flows, {counts['coefficient']} coefficients, {counts['result']} results, {counts['view']} view; "
          f"{len(spec['representations'])} exclusive import representations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
