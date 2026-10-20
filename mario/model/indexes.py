"""Regional views of logical indexes, derived from materialized matrix axes."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from mario.model.conventions import _MASTER_INDEX


_AXIS_SOURCES = {
    "a": (
        ("S", "index"),
        ("U", "columns"),
        ("s", "index"),
        ("u", "columns"),
        ("Ya", "index"),
        ("Ea", "columns"),
        ("Va", "columns"),
        ("Xa", "index"),
        ("ea", "columns"),
        ("va", "columns"),
    ),
    "c": (
        ("U", "index"),
        ("S", "columns"),
        ("u", "index"),
        ("s", "columns"),
        ("Yc", "index"),
        ("Ec", "columns"),
        ("Vc", "columns"),
        ("Xc", "index"),
        ("ec", "columns"),
        ("vc", "columns"),
    ),
    "s": (
        ("Z", "index"),
        ("z", "index"),
        ("Y", "index"),
        ("E", "columns"),
        ("X", "index"),
    ),
    "n": (
        ("Yc", "columns"),
        ("Ya", "columns"),
        ("Y", "columns"),
        ("EY", "columns"),
        ("VY", "columns"),
    ),
    "f": (
        ("Va", "index"),
        ("Vc", "index"),
        ("V", "index"),
        ("va", "index"),
        ("vc", "index"),
        ("v", "index"),
        ("VY", "index"),
    ),
    "k": (
        ("Ea", "index"),
        ("Ec", "index"),
        ("E", "index"),
        ("ea", "index"),
        ("ec", "index"),
        ("e", "index"),
        ("EY", "index"),
    ),
}
_UNIFIED_SOURCES = (
    ("Z", "index"),
    ("z", "index"),
    ("Y", "index"),
    ("E", "columns"),
    ("X", "index"),
)


def regional_membership(code, blocks, regions):
    """Return ordered regional members without resolving or reading matrix values.

    ``None`` means that the materialized blocks do not expose a regional axis
    for this set. Global extension sets and global final-demand categories
    therefore keep their existing representation.
    """
    sources = _AXIS_SOURCES.get(code, ())
    if code in ("a", "c"):
        sources += _UNIFIED_SOURCES
    for name, side in sources:
        block = blocks.get(name)
        axis = getattr(block, side, None)
        if not isinstance(axis, pd.MultiIndex):
            continue
        label = _MASTER_INDEX[code]
        if axis.nlevels == 3 and (axis.get_level_values(1) == label).any():
            selected = axis[axis.get_level_values(1) == label]
            region_values, items = selected.get_level_values(
                0
            ), selected.get_level_values(2)
        elif _MASTER_INDEX["r"] in axis.names and label in axis.names:
            region_values, items = axis.get_level_values(
                _MASTER_INDEX["r"]
            ), axis.get_level_values(label)
        else:
            continue
        if code in ("f", "k") and not region_values.isin(regions).all():
            # Extension layouts may mix regional rows with global scopes
            # outside the Region set. Keep their complete legacy catalog:
            # filtering to real regions would silently discard global accounts.
            return None
        pairs = pd.DataFrame({"region": region_values, "item": items}).drop_duplicates()
        result = {region: [] for region in regions}
        for region, item in pairs.itertuples(index=False, name=None):
            if region in result:
                result[region].append(item)
        if not any(result.values()):
            continue
        return result
    return None


def main_index_view(values, *, code, regions, blocks, region=None, flat=False):
    """Expose a list for a common classification, otherwise regional lists.

    Legacy logical indexes remain unchanged in storage. Regional membership is
    obtained from the actual axes, so getters never create Cartesian products
    or materialize derived matrices. Return values are always independent lists.
    """
    if isinstance(values, Mapping):
        membership = {r: list(values.get(r, ())) for r in regions}
        union = list(
            dict.fromkeys(item for items in membership.values() for item in items)
        )
    else:
        union = list(values)
        membership = regional_membership(code, blocks, regions)
    if code == "r" and region is not None:
        return [region]
    if membership is None:
        return union
    if region is not None:
        return list(membership[region])
    if flat:
        observed = set(item for items in membership.values() for item in items)
        return list(
            dict.fromkeys(
                [item for item in union if item in observed]
                + [item for items in membership.values() for item in items]
            )
        )
    first = next(iter(membership.values()), [])
    if all(set(items) == set(first) for items in membership.values()):
        # Preserve the legacy label order even when regional axis orders differ.
        observed = set(first)
        return list(dict.fromkeys([item for item in union if item in observed] + first))
    return {r: list(items) for r, items in membership.items()}
