"""Fetch a first-order net electricity import mix live from ENTSO-E.

Companion of :mod:`mario.model.electricity_trade`: when a caller has no nxbase
snapshot but *does* have an ENTSO-E Transparency Platform API key, this builds
the same ``(destination, origin, share)`` frame directly from the platform.

Why not just use ``entsoe-py``'s pandas client: MARIO pins ``pandas==3.0.2``
and ``entsoe-py``'s ``EntsoePandasClient`` breaks at runtime on pandas 3
(deprecated ``"60T"`` frequency aliases in its response resampling). We
therefore use only ``entsoe-py``'s **raw** client (``EntsoeRawClient``, which
returns the platform XML untouched and is pandas-version agnostic) for the
HTTP/zone/EIC machinery, and parse the XML to annual energy ourselves with the
standard library -- so nothing touches the fragile pandas path. ``entsoe-py``
is therefore an *optional* dependency, imported lazily.

Basis and caveats are identical to nxbase's entsoe_pull.py (the governed
snapshot producer): scheduled commercial exchanges (A09) netted per border,
ENTSO-E area only, non-ENTSO-E regions left to the caller. See
:mod:`mario.model.electricity_trade`.
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

# EXIOBASE European country -> ENTSO-E bidding-zone code(s) (mirrors nxbase
# entsoe_pull.py; kept here so MARIO's live fetch is self-contained).
COUNTRY_ZONES: dict[str, list[str]] = {
    "AT": ["AT"], "BE": ["BE"], "BG": ["BG"], "CH": ["CH"], "CZ": ["CZ"],
    "DE": ["DE_LU"], "ES": ["ES"], "FI": ["FI"], "FR": ["FR"], "GR": ["GR"],
    "HR": ["HR"], "HU": ["HU"], "IE": ["IE_SEM"], "IT": ["IT"], "NL": ["NL"],
    "PL": ["PL"], "PT": ["PT"], "RO": ["RO"], "SI": ["SI"], "SK": ["SK"],
    "EE": ["EE"], "LV": ["LV"], "LT": ["LT"], "MT": ["MT"],
    "DK": ["DK_1", "DK_2"],
    "SE": ["SE_1", "SE_2", "SE_3", "SE_4"],
    "NO": ["NO_1", "NO_2", "NO_3", "NO_4", "NO_5"],
}
DOMESTIC_ONLY = ["CY", "LU"]

EXIOBASE_COUNTRIES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
    "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
    "SE", "SI", "SK", "GB", "US", "JP", "CN", "CA", "KR", "BR", "IN", "MX",
    "RU", "AU", "CH", "TR", "TW", "NO", "ID", "ZA",
}
_ZONE_SPECIAL = {"DE_LU": "DE", "IE_SEM": "IE", "GB_NIR": "GB"}

# ISO-8601 period resolutions -> hours, so a quantity (average MW over the
# interval) integrates to MWh.
_RES_HOURS = {
    "PT15M": 0.25, "PT30M": 0.5, "PT45M": 0.75, "PT60M": 1.0, "PT1H": 1.0,
    "P1D": 24.0, "P7D": 168.0, "P1M": 730.0, "P1Y": 8760.0,
}


def zone_to_country(zone: str) -> str:
    """Map an ENTSO-E zone/area token to an EXIOBASE-country site short."""
    if zone in _ZONE_SPECIAL:
        return _ZONE_SPECIAL[zone]
    iso2 = zone[:2]
    if iso2 in EXIOBASE_COUNTRIES or iso2 in COUNTRY_ZONES:
        return iso2
    return "WE"  # RoW Europe (EXIOBASE aggregate)


def _period_energy(period: ET.Element) -> float:
    """Integrate one <Period> to energy (MWh), honoring ENTSO-E curveType A03.

    A03 uses **variable-length blocks**: points are sparse and a point's value
    holds from its ``position`` until the next point's position, the last one
    running to the end of the period. Each point therefore covers
    ``(next_position - position)`` resolution intervals. A naive one-hour-per-
    point sum under-counts wherever positions are sparse (e.g. FR->IT scheduled
    exchange: 517 points spanning 744 hourly slots) -- which is exactly the gap
    structure that also crashes entsoe-py's pandas parser.
    """
    res_hours = _RES_HOURS.get(period.findtext("{*}resolution") or "", 1.0)
    points = sorted(
        (int(pt.findtext("{*}position")), float(pt.findtext("{*}quantity")))
        for pt in period.iterfind("{*}Point")
        if pt.findtext("{*}quantity") is not None and pt.findtext("{*}position") is not None
    )
    if not points:
        return 0.0
    # Total resolution intervals in the period, from its timeInterval; the last
    # point's block runs to this end.
    n_intervals = points[-1][0]
    start = period.findtext("{*}timeInterval/{*}start")
    end = period.findtext("{*}timeInterval/{*}end")
    if start and end:
        span_hours = (
            datetime.fromisoformat(end.replace("Z", "+00:00"))
            - datetime.fromisoformat(start.replace("Z", "+00:00"))
        ).total_seconds() / 3600.0
        n_intervals = max(n_intervals, round(span_hours / res_hours))
    total = 0.0
    for i, (position, quantity) in enumerate(points):
        next_position = points[i + 1][0] if i + 1 < len(points) else n_intervals + 1
        total += quantity * (next_position - position) * res_hours
    return total


def _parse_exchange_mwh(xml: str) -> float:
    """Total scheduled exchange energy (MWh) in one A09 document (all TimeSeries)."""
    root = ET.fromstring(xml)
    return sum(
        _period_energy(period)
        for ts in root.iterfind("{*}TimeSeries")
        for period in ts.iterfind("{*}Period")
    )


def _parse_generation_mwh(xml: str) -> float:
    """Total actual generation energy (MWh) in one A75 document.

    Sums only generation TimeSeries (``inBiddingZone_Domain``); the storage
    consumption side (``outBiddingZone_Domain`` with no in-zone) is skipped so
    pumped-storage load is not netted out of generation.
    """
    root = ET.fromstring(xml)
    total = 0.0
    for ts in root.iterfind("{*}TimeSeries"):
        has_in = ts.find("{*}inBiddingZone_Domain.mRID") is not None
        has_out = ts.find("{*}outBiddingZone_Domain.mRID") is not None
        if has_out and not has_in:
            continue  # storage consumption, not generation
        for period in ts.iterfind("{*}Period"):
            total += _period_energy(period)
    return total


def _raw_client(api_key: str):
    """Lazily build an ENTSO-E raw client (entsoe-py optional; pandas-3 safe).

    Retries transient HTTP/connection errors so a dropped socket does not
    silently under-count a border (which would inflate the domestic share).
    """
    try:
        from entsoe import EntsoeRawClient
    except ImportError as exc:  # pragma: no cover - entsoe-py is a pinned dependency
        raise ImportError(
            "The live ENTSO-E fetch needs the 'entsoe-py' package (a pinned MARIO "
            "dependency: pip install 'entsoe-py==0.8.0'; "
            "https://github.com/EnergieID/entsoe-py). Only its raw XML client is "
            "used, so it coexists with pandas 3. Or pass entsoe_path=... with a "
            "snapshot CSV instead."
        ) from exc
    return EntsoeRawClient(api_key=api_key, retry_count=6, retry_delay=15, timeout=300)


def _is_no_data(exc: Exception) -> bool:
    """True if `exc` is ENTSO-E's genuine no-data signal (safe to skip a border)."""
    try:
        from entsoe.exceptions import NoMatchingDataError
    except ImportError:  # pragma: no cover
        return False
    return isinstance(exc, NoMatchingDataError)


