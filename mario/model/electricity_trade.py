"""Resolve electricity import-mix (trade) updates from ENTSO-E snapshots.

This is the trade-side companion of :mod:`mario.model.electricity_mix` (which
resolves the *generation* mix from EMBER). It turns a first-order **net
commercial** electricity import mix -- destination country -> {origin country:
share} -- into the ``shares_by_destination`` mapping consumed by
:meth:`Database.update_trade_mix`, so a caller can write::

    db.update_trade_mix("electricity", items="<electricity commodity>", year=2024)

and have each region's electricity sourcing rewritten to the observed mix.

Data model and caveats
----------------------
The mix is a **first-order** adjacent-country decomposition: what each market
net-sources from its direct neighbours. It is *not* flow-traced. The true
generation origin (French nuclear behind an Italian import that physically
routed through Switzerland) is recovered downstream by MARIO's own Leontief
inverse when footprints are computed -- feeding a pre-traced mix here would
double-count. See nxbase docs/knowledge/nxsut_bridge.md.

* **Basis**: ENTSO-E *scheduled commercial exchanges* (A09), netted per
  border, not physical cross-border flows (A11) -- physical flows are
  transit/loop-inflated and misrepresent the purchase. Validated against
  Electricity Maps (the "how" of that comparison cannot be redistributed:
  Electricity Maps data is proprietary).
* **Coverage**: the ENTSO-E (European) synchronous area only. Non-ENTSO-E
  EXIOBASE regions (US, CN, JP, ... and the RoW aggregates) are electrically
  near-isolated; with ``fill_uncovered_domestic=True`` (default) they are set
  domestic-only (100% self), the deliberate simplification of the design.
* **Reliability**: ENTSO-E is not always right. Non-EU zones with poor
  coverage (notably CH -- "Synthetic" on Electricity Maps) can fail their own
  energy balance; their mix is kept as-is and flagged rather than corrected.

The mix source is interchangeable, all yielding the same flat
``(destination, origin, share[, year])`` frame: the packaged CSV, an
``entsoe_path`` override (an nxbase snapshot or query export), or -- for users
without nxbase -- a live ENTSO-E fetch from their own API key (``entsoe_api_key``,
see :mod:`mario.model.entsoe_fetch`). Mirrors ``ember_path`` on the supply side,
plus the API-key fetch for standalone users.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
import logging

import pandas as pd

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.model._api_key import resolve_api_key
from mario.model.conventions import _MASTER_INDEX

_ENTSOE_IMPORT_MIX_FILE = "entsoe_electricity_import_mix.csv"
_REQUIRED_COLUMNS = {"destination", "origin", "share"}

logger = logging.getLogger(__name__)


def _load_import_mix_snapshot(entsoe_path: str | Path | None) -> pd.DataFrame:
    """Load one ENTSO-E electricity import-mix snapshot.

    Accepts the flat schema written by nxbase's entsoe_pull.py --
    ``destination, origin, share`` with an optional ``year`` column (the
    packaged multi-year default carries it; a single-year nxbase snapshot does
    not). Column names are matched case-insensitively so an nxbase query CSV
    drops in unchanged.
    """
    if entsoe_path is None:
        path = resources.files("mario.settings").joinpath(_ENTSOE_IMPORT_MIX_FILE)
        with resources.as_file(path) as resolved:
            frame = pd.read_csv(resolved)
    else:
        frame = pd.read_csv(Path(entsoe_path))

    return _normalize_snapshot(frame)


def _normalize_snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize a (destination, origin, share[, year]) frame from any source."""
    frame = frame.rename(columns={col: str(col).strip().lower() for col in frame.columns})
    missing = _REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise WrongInput(
            f"The ENTSO-E import-mix snapshot is missing required columns: "
            f"{sorted(missing)}. Expected a flat (destination, origin, share"
            "[, year]) table as written by nxbase entsoe_pull.py."
        )

    keep = ["destination", "origin", "share"] + (["year"] if "year" in frame.columns else [])
    snapshot = frame.loc[:, keep].copy()
    snapshot["destination"] = snapshot["destination"].astype(str).str.strip().str.upper()
    snapshot["origin"] = snapshot["origin"].astype(str).str.strip().str.upper()
    snapshot["share"] = pd.to_numeric(snapshot["share"], errors="coerce")
    snapshot = snapshot.dropna(subset=["share"])
    if "year" in snapshot.columns:
        snapshot["year"] = pd.to_numeric(snapshot["year"], errors="coerce").astype("Int64")
    return snapshot


def _select_year(snapshot: pd.DataFrame, year: int | None) -> pd.DataFrame:
    """Restrict a multi-year snapshot to one year (no-op when there is no year column)."""
    if "year" not in snapshot.columns:
        return snapshot
    available = sorted(int(y) for y in snapshot["year"].dropna().unique())
    if not available:
        return snapshot.drop(columns=["year"])
    if year is None:
        chosen = available[-1]
        log_time(logger, f"Electricity trade mix: using latest ENTSO-E year {chosen}.", "info")
    elif int(year) in available:
        chosen = int(year)
    else:
        chosen = min(available, key=lambda y: abs(y - int(year)))
        log_time(
            logger,
            f"Electricity trade mix: no ENTSO-E import mix for {year}; using nearest year {chosen}.",
            "info",
        )
    return snapshot.loc[snapshot["year"] == chosen].drop(columns=["year"])


