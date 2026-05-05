"""Runtime region concordance, clustering and aggregation helpers."""

from __future__ import annotations

import copy
import logging
from functools import lru_cache
from importlib import resources

import pandas as pd

from mario.log_exc.exceptions import WrongInput

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
SOURCE_CONCORDANCE_HINTS = {
    "adb": ("ADB",),
    "bea": ("BEA",),
    "ceads": ("CEADS",),
    "cepalstat": ("CEPALSTAT",),
    "emerging": ("EMERGING",),
    "eora": ("EORA1",),
    "eurostat": ("EUROSTAT",),
    "exiobase": ("EXIOBASE",),
    "figaro": ("FIGARO",),
    "gloria": ("GLORIA",),
    "istat": ("ISTAT",),
    "oecd": ("OECD",),
    "statcan": ("StatCan",),
    "useeio": ("USEEIO",),
    "wiod": ("WIOD",),
}
REGION_AGGREGATION_ALIASES = {
    "continent": "continent",
    "continents": "continent",
    "unregion": "UNregion",
    "unregions": "UNregion",
    "un_region": "UNregion",
    "un_regions": "UNregion",
    "eu": "EU",
    "oecd": "OECD",
    "g7": "G7",
    "g20": "G20",
}


def _dedupe(sequence):
    """Return a list without duplicates while preserving order."""
    return list(dict.fromkeys(sequence))


def coverage_workbook_resource():
    """Return the packaged country coverage workbook resource."""
    return resources.files("mario.clusters").joinpath("Country_coverage.xlsx")


@lru_cache(maxsize=1)
def load_concordance():
    """Load the packaged source-code to ISO3 concordance sheet."""
    with coverage_workbook_resource().open("rb") as handle:
        frame = pd.read_excel(handle, sheet_name="concordance", header=1)

    frame = frame.rename(columns={frame.columns[0]: "ISO3"})
    frame["ISO3"] = frame["ISO3"].astype(str).str.strip().str.upper()
    return frame


@lru_cache(maxsize=1)
def _country_converter():
    """Return a shared country converter instance when available."""
    if coco is None:
        return None
    return coco.CountryConverter()


def _preferred_concordance_columns(source):
    """Choose workbook columns that match one database source string."""
    source_value = str(source or "").casefold()
    preferred = []

    for token, columns in SOURCE_CONCORDANCE_HINTS.items():
        if token in source_value:
            preferred.extend(columns)

    for column in load_concordance().columns:
        if column == "ISO3":
            continue
        if str(column).casefold() in source_value:
            preferred.append(column)

    return [column for column in _dedupe(preferred) if column in load_concordance().columns]


@lru_cache(maxsize=None)
def _concordance_lookup(column):
    """Build an exact case-insensitive lookup from one source column to ISO3."""
    frame = load_concordance()
    if column not in frame.columns:
        return {}

    mapping = {}
    for iso3, source_code in frame[["ISO3", column]].dropna().itertuples(index=False):
        mapping.setdefault(str(source_code).casefold(), str(iso3).upper())

    return mapping


def _source_concordance_mapping(source):
    """Resolve source-specific non-standard region labels from the workbook."""
    mapping = {}
    for column in _preferred_concordance_columns(source):
        mapping.update(_concordance_lookup(column))
    return mapping


def _preferred_country_converter_columns(source):
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


def database_region_to_iso3(database):
    """Map database region labels to ISO3 codes using concordance and fallbacks."""
    labels = list(database.get_index("Region"))
    iso3_to_labels = {}
    source_lookup = _source_concordance_mapping(getattr(database.meta, "source", None))

    for label in labels:
        iso3 = source_lookup.get(str(label).casefold())
        if iso3 is None:
            continue
        iso3_to_labels.setdefault(iso3, [])
        if label not in iso3_to_labels[iso3]:
            iso3_to_labels[iso3].append(label)

    already_mapped = {label for values in iso3_to_labels.values() for label in values}
    pending = [label for label in labels if label not in already_mapped]

    for label in pending:
        iso3 = None
        for column in _preferred_country_converter_columns(getattr(database.meta, "source", None)):
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


def build_region_clusters(database):
    """Build default clusters for the Region set."""
    clusters = {"all": list(database.get_index("Region"))}
    iso3_to_labels = database_region_to_iso3(database)
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
    """Build default clusters for one database."""
    clusters = {
        set_name: {"all": list(database.get_index(set_name))}
        for set_name in database.sets
    }

    if "Region" in clusters:
        clusters["Region"].update(build_region_clusters(database))

    return copy.deepcopy(clusters)