def _query(fn, *args, retries: int = 3, **kwargs) -> tuple[str | None, bool]:
    """Run one ENTSO-E raw query, retrying transient errors beyond the client's own.

    Returns ``(xml_or_None, failed)``. ``failed`` is True only when a non-no-data
    error persists through all retries (a genuine no-data response returns
    ``(None, False)`` -- a real zero, not a failure). ENTSO-E read timeouts on a
    big document are transient; retrying here (on top of the client's retries)
    keeps one slow query from aborting a 15-minute whole-area fetch.
    """
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs), False
        except Exception as exc:  # noqa: BLE001
            if _is_no_data(exc):
                return None, False
            if attempt == retries - 1:
                return None, True
            time.sleep(10 * (attempt + 1))
    return None, True


def _annual_generation(client, zones, start, end, failures: list[str]) -> float:
    total = 0.0
    for z in zones:
        xml, failed = _query(client.query_generation, z, start=start, end=end)
        if failed:
            failures.append(f"generation:{z}")
        elif xml is not None:
            total += _parse_generation_mwh(xml)
    return total


def _annual_net_imports(
    client, country, zones, neighbours, start, end, failures: list[str]
) -> dict[str, float]:
    """Net scheduled imports into `country` by EXIOBASE origin (inflow-outflow>0)."""
    inflow: dict[str, float] = {}
    outflow: dict[str, float] = {}

    def energy(a: str, b: str) -> float:
        xml, failed = _query(client.query_scheduled_exchanges, a, b, start=start, end=end)
        if failed:
            failures.append(f"exchange:{a}->{b}")
            return 0.0
        return _parse_exchange_mwh(xml) if xml is not None else 0.0

    for z in zones:
        for nb in neighbours.get(z, []):
            origin = zone_to_country(nb)
            if origin == country:
                continue
            inflow[origin] = inflow.get(origin, 0.0) + energy(nb, z)   # nb -> z (import)
            outflow[origin] = outflow.get(origin, 0.0) + energy(z, nb)  # z -> nb (export)
    net: dict[str, float] = {}
    for origin in set(inflow) | set(outflow):
        value = inflow.get(origin, 0.0) - outflow.get(origin, 0.0)
        if value > 0:
            net[origin] = value
    return net


