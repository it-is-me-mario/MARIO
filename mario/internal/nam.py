"""Native NAM account identity, coverage and block validation.

No FIGARO item code is required here. Import partners and products describe a
flow, while reference economy / set / item identifies its accounting node.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from numbers import Real
from types import MappingProxyType

import numpy as np
import pandas as pd
from scipy import sparse

from mario.log_exc.exceptions import DataMissing
from mario.model.nam import (
    NAM_ACCOUNT_NAMES, NAM_BLOCKS, NAM_DOMAINS, NAM_REPRESENTATIONS, NAM_SETS,
    nam_default_layout, nam_set_id,
)
from mario.parsers.matrix_layouts import nam_block_spec, normalize_nam_matrix_layouts


def _coo(frame):
    """Extract sparse values without expanding a sparse frame into dense memory."""
    if frame.empty:
        return sparse.coo_matrix(frame.shape, dtype=float)
    if all(isinstance(dtype, pd.SparseDtype) and dtype.fill_value == 0 for dtype in frame.dtypes):
        return frame.sparse.to_coo()
    return sparse.coo_matrix(frame.to_numpy(dtype=float))


def _account_projection(axis):
    return pd.MultiIndex.from_arrays(
        [axis.get_level_values(name) for name in NAM_ACCOUNT_NAMES], names=NAM_ACCOUNT_NAMES
    )


@dataclass(frozen=True)
class NAMSchema:
    """Internal national-account schema shared by all scenarios of a NAM state.

    Memberships are explicit ``{reference_region: {set_id: [item, ...]}}``.
    Item codes are arbitrary source labels. Rich descriptors have declared
    value lists but no automatic Cartesian expansion. Source codes/aliases may
    be kept in block provenance; neither changes account identity.
    """

    memberships: dict
    representation: str
    currency: str
    scale: float
    period: str | int
    matrix_layouts: dict = field(default_factory=dict)
    descriptors: dict = field(default_factory=dict)
    item_metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.representation not in NAM_REPRESENTATIONS:
            raise ValueError(f"Unknown NAM import representation: {self.representation!r}.")
        if (not isinstance(self.currency, str) or not self.currency.strip()
                or isinstance(self.scale, bool) or not isinstance(self.scale, Real)
                or not np.isfinite(self.scale) or self.scale <= 0
                or isinstance(self.period, bool) or not isinstance(self.period, (str, int))
                or self.period == ""):
            raise ValueError("NAM requires a currency, positive finite scale and reference period.")
        normalized = {}
        nodes = []
        for region, groups in self.memberships.items():
            if not isinstance(region, str) or not region:
                raise ValueError("NAM reference regions must be nonempty strings.")
            normalized[region] = {}
            for group, items in groups.items():
                key = nam_set_id(group)
                if key in normalized[region]:
                    raise ValueError(f"Duplicate NAM set {key} in {region}.")
                if isinstance(items, str):
                    raise ValueError("NAM membership requires a sequence of item codes, not a string.")
                values = tuple(items)
                if any(not isinstance(item, str) or not item for item in values) or len(set(values)) != len(values):
                    raise ValueError(f"Invalid or duplicate item codes in {region}/{key}.")
                normalized[region][key] = values
                nodes.extend((region, NAM_SETS[key]["label"], item) for item in values)
        if not nodes:
            raise ValueError("A NAM needs at least one declared accounting node.")
        layouts = normalize_nam_matrix_layouts(self.matrix_layouts)
        descriptors = {key: tuple(values) for key, values in self.descriptors.items()}
        for key, values in descriptors.items():
            if key not in {"origin_region", "destination_region", "partner_region", "imported_commodity"}:
                raise ValueError(f"Unknown NAM descriptor: {key}.")
            if len(set(values)) != len(values) or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"Invalid NAM descriptor members: {key}.")
        for layout in layouts.values():
            for roles in layout.values():
                missing = set(roles[:-1]) - {"reference_region"} - descriptors.keys()
                if missing:
                    raise ValueError(f"Undeclared NAM descriptor memberships: {sorted(missing)}.")
        object.__setattr__(self, "memberships", MappingProxyType({
            r: MappingProxyType(groups) for r, groups in normalized.items()
        }))
        object.__setattr__(self, "matrix_layouts", MappingProxyType({
            name: MappingProxyType(layout) for name, layout in layouts.items()
        }))
        object.__setattr__(self, "descriptors", MappingProxyType(descriptors))
        item_metadata = {}
        for region, groups in self.item_metadata.items():
            if region not in normalized:
                raise ValueError(f"Unknown reference economy in NAM item metadata: {region}.")
            item_metadata[region] = {}
            for group, items in groups.items():
                key = nam_set_id(group)
                if key in item_metadata[region]:
                    raise ValueError(f"Duplicate NAM metadata set: {region}/{key}.")
                item_metadata[region][key] = {}
                for item, attributes in items.items():
                    if item not in normalized[region].get(key, ()) or not isinstance(attributes, dict):
                        raise ValueError(f"Undeclared NAM metadata item: {region}/{key}/{item}.")
                    if any(not isinstance(k, str) or not isinstance(v, (str, int, float, bool, type(None)))
                           or isinstance(v, float) and not np.isfinite(v) for k, v in attributes.items()):
                        raise ValueError("NAM item metadata requires finite JSON scalar attributes.")
                    item_metadata[region][key][item] = MappingProxyType(dict(attributes))
                item_metadata[region][key] = MappingProxyType(item_metadata[region][key])
            item_metadata[region] = MappingProxyType(item_metadata[region])
        object.__setattr__(self, "item_metadata", MappingProxyType(item_metadata))

    def __deepcopy__(self, memo):
        # All containers and their string/tuple contents are immutable.
        return self

    def to_dict(self):
        """Serialize identity/layout metadata independently of block storage."""
        return {
            "memberships": {region: {key: list(items) for key, items in groups.items()}
                            for region, groups in self.memberships.items()},
            "representation": self.representation, "currency": self.currency,
            "scale": self.scale, "period": self.period,
            "matrix_layouts": {name: {side: list(roles) for side, roles in layout.items()}
                               for name, layout in self.matrix_layouts.items()},
            "descriptors": {key: list(items) for key, items in self.descriptors.items()},
            "item_metadata": {r: {s: {i: dict(a) for i, a in items.items()} for s, items in groups.items()}
                              for r, groups in self.item_metadata.items()},
        }

    def accounts(self, domain="all_accounts"):
        """Return observed nodes, preserving regional membership and set identity."""
        groups = NAM_DOMAINS[domain]["sets"]
        return pd.MultiIndex.from_tuples([
            (region, NAM_SETS[group]["label"], item)
            for region, members in self.memberships.items()
            for group in groups for item in members.get(group, ())
        ], names=NAM_ACCOUNT_NAMES)

    def layout(self, name):
        if NAM_BLOCKS[name]["role"] == "coefficient":
            return self.layout(NAM_BLOCKS[name]["source"])
        return dict(self.matrix_layouts.get(name, nam_default_layout(name)))

    def block_spec(self, name):
        block = NAM_BLOCKS[name]
        if name == "X" or "account_set" in block:
            from mario.compute import block_spec

            return block_spec(name, row_axes=[("reference_region", "region"),
                              ("Set", "accounting_sets"), ("Item", block["rows"])],
                              col_axes=[("production", "scalar")])
        return nam_block_spec(name, self.layout(name))

    def dependencies(self, name):
        """Resolve coverage-dependent inputs using the selected import authority."""
        block = NAM_BLOCKS[name]
        if name == "T":
            return self.required_flows()
        if "account_set" in block:
            return tuple(n for n in self.required_flows()
                         if NAM_BLOCKS[n]["columns"] == block["account_set"])
        return tuple(block.get("depends_on", ()))

    def required_flows(self):
        """List active flow domains; absent domains do not imply missing flows."""
        inactive = NAM_REPRESENTATIONS[self.representation]["alternative_import_blocks"]
        return tuple(name for name, block in NAM_BLOCKS.items()
                     if block["role"] == "flow" and name not in inactive
                     and any(any(groups.get(key) for key in NAM_DOMAINS[block["rows"]]["sets"])
                             and any(groups.get(key) for key in NAM_DOMAINS[block["columns"]]["sets"])
                             for groups in self.memberships.values()))

    def zero_block(self, name):
        """Build an explicitly declared zero only on a default accounting layout."""
        if self.layout(name) != nam_default_layout(name):
            raise ValueError(f"{name}: supply explicit axes for a rich-layout declared zero.")
        block = NAM_BLOCKS[name]
        rows, columns = self.accounts(block["rows"]), self.accounts(block["columns"])
        return pd.DataFrame.sparse.from_spmatrix(
            sparse.csr_matrix((len(rows), len(columns))), index=rows, columns=columns
        )

    def validate_axis(self, axis, *, domain, roles, label):
        expected = tuple("Region" if role == "reference_region" else role for role in roles[:-1]) + ("Set", "Item")
        if not isinstance(axis, pd.MultiIndex) or tuple(axis.names) != expected:
            raise ValueError(f"{label}: expected named MultiIndex {expected}.")
        if axis.has_duplicates or axis.to_frame(index=False).isna().any().any():
            raise ValueError(f"{label}: duplicate or missing axis labels.")
        projected = _account_projection(axis)
        accounts = self.accounts(domain)
        if set(projected) != set(accounts):
            raise ValueError(f"{label}: axis must cover the full declared {domain} domain, including zero members.")
        for role in roles[:-1]:
            if role != "reference_region" and not axis.get_level_values(role).isin(self.descriptors[role]).all():
                raise ValueError(f"{label}: undeclared {role} descriptor value.")

    def prepare_block(self, name, value, metadata):
        """Validate without mutating storage; return an independent value/record."""
        if name not in NAM_BLOCKS:
            raise ValueError(f"Unknown NAM block {name!r}; declare an extension before storing it.")
        metadata = deepcopy(metadata or {})
        presence = metadata.setdefault("presence", "observed")
        if presence not in {"observed", "declared_zero", "unavailable", "derived"}:
            raise ValueError(f"{name}: invalid presence state {presence!r}.")
        block = NAM_BLOCKS[name]
        if block["role"] != "flow":
            if presence != "derived":
                raise ValueError(f"{name}: a derived result/view cannot be stored as a native payment.")
            if not isinstance(value, pd.DataFrame):
                raise TypeError(f"{name}: derived NAM blocks must be pandas DataFrames.")
            if block["role"] == "coefficient":
                metadata.update(units="dimensionless", source=block["source"],
                                denominator=block["denominator"], normalization="column_account_total", period=self.period)
                metadata.pop("currency", None)
                metadata.pop("scale", None)
            else:
                metadata.update(currency=self.currency, scale=self.scale, period=self.period)
            return value.copy(deep=True), metadata
        inactive = NAM_REPRESENTATIONS[self.representation]["alternative_import_blocks"]
        if name in inactive and presence not in {"derived", "unavailable"}:
            raise ValueError(f"{name}: alternative import representation may only be a derived view.")
        if name not in inactive and presence == "derived":
            raise ValueError(f"{name}: authoritative flow needs observed or declared_zero provenance.")
        if presence == "unavailable":
            if value is not None:
                raise ValueError(f"{name}: unavailable blocks cannot contain values.")
            return None, metadata
        if value is None and presence == "declared_zero":
            value = self.zero_block(name)
        if not isinstance(value, pd.DataFrame):
            raise TypeError(f"{name}: native NAM blocks must be pandas DataFrames.")
        layout = self.layout(name)
        self.validate_axis(value.index, domain=block["rows"], roles=layout["rows"], label=f"{name}.rows")
        self.validate_axis(value.columns, domain=block["columns"], roles=layout["columns"], label=f"{name}.columns")
        if any(not pd.api.types.is_numeric_dtype(dtype) or pd.api.types.is_complex_dtype(dtype) for dtype in value.dtypes):
            raise ValueError(f"{name}: monetary values must be real numeric values.")
        coo = _coo(value)
        if not np.isfinite(coo.data).all():
            raise ValueError(f"{name}: nonfinite or missing monetary values.")
        if presence == "declared_zero" and np.any(coo.data != 0):
            raise ValueError(f"{name}: declared_zero block contains nonzero values.")
        row_regions = value.index.get_level_values("Region").to_numpy()
        col_regions = value.columns.get_level_values("Region").to_numpy()
        if np.any((coo.data != 0) & (row_regions[coo.row] != col_regions[coo.col])):
            raise ValueError(f"{name}: national ledgers cannot mix reference economies in one transaction.")
        for key in ("currency", "scale", "period"):
            expected = getattr(self, key)
            if key in metadata and metadata[key] != expected:
                raise ValueError(f"{name}: incompatible {key}; normalize units before storing flows.")
            metadata[key] = expected
        if not metadata.get("valuation"):
            raise ValueError(f"{name}: declare the block valuation (including mixed/unknown if applicable).")
        metadata["layout"] = layout
        return value.copy(deep=True), metadata


def presence(state, name, scenario):
    """Missing data and explicit unavailable overrides have the same coverage state."""
    try:
        return state._resolve_block_record(name, scenario).metadata["presence"]
    except KeyError:
        return "unavailable"


def coverage(state, scenario):
    required = state.nam_schema.required_flows()
    states = {name: presence(state, name, scenario) for name in required}
    return {"representation": state.nam_schema.representation, "blocks": states,
            "unavailable": tuple(name for name, status in states.items() if status == "unavailable"),
            "balance_certified": False}


def ensure_available(state, names, scenario):
    missing = [name for name in names if not state.has_matrix(name, scenario)]
    if missing:
        raise DataMissing(f"Unavailable NAM blocks in {scenario}: {', '.join(missing)}.")
