"""Read the structural manifest accompanying native accounting blocks."""

import json
from pathlib import Path

import pandas as pd
import numpy as np

from mario.log_exc.exceptions import WrongInput


MANIFEST = "accounting.json"
EXCEL_MANIFEST = "accounting"


def read_manifest(path, *, excel=False):
    """Read configuration and axis declarations from an exported bundle."""
    if excel:
        with pd.ExcelFile(path) as book:
            if EXCEL_MANIFEST not in book.sheet_names:
                return {}
            payload = book.parse(EXCEL_MANIFEST, header=None).iloc[0, 0]
        return json.loads(payload)
    target = Path(path) / MANIFEST
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}


def manifest_layouts(manifest, layouts):
    """Use exported factor layouts unless the caller supplied declarations."""
    return layouts if layouts is not None else manifest.get("matrix_layouts", {})


def _flat_axis(data, declaration, side):
    names = declaration[side]
    if names == ["Import account"]:
        return pd.Index(["Total imports"] * len(data), name="Import account")
    columns = declaration[f"{side}_sets"]
    fields = []
    for name in columns:
        key = f"{name}_{'from' if side == 'index' else 'to'}"
        if key not in data:
            raise WrongInput(f"Import block is missing the declared {key} column.")
        fields.append(data[key].replace("", None).tolist())
    if "Level" in names:
        fields.insert(1, [columns[-1]] * len(data))
    if len(names) == 1:
        return pd.Index(fields[0], name=names[0])
    return pd.MultiIndex.from_arrays(fields, names=names)


def flat_import_frames(data, manifest):
    """Rebuild import frames with their declared descriptor axes."""
    frames = {}
    for name, declaration in manifest.get("imports", {}).items():
        subset = data.loc[data["Matrix"] == name].copy()
        if subset.empty:
            raise WrongInput(f"Accounting bundle is missing import block {name}.")
        rows = _flat_axis(subset, declaration, "index")
        columns = _flat_axis(subset, declaration, "columns")
        row_codes, row_axis = pd.factorize(rows, sort=False)
        col_codes, col_axis = pd.factorize(columns, sort=False)
        if pd.MultiIndex.from_arrays([row_codes, col_codes]).has_duplicates:
            raise WrongInput(f"Accounting bundle contains duplicate cells in {name}.")
        values = np.zeros((len(row_axis), len(col_axis)))
        values[row_codes, col_codes] = pd.to_numeric(subset["Value"], errors="raise")
        frames[name] = pd.DataFrame(values, index=row_axis, columns=col_axis)
    return frames


def read_import_frames(path, manifest, *, mode, suffix=None, sep=",", excel=False):
    """Read matrix-format imports using their exported axis depths."""
    declarations = manifest.get(mode, {}).get("imports", {}) if excel else manifest.get("imports", {})
    frames = {}
    for name, declaration in declarations.items():
        if excel:
            frame = pd.read_excel(
                path, sheet_name=f"{mode}_{name}",
                index_col=list(range(len(declaration["index"]))),
                header=list(range(len(declaration["columns"]))),
            )
        elif suffix == "parquet":
            frame = pd.read_parquet(Path(path) / f"{name}.parquet")
        else:
            candidates = list(Path(path).glob(f"{name}.{suffix or '*'}"))
            if len(candidates) != 1:
                raise WrongInput(f"Accounting bundle requires one file for import block {name}.")
            frame = pd.read_csv(
                candidates[0], sep=sep,
                index_col=list(range(len(declaration["index"]))),
                header=list(range(len(declaration["columns"]))),
            )
        frame.index.names = declaration["index"]
        frame.columns.names = declaration["columns"]
        frames[name] = frame
    return frames


def restore_configuration(state, manifest):
    """Attach accounting choices before a public database can calculate."""
    if manifest:
        state.metadata.extra["model_configuration"] = manifest["configuration"]
        state.metadata.extra["sector_type"] = manifest.get("sector_type")
        state.metadata.tech_assumption = manifest.get("tech_assumption", state.metadata.tech_assumption)


def restore_public_axes(matrices, manifest):
    """Restore public axis conventions and align imports with economic blocks."""
    frames = matrices["baseline"]
    if manifest.get("legacy_public_axes"):
        for name, frame in frames.items():
            for side in ("index", "columns"):
                if side == "index" and name.startswith(("IMP", "imp")):
                    continue
                axis = getattr(frame, side)
                if axis.nlevels == 2 and axis.names[0] == "Region" and axis.names[1] in {
                    "Sector", "Activity", "Commodity", "Consumption category",
                }:
                    restored = pd.MultiIndex.from_arrays(
                        [axis.get_level_values(0), [axis.names[1]] * len(axis), axis.get_level_values(1)],
                        names=["Region", "Level", "Item"],
                    )
                    setattr(frame, side, restored)

    for names, references in (
        (("IMP", "imp"), ("V", "v")),
        (("IMP_a", "imp_a"), ("Va", "va")),
        (("IMP_c", "imp_c"), ("Vc", "vc")),
        (("IMP_Y",), ("VY",)),
    ):
        for name in names:
            if name not in frames:
                continue
            reference = next((key for key in references if key in frames), None)
            if reference is None:
                raise WrongInput(f"Import block {name} has no corresponding economic block.")
            frame = frames[name]
            columns = frames[reference].columns
            if (
                not frame.columns.is_unique
                or len(frame.columns) != len(columns)
                or (frame.columns.get_indexer(columns) < 0).any()
            ):
                raise WrongInput(f"Import block {name} columns do not match {reference} columns.")
            frames[name] = frame.reindex(columns=columns)
