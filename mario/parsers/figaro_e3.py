"""Local JRC FIGARO-E3 CSV bundles, with explicit format/inventory choices."""
from __future__ import annotations

from dataclasses import dataclass, field
import csv
from functools import lru_cache
import hashlib
import logging
from numbers import Real
from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX as MI
from mario.utils import rename_index

logger = logging.getLogger(__name__)
SOURCE = "https://data.jrc.ec.europa.eu/collection/id-00403"
GHG_CODES = ("CO2", "CH4", "N2O", "F-gases")
ENERGY_CODES = ("PES", "NEU", "FEU", "EOU", "LOSS", "NENE")
EMPLOYMENT_CODES = ("EMPLS_M", "EMPLS_F", "EMPMS_M", "EMPMS_F", "EMPHS_M", "EMPHS_F")
FINAL_CODES = ("P3_S13", "P3_S14", "P3_S15", "P51G", "P5M")
MONETARY_UNIT = "million EUR"


@dataclass
class FigaroE3Layout:
    root: Path
    year: int
    table: str
    mode: str
    emissions: str
    files: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    labels: dict = field(default_factory=dict)
    diagonal_correction: dict = field(default_factory=dict)
    reference_outputs: dict = field(default_factory=dict)

    @property
    def dataset_name(self):
        return f"FIGARO E3 {self.year} {self.table} {self.mode}".strip()

    @property
    def source(self):
        basis = "CO2eq AR5 GWP100" if self.emissions == "co2eq" else "gas mass" if self.emissions == "mass" else "no GHG inventory"
        return f"FIGARO E3 {basis} ({SOURCE})"


def _correct_irish_paper_loop(matrices, layout, epsilon, satellite_units):
    """Correct only the verified, isolated 2015 IE paper-incineration loop.

    Retain the original output reference: recomputing it from the reduced
    self-flow would otherwise restore a unit own-input coefficient. The
    resulting small balance gap is reported, not assigned to invented final
    demand or value added. This is a FIGARO-E3 source treatment, not a generic
    singular-system policy.
    """
    report = {"epsilon": epsilon, "applied": False, "status": "disabled" if epsilon is None else "not_needed"}
    layout.diagonal_correction = report
    if epsilon is None:
        return
    if layout.table == "IOT":
        code = "E37T39_D" if layout.mode == "industry" else "CPA_E37T39_D"
        node = ("IE", MI["s"], code)
        flow, demand, accounts = matrices["Z"], matrices["Y"], matrices["E"]
        if node not in flow.index:
            return
        row, column = node, node
        output = flow.sum(axis=1) + demand.sum(axis=1)
        originals = {"X": output.to_frame("production")}
        source_flow = float(flow.at[row, column])
        isolated = (
            np.count_nonzero(flow.loc[row].to_numpy()) == 1
            and np.count_nonzero(flow.loc[:, column].to_numpy()) == 1
            and not np.any(demand.loc[row].to_numpy())
            and source_flow > 0 and float(output.loc[node]) == source_flow
        )
        block = "Z"
    else:
        activity = ("IE", MI["a"], "E37T39_D")
        commodity = ("IE", MI["c"], "CPA_E37T39_D")
        flow, supply, demand, accounts = matrices["U"], matrices["S"], matrices["Yc"], matrices["Ea"]
        if activity not in supply.index or commodity not in flow.index:
            return
        row, column, node = commodity, activity, activity
        output = flow.sum(axis=1) + demand.sum(axis=1)
        originals = {"Xc": output.to_frame("production")}
        source_flow = float(flow.at[row, column])
        isolated = (
            np.count_nonzero(flow.loc[row].to_numpy()) == 1
            and np.count_nonzero(flow.loc[:, column].to_numpy()) == 1
            and np.count_nonzero(supply.loc[activity].to_numpy()) == 1
            and np.count_nonzero(supply.loc[:, commodity].to_numpy()) == 1
            and not np.any(demand.loc[commodity].to_numpy())
            and not np.any(matrices["Ya"].loc[activity].to_numpy())
            and source_flow > 0
            and float(supply.at[activity, commodity]) == source_flow
            and float(output.loc[commodity]) == source_flow
        )
        block = "U"
    if not isolated:
        report["status"] = "source_pattern_not_matched"
        return
    corrected = source_flow * (1. - epsilon)
    if not 0 < corrected < source_flow:
        raise WrongInput("diagonal_correction cannot change this source flow at float64 precision; choose a larger representable epsilon.")
    flow.at[row, column] = corrected
    rename_index(originals)
    layout.reference_outputs = originals
    gap = source_flow - corrected
    report.update({
        "applied": True, "status": "corrected", "block": block,
        "row": list(row), "column": list(column),
        "source_flow_million_eur": source_flow,
        "corrected_flow_million_eur": corrected,
        "source_own_input_coefficient": 1., "corrected_own_input_coefficient": 1. - epsilon,
        "balance_gap_million_eur": gap,
        "reference_output_blocks": list(originals),
        "reference_output_million_eur": source_flow,
        "unchanged_production_accounts": [
            {"account": str(label), "amount": float(amount), "unit": unit}
            for (label, amount), unit in zip(accounts.loc[:, node].items(), satellite_units)
        ],
        "interpretation": "Parser-specific numerical correction. Original output references and absolute production accounts are retained; the isolated accounts are not allocated to native final demand. The reported balance gap is not inserted into final demand or value added.",
    })
    note = (f"FIGARO E3: corrected the isolated IE paper-incineration loop in {block} "
            f"with epsilon={epsilon:g}; own-input coefficient 1 -> {1.-epsilon:g}. "
            "Original output reference and absolute satellite accounts retained; "
            f"balance gap {gap:g} million EUR. See the figaro_e3 diagonal_correction report.")
    layout.notes.append(note)
    warnings.warn(note, UserWarning, stacklevel=3)


