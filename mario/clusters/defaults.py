"""Default cluster generation for MARIO databases."""

from __future__ import annotations

import copy
import logging
from functools import lru_cache
from importlib import resources

import yaml

logger = logging.getLogger(__name__)

try:
    import country_converter as coco
except ModuleNotFoundError:  # pragma: no cover - handled by graceful fallback
    coco = None


GROUP_COLUMNS = ("EU", "OECD", "G7", "G20")
GENERIC_SOURCE_CANDIDATES = (
    "ISO3",
    "ISO2",
    "name_short",
    "name_official",
)
SOURCE_CLASS_HINTS = {
    "exiobase": ("EXIO3", "EXIO2", "EXIO1"),
    "wiod": ("WIOD",),
    "eora": ("Eora",),
    "emerging": ("ISO3",),
    "gloria": ("ISO3",),
    "oecd": ("ISO3",),
    "figaro": ("ISO3",),
    "istat": ("ISO3",),
    "adb": ("ISO3",),
    "gtap": ("ISO3",),
    "statcan": ("ISO3",),
}


def _dedupe(sequence):
    """Return a list without duplicates while preserving order."""
    return list(dict.fromkeys(sequence))


@lru_cache(maxsize=1)
def _country_converter():
    """Return a shared country converter instance when available."""
    if coco is None:
        return None
    return coco.CountryConverter()


@lru_cache(maxsize=1)
def _region_mapping_config():
    """Load manual ISO3-to-region overrides from the packaged YAML file."""
    with resources.files("mario.clusters").joinpath("region_mapping.yaml").open(
        "r", encoding="utf8"
    ) as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        logger.warning("Ignoring invalid region mapping config because it is not a mapping.")
        return {"default": {}, "sources": {}}

    default = raw.get("default") or {}
    sources = raw.get("sources") or {}
    if not isinstance(default, dict):
        default = {}
    if not isinstance(sources, dict):
        sources = {}

    return {"default": default, "sources": sources}


def _matching_source_overrides(source):
    """Return manual region overrides relevant to one database source string."""
    config = _region_mapping_config()
    overrides = {}

    for iso3, labels in (config.get("default") or {}).items():
        overrides[str(iso3).upper()] = labels

    source_value = str(source or "").casefold()
    for token, mappings in (config.get("sources") or {}).items():
        if str(token).casefold() in source_value:
            for iso3, labels in (mappings or {}).items():
                overrides[str(iso3).upper()] = labels

    return overrides


def _preferred_source_columns(source):
    """Choose country-converter source columns using source-specific hints first."""
    source_value = str(source or "").casefold()
    preferred = []

    for token, columns in SOURCE_CLASS_HINTS.items():
        if token in source_value:
            preferred.extend(columns)

    preferred.extend(GENERIC_SOURCE_CANDIDATES)
    return _dedupe(preferred)


@lru_cache(maxsize=None)
def _classification_lookup(column):
    """Build an exact case-insensitive lookup from one classification to ISO3."""
    cc = _country_converter()
    if cc is None or column not in cc.data.columns:
        return {}

    mapping = {}
    for value, iso3 in cc.data[[column, "ISO3"]].dropna().itertuples(index=False):
        mapping.setdefault(str(value).casefold(), str(iso3).upper())

    return mapping


def _manual_iso3_mapping(database):
    """Resolve manually configured ISO3-to-region mappings for one database."""
    labels = set(database.get_index("Region"))
    resolved = {}

    for iso3, targets in _matching_source_overrides(getattr(database.meta, "source", None)).items():
        if isinstance(targets, str):
            targets = [targets]
        else:
            targets = list(targets)
        present = [label for label in targets if label in labels]
        if present:
            resolved[iso3] = present

    return resolved


def _region_iso3_mapping(database):
    """Map database region labels to ISO3 codes using manual and automatic hints."""
    labels = list(database.get_index("Region"))
    iso3_to_labels = {}

    for iso3, region_labels in _manual_iso3_mapping(database).items():
        iso3_to_labels.setdefault(iso3, [])
        for label in region_labels:
            if label not in iso3_to_labels[iso3]:
                iso3_to_labels[iso3].append(label)

    already_mapped = {label for region_labels in iso3_to_labels.values() for label in region_labels}
    pending = [label for label in labels if label not in already_mapped]

    for label in pending:
        iso3 = None
        for column in _preferred_source_columns(getattr(database.meta, "source", None)):
            iso3 = _classification_lookup(column).get(str(label).casefold())
            if iso3:
                break
        if iso3 is None:
            continue

        iso3_to_labels.setdefault(iso3, [])
        if label not in iso3_to_labels[iso3]:
            iso3_to_labels[iso3].append(label)

    return iso3_to_labels


@lru_cache(maxsize=1)
def _iso3_metadata():
    """Return country-converter metadata keyed by ISO3."""
    cc = _country_converter()
    if cc is None:
        return {}

    frame = cc.data.dropna(subset=["ISO3"]).drop_duplicates(subset=["ISO3"]).copy()
    frame["ISO3"] = frame["ISO3"].astype(str).str.upper()
    return frame.set_index("ISO3")


def _append_members(container, name, members):
    """Append members to one cluster name while preserving order."""
    if not members:
        return

    target = container.setdefault(name, [])
    for member in members:
        if member not in target:
            target.append(member)


def _build_region_clusters(database):
    """Build default clusters for the Region set."""
    clusters = {"all": list(database.get_index("Region"))}
    iso3_to_labels = _region_iso3_mapping(database)
    metadata = _iso3_metadata()

    if metadata is None or len(metadata) == 0:
        return clusters

    for iso3, labels in iso3_to_labels.items():
        if iso3 not in metadata.index:
            continue

        row = metadata.loc[iso3]

        continent = row.get("continent")
        if continent is not None and str(continent) != "nan":
            _append_members(clusters, f"continent:{continent}", labels)

        un_region = row.get("UNregion")
        if un_region is not None and str(un_region) != "nan":
            _append_members(clusters, f"UNregion:{un_region}", labels)

        for group in GROUP_COLUMNS:
            value = row.get(group)
            if value is None or str(value) == "nan":
                continue

            if group == "OECD":
                _append_members(clusters, group, labels)
            elif str(value) == group:
                _append_members(clusters, group, labels)

    return clusters


def build_default_clusters(database):
    """Build default clusters for one database.

    Default clusters always include ``all`` for every database set. When the
    database exposes a ``Region`` set and ``country_converter`` is available,
    MARIO also adds a curated subset of region groupings derived from ISO3
    mappings:

    - ``continent:*``
    - ``UNregion:*``
    - ``EU``
    - ``OECD``
    - ``G7``
    - ``G20``
    """

    clusters = {
        set_name: {"all": list(database.get_index(set_name))}
        for set_name in database.sets
    }

    if "Region" in clusters:
        clusters["Region"].update(_build_region_clusters(database))

    return copy.deepcopy(clusters)
