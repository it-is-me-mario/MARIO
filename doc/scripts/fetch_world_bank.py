"""Refresh the browser's pinned WDI reference; never runs during a docs build."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

INDICATORS = {
    "NY.GDP.MKTP.CD": "gdp",
    "NY.GDP.PCAP.CD": "gdp_per_capita",
    "SP.POP.TOTL": "population",
    "PA.NUS.FCRF": "local_currency_per_usd",
}
API = "https://api.worldbank.org/v2"


def pages(url):
    rows, provenance = [], []
    page = 1
    while True:
        request = f"{url}&page={page}"
        with urlopen(request, timeout=90) as response:
            raw = response.read()
        data = json.loads(raw)
        if not isinstance(data, list) or len(data) != 2 or not isinstance(data[0], dict) or "pages" not in data[0]:
            raise ValueError(f"Unexpected World Bank response: {request}")
        rows.extend(data[1] or [])
        provenance.append({"url": request, "sha256": hashlib.sha256(raw).hexdigest(),
                           "last_updated": data[0].get("lastupdated")})
        if page >= data[0]["pages"]:
            break
        page += 1
    return rows, provenance



def euro_rates(reference, start, end):
    """Annual USD/EUR rates; pre-1999 values use Eurostat's ECU convention."""
    years = {year: 1 / row["local_currency_per_usd"]
             for year, row in reference["countries"]["DEU"]["years"].items()
             if int(year) >= 1999 and row.get("local_currency_per_usd", 0)}
    sources = [{"url": "https://data.worldbank.org/indicator/PA.NUS.FCRF?locations=DE",
                "years": sorted(map(int, years))}]
    if start < 1999:
        url = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ert_bil_eur_a"
               f"?lang=en&currency=USD&statinfo=AVG&sinceTimePeriod={start}&untilTimePeriod={min(end,1998)}")
        with urlopen(url, timeout=90) as response:
            raw = response.read()
        data = json.loads(raw)
        if data["id"][-1] != "time" or any(n != 1 for n in data["size"][:-1]):
            raise ValueError("Unexpected Eurostat exchange-rate dimensions")
        if set(data["dimension"]["currency"]["category"]["index"]) != {"USD"}:
            raise ValueError("Expected USD per EUR/ECU")
        dates = data["dimension"]["time"]["category"]["index"]
        observations = data["value"]
        for year, index in dates.items():
            rate = observations.get(str(index)) if isinstance(observations, dict) else observations[index]
            if rate is not None and rate > 0:
                years[year] = rate
        sources.insert(0, {"url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                           "years": sorted(map(int, dates))})
    return {"EUR": {"quote": "USD per EUR (ECU before 1999)", "years": years,
                    "annual_average": True,
                    "historical_convention": "Eurostat EUR/ECU annual series: ECU before 1999, replaced by EUR at 1:1. German pre-1999 DEM/USD rates are never used as EUR rates.",
                    "sources": sources}}

def fetch(start, end):
    countries, sources = pages(f"{API}/country?format=json&per_page=400")
    # Exclude World Bank regional/income totals; never treat them as countries.
    registry = {c["id"]: {"name": c["name"], "iso2": c["iso2Code"], "years": {}}
                for c in countries if c["region"]["id"] != "NA" or c["id"] == "WLD"}
    for indicator, field in INDICATORS.items():
        records, provenance = pages(
            f"{API}/country/all/indicator/{indicator}?source=2&date={start}:{end}&format=json&per_page=20000")
        sources.extend(provenance)
        for r in records:
            country = registry.get(r["countryiso3code"])
            if country is not None:
                # Missing values remain null; no nearest-year substitution.
                country["years"].setdefault(r["date"], {})[field] = r["value"]
    world = registry.pop("WLD")
    result = {"schema_version": 1, "source": "World Bank, World Development Indicators",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "license": "CC BY 4.0", "license_url": "https://datacatalog.worldbank.org/public-licenses",
            "indicators": INDICATORS, "years": list(range(start, end + 1)),
            "sources": sources, "countries": registry, "aggregates": {"WLD": world}}
    result["currency_rates"] = euro_rates(result, start, end)
    return result


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--start", type=int, default=1995)
    cli.add_argument("--end", type=int, default=2024)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.start > args.end:
        cli.error("start must be no later than end")
    result = fetch(args.start, args.end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    print(f"WDI: {len(result['countries'])} economies, {args.start}–{args.end}")