@lru_cache(maxsize=128)
def _digest(path: str, size: int, mtime_ns: int):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _one_file(root: Path, name: str, *, required=True):
    """Collapse byte-identical browser copies; never guess between revisions."""
    stem, suffix = Path(name).stem, Path(name).suffix
    pattern = re.compile(re.escape(stem) + r"(?: copy|[- ]\d+| \(\d+\))?" + re.escape(suffix) + "$", re.I)
    candidates = sorted(p for p in root.rglob("*" + suffix)
                        if not p.name.startswith("._") and pattern.fullmatch(p.name))
    if not candidates:
        if required:
            raise WrongInput(f"Missing FIGARO E3 file {name!r} under {root}.")
        return None
    if len(candidates) > 1:
        hashes = {_digest(str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns) for p in candidates}
        if len(hashes) != 1:
            raise WrongInput(f"Conflicting FIGARO E3 versions of {name!r}: {[str(p) for p in candidates]}. Select a directory containing one release.")
    return next((p for p in candidates if p.name == name), candidates[0])


def _select(root, stem, input_format):
    kinds = ("matrix", "flatfile") if input_format == "auto" else (input_format,)
    for kind in kinds:
        path = _one_file(root, f"{kind}_{stem}.csv", required=False)
        if path is not None:
            return path, kind
    raise WrongInput(f"No {input_format} FIGARO E3 input for {stem!r} under {root}.")


def _metadata(root):
    paths = sorted(p for p in root.rglob("*FIGARO*Classifications*.xlsx") if not p.name.startswith("._"))
    if not paths:
        raise WrongInput("FIGARO E3 requires its published FIGARO-env_Classifications.xlsx workbook.")
    if len(paths) > 1 and len({_digest(str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns) for p in paths}) > 1:
        raise WrongInput("More than one FIGARO E3 classification revision was found. Select one release directory.")
    sheets = {"regions": "Country resolution", "activities": "Industry resolution",
              "products": "Product resolution", "additional": "Additional rows and colums"}
    with pd.ExcelFile(paths[0]) as book:
        result = {}
        for key, sheet in sheets.items():
            frame = pd.read_excel(book, sheet_name=sheet, dtype=str).iloc[:, :2].dropna(subset=["code"])
            if frame["code"].str.strip().duplicated().any():
                raise WrongFormat(f"Duplicate FIGARO E3 classification codes in {sheet}.")
            result[key] = dict(zip(frame.iloc[:, 0].str.strip(), frame.iloc[:, 1].fillna("").str.strip()))
    result["regions"].pop("W2", None)
    result["path"] = str(paths[0])
    return result


def _axis(regions, items, level):
    return pd.MultiIndex.from_tuples([(r, MI[level], item) for r in regions for item in items])


def _raw_keys(regions, items):
    return [f"{r}_{item}" for r in regions for item in items]


