"""Resolve electricity generation mix updates from EMBER snapshots."""

from __future__ import annotations

from collections.abc import MutableMapping
from functools import lru_cache
from importlib import resources
from pathlib import Path
import logging
import re

import pandas as pd
import yaml

from mario.clusters.coverage import resolve_region_labels_to_iso3_members
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _ENUM, _MASTER_INDEX


_EMBER_SNAPSHOT_FILE = "ember_electricity_generation.csv"
_ELECTRICITY_MIX_PROFILES_FILE = "electricity_mix_profiles.yaml"

logger = logging.getLogger(__name__)


def _normalize_label(value: str) -> str:
    """Return one comparable label token."""
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def _format_region_list(values: list[str], *, max_items: int = 8) -> str:
    """Format one region list for compact logs."""
    unique_values = sorted({str(value) for value in values})
    if not unique_values:
        return ""
    if len(unique_values) <= max_items:
        return ", ".join(unique_values)
    shown = ", ".join(unique_values[:max_items])
    return f"{shown}, ... (+{len(unique_values) - max_items} more)"


def _format_year_fallbacks(fallbacks: list[str], *, max_items: int = 8) -> str:
    """Format one compact region/year fallback summary."""
    unique_values = sorted({str(value) for value in fallbacks})
    if not unique_values:
        return ""

    if len(unique_values) <= max_items:
        return ", ".join(unique_values)
    shown = ", ".join(unique_values[:max_items])
    return f"{shown}, ... (+{len(unique_values) - max_items} more)"


@lru_cache(maxsize=1)
def _load_electricity_mix_profiles() -> dict[str, dict[str, object]]:
    """Load the packaged electricity-mix profile definitions."""
    path = resources.files("mario.settings").joinpath(_ELECTRICITY_MIX_PROFILES_FILE)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data.get("profiles", {})


def _load_ember_snapshot(ember_path: str | Path | None) -> pd.DataFrame:
    """Load the reduced EMBER electricity-generation snapshot."""
    if ember_path is None:
        path = resources.files("mario.settings").joinpath(_EMBER_SNAPSHOT_FILE)
    else:
        path = Path(ember_path)

    frame = pd.read_csv(path)
    required_columns = {"ISO3", "Year", "Variable", "Value"}
    missing = required_columns.difference(frame.columns)
    if missing:
        raise WrongInput(
            f"The EMBER snapshot '{path}' is missing required columns: {sorted(missing)}"
        )

    snapshot = frame.loc[:, ["ISO3", "Year", "Variable", "Value"]].copy()
    snapshot["ISO3"] = snapshot["ISO3"].astype(str).str.strip().str.upper()
    snapshot["Year"] = snapshot["Year"].astype(int)
    snapshot["Variable"] = snapshot["Variable"].astype(str).str.strip()
    snapshot["Value"] = pd.to_numeric(snapshot["Value"], errors="coerce")
    snapshot = snapshot.dropna(subset=["Value"])
    return snapshot


def _match_profile_sectors(
    sectors: list[str],
    profile: dict[str, object],
) -> dict[str, list[str]] | None:
    """Match one profile against the current database sector list."""
    groups = profile.get("groups", {})
    required_groups = set(profile.get("required_groups", []))
    matched_groups: dict[str, list[str]] = {}

    for group, aliases in groups.items():
        normalized_aliases = {_normalize_label(alias) for alias in aliases}
        matched = [sector for sector in sectors if _normalize_label(sector) in normalized_aliases]
        if group in required_groups and not matched:
            return None
        matched_groups[group] = matched

    return matched_groups


def _match_aggregated_ember_groups(
    sectors: list[str],
    profile: dict[str, object],
) -> dict[str, list[str]] | None:
    """Match one database already aggregated to EMBER-like electricity groups."""
    normalized_sectors = {_normalize_label(sector): sector for sector in sectors}
    ember_variables = profile.get("ember_variables", {})

    for prefix in ("production of electricity by ", "electricity by "):
        matched_groups: dict[str, list[str]] = {}
        for group, variable in ember_variables.items():
            label = normalized_sectors.get(_normalize_label(f"{prefix}{str(variable).strip().lower()}"))
            if label is None:
                break
            matched_groups[group] = [label]
        else:
            return matched_groups

    return None


