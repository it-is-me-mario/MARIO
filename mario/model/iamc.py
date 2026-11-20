"""Annual IAMC scenario data and production shares for MARIO supply mixes."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


_DIMENSIONS = ["Model", "Scenario", "Region", "Variable", "Unit"]
_ELECTRICITY = "Secondary Energy|Electricity"
_EXIOBASE_GENERATORS = {
    "coal": "Coal",
    "gas": "Gas",
    "nuclear": "Nuclear",
    "hydro": "Hydro",
    "wind": "Wind",
    "petroleum and other oil derivatives": "Oil",
    "biomass and waste": "Biomass",
    "Geothermal": "Geothermal",
    "solar photovoltaic": "Solar|PV",
    "solar thermal": "Solar|CSP",
}

# Relative LCOE (wind = 1), Peng et al. 2026, Supporting Information 1, Table S6.
_PENG_ELECTRICITY_COSTS = {
    "Coal": 2.76,
    "Gas": 1.47,
    "Nuclear": 4.08,
    "Hydro": 1.20,
    "Wind": 1.00,
    "Oil": 3.99,
    "Biomass": 1.79,
    "Geothermal": 2.07,
    "Solar|PV": 0.95,
    "Solar|CSP": 3.55,
}


def _year(column):
    if re.fullmatch(r"[0-9]{4}(?:\.0)?", str(column)):
        return int(float(column))
    return None


def read_iamc(source, *, sheet_name=0):
    """Read an annual IAMC CSV, XLSX worksheet, pandas ExcelFile or DataFrame.

    Accept wide year columns or long Year/Value data. Preserve model, scenario,
    region, variable and unit labels, including project-specific names.
    Returns an IamData object whose frame contains one row per time series.
    """
    if isinstance(source, pd.DataFrame):
        frame = source.copy()
    elif isinstance(source, pd.ExcelFile) or Path(source).suffix.lower() in (
        ".xlsx",
        ".xlsm",
    ):
        frame = pd.read_excel(source, sheet_name=sheet_name, keep_default_na=False)
    else:
        frame = pd.read_csv(source, keep_default_na=False)
    columns = {name.lower(): name for name in [*_DIMENSIONS, "Year", "Value"]}
    frame = frame.rename(columns=lambda c: columns.get(str(c).strip().lower(), c))
    if frame.columns.has_duplicates or not set(_DIMENSIONS).issubset(frame.columns):
        raise ValueError(f"Expected unique IAMC columns including {_DIMENSIONS}.")
    frame = frame.mask(frame.eq(""))
    # The official IIASA download ends in a single-cell copyright notice.
    footer = frame.Model.astype(str).str.strip().str.startswith("© IIASA") & frame.drop(
        columns="Model"
    ).isna().all(axis=1)
    frame = frame.loc[~footer].dropna(how="all")
    if frame.empty or frame[_DIMENSIONS].isna().any().any():
        raise ValueError("No series or missing IAMC dimensions.")
    for col in frame:
        if str(col).strip().lower() == "subannual":
            periods = frame[col].dropna().astype(str).str.lower()
            if not periods.isin(["year", "annual"]).all():
                raise ValueError(
                    "Select annual observations before importing subannual data."
                )
    if "Year" in frame or "Value" in frame:
        if not {"Year", "Value"}.issubset(frame):
            raise ValueError("Long IAMC data needs both Year and Value.")
        frame["Year"] = frame.Year.map(_year)
        if frame.Year.isna().any():
            raise ValueError("Expected four-digit annual years.")
        frame = frame.pivot(
            index=_DIMENSIONS, columns="Year", values="Value"
        ).reset_index()
    years = {col: _year(col) for col in frame.columns if _year(col) is not None}
    if not years or len(set(years.values())) != len(years):
        raise ValueError("Missing or duplicate annual year columns.")
    if frame.duplicated(_DIMENSIONS).any():
        raise ValueError(
            "Duplicate IAMC series. Select a single annual series per set of dimensions."
        )
    return IamData(frame[[*_DIMENSIONS, *years]].rename(columns=years))


@dataclass
class IamData:
    """Annual reporting series in wide IAMC format."""

    frame: pd.DataFrame

    def supply_mix(
        self,
        *,
        model,
        scenario,
        year,
        regions,
        unit,
        basis,
        variables="exiobase-electricity",
        total=None,
        prices=None,
    ):
        """Return target region -> native label -> share for update_supply_mix.

        regions maps each target region to one IAM region or disjoint IAM regions
        to sum. The same source cannot be assigned to multiple target regions.
        variables maps native labels to series names or lists of additive series.
        The preset maps ten reported generation technologies to EXIOBASE activities
        and checks closure against Secondary Energy|Electricity before assigning
        zero to ocean and unspecified generation. Custom mixes can specify a total
        for the same check (relative tolerance 1e-5).

        basis='physical' uses production quantities. basis='value' multiplies
        by strictly positive prices[target_region][native_label] in one consistent
        valuation per unit. Regional prices apply after geographic aggregation.
        For the electricity preset, prices="peng-2026" uses Peng et al.'s
        Table S6 relative generation costs in each target region (wind = 1).
        Returns shares within the specified production bundle, not output levels.
        """
        preset = isinstance(variables, str) and variables == "exiobase-electricity"
        if isinstance(prices, str):
            if prices != "peng-2026" or not preset or basis != "value":
                raise ValueError(
                    "prices='peng-2026' requires the EXIOBASE electricity preset and a value mix."
                )
            if not isinstance(regions, Mapping):
                raise ValueError(
                    "Provide a mapping from target regions to IAM regions."
                )
            ratios = {
                f"Production of electricity by {label}": _PENG_ELECTRICITY_COSTS[fuel]
                for label, fuel in _EXIOBASE_GENERATORS.items()
            }
            prices = dict.fromkeys(regions, ratios)
        if preset:
            variables = {
                f"Production of electricity by {label}": f"{_ELECTRICITY}|{fuel}"
                for label, fuel in _EXIOBASE_GENERATORS.items()
            }
            if total is not None and total != _ELECTRICITY:
                raise ValueError(
                    f"The electricity preset requires total={_ELECTRICITY!r}."
                )
            total = _ELECTRICITY
        if (
            not isinstance(variables, Mapping)
            or not variables
            or not isinstance(regions, Mapping)
            or not regions
        ):
            raise ValueError("Provide non-empty native variable and region mappings.")
        if basis not in ("physical", "value") or (prices is not None) != (
            basis == "value"
        ):
            raise ValueError(
                "Use basis='physical' without prices or basis='value' with prices."
            )
        if prices is not None and (
            not isinstance(prices, Mapping) or set(prices) != set(regions)
        ):
            raise ValueError("Supply prices for exactly the selected target regions.")
        groups = {
            k: [v] if isinstance(v, str) else list(v) for k, v in variables.items()
        }
        series = [v for members in groups.values() for v in members]
        if any(not v for v in groups.values()) or len(series) != len(set(series)):
            raise ValueError(
                "Each native label needs distinct, non-overlapping IAM variables."
            )
        if any(v.startswith(other + "|") for v in series for other in series):
            raise ValueError(
                "An aggregate and its component cannot both contribute to the mix."
            )
        if total in series and len(series) > 1:
            raise ValueError(
                "The total used for validation must be separate from the components."
            )
        if year not in self.frame:
            raise ValueError(f"Year {year!r} is unavailable.")
        data = self.frame
        subset = data.loc[
            (data.Model == model) & (data.Scenario == scenario) & (data.Unit == unit)
        ]
        values = subset.set_index(["Region", "Variable"])[year]
        if values.empty:
            raise ValueError(f"No series for {model!r}, {scenario!r}, {unit!r}.")
        result = {}
        used_regions = set()
        for target, sources in regions.items():
            sources = [sources] if isinstance(sources, str) else list(sources)
            if (
                not sources
                or len(set(sources)) != len(sources)
                or used_regions.intersection(sources)
            ):
                raise ValueError(
                    "Regional aggregation requires distinct, non-overlapping source regions."
                )
            if len(sources) > 1 and unit.strip().lower() in {
                "%",
                "percent",
                "fraction",
                "share",
                "1",
            }:
                raise ValueError(
                    "Aggregate physical production before calculating shares across regions."
                )
            used_regions.update(sources)
            requested = list(dict.fromkeys([*series, *([total] if total else [])]))
            required = pd.MultiIndex.from_product(
                [sources, requested], names=values.index.names
            )
            selected = pd.to_numeric(values.reindex(required), errors="raise")
            invalid = selected.isna() | ~np.isfinite(selected) | (selected < 0)
            if invalid.any():
                raise ValueError(
                    f"Missing, non-finite or negative {unit} at {year}: {selected.index[invalid].tolist()}"
                )
            by_region = selected.unstack()
            if total and not np.allclose(
                by_region[series].sum(axis=1), by_region[total], rtol=1e-5, atol=0
            ):
                raise ValueError(
                    f"Mapped production does not reconcile to {total!r} in {sources}."
                )
            quantities = by_region.sum(axis=0)
            weights = pd.Series({k: quantities.loc[v].sum() for k, v in groups.items()})
            if prices is not None:
                factors = pd.Series(prices[target], dtype=float)
                if preset:
                    aliases = {item.casefold(): item for item in weights.index}
                    factors.index = [
                        aliases.get(str(item).casefold(), item)
                        for item in factors.index
                    ]
                if (
                    factors.index.has_duplicates
                    or set(factors.index) != set(weights.index)
                    or not np.isfinite(factors).all()
                    or (factors <= 0).any()
                ):
                    raise ValueError(
                        f"Expected a finite positive price for each mapped technology in {target!r}."
                    )
                weights = weights * factors.reindex(weights.index)
            if not np.isfinite(weights.sum()) or weights.sum() <= 0:
                raise ValueError(f"No positive, finite production mix in {target!r}.")
            result[target] = (weights / weights.sum()).to_dict()
            if preset:
                result[target].update(
                    {
                        "Production of electricity by tide, wave, ocean": 0.0,
                        "Production of electricity nec": 0.0,
                    }
                )
        return result
