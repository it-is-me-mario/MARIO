"""Offline native-classification lookups shared with the Database explorer.

Only explicit native identities and typed correspondence routes are used.
Parent labels, string similarity and allocation weights play no role.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from functools import lru_cache
import gzip
from importlib.resources import files
import json
import re

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.database_profiles.concordances import CLASSIFICATIONS, load_manifest as _manifest
from mario.database_profiles.registry import identify_database


def _token(value):
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _name(value):
    return " ".join(str(value).split()).casefold()


def _classification(value):
    for key, (label, _, aliases) in CLASSIFICATIONS.items():
        if _token(value) in {_token(key), _token(label), *aliases}:
            return key
    raise WrongInput(
        f"Unknown classification {value!r}. Specify its edition. Known classifications: "
        + ", ".join(v[0] for v in CLASSIFICATIONS.values())
    )


@lru_cache(maxsize=3)
def _bundle(family):
    resource = files("mario.database_profiles").joinpath(f"data/concordances/{family.lower()}.json.gz")
    with resource.open("rb") as stream, gzip.GzipFile(fileobj=stream) as archive:
        bundle = json.load(archive)
    bundle.update(_shared())
    return bundle


@lru_cache(maxsize=1)
def _shared():
    resource = files("mario.database_profiles").joinpath("data/concordances/shared.json.gz")
    with resource.open("rb") as stream, gzip.GzipFile(fileobj=stream) as archive:
        bundle = json.load(archive)
    index, namespaces = defaultdict(list), defaultdict(set)
    for edge in bundle["bridges"]:
        index[tuple(edge["left"])].append(edge)
        namespaces[edge["left"][0]].add(edge["right"][0])
    bundle["_bridge_index"] = index
    bundle["_namespace_neighbours"] = namespaces
    bundle["_namespace_paths"] = {}
    return bundle


def _family(database):
    profile = identify_database(database)
    if not profile["concordance_family"]:
        raise WrongInput(f"No bundled concordance profile for {profile['label']}.")
    return profile["concordance_family"]


def _set(database, value, classification):
    requested = _token(value) if value is not None else ""
    if database.table_type == "SUT":
        if not requested:
            return MI["a"], "activity"
        resolved = database._resolve_set_name(value, raise_on_missing=False)
        if resolved in (MI["a"], MI["c"]):
            return resolved, "activity" if resolved == MI["a"] else "commodity"
        raise WrongInput("For SUT concordances select set='Activity' or set='Commodity'.")
    if requested not in {"", "s", "sector", "sectors", "a", "activity", "activities", "c", "commodity", "commodities", _token(MI['s'])}:
        raise WrongInput("Concordances apply to Sector, Activity or Commodity, not to accounts or regions.")
    source = str(getattr(database.meta, "source", "")).casefold()
    native_kind = getattr(database.meta, "sector_type", None)
    if native_kind is None:
        # Older saved models already record the successful transformation.
        for note in reversed(getattr(database.meta, "_history", [])):
            match = re.search(r"Transformation of the database from SUT to IOT via method ([ABCD])\b", note)
            if match:
                native_kind = MI["c"] if match.group(1) in ("A", "B") else MI["a"]
                break
    if native_kind in (MI["a"], MI["c"]):
        kind = "activity" if native_kind == MI["a"] else "commodity"
    elif (re.search(r"\bpxp\b", source) or "bonsai" in source or "emerging" in source
          or ("exiobase" in source and "hybrid" in source)):
        kind = "commodity"
    elif re.search(r"\bixi\b", source):
        kind = "activity"
    else:
        kind = "activity"
    explicit = "activity" if requested in {"a", "activity", "activities"} else "commodity" if requested in {"c", "commodity", "commodities"} else None
    # BONSAI supplies an explicit reference-product/process association. Its
    # activity projection keeps the actual HIOT Sector labels as dictionary keys.
    if "bonsai" in source:
        kind = explicit or (CLASSIFICATIONS[classification][1] if classification else kind)
    elif explicit and explicit != kind:
        raise WrongInput(f"This IOT's Sector set represents {kind} identities, not {explicit} identities.")
    return MI["s"], kind


def _aliases(native):
    identity = native.get("native_identity", {})
    result = [native.get("code"), native.get("name"), native.get("nxbase_short"), identity.get("short")]
    result += [row.get("name") for row in native.get("historical_descriptors", [])]
    return {_name(value) for value in result if value}


def _profile(database, family, kind, items):
    source = str(getattr(database.meta, "source", "")).casefold()
    profiles = [p for p in _bundle(family)["profiles"] if p["kind"] == kind]
    hybrid = "hybrid" in source or family == "BONSAI"
    profiles = [p for p in profiles if (p["units"] == "Hybrid") == hybrid]
    if family == "BONSAI" and kind == "activity":
        profiles = [p for p in profiles if bool(p.get("reference_process")) == (database.table_type == "IOT")]
    if family == "GTAP":
        profiles = [p for p in profiles if ("POWER" in p["namespace"]) == ("power" in source or "power" in str(getattr(database.meta, "name", "")).casefold())]
    if family == "EXIOBASE" and hybrid and kind == "commodity":
        namespace = "EXIO3HSUTP" if database.table_type == "SUT" else "EXIO3HIOTP"
        profiles = [p for p in profiles if p["namespace"] == namespace]
    if family == "GLORIA":
        release = re.search(r"release\s+v?(\d+)", source)
        if release and release.group(1).zfill(3) != "060":
            raise WrongInput("Bundled GLORIA concordances cover release 060; this source declares another release.")
    if not profiles:
        raise WrongInput(f"No bundled {kind} concordances for {family} and this native table variant.")
    if family == "EMERGING":
        version = getattr(database.meta, "version", None)
        match = re.search(r"(?:version|release|\bv)\s*(\d+\.\d+|e)\b", source)
        version = str(version) if version is not None else match.group(1) if match else None
        if version is not None:
            # Standard V2 filenames identify a family, not a minor release.
            # Keep that constraint, then select by native identities below.
            profiles = [p for p in profiles if any(
                version.casefold() == v.casefold()
                or (version.casefold() == "2.x" and re.fullmatch(r"2\.\d+", v))
                for v in p["releases"]
            )]
            if not profiles:
                raise WrongInput(f"No bundled EMERGING concordance profile for release {version!r}.")
    # Compare identities, never sector counts alone. Ambiguous vocabularies
    # require a source variant instead of selecting an arbitrary profile.
    scores = []
    for profile in profiles:
        known = {alias for n in profile["native"] for alias in _aliases(n)}
        scores.append(sum(_name(item) in known for item in items))
    maximum = max(scores)
    candidates = [p for p, score in zip(profiles, scores) if score == maximum]
    labels = {_name(item) for item in items}
    exact = [p for p in candidates if len(p["native"]) == len(labels)
             and all(_aliases(n) & labels for n in p["native"])]
    if len(exact) == 1:
        candidates = exact
    if len(candidates) != 1:
        raise WrongInput(f"Ambiguous {family} classification profile; the native identities do not identify a unique mapped variant.")
    return candidates[0]


def _namespace_path(bundle, start, target):
    key = (start, target)
    cache = bundle["_namespace_paths"]
    if key in cache:
        return cache[key]
    if start == target:
        return [start]
    queue = deque([[start]])
    while queue:
        path = queue.popleft()
        neighbours = sorted(bundle["_namespace_neighbours"][path[-1]])
        for namespace in neighbours:
            if namespace in path:
                continue
            extended = [*path, namespace]
            if namespace == target:
                cache[key] = extended
                return extended
            queue.append(extended)
    cache[key] = None
    return None


def _available(profile, bundle):
    direct = profile["direct_classifications"]
    base = profile["reference"]
    return [key for key in CLASSIFICATIONS if key in direct or _namespace_path(bundle, base, key)]


def _native_paths(native, bundle, classification):
    for own in native.get("links", {}).values():
        link = {**native.get("link_defaults", {}), **own}
        for path in [link, *link.get("alternatives", []), *({"steps": s} for s in link.get("alternative_steps", []))]:
            steps = [bundle["route_steps"][sid] for sid in path["steps"]]
            nodes = [steps[0]["source_left"], *[s["source_right"] for s in steps]]
            yield {"nodes": nodes, "steps": steps, "status": link.get("status", "documented"),
                   "mapping_origin": link.get("mapping_origin", "published"), "note": link.get("review_note", "")}
    for path in native.get("additional_routes", {}).get(classification, []):
        yield path


def _project(native, profile, bundle, target, details):
    results = defaultdict(list)
    seen = set()
    bridges = bundle["_bridge_index"]
    for path in _native_paths(native, bundle, target):
        positions = [i for i, node in enumerate(path["nodes"]) if node[0] == target]
        if positions:
            last = positions[-1]
            candidates = [{**path, "nodes": path["nodes"][:last+1], "steps": path["steps"][:last]}]
        else:
            route = _namespace_path(bundle, path["nodes"][-1][0], target)
            candidates = [path] if route else []
            for namespace in (route or [])[1:]:
                candidates = [
                    {**candidate, "nodes": [*candidate["nodes"], edge["right"]],
                     "steps": [*candidate["steps"], edge], "status": "partial",
                     "mapping_origin": "derived_classification_bridge",
                     "note": "Composed official classification correspondence; reverse and many-to-many routes do not establish exact native scope or allocation weights."}
                    for candidate in candidates for edge in bridges[tuple(candidate["nodes"][-1])]
                    if edge["right"][0] == namespace
                ]
        for candidate in candidates:
            code = candidate["nodes"][-1][1]
            signature = (code, json.dumps(candidate["steps"], sort_keys=True)) if details else code
            if signature in seen:
                continue
            seen.add(signature)
            results[code].append(candidate if details else None)
    # Broad supplied anchors are valid at their own level only. They must
    # never become an enumeration of all their possible descendant classes.
    for anchor in native.get("coarse", {}).get("anchors", []):
        steps = [bundle["route_steps"][sid] for sid in anchor["steps"]]
        node = steps[-1]["source_right"]
        if node[0] == target:
            results[node[1]].append({"nodes": [steps[0]["source_left"], *[s["source_right"] for s in steps]],
                                     "steps": steps, "status": "coarse", "mapping_origin": "published_broad_anchor",
                                     "note": native["coarse"].get("note", "")})
    return dict(sorted(results.items()))


def get_concordances(database, set_name=None, classification=None, item=None, *, region=None, details=False):
    """Implement the public method without changing model state or resolving IO matrices."""
    if not isinstance(details, bool):
        raise WrongInput("details must be True or False.")
    target = _classification(classification) if classification is not None else None
    actual_set, kind = _set(database, set_name, target)
    members = database.get_index(actual_set, region=region, flat=region is None)
    family = _family(database)
    profile = _profile(database, family, kind, members)
    bundle = _bundle(family)
    target = target or ("NACE2.1" if kind == "activity" else "CPA2.2")
    available = _available(profile, bundle)
    if target not in available:
        raise WrongInput(f"{CLASSIFICATIONS[target][0]} is unavailable for this {family} set. Available: "
                         + ", ".join(CLASSIFICATIONS[k][0] for k in available))
    if item is None:
        selected = members
    elif isinstance(item, str):
        selected = [item]
    else:
        try:
            selected = list(item)
        except TypeError as exc:
            raise WrongInput("item must be a native label or an iterable of native labels.") from exc
    if any(not isinstance(value, str) for value in selected):
        raise WrongInput("item labels must be strings.")
    unknown = [value for value in selected if value not in members]
    if unknown:
        raise WrongInput(f"Unknown items in {actual_set}" + (f" for region {region!r}" if region is not None else "") + f": {unknown[:10]}")
    lookup = defaultdict(list)
    for native in profile["native"]:
        for alias in _aliases(native):
            lookup[alias].append(native)
    output = {}
    for label in dict.fromkeys(selected):
        natives = lookup[_name(label)]
        native = natives[0] if len(natives) == 1 else None
        matches = _project(native, profile, bundle, target, details) if native else {}
        if not details:
            output[label] = list(matches)
            continue
        sources = {step["source"] for paths in matches.values() for path in paths for step in path["steps"]}
        output[label] = {
            "codes": list(matches), "classification": CLASSIFICATIONS[target][0],
            "native_code": native["code"] if native else None,
            "native_name": native["name"] if native else None,
            "status": "mapped" if matches else "unverified" if native else "ambiguous_identity" if natives else "unknown_native_identity",
            "matches": {code: {"name": bundle["node_names"].get(target+":"+code, code), "routes": paths} for code, paths in matches.items()},
            "sources": {sid: bundle["sources"][sid] for sid in sorted(sources)},
            "as_of": _manifest()["as_of"], "profile": profile["id"],
            "note": "Correspondence codes are not allocation weights. An empty result is unverified, not proof of absence.",
        }
    return deepcopy(output) if details else output


def available_concordances(database):
    """List target editions for each native productive set."""
    family = _family(database)
    sets = [MI["a"], MI["c"]] if database.table_type == "SUT" else [MI["s"]]
    result, errors = {}, []
    for set_name in sets:
        actual, kind = _set(database, set_name, None)
        members = database.get_index(actual, flat=True)
        try:
            profile = _profile(database, family, kind, members)
        except WrongInput as exc:
            errors.append(exc)
            continue
        result[actual] = [CLASSIFICATIONS[k][0] for k in _available(profile, _bundle(family))]
    if not result and errors:
        raise errors[0]
    if database.table_type == "IOT" and family == "BONSAI":
        profile = _profile(database, family, "activity", database.get_index(MI["s"], flat=True))
        result[MI["s"]] = list(dict.fromkeys([*result[MI["s"]], *(CLASSIFICATIONS[k][0] for k in _available(profile, _bundle(family)))]))
    return result