def _resolve_electricity_profile(database) -> tuple[dict[str, object], dict[str, list[str]]]:
    """Resolve the supported electricity profile for one database."""
    sectors = list(database.get_index(_MASTER_INDEX["s"]))
    for profile in _load_electricity_mix_profiles().values():
        matched = _match_profile_sectors(sectors, profile)
        if matched is not None:
            return profile, matched

        matched = _match_aggregated_ember_groups(sectors, profile)
        if matched is not None:
            return profile, matched

    raise NotImplementable(
        "update_supply_mix_iot('electricity') currently supports only IOT databases exposing the expected "
        "electricity generation sectors, either in the original disaggregated form or already aggregated "
        "to the compatible EMBER groups."
    )


def resolve_electricity_mix_sectors(database) -> list[str]:
    """Return the generation sectors covered by ``update_supply_mix_iot('electricity')``."""
    _, matched_groups = _resolve_electricity_profile(database)
    sectors = []
    for members in matched_groups.values():
        for sector in members:
            if sector not in sectors:
                sectors.append(sector)
    return sectors


def _electricity_group_prefix(matched_groups: dict[str, list[str]]) -> str:
    """Infer one aggregated electricity label prefix from the matched sectors."""
    sectors = [sector for members in matched_groups.values() for sector in members]
    for sector in sectors:
        sector_text = str(sector)
        lowered = sector_text.casefold()
        if lowered.startswith("production of electricity by "):
            return sector_text[: len("production of electricity by ")]
        if lowered.startswith("electricity by "):
            return sector_text[: len("electricity by ")]
    return "production of electricity by "


def resolve_electricity_ember_group_labels(database) -> dict[str, str]:
    """Return one EMBER-group -> aggregated sector label mapping for the database."""
    profile, matched_groups = _resolve_electricity_profile(database)
    prefix = _electricity_group_prefix(matched_groups)
    return {
        group: f"{prefix}{str(variable).strip().lower()}"
        for group, variable in profile["ember_variables"].items()
    }


def build_electricity_ember_sector_aggregation(database) -> pd.DataFrame:
    """Build one Sector aggregation index that compacts electricity to EMBER groups."""
    _, matched_groups = _resolve_electricity_profile(database)
    labels = resolve_electricity_ember_group_labels(database)
    sectors = list(database.get_index(_MASTER_INDEX["s"]))
    aggregation = pd.DataFrame({"Aggregation": sectors}, index=sectors)

    for group, members in matched_groups.items():
        aggregation.loc[members, "Aggregation"] = labels[group]

    return aggregation


def _select_nearest_year(years: list[int], requested_year: int) -> int:
    """Pick the closest available year, preferring the previous year on ties."""
    return min(years, key=lambda candidate: (abs(candidate - requested_year), candidate > requested_year, candidate))


def _fallback_distribution(
    sectors: list[str],
    *,
    fallback_order: list[str],
) -> pd.Series:
    """Return one deterministic split when the baseline group has no internal weights."""
    distribution = pd.Series(0.0, index=sectors, dtype=float)
    normalized_actual = {_normalize_label(sector): sector for sector in sectors}

    for alias in fallback_order:
        sector = normalized_actual.get(_normalize_label(alias))
        if sector is not None:
            distribution.loc[sector] = 1.0
            return distribution

    distribution.iloc[0] = 1.0
    return distribution


def _group_internal_weights(
    row_totals: pd.Series,
    *,
    region: str,
    sectors: list[str],
    fallback_order: list[str],
) -> pd.Series:
    """Return one within-group sector split based on the current database composition."""
    selector = (region, _MASTER_INDEX["s"], sectors)
    totals = row_totals.loc[selector].groupby(level="Item").sum().astype(float)
    total = float(totals.sum())
    if total > 0:
        return totals / total
    return _fallback_distribution(sectors, fallback_order=fallback_order)


def _invert_region_aggregation_frame(frame: pd.DataFrame | pd.Series) -> dict[str, list[str]]:
    """Convert one Region aggregation sheet to ``aggregated -> members``."""
    if isinstance(frame, pd.Series):
        frame = frame.to_frame(name="Aggregation")
    else:
        frame = frame.copy()

    if frame.shape[1] > 1:
        frame = frame.iloc[:, 0].to_frame(name="Aggregation")
    else:
        frame.columns = ["Aggregation"]

    mapping: dict[str, list[str]] = {}
    for member, target in frame["Aggregation"].items():
        if pd.isna(target):
            continue
        mapping.setdefault(str(target), [])
        if str(member) not in mapping[str(target)]:
            mapping[str(target)].append(str(member))
    return mapping


