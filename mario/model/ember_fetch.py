"""Fetch electricity generation live from the Ember API.

Supply-side companion of :mod:`mario.model.entsoe_fetch`. When a caller has no
EMBER snapshot CSV but does have an Ember API key, this pulls yearly generation
by fuel directly from Ember's public REST API and returns it in the reduced
``ISO3, Year, Variable, Value`` schema that
:func:`mario.model.electricity_mix.build_electricity_mix_shares` reads -- so an
``api_key={"ember": ...}`` fetch is a drop-in for an ``ember_path`` snapshot.

Unlike the ENTSO-E side (which needs entsoe-py's zone/EIC machinery), the Ember
API is a plain JSON REST endpoint: the only dependency is ``requests`` and the
key is a query parameter. Ember covers **all countries** (why the generation
mix uses Ember, not the Europe-only ENTSO-E; see ``update_supply_mix``).

Docs: https://api.ember-energy.org/v1/docs -- register a key at
https://ember-energy.org/data/api/
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_EMBER_GENERATION_URL = "https://api.ember-energy.org/v1/electricity-generation/yearly"
# Ember fuel series that map to the EMBER generation taxonomy MARIO expects
# (aggregate roll-ups like "Clean"/"Fossil"/"Demand" are excluded via the API's
# is_aggregate_series=false filter).


def fetch_generation(
    api_key: str,
    year: int,
    *,
    end_year: int | None = None,
    is_aggregate_entity: bool | None = None,
    timeout: int = 120,
) -> pd.DataFrame:
    """Fetch yearly generation-by-fuel from the Ember API.

    Returns a reduced frame ``ISO3, Year, Variable, Value`` (Value in TWh),
    matching the packaged EMBER snapshot, with only the disaggregated fuel
    series (Bioenergy, Coal, Gas, Hydro, Nuclear, Solar, Wind, ...).

    ``year`` alone fetches one year (the supply-mix case); pass ``end_year`` for
    an inclusive range (``year..end_year``). ``is_aggregate_entity=False``
    restricts to individual countries (drops region roll-ups like "Europe"),
    which nxbase's per-country ingestion wants; ``None`` (default) returns both.
    """
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "The live Ember fetch needs the 'requests' package (pip install requests)."
        ) from exc

    end = year if end_year is None else end_year
    span = str(year) if end == year else f"{year}-{end}"
    logger.info("Ember fetch: downloading %s generation-by-fuel from the Ember API.", span)
    params = {
        "start_date": str(year),
        "end_date": str(end),
        "is_aggregate_series": "false",
        "api_key": api_key,
    }
    if is_aggregate_entity is not None:
        params["is_aggregate_entity"] = "true" if is_aggregate_entity else "false"
    response = requests.get(_EMBER_GENERATION_URL, params=params, timeout=timeout)
    response.raise_for_status()
    rows = response.json().get("data", [])

    # Map API series names to MARIO's canonical EMBER taxonomy (case-insensitive:
    # the API returns "Other fossil"/"Other renewables" lowercase) and drop any
    # series that is not a generation fuel MARIO tracks (e.g. "Net imports").
    from mario.model.electricity_mix import _EMBER_RAW_RELEASE_VARIABLES

    canonical = {name.casefold(): name for name in _EMBER_RAW_RELEASE_VARIABLES}
    records = []
    for row in rows:
        if row.get("is_aggregate_series", False) or not row.get("entity_code"):
            continue
        variable = canonical.get(str(row.get("series", "")).strip().casefold())
        if variable is None:
            continue
        records.append(
            {
                "ISO3": row["entity_code"],
                "Year": int(row["date"]),
                "Variable": variable,
                "Value": row["generation_twh"],
            }
        )
    frame = pd.DataFrame.from_records(records)
    logger.info(
        "Ember fetch: %s rows for %s across %s countries.",
        len(frame),
        year,
        frame["ISO3"].nunique() if not frame.empty else 0,
    )
    return frame
