"""Propose non-overlapping aggregation inputs from classification footprints."""
from collections.abc import Mapping
from copy import deepcopy

import pandas as pd

from mario.database_profiles.concordances import AGGREGATION_LEVELS, CLASSIFICATIONS
from mario.log_exc.exceptions import WrongInput
from mario.model.concordances import (
    _classification, _manifest, _set, _shared, available_concordances, get_concordances,
)


def available_aggregations(database):
    """List editions with a packaged official hierarchy, by native set."""
    return {
        name: {label: list(AGGREGATION_LEVELS[_classification(label)])
               for label in editions if _classification(label) in AGGREGATION_LEVELS}
        for name, editions in available_concordances(database).items()
    }


def _level(classification, value):
    levels = AGGREGATION_LEVELS.get(classification, {})
    aliases = {"sections": "section", "2digits": "division", "2digit": "division",
               "3digits": "group", "3digit": "group", "4digits": "class", "4digit": "class",
               "5digits": "category", "5digit": "category", "6digits": "subcategory", "6digit": "subcategory"}
    token = str(value).casefold().replace(" ", "").replace("-", "").replace("_", "")
    token = aliases.get(token, token)
    if token not in levels:
        raise WrongInput(f"No packaged aggregation level {value!r} for {CLASSIFICATIONS[classification][0]}. "
                         f"Available levels: {', '.join(levels) or 'none'}.")
    return token, levels[token]


def get_aggregation(database, set_name=None, classification=None, level="section", *, unresolved="keep"):
    """Return reviewable inputs accepted by Database.aggregate; never split an item."""
    if unresolved not in ("keep", "raise"):
        raise WrongInput("unresolved must be 'keep' or 'raise'.")
    target = _classification(classification) if classification is not None else None
    actual_set, kind = _set(database, set_name, target)
    target = target or ("NACE2.1" if kind == "activity" else "CPA2.2")
    level, depth = _level(target, level)
    hierarchy = _shared()["hierarchies"][target]
    nodes = {node["code"]: node for node in hierarchy["nodes"]}
    concordances = get_concordances(database, actual_set, target)
    assignments, pending = {}, {}
    groups = {}
    for item, codes in concordances.items():
        ancestors = set()
        incomplete = False
        for code in codes:
            node = nodes.get(code)
            while node and node["level"] > depth:
                node = nodes.get(node["parent"])
            if node is None or node["level"] != depth:
                incomplete = True
            else:
                ancestors.add(node["code"])
        if codes and not incomplete and len(ancestors) == 1:
            code = next(iter(ancestors))
            label = f"{CLASSIFICATIONS[target][0]}:{code}"
            assignments[item] = label
            groups[label] = {"code": code, "name": nodes[code]["name"]}
        else:
            assignments[item] = item
            pending[item] = {"reason": "unverified" if not codes else "coarser_than_level" if incomplete else "multiple_groups",
                             "codes": codes, "groups": sorted(ancestors)}
    if pending and unresolved == "raise":
        raise WrongInput(f"Cannot assign {len(pending)} native items to one {level}: {list(pending)[:10]}. "
                         "Use unresolved='keep' to retain them individually and inspect the mapping report.")
    # Protect retained native identities from accidental collisions with the
    # generated classification labels; an unresolved item must remain separate.
    collisions = set(pending).intersection(groups)
    if collisions:
        raise WrongInput(f"Classification group labels collide with retained native items: {sorted(collisions)}.")
    domain = database.get_index(actual_set)
    if isinstance(domain, Mapping):
        pairs = [(region, item) for region, items in domain.items() for item in items]
        index = pd.MultiIndex.from_tuples(pairs, names=["Region", "Item"])
        targets = [assignments[item] for _, item in pairs]
    else:
        index = pd.Index(domain)
        targets = [assignments[item] for item in domain]
    frame = pd.DataFrame({"Aggregation": targets}, index=index)
    frame.attrs["concordance"] = {
        "classification": CLASSIFICATIONS[target][0], "level": level,
        "as_of": _manifest()["as_of"], "hierarchy_source": deepcopy(_shared()["sources"][hierarchy["source"]]),
        "groups": groups, "assigned_items": len(assignments)-len(pending), "unresolved": pending,
        "note": "Suggested grouping of qualified correspondence footprints, not certified native containment. "
                "Every item has one target; unresolved items stay separate. No allocation weights are inferred. "
                "Review source qualifications with get_concordances(details=True) before aggregation.",
    }
    return {actual_set: frame}