def _normalize_region_aggregation(region_aggregation) -> dict[str, list[str]] | None:
    """Normalize explicit region aggregation inputs to ``aggregated -> members``."""
    if region_aggregation is None:
        return None

    if isinstance(region_aggregation, (str, Path)):
        frame = pd.read_excel(region_aggregation, sheet_name=_MASTER_INDEX["r"], index_col=0)
        return _invert_region_aggregation_frame(frame)

    if isinstance(region_aggregation, (pd.Series, pd.DataFrame)):
        return _invert_region_aggregation_frame(region_aggregation)

    if isinstance(region_aggregation, MutableMapping):
        if _MASTER_INDEX["r"] in region_aggregation and len(region_aggregation) == 1:
            return _normalize_region_aggregation(region_aggregation[_MASTER_INDEX["r"]])

        scalar_mapping = all(
            not isinstance(value, (list, tuple, set, pd.Index, pd.Series, pd.DataFrame))
            for value in region_aggregation.values()
        )
        if scalar_mapping:
            return _invert_region_aggregation_frame(pd.Series(region_aggregation, name="Aggregation"))

        mapping: dict[str, list[str]] = {}
        for target, members in region_aggregation.items():
            member_values = [members] if isinstance(members, str) else list(members)
            mapping[str(target)] = [str(member) for member in member_values]
        return mapping

    raise WrongInput(
        "region_aggregation must be one Region aggregation workbook, one pandas Series/DataFrame, or one mapping."
    )


def _region_member_mapping(database, region_aggregation) -> dict[str, list[str]]:
    """Resolve current database regions to original region labels."""
    explicit_mapping = _normalize_region_aggregation(region_aggregation)
    stored_mapping = getattr(database.meta, "region_aggregation_map", None)
    active_mapping = explicit_mapping if explicit_mapping is not None else stored_mapping

    resolved: dict[str, list[str]] = {}
    for region in database.get_index(_MASTER_INDEX["r"]):
        region_key = str(region)
        members = None
        if isinstance(active_mapping, dict):
            members = active_mapping.get(region_key)
        resolved[region_key] = list(members) if members else [region_key]
    return resolved


def _resolve_region_to_iso3_members(database, region_aggregation) -> dict[str, list[str]]:
    """Resolve each current database region to the ISO3 members used for EMBER."""
    source = getattr(database.meta, "source", None)
    explicit_mapping = _normalize_region_aggregation(region_aggregation)
    explicit_regions = set(explicit_mapping) if isinstance(explicit_mapping, dict) else set()
    region_members = _region_member_mapping(database, region_aggregation)
    region_to_iso3_members: dict[str, list[str]] = {}
    unresolved: dict[str, list[str]] = {}

    for region, member_labels in region_members.items():
        resolved_members = resolve_region_labels_to_iso3_members(member_labels, source=source)
        iso3_members: list[str] = []
        for members in resolved_members.values():
            for iso3 in members:
                if iso3 not in iso3_members:
                    iso3_members.append(iso3)

        if iso3_members:
            region_to_iso3_members[region] = iso3_members

        missing = [label for label in member_labels if str(label) not in resolved_members]
        if missing and region in explicit_regions:
            unresolved[region] = missing

    if explicit_mapping is not None and unresolved:
        details = "; ".join(
            f"{region}: {', '.join(labels)}" for region, labels in sorted(unresolved.items())
        )
        raise WrongInput(
            "Could not resolve some region_aggregation members to ISO3. "
            "Pass member labels already expressed as ISO3 or parse the database with source=... matching the original database nomenclature. "
            f"Unresolved members: {details}."
        )

    return region_to_iso3_members


def _select_snapshot_for_region_members(snapshot_by_iso3, iso3_members: list[str], requested_year: int):
    """Collect one aggregated EMBER slice for a region's ISO3 members."""
    selected_frames = []
    fallback_members: list[tuple[str, int]] = []

    for iso3 in iso3_members:
        member_snapshot = snapshot_by_iso3.get(iso3)
        if member_snapshot is None or member_snapshot.empty:
            continue

        available_years = sorted(int(value) for value in member_snapshot["Year"].unique())
        selected_year = _select_nearest_year(available_years, requested_year)
        if selected_year != requested_year:
            fallback_members.append((iso3, selected_year))

        selected_frames.append(member_snapshot.loc[member_snapshot["Year"] == selected_year, ["Variable", "Value"]])

    if not selected_frames:
        return None, fallback_members

    selected = pd.concat(selected_frames, axis=0).groupby("Variable", sort=False)["Value"].sum()
    return selected, fallback_members