def _economic(path, kind, rows, columns, *, chunksize):
    """Read only wanted axes, bounding flat-file memory independently of size."""
    row_lookup, col_lookup = {v: i for i, v in enumerate(rows)}, {v: i for i, v in enumerate(columns)}
    values = np.zeros((len(rows), len(columns)), dtype=np.float64)
    seen = np.zeros(values.shape, dtype=bool)
    log_time(logger, f"Parser: reading FIGARO E3 {path.name} ({kind}).", "info")
    if kind == "matrix":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream))
        if len(header) != len(set(header)):
            raise WrongFormat(f"Duplicate columns in {path.name}.")
        missing, extra = set(columns) - set(header[1:]), set(header[1:]) - set(columns)
        if missing or extra:
            raise WrongFormat(f"Missing/unexpected FIGARO E3 columns in {path.name}: missing={sorted(missing)[:8]}, extra={sorted(extra)[:8]}.")
        for block in pd.read_csv(path, index_col=0, usecols=[header[0], *columns], chunksize=min(chunksize, 256)):
            positions = block.index.map(row_lookup)
            keep = positions.notna()
            if not keep.all():
                raise WrongFormat(f"Unexpected FIGARO E3 rows in {path.name}: {block.index[~keep].tolist()[:8]}.")
            selected = block.loc[keep, columns]
            idx = positions[keep].to_numpy(dtype=int)
            if len(set(idx)) != len(idx) or seen[idx].any():
                raise WrongFormat(f"Duplicate FIGARO E3 rows in {path.name}.")
            values[idx] = selected.to_numpy(dtype=float)
            seen[idx] = True
        if not seen.all():
            raise WrongFormat(f"Missing FIGARO E3 rows in {path.name}.")
    else:
        header = pd.read_csv(path, nrows=0).columns.tolist()
        if len(header) < 3 or "obsValue" not in header:
            raise WrongFormat(f"Unexpected FIGARO E3 flat-file header in {path.name}.")
        keys = header[:2]
        read_columns = [*keys, "obsValue", *(["unit"] if "unit" in header else [])]
        for block in pd.read_csv(path, usecols=read_columns, chunksize=chunksize):
            if "unit" in block and not set(block["unit"].str.strip().str.casefold()) <= {"million euro", "million eur", "mio_eur"}:
                raise WrongFormat(f"Unexpected FIGARO E3 monetary units in {path.name}.")
            ri = block[keys[0]].map(row_lookup)
            ci = block[keys[1]].map(col_lookup)
            keep = ri.notna() & ci.notna()
            if not keep.all():
                raise WrongFormat(f"Unexpected FIGARO E3 flat-file axis labels in {path.name}.")
            row = ri[keep].to_numpy(dtype=int)
            col = ci[keep].to_numpy(dtype=int)
            linear = row * len(columns) + col
            if len(np.unique(linear)) != len(linear) or seen[row, col].any():
                raise WrongFormat(f"Duplicate FIGARO E3 observations in {path.name}.")
            values[row, col] = block.loc[keep, "obsValue"].to_numpy(dtype=float)
            seen[row, col] = True
        # Published supply lists omit structural zeros; completeness is checked
        # against the classification axes for all other economic files.
        if "-supply_" not in path.name and not seen.all():
            raise WrongFormat(f"Missing FIGARO E3 observations in {path.name}; absent values are not assumed zero.")
        if "-supply_" in path.name:
            # The source supplies complete domestic product/industry grids;
            # unlisted cross-country supply cells are structural zeros.
            row_regions = np.array([key.split("_", 1)[0] for key in rows])
            col_regions = np.array([key.split("_", 1)[0] for key in columns])
            for region in set(row_regions):
                if not seen[np.ix_(row_regions == region, col_regions == region)].all():
                    raise WrongFormat(f"Missing FIGARO E3 domestic supply observations in {path.name} for {region}.")
    if not np.isfinite(values).all():
        raise WrongFormat(f"Non-finite FIGARO E3 values in {path.name}.")
    return values


def _extension_matrix(path, *, transpose=False):
    frame = pd.read_csv(path, index_col=0)
    if transpose:
        frame = frame.T
    frame.index = frame.index.astype(str).str.strip()
    frame.columns = frame.columns.astype(str).str.strip()
    if not frame.index.is_unique or not frame.columns.is_unique:
        raise WrongFormat(f"Duplicate FIGARO E3 extension labels in {path.name}.")
    return frame


