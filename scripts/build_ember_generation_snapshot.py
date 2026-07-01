"""Build the reduced EMBER electricity-generation snapshot packaged with MARIO."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


_USECOLS = [
    "Area",
    "ISO 3 code",
    "Year",
    "Area type",
    "Category",
    "Subcategory",
    "Variable",
    "Unit",
    "Value",
]
_VARIABLES = [
    "Bioenergy",
    "Coal",
    "Gas",
    "Hydro",
    "Nuclear",
    "Other Fossil",
    "Other Renewables",
    "Solar",
    "Wind",
]


def build_snapshot(source: Path, output: Path) -> None:
    """Filter one raw EMBER CSV down to the MARIO runtime snapshot."""
    filtered = []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("Area type") != "Country or economy":
                continue
            if row.get("Category") != "Electricity generation":
                continue
            if row.get("Subcategory") != "Fuel":
                continue
            if row.get("Unit") != "TWh":
                continue
            if row.get("Variable") not in _VARIABLES:
                continue

            iso3 = str(row.get("ISO 3 code", "")).strip().upper()
            if not iso3:
                continue

            try:
                year = int(float(row.get("Year", "")))
                value = float(row.get("Value", ""))
            except (TypeError, ValueError):
                continue

            filtered.append(
                {
                    "ISO3": iso3,
                    "Year": year,
                    "Variable": str(row.get("Variable", "")).strip(),
                    "Value": value,
                }
            )

    filtered.sort(key=lambda item: (item["ISO3"], item["Year"], item["Variable"]))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ISO3", "Year", "Variable", "Value"])
        writer.writeheader()
        writer.writerows(filtered)


def main() -> None:
    """Parse CLI arguments and build the packaged EMBER snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to the raw EMBER yearly_full_release_long_format.csv file.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "mario" / "settings" / "ember_electricity_generation.csv",
        help="Destination path for the reduced EMBER snapshot.",
    )
    args = parser.parse_args()
    build_snapshot(args.source, args.output)


if __name__ == "__main__":
    main()