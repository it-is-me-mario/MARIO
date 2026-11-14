"""Persist accounting configuration together with native import blocks."""

import json

from mario.model.configuration import configuration_values, import_blocks
from mario.ops.import_accounts import factor_row_values
from mario.parsers.accounting import MANIFEST


def _axis_sets(axis):
    names = list(axis.names)
    if names == ["Import account"]:
        return []
    if "Level" in names:
        return [names[0], axis.get_level_values("Level")[0]]
    return names


def accounting_manifest(database, scenario, mode):
    """Describe native layouts independently of optional descriptive metadata."""
    values = configuration_values(database)
    if not values:
        return {}
    values["trade_representations"] = {
        "baseline": values.get("trade_representations", {}).get(scenario, "unspecified")
    }
    factor = "Va" if database.table_type == "SUT" else "V"
    reference = next(
        (database.get_block(name, scenario=scenario) for name in (factor, factor.lower())
         if database.has_matrix(name, scenario=scenario)), None,
    )
    if reference is None:
        reference = database.resolve(factor, scenario=scenario)
    prefix, _ = factor_row_values(reference.index)
    declarations = {}
    for name in import_blocks(database, mode):
        frame = database.resolve(name, scenario=scenario)
        declarations[name] = {
            "index": list(frame.index.names), "columns": list(frame.columns.names),
            "index_sets": _axis_sets(frame.index), "columns_sets": _axis_sets(frame.columns),
        }
    return {
        "configuration": values,
        "tech_assumption": getattr(database.meta, "tech_assumption", None),
        "sector_type": getattr(database.meta, "sector_type", None),
        "matrix_layouts": {"V": list(prefix), "VY": list(prefix)} if prefix else {},
        "legacy_public_axes": "Level" in reference.columns.names,
        "imports": declarations,
    }


def write_accounting_manifest(database, root, scenario, mode):
    """Write structural choices into the same directory as their matrices."""
    manifest = accounting_manifest(database, scenario, mode)
    target = root / MANIFEST
    if manifest:
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    elif target.exists():
        target.unlink()
