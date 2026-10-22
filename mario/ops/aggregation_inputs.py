"""Aggregation workbook groups and validated source-to-target mappings."""

from collections.abc import Mapping
import csv
from io import StringIO

import pandas as pd

from mario.log_exc.exceptions import DataMissing, WrongInput
from mario.model.conventions import _MASTER_INDEX as MI


def classification_groups(membership):
    """Group regions by their entire member set, independently of label order."""
    groups = {}
    for region, items in membership.items():
        groups.setdefault(frozenset(items), []).append(region)
    return list(groups.values())


def format_regions(regions):
    """Write a readable CSV list, quoting region names containing punctuation."""
    return ", ".join(
        (
            '"' + str(region).replace('"', '""') + '"'
            if any(char in str(region) for char in ',"\n\r')
            or str(region) != str(region).strip()
            else str(region)
        )
        for region in regions
    )


def _parse_regions(value, regions):
    if isinstance(value, str):
        try:
            rows = list(csv.reader(StringIO(value), skipinitialspace=True, strict=True))
        except csv.Error as error:
            raise WrongInput(f"Invalid Regions list: {value!r}.") from error
        members = rows[0] if len(rows) == 1 else []
    elif isinstance(value, (list, tuple)):
        members = list(value)
    else:
        members = []
    lookup = {str(region): region for region in regions}
    if not members or any(str(member) not in lookup for member in members):
        raise WrongInput(f"Unknown or empty Regions list: {value!r}.")
    members = [lookup[str(member)] for member in members]
    if len(set(members)) != len(members):
        raise WrongInput(f"Duplicate regions in Regions list: {value!r}.")
    return members


def regional_signatures(indexes, regions):
    """Compare strings in every regional set; infer no classification meaning."""
    domains = [value for value in indexes.values() if isinstance(value, Mapping)]
    return {
        region: tuple(frozenset(domain.get(region, ())) for domain in domains)
        for region in regions
    }


def compatible_region_groups(indexes, regions):
    signatures = regional_signatures(indexes, regions)
    groups = {}
    for region in regions:
        groups.setdefault(signatures[region], []).append(region)
    return [group for group in groups.values() if len(group) > 1]


def aggregation_template(level, indexes, region_index=None):
    """Return a sheet and whether it needs the legacy Excel index column."""
    members = indexes[level]
    regions = indexes[MI["r"]]
    if level == MI["r"] and any(isinstance(v, Mapping) for v in indexes.values()):
        targets = {} if region_index is None else region_index["Aggregation"].to_dict()
        rows = [
            (format_regions(group), region, targets.get(region))
            for group in compatible_region_groups(indexes, regions)
            for region in group
        ]
        return pd.DataFrame(rows, columns=["Regions", MI["r"], "Aggregation"]), False
    if isinstance(members, Mapping):
        rows = [
            (format_regions(group), item, None)
            for group in classification_groups(members)
            for item in members[group[0]]
        ]
        return pd.DataFrame(rows, columns=["Regions", "Item", "Aggregation"]), False
    if level == MI["r"] and region_index is not None:
        return region_index.copy(), True
    return pd.DataFrame(index=members, columns=["Aggregation"]), True


def _target(value, source, level, ignore_nan):
    if not pd.api.types.is_scalar(value):
        raise WrongInput(f"Invalid aggregation target {value!r} for {level}.")
    if pd.isna(value) or value == "":
        if not ignore_nan:
            raise DataMissing(
                f"nan values found for the aggregation of {level} for {source!r}. "
                "Pass ignore_nan=True to retain the original label."
            )
        return source
    try:
        hash(value)
    except TypeError as error:
        raise WrongInput(
            f"Invalid aggregation target {value!r} for {level}."
        ) from error
    return value