def _normalize_region_aggregation_name(region_aggregation):
    """Normalize a preset region aggregation name."""
    normalized = str(region_aggregation).strip().casefold().replace(" ", "").replace("_", "")
    if normalized not in REGION_AGGREGATION_ALIASES:
        raise WrongInput(
            "region_aggregation should be one of 'continent', 'UNregion', 'EU', 'OECD', 'G7', 'G20', "
            "or an explicit mapping."
        )

    return REGION_AGGREGATION_ALIASES[normalized]


def _group_name_for_scheme(row, scheme):
    """Return one aggregation target label for one ISO3 metadata row."""
    if scheme == "continent":
        value = row.get("continent")
        if value is None or str(value) == "nan":
            return None
        return str(value)

    if scheme == "UNregion":
        value = row.get("UNregion")
        if value is None or str(value) == "nan":
            return None
        return str(value)

    value = row.get(scheme)
    if value is None or str(value) == "nan":
        return None
    if scheme == "OECD":
        return scheme
    if str(value) == scheme:
        return scheme
    return None


def _identity_region_aggregation(database):
    """Return the identity aggregation index for Region."""
    labels = list(database.get_index("Region"))
    return pd.DataFrame({"Aggregation": labels}, index=labels)


def _aggregation_from_scalar_mapping(database, mapping):
    """Build a Region aggregation index from a source-region to target mapping."""
    labels = list(database.get_index("Region"))
    unknown = set(mapping).difference(labels)
    if unknown:
        raise WrongInput(f"Following item are not acceptable for level Region \n {unknown}")

    values = {label: label for label in labels}
    for source, target in mapping.items():
        values[source] = str(target)

    return pd.DataFrame({"Aggregation": [values[label] for label in labels]}, index=labels)


def _aggregation_from_group_mapping(database, mapping):
    """Build a Region aggregation index from a target-group to members mapping."""
    labels = list(database.get_index("Region"))
    values = {label: label for label in labels}

    for target, members in mapping.items():
        members = [members] if isinstance(members, str) else list(members)
        unknown = set(members).difference(labels)
        if unknown:
            raise WrongInput(f"Following item are not acceptable for level Region \n {unknown}")
        for member in members:
            values[member] = str(target)

    return pd.DataFrame({"Aggregation": [values[label] for label in labels]}, index=labels)


def _aggregation_from_frame(database, frame):
    """Build a Region aggregation index from a Series/DataFrame payload."""
    labels = list(database.get_index("Region"))

    if isinstance(frame, pd.Series):
        frame = frame.to_frame(name="Aggregation")
    else:
        frame = frame.copy()

    if frame.shape[1] > 1:
        frame = frame.iloc[:, 0].to_frame()

    unknown = set(frame.index).difference(labels)
    if unknown:
        raise WrongInput(f"Following item are not acceptable for level Region \n {unknown}")

    values = {label: label for label in labels}
    column = frame.columns[0]
    for label, target in frame[column].items():
        values[label] = label if pd.isna(target) else str(target)

    return pd.DataFrame({"Aggregation": [values[label] for label in labels]}, index=labels)


def build_region_aggregation_index(database, region_aggregation):
    """Build a Region aggregation index from a preset or explicit mapping."""
    if region_aggregation is None:
        return None

    if isinstance(region_aggregation, str):
        scheme = _normalize_region_aggregation_name(region_aggregation)
        mapping = _identity_region_aggregation(database)
        iso3_to_labels = database_region_to_iso3(database)
        metadata = _iso3_metadata()

        if metadata is None or len(metadata) == 0:
            return mapping

        values = mapping["Aggregation"].to_dict()
        for iso3, labels in iso3_to_labels.items():
            if iso3 not in metadata.index:
                continue

            target = _group_name_for_scheme(metadata.loc[iso3], scheme)
            if target is None:
                continue
            for label in labels:
                values[label] = target

        return pd.DataFrame({"Aggregation": [values[label] for label in mapping.index]}, index=mapping.index)

    if isinstance(region_aggregation, (pd.Series, pd.DataFrame)):
        return _aggregation_from_frame(database, region_aggregation)

    if isinstance(region_aggregation, dict):
        if not region_aggregation:
            return _identity_region_aggregation(database)

        if all(
            not isinstance(value, (list, tuple, set, pd.Index, pd.Series, pd.DataFrame))
            for value in region_aggregation.values()
        ):
            return _aggregation_from_scalar_mapping(database, region_aggregation)

        return _aggregation_from_group_mapping(database, region_aggregation)

    raise WrongInput(
        "region_aggregation should be a preset string, a mapping, a pandas Series, or a pandas DataFrame."
    )