def fetch_import_mix(api_key: str, year: int) -> pd.DataFrame:
    """Fetch the first-order net commercial import mix for `year` from ENTSO-E.

    Returns the same flat ``(destination, origin, share)`` frame nxbase's
    entsoe_pull.py writes, so it is a drop-in for ``entsoe_path``. Each
    destination's shares (domestic diagonal + net imports) sum to 1; regions
    with no generation data (GB, MT) are skipped for the caller to fill.
    """
    from entsoe.mappings import NEIGHBOURS

    logger.info(
        "ENTSO-E fetch: downloading %s scheduled exchanges + generation for %s "
        "countries via entsoe-py's raw client (parsed in-house, pandas-3 safe). "
        "This makes many Transparency Platform requests and can take minutes.",
        year,
        len(COUNTRY_ZONES),
    )
    client = _raw_client(api_key)
    start = pd.Timestamp(f"{year}0101", tz="Europe/Brussels")
    end = pd.Timestamp(f"{year + 1}0101", tz="Europe/Brussels")

    records: list[dict] = [
        {"destination": c, "origin": c, "share": 1.0} for c in DOMESTIC_ONLY
    ]
    covered: list[str] = []
    skipped: list[str] = []
    failures: list[str] = []
    for country, zones in COUNTRY_ZONES.items():
        logger.info("ENTSO-E fetch: downloading %s ...", country)
        gen = _annual_generation(client, zones, start, end, failures)
        if gen <= 0:
            skipped.append(country)
            continue
        imp = _annual_net_imports(client, country, zones, NEIGHBOURS, start, end, failures)
        denom = gen + sum(imp.values())
        shares = {country: gen / denom}
        for origin, mwh in imp.items():
            shares[origin] = shares.get(origin, 0.0) + mwh / denom
        for origin, share in sorted(shares.items(), key=lambda kv: -kv[1]):
            records.append({"destination": country, "origin": origin, "share": share})
        covered.append(country)

    logger.info(
        "ENTSO-E fetch: done -- %s countries covered + %s domestic-only%s.",
        len(covered),
        len(DOMESTIC_ONLY),
        f"; skipped (no generation data) {sorted(skipped)}" if skipped else "",
    )
    if failures:
        # Persistent per-query failures are surfaced loudly (never a silent
        # under-count): the mix for the affected destinations may be slightly off
        # -- re-run to fill the gaps.
        logger.warning(
            "ENTSO-E fetch: %s queries failed after retries and were skipped; the "
            "mix for the affected destinations may be slightly off -- re-run to "
            "fill them. Failed queries: %s",
            len(failures),
            failures,
        )
    return pd.DataFrame.from_records(records)