def _extension_flat(path, *, year, method=None):
    frame = pd.read_csv(path)
    for col in frame.columns:
        if pd.api.types.is_string_dtype(frame[col].dtype):
            frame[col] = frame[col].str.strip()
    if set(frame["timePeriod"]) != {year}:
        raise WrongFormat(f"Unexpected observation year in {path.name}.")
    if method:
        frame = frame.loc[frame["codeEstimMethod"] == method]
    units = frame["unit"].astype(str).str.replace(" ", "").str.casefold()
    if "employment" in path.name:
        valid = units.eq("k")
    elif "_ENE_" in path.name:
        valid = units.eq("tj")
    else:
        co2eq = "_CO2e_" in path.name
        characterized = pd.Series(co2eq, index=frame.index) | frame["codeIndicator"].eq("F-gases")
        valid = (characterized & units.isin(["ktco2e", "ggco2e", "ktco2-eq", "ggco2-eq"])) | (~characterized & units.isin(["kt", "gg"]))
    if not valid.all():
        raise WrongFormat(f"Unexpected FIGARO E3 extension units in {path.name}.")
    if "codeEproduct" in frame and set(frame["codeEproduct"]) != {"Total"}:
        raise WrongFormat("FIGARO E3 energy product detail must be selected explicitly; expected published Total rows.")
    frame["axis"] = frame["refArea"] + "_" + frame["colPi"]
    if frame.duplicated(["codeIndicator", "axis"]).any():
        raise WrongFormat(f"Duplicate FIGARO E3 extension observations in {path.name}.")
    return frame.pivot(index="codeIndicator", columns="axis", values="obsValue")


def _extensions(root, metadata, *, input_format, year, emissions, employment, selected):
    akeys = _raw_keys(metadata["regions"], metadata["activities"])
    fkeys = _raw_keys(metadata["regions"], FINAL_CODES)
    rows, row_units, frames, used = [], [], [], {}
    def add(frame, codes, labels, units, path, *, final=True):
        wanted = akeys + (fkeys if final else [])
        if set(codes) != set(frame.index) or set(wanted) != set(frame.columns):
            raise WrongFormat(f"FIGARO E3 extension axes do not match classifications: {path.name}.")
        block = frame.loc[list(codes), wanted].astype(float)
        if not np.isfinite(block.to_numpy()).all():
            raise WrongFormat(f"Incomplete/non-finite FIGARO E3 extension in {path.name}.")
        if not final:
            block = block.reindex(columns=akeys + fkeys, fill_value=0.)
        block.index = labels
        rows.extend(labels)
        row_units.extend(units)
        frames.append(block)
        used[path.name] = str(path)
    if "emissions" in selected:
        stem = f"FIGARO-e_AEM_Gg{'_CO2e' if emissions == 'co2eq' else ''}_{year}"
        path, kind = _select(root, stem, input_format)
        frame = _extension_matrix(path) if kind == "matrix" else _extension_flat(path, year=year)
        labels = [f"GHG | {gas} | {'AR5 GWP100 CO2eq' if emissions == 'co2eq' else 'native'}" for gas in GHG_CODES]
        units = ["kt CO2-eq"] * 4 if emissions == "co2eq" else ["kt", "kt", "kt", "kt CO2-eq"]
        add(frame, GHG_CODES, labels, units, path)
    if "energy" in selected:
        flat = _one_file(root, f"flatfile_FIGARO-e_ENE_TJ_{year}.csv", required=False)
        # A single list contains all six indicators, including PES and NENE.
        use_flat = input_format == "flatfile" or (input_format == "auto" and flat is not None)
        if use_flat:
            if flat is None:
                raise WrongInput("Missing FIGARO E3 flat energy account.")
            frame = _extension_flat(flat, year=year)
            add(frame, ENERGY_CODES, [f"Energy | {c}" for c in ENERGY_CODES], ["TJ"]*6, flat)
        else:
            for code in ENERGY_CODES:
                path = _one_file(root, f"matrix_FIGARO-e_ENE_{code}_TJ_{year}.csv")
                frame = _extension_matrix(path)
                add(frame, ["Total"], [f"Energy | {code}"], ["TJ"], path)
    if "employment" in selected:
        methods = ("EDU", "OCC") if employment == "both" else (employment,)
        for method in methods:
            matrix = _one_file(root, f"matrix_FIGARO-e_employment_{method}_k_{year}.csv", required=False)
            if input_format != "flatfile" and matrix is not None:
                path, frame = matrix, _extension_matrix(matrix, transpose=True)
            else:
                if input_format == "matrix":
                    raise WrongInput(f"Missing matrix FIGARO E3 employment {method}.")
                path = _one_file(root, f"flatfile_FIGARO-e_employment_{year}.csv")
                frame = _extension_flat(path, year=year, method=method)
            add(frame, EMPLOYMENT_CODES, [f"Employment | {method} | {c}" for c in EMPLOYMENT_CODES], ["thousand persons"]*6, path, final=False)
    if not frames:
        return pd.DataFrame(0., index=["-"], columns=akeys+fkeys), ["None"], used
    return pd.concat(frames), row_units, used


