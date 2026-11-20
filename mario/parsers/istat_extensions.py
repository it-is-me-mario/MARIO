"""Optional activity-based satellite accounts for the ISTAT A64 SUT.

Eurostat publishes Italy's AEA, employment and PEFA accounts on compatible
NACE Rev. 2 branches. Match source codes, never descriptions or positions.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from numbers import Real
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import requests

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.utils import rename_index

_API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
_GROUPS = ("emissions", "employment", "energy")
_NACE = dict(zip(
    "V01 V02 V03 VB V10_12 V13_15 V16 V17 V18 V19 V20 V21 V22 V23 V24 V25 "
    "V26 V27 V28 V29 V30 V31_32 V33 VD V36 V37_39 VF V45 V46 V47 V49 V50 "
    "V51 V52 V53 VI V58 V59_60 V61 V62_63 V64 V65 V66 VL V69_70 V71 V72 "
    "V73 V74_75 V77 V78 V79 V80_82 VO VP V86 V87_88 V90_92 V93 V94 V95 V96 VT".split(),
    "A01 A02 A03 B C10-C12 C13-C15 C16 C17 C18 C19 C20 C21 C22 C23 C24 C25 "
    "C26 C27 C28 C29 C30 C31_C32 C33 D E36 E37-E39 F G45 G46 G47 H49 H50 "
    "H51 H52 H53 I J58 J59_J60 J61 J62_J63 K64 K65 K66 L M69_M70 M71 M72 "
    "M73 M74_M75 N77 N78 N79 N80-N82 O P Q86 Q87_Q88 R90-R92 R93 S94 S95 S96 T".split(),
))
_POLLUTANTS = (
    "GHG", "CO2", "CH4", "CH4_CO2E", "N2O", "N2O_CO2E", "HFC_CO2E",
    "PFC_CO2E", "NF3_SF6_CO2E", "CO2_BIO", "ACG", "SOX_SO2E", "NOX_SO2E",
    "NH3_SO2E", "O3PR", "NOX_NMVOCE", "CO", "CO_NMVOCE", "CH4_NMVOCE",
    "NOX", "NH3", "PM2_5", "PM10", "NMVOC",
)
_SOURCES = {
    "emissions": ("env_ac_ainah_r2", "T", "airpol", _POLLUTANTS),
    "employment": ("nama_10_a64_e", "THS_PER", "na_item", ("EMP_DC",)),
    "energy": ("env_ac_pefa04", "TJ", "indic_pefa", ("NETDOM_EUSE",)),
}
_HOUSEHOLDS = "Spesa per consumi finali delle famiglie"


def normalize_istat_extensions(selection) -> tuple[str, ...]:
    """Validate the optional selector before any download or workbook access."""
    if selection is None:
        return ()
    if isinstance(selection, str):
        if selection == "all":
            return _GROUPS
        selected = [selection]
    else:
        try:
            selected = list(selection)
        except TypeError as exc:
            raise WrongInput("ISTAT extensions must be None, 'all', or a selection of emissions, employment, energy.") from exc
    if any(not isinstance(item, str) or item not in _GROUPS for item in selected):
        raise WrongInput(f"ISTAT extensions must be selected from {list(_GROUPS)}.")
    return tuple(group for group in _GROUPS if group in selected)


def _categories(payload, dimension):
    category = payload["dimension"][dimension]["category"]
    index = category["index"]
    if isinstance(index, list):
        index = {code: position for position, code in enumerate(index)}
    if not isinstance(index, dict) or sorted(index.values()) != list(range(len(index))):
        raise ValueError(f"Invalid category positions for {dimension}.")
    return index


class _Observations:
    """Read sparse or dense JSON-stat values with explicit coordinate checks."""

    def __init__(self, payload, dataset, year, unit, indicator_dimension):
        self.payload = payload
        self.dataset = dataset
        try:
            self.dimensions = payload["id"]
            self.sizes = payload["size"]
            expected = {"freq", "geo", "time", "unit", "nace_r2", indicator_dimension}
            if set(self.dimensions) != expected or len(self.dimensions) != len(expected):
                raise ValueError("Unexpected JSON-stat dimensions.")
            if len(self.sizes) != len(self.dimensions):
                raise ValueError("Invalid JSON-stat sizes.")
            self.categories = {dim: _categories(payload, dim) for dim in self.dimensions}
            if any(len(self.categories[dim]) != size for dim, size in zip(self.dimensions, self.sizes)):
                raise ValueError("Category sizes do not match dimensions.")
            self.fixed = {"freq": "A", "geo": "IT", "time": str(year), "unit": unit}
            if any(set(self.categories[dim]) != {code} for dim, code in self.fixed.items()):
                raise ValueError("Expected annual Italian observations for the requested year and unit.")
            self.values = payload["value"]
            self.status = payload.get("status", {})
            if not isinstance(self.values, (dict, list)) or not isinstance(self.status, (dict, list)):
                raise ValueError("Invalid observation storage.")
            self.indicator_dimension = indicator_dimension
            self.flags = []
        except (KeyError, TypeError, ValueError) as exc:
            raise WrongFormat(f"Invalid Eurostat {dataset} snapshot: {exc}") from exc

    @staticmethod
    def _get(values, position):
        if isinstance(values, dict):
            return values.get(str(position))
        return values[position] if position < len(values) else None

    def read(self, indicator, nace):
        chosen = {**self.fixed, self.indicator_dimension: indicator, "nace_r2": nace}
        try:
            position = 0
            for dim, size in zip(self.dimensions, self.sizes):
                position = position * size + self.categories[dim][chosen[dim]]
            value = self._get(self.values, position)
            flag = self._get(self.status, position)
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError("Missing or non-finite observation")
            if flag and "c" in str(flag).lower():
                raise ValueError("Confidential observation")
            if flag:
                self.flags.append({self.indicator_dimension: indicator, "nace_r2": nace, "status": flag})
            return float(value)
        except (KeyError, ValueError) as exc:
            raise WrongFormat(
                f"Eurostat {self.dataset}: {indicator}/{nace} is unavailable "
                "for the selected year. Missing/confidential values are not zero."
            ) from exc


def _cache_root(path):
    path = Path(path)
    return (path.parent if path.is_file() or path.suffix.lower() in {".zip", ".xlsx", ".xls"} else path) / "extensions"


def _load_source(group, *, year, codes, cache, download, overwrite):
    dataset, unit, indicator_dimension, indicators = _SOURCES[group]
    params = {"geo": "IT", "time": str(year), "unit": unit, "freq": "A", "lang": "en"}
    if group != "emissions":
        params[indicator_dimension] = indicators[0]
    path = cache / f"{dataset}_IT_{year}.json"
    refresh = download and (overwrite or not path.exists())
    if refresh:
        try:
            response = requests.get(_API + dataset, params=params, timeout=60)
            response.raise_for_status()
            snapshot = {
                "dataset": dataset, "query": params,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "payload": response.json(),
            }
        except (requests.RequestException, ValueError) as exc:
            raise WrongInput(f"Could not download Eurostat {dataset}: {exc}") from exc
    else:
        if not path.is_file():
            raise WrongInput(f"Missing ISTAT extension cache: {path}. Use download=True to fetch the selected accounts.")
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise WrongFormat(f"Could not read ISTAT extension cache {path}: {exc}") from exc
    if not isinstance(snapshot, dict) or snapshot.get("dataset") != dataset or snapshot.get("query") != params:
        raise WrongFormat(f"ISTAT extension cache {path} does not match the requested dataset/query.")
    observations = _Observations(snapshot.get("payload", {}), dataset, year, unit, indicator_dimension)
    nace_codes = list(codes) + (["HH"] if group != "employment" else [])
    data = {indicator: [observations.read(indicator, code) for code in nace_codes] for indicator in indicators}
    # Replace a previous cache only after validating every required observation.
    if refresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(snapshot, stream, ensure_ascii=False, allow_nan=False)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    report = {
        "dataset": dataset, "url": _API + dataset, "query": params,
        "cache": str(path), "retrieved_at": snapshot.get("retrieved_at"),
        "updated": observations.payload.get("updated"), "status": observations.flags,
        "indicator_descriptions": observations.payload["dimension"][indicator_dimension]["category"].get("label", {}),
    }
    return data, report


def _emission_unit(code):
    if code == "GHG" or code.endswith("_CO2E"):
        return "t CO2-eq"
    if code == "ACG" or code.endswith("_SO2E"):
        return "t SO2-eq"
    if code == "O3PR" or code.endswith("_NMVOCE"):
        return "t NMVOC-eq"
    return "t"


def attach_istat_extensions(matrices, indexes, units, layout, *, selection, path, download, overwrite):
    """Replace the empty satellite placeholder with selected source accounts."""
    try:
        codes = [_NACE[code] for code in layout.activity_codes]
    except KeyError as exc:
        raise WrongFormat(f"Unsupported ISTAT activity code for satellite alignment: {exc.args[0]}.") from exc
    baseline = matrices["baseline"]
    if not codes or len(codes) != len(baseline["S"].index) or len(set(codes)) != len(codes):
        raise WrongFormat("ISTAT activity codes do not uniquely match the SUT activity axis.")
    fd_labels = baseline["EY"].columns.get_level_values(-1).tolist()
    household_column = None
    if "emissions" in selection or "energy" in selection:
        if fd_labels.count(_HOUSEHOLDS) != 1:
            raise WrongFormat("ISTAT environmental accounts require one household final-consumption column.")
        household_column = fd_labels.index(_HOUSEHOLDS)
    hours = None
    if "employment" in selection:
        try:
            hours = np.asarray(layout.hours_worked, dtype=float)
            if len(hours) != len(codes) or not np.isfinite(hours).all() or (hours < 0).any():
                raise ValueError("Invalid hours")
        except (TypeError, ValueError) as exc:
            raise WrongFormat("ISTAT employment extensions require complete 'Ore lavorate (migliaia)' observations in USE.") from exc
    rows, ea, ey, row_units, sources = [], [], [], [], []

    def add_row(label, values, unit, household=0.0):
        rows.append(label)
        ea.append(values)
        final = np.zeros(len(fd_labels))
        if household_column is not None:
            final[household_column] = household
        ey.append(final)
        row_units.append(unit)

    for group in selection:
        data, source = _load_source(group, year=layout.year, codes=codes, cache=_cache_root(path), download=download, overwrite=overwrite)
        sources.append(source)
        if group == "emissions":
            for code, values in data.items():
                add_row(f"AEA | {code}", values[:-1], _emission_unit(code), values[-1])
        elif group == "employment":
            add_row("Employment | Total", np.asarray(data["EMP_DC"]) * 1000.0, "persons")
            add_row("Employment | Hours worked", hours * 1000.0, "hours")
            sources.append({"dataset": "ISTAT USE", "year": layout.year, "indicator": "Ore lavorate (migliaia)", "scale": 1000.0})
        else:
            values = data["NETDOM_EUSE"]
            add_row("Energy | Net domestic energy use", values[:-1], "TJ", values[-1])
    axis = pd.Index(rows)
    baseline["Ea"] = pd.DataFrame(ea, index=axis, columns=baseline["Ea"].columns)
    baseline["Ec"] = pd.DataFrame(0.0, index=axis, columns=baseline["Ec"].columns)
    baseline["EY"] = pd.DataFrame(ey, index=axis, columns=baseline["EY"].columns)
    indexes["k"]["main"] = rows
    units[_MASTER_INDEX["k"]] = pd.DataFrame({"unit": row_units}, index=axis)
    rename_index({name: baseline[name] for name in ("Ea", "Ec", "EY")})
    return {
        "groups": list(selection), "year": layout.year, "geo": "IT",
        "activity_mapping": dict(zip(layout.activity_codes, codes)),
        "household_final_demand": _HOUSEHOLDS if household_column is not None else None,
        "sources": sources,
    }