def normalize_aggregation_sheet(frame, level, indexes, *, ignore_nan=False):
    """Expand grouped rows to actual (region, item) pairs, retaining omitted nodes."""
    if not isinstance(frame, pd.DataFrame):
        raise WrongInput(f"Aggregation input for {level} must be a DataFrame.")
    frame = frame.copy(deep=True)
    if frame.index.name == "Regions":
        frame = frame.reset_index()
    members = indexes[level]
    regions = indexes[MI["r"]]
    regional = isinstance(members, Mapping)
    classifications = (
        {region: frozenset(items) for region, items in members.items()}
        if regional
        else {}
    )
    grouped = "Regions" in frame.columns
    paired = isinstance(frame.index, pd.MultiIndex)
    sources = []
    if grouped:
        item_column = MI["r"] if level == MI["r"] else "Item"
        required = {"Regions", item_column, "Aggregation"}
        if not required.issubset(frame.columns) or frame.columns.duplicated().any():
            raise WrongInput(f"{level} sheet requires columns {sorted(required)}.")
        signatures = regional_signatures(indexes, regions)
        for group_value, item, target in frame[
            ["Regions", item_column, "Aggregation"]
        ].itertuples(index=False, name=None):
            group = _parse_regions(group_value, regions)
            if level == MI["r"]:
                if item not in group or len({signatures[r] for r in group}) != 1:
                    raise WrongInput(
                        f"Invalid compatible region group {group_value!r}."
                    )
                sources.append((item, target))
            elif regional:
                if len({classifications[r] for r in group}) != 1:
                    raise WrongInput(
                        f"Regions {group!r} have different full classifications for {level}."
                    )
                sources.extend(((r, item), target) for r in group)
            else:
                raise WrongInput(
                    f"Regions groups are not needed for common set {level}."
                )
    elif paired:
        if not regional or frame.index.nlevels != 2 or frame.shape[1] != 1:
            raise WrongInput(f"Invalid regional aggregation index for {level}.")
        sources = list(frame.iloc[:, 0].items())
    else:
        if frame.shape[1] == 0:
            raise WrongInput(f"Missing Aggregation column for {level}.")
        # Historical workbooks may have arbitrary names and extra annotation columns.
        for item, target in frame.iloc[:, 0].items():
            item = "None" if pd.isna(item) or item == "" else item
            if regional:
                selected = [r for r in regions if item in members[r]]
                if not selected:
                    raise WrongInput(
                        f"Following item are not acceptable for level {level}: {item!r}"
                    )
                sources.extend(((r, item), target) for r in selected)
            else:
                sources.append((item, target))

    valid = (
        {(r, item) for r, items in members.items() for item in items}
        if regional
        else set(members)
    )
    mapping = {}
    for source, target in sources:
        if source not in valid:
            raise WrongInput(
                f"Following item are not acceptable for level {level}: {source!r}"
            )
        if source in mapping:
            raise WrongInput(f"Duplicate aggregation source for {level}: {source!r}.")
        original = source[1] if regional else source
        mapping[source] = _target(target, original, level, ignore_nan)

    if regional:
        pairs = [(r, item) for r, items in members.items() for item in items]
        axis = pd.MultiIndex.from_tuples(pairs, names=[MI["r"], "Item"])
        return pd.DataFrame(
            {"Aggregation": [mapping.get(pair, pair[1]) for pair in pairs]}, index=axis
        )
    if level == MI["r"]:
        # Ineligible regions are omitted from the template, but never from the database.
        mapping = {r: mapping.get(r, r) for r in regions}
        return pd.DataFrame(
            {"Aggregation": list(mapping.values())},
            index=pd.Index(list(mapping), name=None if grouped else frame.index.name),
            dtype=object if not grouped and frame.iloc[:, 0].dtype == object else None,
        )
    return pd.DataFrame(
        {"Aggregation": list(mapping.values())},
        index=pd.Index(list(mapping), name=frame.index.name),
        dtype=object if frame.iloc[:, 0].dtype == object else None,
    )


def validate_region_aggregation(indexes, mappings):
    """Prevent geographic mergers across different original or mapped string sets."""
    mapping = mappings.get(MI["r"])
    if mapping is None:
        return
    regions = indexes[MI["r"]]
    signatures = regional_signatures(indexes, regions)
    targets = mapping["Aggregation"].to_dict()
    groups = {}
    for region in regions:
        groups.setdefault(targets.get(region, region), []).append(region)
    for target, group in groups.items():
        if len(group) < 2:
            continue
        if len({signatures[r] for r in group}) > 1:
            raise WrongInput(
                f"Cannot aggregate regions {group!r} into {target!r}: "
                "their regional classifications contain different labels."
            )
        for level, domain in indexes.items():
            item_mapping = mappings.get(level)
            if not isinstance(domain, Mapping) or item_mapping is None:
                continue
            values = item_mapping["Aggregation"].to_dict()
            paired = isinstance(item_mapping.index, pd.MultiIndex)
            final = {
                frozenset(
                    values.get((r, item) if paired else item, item)
                    for item in domain[r]
                )
                for r in group
            }
            if len(final) > 1:
                raise WrongInput(
                    f"Cannot aggregate regions {group!r} into {target!r}: "
                    f"their mapped {level} labels differ."
                )
