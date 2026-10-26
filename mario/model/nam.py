"""Structural NAM contract; item codes belong to the source, never to the schema.

The packaged JSON owns the implemented single-set structural contract;
coefficient and conversion proposals remain in the development documentation.
"""

from __future__ import annotations

import json
from importlib.resources import files

from mario.model.enums import BlockRole


_CONTRACT = json.loads(files("mario.model").joinpath("nam_schema.json").read_text())
NAM_SETS = _CONTRACT["sets"]
NAM_DOMAINS = _CONTRACT["domains"]
NAM_AXIS_ROLES = _CONTRACT["axis_roles"]
NAM_REPRESENTATIONS = _CONTRACT["representations"]
NAM_BLOCKS = {block["name"]: block for block in _CONTRACT["matrices"]}
NAM_ACCOUNT_NAMES = ("Region", "Set", "Item")
NAM_DERIVED = tuple(name for name, block in NAM_BLOCKS.items() if block["role"] != "flow")


def validate_nam_contract(contract):
    """Reject unions on elementary axes and duplicate ownership of T cells."""
    owners = {}
    for name, definition in contract["sets"].items():
        if not definition.get("short_name"):
            raise ValueError(f"{name}: missing NAM short name.")
    aliases = {}
    for key, definition in contract["sets"].items():
        for alias in (key, definition["label"], definition["short_name"]):
            alias = alias.strip().casefold()
            if alias in aliases and aliases[alias] != key:
                raise ValueError("NAM set IDs, labels and short names must resolve unambiguously.")
            aliases[alias] = key
    for block in contract["matrices"]:
        if block["name"] in {"T", "t", "X"}:
            if block["name"] == "X":
                if (block["rows"], block["columns"]) != ("all_accounts", "scalar"):
                    raise ValueError("X must contain one total for every accounting node.")
                continue
            if block["rows"] != "all_accounts" or block["columns"] != "all_accounts":
                raise ValueError("T must have identical complete accounting sets on both axes.")
            if contract["domains"]["all_accounts"]["sets"] != list(contract["sets"]):
                raise ValueError("T must preserve the complete accounting-set order.")
            continue
        for side in ("rows", "columns"):
            domain = contract["domains"][block[side]]
            if domain.get("derived_only") and block["role"] == "result":
                continue  # A result label, e.g. B9, is not a monetary account.
            if len(domain["sets"]) != 1:
                raise ValueError(f"{block['name']}.{side}: exactly one accounting set is required.")
        if block["role"] == "flow":
            pair = (block["rows"], block["columns"])
            if pair in owners:
                raise ValueError(f"Duplicate NAM accounting-cell ownership: {pair}.")
            owners[pair] = block["name"]
        if block["role"] == "coefficient":
            source = next(b for b in contract["matrices"] if b["name"] == block["source"])
            if block["name"] != source["name"].lower() or any(block[s] != source[s] for s in ("rows", "columns")):
                raise ValueError("NAM coefficients must preserve the source axes and use its lowercase name.")


validate_nam_contract(_CONTRACT)


def nam_set_id(value: str) -> str:
    """Resolve a set ID, short name or display label without interpreting items."""
    value = str(value).strip().casefold()
    for key, definition in NAM_SETS.items():
        if value in {key.casefold(), definition["label"].casefold(), definition["short_name"].casefold()}:
            return key
    raise ValueError(f"Unknown NAM set: {value!r}.")


def nam_block_role(name: str) -> BlockRole:
    """Return the registered role, including explicit lowercase coefficients."""
    return BlockRole(NAM_BLOCKS[name]["role"])


def nam_default_layout(name: str) -> dict[str, tuple[str, ...]]:
    """Return the reference-economy layout for a native flow block."""
    block = NAM_BLOCKS[name]
    return {side: ("reference_region", block[side]) for side in ("rows", "columns")}
