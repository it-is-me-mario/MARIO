"""Audit locally held Eora1 26 releases and refresh scope-only year metadata.

The parsed 2017 profile supplies the native inventory. Other supplied label
files must match it byte-for-byte; no numerical observations are loaded or copied.
The locally held 2016 folder lacks labels_VA.txt, so a complete common label
folder is needed through parse_eora(indeces=...) for that year.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

DATA_KINDS = ("T", "FD", "VA", "Q", "QY")
LABEL_KINDS = ("T", "FD", "VA", "Q")
PROFILE_ID = "eora26-2017-bp"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matrix_shape(path: Path) -> tuple[int, tuple[int, ...]]:
    widths = set()
    with path.open(encoding="utf-8") as stream:
        rows = 0
        for line in stream:
            rows += 1
            widths.add(line.count("\t") + 1)
    return rows, tuple(sorted(widths))


def audit(root: Path) -> tuple[list[int], list[int]]:
    reference = root / "Eora26_2017_bp"
    if not reference.is_dir():
        raise ValueError("The parsed 2017 reference folder is missing")
    labels = {kind: digest(reference / f"labels_{kind}.txt") for kind in LABEL_KINDS}
    reference_va = matrix_shape(reference / "Eora26_2017_bp_VA.txt")
    years, shared_index = [], []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        match = re.fullmatch(r"Eora26_(\d{4})_bp", folder.name)
        if not match:
            continue
        year = int(match.group(1))
        for kind in DATA_KINDS:
            path = folder / f"Eora26_{year}_bp_{kind}.txt"
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Incomplete {year} source matrix: {kind}")
        for kind, expected in labels.items():
            path = folder / f"labels_{kind}.txt"
            if not path.is_file():
                if year == 2016 and kind == "VA" and matrix_shape(folder / f"Eora26_{year}_bp_VA.txt") == reference_va:
                    shared_index.append(year)
                    continue
                raise ValueError(f"Missing {year} index file: labels_{kind}.txt")
            if digest(path) != expected:
                raise ValueError(f"{year} labels_{kind}.txt differs from the parsed 2017 inventory")
        years.append(year)
    if 2017 not in years:
        raise ValueError("No 2017 reference year found")
    return years, shared_index


def year_periods(years: list[int]) -> str:
    periods = []
    start = last = years[0]
    for year in [*years[1:], None]:
        if year is not None and year == last + 1:
            last = year
            continue
        periods.append(str(start) if start == last else f"{start}–{last}")
        start = last = year
    return ", ".join(periods)


def write_json(path: Path, data: dict) -> None:
    compact = path.name == "country-scope.json"
    text = json.dumps(data, ensure_ascii=False, **({"separators": (",", ":")} if compact else {"indent": 2})) + "\n"
    path.write_text(text, encoding="utf-8")


def update(data: Path, years: list[int], shared_index: list[int]) -> None:
    if not years or years != sorted(set(years)):
        raise ValueError("Years must be distinct and sorted")
    year_text = year_periods(years)
    note = (f"Eora1 26 · basic prices. Locally verified native sets for {year_text}: "
            "189 retained regions and 26 sectors. The 2017 inventory was parsed with MARIO; "
            "other locally held years were checked for source files and matching labels, not fully parsed. "
            "The publisher also has 2004, but that year was not downloaded locally and its sets were not checked. "
            "The 2016 local copy lacks labels_VA.txt; its VA matrix has the 2017 shape, "
            "so parsing that year requires indeces= pointing to a complete common label folder. "
            "Scope metadata only; numerical indicators are not published.")
    paths = [data / "database_profiles.json", data / "database_profiles" / f"{PROFILE_ID}.json",
             data / "economy" / "country-scope.json", data / "economy" / "download-metadata.json"]
    catalog, detail, scope, downloads = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    summary = next(p for p in catalog["profiles"] if p["id"] == PROFILE_ID)
    scope_row = next(p for p in scope["profiles"] if p["id"] == PROFILE_ID)
    download = downloads["profiles"][PROFILE_ID]
    for profile in (summary, detail):
        if profile["year"] != 2017 or profile["counts"]["Region"] != 189 or profile["counts"]["Sector"] != 26:
            raise ValueError("The source inventory is not the reviewed 2017 Eora1 26 profile")
        if profile.get("numeric_publication") is not False or profile.get("workbook_allowed") is not False:
            raise ValueError("EORA must remain scope-only")
        profile["label"] = "Eora1 26 · basic prices"
        profile["years"] = years
        profile["scope_note"] = note
        profile["local_index_overrides"] = {str(year): 2017 for year in shared_index}
        profile["year_evidence"] = {
            "parsed": [2017], "source_structure_checked": [year for year in years if year != 2017],
            "note": "2017 parsed with MARIO; other locally held years checked for complete source files and matching labels. The source offers 2004, which has not been downloaded or checked here. The 2016 local copy needs the shared 2017 label folder (indeces=).",
            "hover_status": "2017 MARIO parse · other local years: source structure checked · 2004 not locally reviewed",
        }
    if scope_row.get("reading_ids") or scope_row.get("numeric_publication") is not False:
        raise ValueError("EORA scope unexpectedly references public numerical readings")
    scope_row["years"] = years
    scope_row["scope_note"] = note
    download["label"] = summary["label"]
    download["years"] = years
    if download["workbook_allowed"] is not False:
        raise ValueError("EORA full set inventory must not be downloadable")
    for path, obj in zip(paths, (catalog, detail, scope, downloads)):
        write_json(path, obj)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Local parent folder containing Eora26_YEAR_bp directories")
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[2] / "source/_static/data")
    args = parser.parse_args()
    years, shared_index = audit(args.root)
    update(args.data, years, shared_index)
    print(f"Eora1 26 scope: {len(years)} years ({year_periods(years)}); shared label index needed for {shared_index}. No numeric data published.")


if __name__ == "__main__":
    main()