def parse_figaro_e3_data(path, *, table="SUT", year=2015, iot_mode="industry",
                         input_format="auto", extensions="all", emissions="co2eq",
                         employment="EDU", extension_allocation=None, chunksize=250_000,
                         diagonal_correction=1e-3):
    """Return native flow blocks, sets, units and source provenance."""
    root = Path(path)
    if not root.is_dir():
        raise WrongInput("FIGARO E3 path must be a directory containing extracted CSVs and classifications.")
    if year != 2015:
        raise WrongInput("This FIGARO E3 release covers 2015 only.")
    input_format = {"flat": "flatfile"}.get(input_format, input_format)
    if input_format not in {"auto", "matrix", "flatfile"}:
        raise WrongInput("input_format must be auto, matrix or flatfile.")
    if table not in {"SUT", "IOT"} or iot_mode not in {"industry", "product"}:
        raise WrongInput("Choose table=SUT/IOT and iot_mode=industry/product.")
    if emissions not in {"co2eq", "mass"} or employment not in {"EDU", "OCC", "both"}:
        raise WrongInput("Choose emissions=co2eq/mass and employment=EDU/OCC/both.")
    if not isinstance(chunksize, int) or chunksize <= 0:
        raise WrongInput("chunksize must be a positive integer.")
    if diagonal_correction is not None:
        if (isinstance(diagonal_correction, (bool, np.bool_))
                or not isinstance(diagonal_correction, Real)
                or not 0 < diagonal_correction < 1
                or not np.isfinite(float(diagonal_correction))
                or 1. - float(diagonal_correction) == 1.):
            raise WrongInput("diagonal_correction must be None or a finite epsilon strictly between 0 and 1, representable at float64 precision.")
        diagonal_correction = float(diagonal_correction)
    if extension_allocation not in {None, "industry_technology"}:
        raise WrongInput("extension_allocation must be None or industry_technology.")
    selected = [] if extensions is False or extensions is None else (["emissions", "energy", "employment"] if extensions is True or extensions == "all" else ([extensions] if isinstance(extensions,str) else list(extensions)))
    if set(selected) - {"emissions", "energy", "employment"}:
        raise WrongInput("Unknown FIGARO E3 extension group; use emissions, energy, employment or all.")
    if table == "IOT" and iot_mode == "product" and selected and extension_allocation is None:
        raise WrongInput("FIGARO E3 extensions are industry-based. Product IOTs require extension_allocation='industry_technology' (and supply data), or extensions=False.")
    metadata = _metadata(root)
    regions, activities, products = [list(metadata[key]) for key in ["regions","activities","products"]]
    factors = [key for key in metadata["additional"] if key not in FINAL_CODES]
    a, c, n = _axis(regions, activities, "a"), _axis(regions, products, "c"), _axis(regions, FINAL_CODES, "n")
    ar, cr, nr = _raw_keys(regions, activities), _raw_keys(regions, products), _raw_keys(regions, FINAL_CODES)
    fr = ["W2_" + code for code in factors]
    layout = FigaroE3Layout(root, year, table, iot_mode if table == "IOT" else "", emissions, labels=metadata)
    if "emissions" not in selected:
        layout.emissions = "none"
    layout.files["classifications"] = metadata.pop("path")
    ext, ext_units, ext_files = _extensions(root, metadata, input_format=input_format, year=year,
                                          emissions=emissions, employment=employment, selected=selected)
    layout.files.update(ext_files)
    k = ext.index
    Ea = pd.DataFrame(ext.loc[:, ar].to_numpy(), index=k, columns=a)
    EY = pd.DataFrame(ext.loc[:, nr].to_numpy(), index=k, columns=n)
    zero = lambda index, columns: pd.DataFrame(0., index=index, columns=columns)
    def load(role, stem, rows, cols):
        file, kind = _select(root, stem+f"_{year}", input_format)
        layout.files[role] = str(file)
        return _economic(file, kind, rows, cols, chunksize=chunksize)
    supply = None
    if table == "SUT" or (iot_mode == "product" and selected):
        supply = load("supply", "FIGARO-e-ic-supply_millionEUR", cr, ar)
    if table == "SUT":
        use = load("use", "FIGARO-e-ic-use_millionEUR", cr+fr, ar+nr)
        U = pd.DataFrame(use[:len(cr), :len(ar)], index=c, columns=a)
        S = pd.DataFrame(supply.T, index=a, columns=c)
        Yc = pd.DataFrame(use[:len(cr), len(ar):], index=c, columns=n)
        Va = pd.DataFrame(use[len(cr):, :len(ar)], index=factors, columns=a)
        VY = pd.DataFrame(use[len(cr):, len(ar):], index=factors, columns=n)
        matrices = {"S":S,"U":U,"Ya":zero(a,n),"Yc":Yc,"Va":Va,"Vc":zero(factors,c),
                    "Ea":Ea,"Ec":zero(k,c),"EY":EY,"VY":VY}
        indices = {"a":{"main":activities},"c":{"main":products},"s":{"main":activities+products}}
        economic_units = {MI["a"]:pd.DataFrame({"unit":MONETARY_UNIT},index=activities),
                          MI["c"]:pd.DataFrame({"unit":MONETARY_UNIT},index=products)}
    else:
        codes, raw = (activities, ar) if iot_mode == "industry" else (products,cr)
        axis = _axis(regions,codes,"s")
        stem = "FIGARO-e-ic-io-D_ind-by-ind_millionEUR" if iot_mode == "industry" else "FIGARO-e-ic-io-B_prod-by-prod_millionEUR"
        data = load("iot", stem, raw+fr, raw+nr)
        E = Ea.to_numpy()
        if iot_mode == "product" and selected:
            output = supply.sum(axis=0)
            missing = (output == 0) & np.any(E != 0, axis=0)
            if missing.any():
                examples = [ar[i] for i in np.flatnonzero(missing)[:5]]
                raise WrongInput(f"Cannot allocate nonzero FIGARO E3 extensions from {int(missing.sum())} zero-output industries to products (examples: {examples}). Parse SUT/industry IOT or omit extensions.")
            coefficients = np.divide(E, output, out=np.zeros_like(E), where=output!=0)
            E = coefficients @ supply.T
            layout.notes.append("Industry-based extensions allocated to products with the industry technology assumption using the complete supply table; direct final-demand extensions retained unchanged.")
        matrices = {"Z":pd.DataFrame(data[:len(raw),:len(raw)],index=axis,columns=axis),
                    "Y":pd.DataFrame(data[:len(raw),len(raw):],index=axis,columns=n),
                    "V":pd.DataFrame(data[len(raw):,:len(raw)],index=factors,columns=axis),
                    "VY":pd.DataFrame(data[len(raw):,len(raw):],index=factors,columns=n),
                    "E":pd.DataFrame(E if iot_mode == "industry" or selected else np.zeros((len(k),len(raw))),index=k,columns=axis),"EY":EY}
        indices = {"s":{"main":codes}}
        economic_units = {MI["s"]:pd.DataFrame({"unit":MONETARY_UNIT},index=codes)}
    indices.update({"r":{"main":regions},"n":{"main":list(FINAL_CODES)},"f":{"main":factors},"k":{"main":list(k)}})
    units = {**economic_units, MI["f"]:pd.DataFrame({"unit":MONETARY_UNIT},index=factors),
             MI["k"]:pd.DataFrame({"unit":ext_units},index=k)}
    layout.notes.extend(["FIGARO E3 is a separate detailed classification; standard FIGARO concordances are not assumed.",
                         "Energy indicators overlap; do not sum PES, NEU and their components. EDU and OCC employment are alternative estimates."])
    _correct_irish_paper_loop(matrices, layout, diagonal_correction, ext_units)
    rename_index(matrices)
    return {"baseline":matrices}, indices, units, layout