def build_electricity_trade_shares(
    database,
    *,
    year: int | None = None,
    entsoe_path: str | Path | None = None,
    api_key=None,
    fill_uncovered_domestic: bool = False,
) -> dict[str, dict[str, float]]:
    """Build one ``destination -> {origin: share}`` mapping from an ENTSO-E mix.

    The mix frame comes from one of three sources, in priority order:

    1. ``entsoe_path`` -- a snapshot CSV (nxbase entsoe_pull.py output or an
       nxbase-query export);
    2. ``api_key={"entsoe": "<key>"}`` -- a live fetch from the ENTSO-E
       Transparency Platform for ``year`` (see :mod:`mario.model.entsoe_fetch`).
       This is the path for users without nxbase access -- they supply their own
       API key instead of a file. ``api_key={"nxbase": ...}`` is reserved for the
       hosted nxbase (not available yet);
    3. neither -- the snapshot packaged with MARIO.

    Regions are matched to the database ``Region`` index by their ISO2 /
    EXIOBASE code (identity mapping; the mix already speaks EXIOBASE codes, RoW
    aggregates included). For every covered destination the returned mix is a
    **full vector over the database regions** -- observed shares for the sourced
    origins and an explicit ``0.0`` for every other region -- so the subsequent
    :meth:`update_trade_mix` fully *replaces* the destination's electricity
    sourcing (origins absent from the mix are zeroed, not kept). Origins outside
    the database are dropped and the destination renormalized.

    ``fill_uncovered_domestic`` (default ``False``) leaves database regions the
    snapshot does not cover on their original table sourcing. Set it ``True`` to
    add a domestic-only vector (100% self) for them -- the "non-ENTSO-E regions
    are near-isolated" simplification (opt-in, since it overwrites the table's
    existing sourcing for regions the mix never observed).
    """
    provider, key = resolve_api_key(api_key, {"entsoe", "nxbase"})
    if provider is not None and entsoe_path is not None:
        raise WrongInput(
            "Pass either entsoe_path (snapshot) or api_key (live fetch), not both."
        )
    if provider == "entsoe":
        if year is None:
            raise WrongInput("A live ENTSO-E fetch needs an explicit year=.")
        from mario.model.entsoe_fetch import fetch_import_mix

        snapshot = _normalize_snapshot(fetch_import_mix(key, int(year)))
    elif provider == "nxbase":
        raise NotImplementable(
            "The 'nxbase' online data source is not available yet; pass entsoe_path=... "
            "with a snapshot CSV, or api_key={'entsoe': '<key>'} for a live fetch."
        )
    else:
        snapshot = _select_year(_load_import_mix_snapshot(entsoe_path), year)
    if snapshot.empty:
        raise WrongInput("The ENTSO-E import mix has no valid observations.")

    db_regions = [str(r) for r in database.get_index(_MASTER_INDEX["r"])]
    db_region_set = set(db_regions)

    shares_by_destination: dict[str, dict[str, float]] = {}
    dropped_destinations: set[str] = set()
    dropped_origins: set[str] = set()

    for destination, block in snapshot.groupby("destination", sort=False):
        if destination not in db_region_set:
            dropped_destinations.add(str(destination))
            continue
        observed = block.groupby("origin")["share"].sum()
        in_db = observed[observed.index.isin(db_region_set)]
        dropped_origins.update(str(o) for o in observed.index if o not in db_region_set)
        total = float(in_db.sum())
        if total <= 0:
            dropped_destinations.add(str(destination))
            continue
        # Full vector over db regions: observed (renormalized) + explicit zeros,
        # so update_trade_mix replaces rather than partially rescales.
        vector = {region: 0.0 for region in db_regions}
        for origin, share in in_db.items():
            vector[str(origin)] = float(share) / total
        shares_by_destination[str(destination)] = vector

    covered = set(shares_by_destination)
    uncovered = [r for r in db_regions if r not in covered]
    if fill_uncovered_domestic:
        # Full vector (self=1, every other origin=0) so update_trade_mix zeroes
        # the region's imports; a bare {region: 1.0} would be a no-op (a single
        # listed origin is just rescaled onto the share it already holds).
        for region in uncovered:
            vector = {r: 0.0 for r in db_regions}
            vector[region] = 1.0
            shares_by_destination[region] = vector

    if dropped_destinations:
        log_time(
            logger,
            "Electricity trade mix: snapshot destinations not in the database and "
            f"ignored: {sorted(dropped_destinations)}.",
            "info",
        )
    if dropped_origins:
        log_time(
            logger,
            "Electricity trade mix: snapshot origins not in the database, dropped and "
            f"renormalized: {sorted(dropped_origins)}.",
            "info",
        )
    if uncovered:
        how = "set domestic-only" if fill_uncovered_domestic else "left unchanged"
        log_time(
            logger,
            f"Electricity trade mix: database regions not covered by ENTSO-E and {how}: "
            f"{sorted(uncovered)}.",
            "info",
        )
    return shares_by_destination