def build_electricity_mix_shares(
    database,
    *,
    scenario: str,
    year: int | None,
    ember_path: str | Path | None = None,
    region_aggregation=None,
) -> dict[str, dict[str, float]]:
    """Build one ``region -> sector shares`` mapping from EMBER electricity generation data."""
    profile, matched_groups = _resolve_electricity_profile(database)
    snapshot = _load_ember_snapshot(ember_path)
    if snapshot.empty:
        raise WrongInput("The EMBER snapshot does not contain any valid electricity-generation observations.")

    if year is None:
        requested_year = int(snapshot["Year"].max())
        log_time(logger, f"Electricity mix: using latest EMBER year {requested_year}.", "info")
    else:
        requested_year = int(year)

    snapshot_by_iso3 = {
        iso3: frame for iso3, frame in snapshot.groupby("ISO3", sort=False)
    }
    region_to_iso3_members = _resolve_region_to_iso3_members(database, region_aggregation)
    ember_variables: dict[str, str] = profile["ember_variables"]
    fallback_order: dict[str, list[str]] = profile.get("fallback_order", {})
    all_profile_sectors = sorted({sector for members in matched_groups.values() for sector in members})
    z_row_totals = (
        database.get_block_as_pandas(_ENUM.z, scenario=scenario)
        .loc[(slice(None), _MASTER_INDEX["s"], all_profile_sectors), :]
        .sum(axis=1)
        .astype(float)
    )

    log_time(
        logger,
        "Electricity mix: aggregating database sectors to EMBER groups and redistributing with the current internal composition.",
        "info",
    )

    shares_by_region: dict[str, dict[str, float]] = {}
    missing_concordance_regions: list[str] = []
    missing_snapshot_regions: list[str] = []
    fallback_year_regions: list[str] = []
    no_positive_generation_regions: list[str] = []
    for region in database.get_index(_MASTER_INDEX["r"]):
        region_key = str(region)
        iso3_members = region_to_iso3_members.get(region_key)
        if not iso3_members:
            missing_concordance_regions.append(region)
            continue

        selected, fallback_members = _select_snapshot_for_region_members(
            snapshot_by_iso3,
            iso3_members,
            requested_year,
        )
        if selected is None:
            missing_snapshot_regions.append(f"{region} ({', '.join(iso3_members)})")
            continue

        if fallback_members:
            detail = "; ".join(f"{iso3} -> {selected_year}" for iso3, selected_year in fallback_members)
            fallback_year_regions.append(f"{region} ({detail})")

        group_totals = pd.Series(
            {
                group: float(selected.get(variable, 0.0))
                for group, variable in ember_variables.items()
            },
            dtype=float,
        )

        total_generation = float(group_totals.sum())
        if total_generation <= 0:
            no_positive_generation_regions.append(f"{region} ({', '.join(iso3_members)})")
            continue

        group_shares = group_totals / total_generation
        fine_shares = pd.Series(dtype=float)
        for group, members in matched_groups.items():
            if not members:
                raise NotImplementable(
                    f"The resolved electricity profile does not expose sectors for EMBER group {group!r}."
                )

            weights = _group_internal_weights(
                z_row_totals,
                region=region,
                sectors=members,
                fallback_order=fallback_order.get(group, members),
            )
            fine_shares = fine_shares.add(weights * float(group_shares.get(group, 0.0)), fill_value=0.0)

        fine_shares = fine_shares / float(fine_shares.sum())
        shares_by_region[region] = fine_shares.to_dict()

    if fallback_year_regions:
        log_time(
            logger,
            f"Electricity mix: no EMBER data for {requested_year} in some covered regions; using nearest year for {_format_year_fallbacks(fallback_year_regions)}.",
            "info",
        )

    if missing_concordance_regions:
        log_time(
            logger,
            f"Electricity mix: regions not covered by the EMBER concordance and left unchanged: {_format_region_list(missing_concordance_regions)}.",
            "info",
        )

    if missing_snapshot_regions:
        log_time(
            logger,
            f"Electricity mix: regions missing from the EMBER snapshot and left unchanged: {_format_region_list(missing_snapshot_regions)}.",
            "info",
        )

    if no_positive_generation_regions:
        log_time(
            logger,
            f"Electricity mix: regions with no positive EMBER generation and left unchanged: {_format_region_list(no_positive_generation_regions)}.",
            "info",
        )

    return shares_by_region