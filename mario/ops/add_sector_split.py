"""Split-specific helpers for the add-sectors workflow."""

from __future__ import annotations

import copy
import warnings
from pathlib import Path

import pandas as pd
import pint

from mario.compute.primitives import calc_E, calc_V, calc_X_from_w, calc_Z, calc_w
from mario.log_exc.exceptions import LackOfInput, NotImplementable, WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import IOT, _ENUM, _MASTER_INDEX as MI
from mario.ops.add_sector_specs import (
    ADD_SECTOR_SPLIT_EXCLUSION_COLUMNS,
    ADD_SECTOR_SPLIT_EXCLUSION_SHEET,
    ADD_SECTOR_SPLIT_OUTPUT_COLUMNS,
    ADD_SECTOR_SPLIT_OUTPUT_SHEET,
    ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS,
    ADD_SECTOR_SPLIT_TOLERANCE_DEFAULTS,
    ADD_SECTOR_SPLIT_TOLERANCE_SHEET,
    ADD_SECTOR_SPLIT_TRADE_COLUMNS,
    ADD_SECTOR_SPLIT_TRADE_SHEET,
)


sn = slice(None)


def _classic_split_row_layouts(instance) -> None:
    """Fail fast when the current split CVXLab model cannot represent row layouts.

    The packaged ``Split_sectors`` CVXLab model only knows the historical MARIO
    split input structure, where:

    - ``V`` rows are just ``Factor of production``
    - ``E`` rows are just ``Satellite account``

    New parser-side ``matrix_layouts`` can expose richer row axes for those
    matrices, but that requires a different optimization model. Until such a
    model exists, ``split=True`` should reject those databases explicitly.
    """

    incompatible = {}
    for matrix_name, expected in ((_ENUM["V"], (MI["f"],)), (_ENUM["E"], (MI["k"],))):
        spec = instance.get_block_spec(matrix_name)
        row_axes = tuple(axis.id for axis in spec.row_axes)
        if row_axes != expected:
            incompatible[matrix_name] = row_axes

    if incompatible:
        details = ", ".join(f"{name}: {axes}" for name, axes in incompatible.items())
        raise NotImplementable(
            "split=True currently supports only classic CVXLab row layouts for E and V. "
            f"Unsupported row layouts detected: {details}. Use the standard layout or a different split model."
        )


def validate_split_parameters(
    instance,
    *,
    cvxlab_path,
    input_data_files_type: str,
    only_input_data_gen: bool,
) -> None:
    """Validate user-facing split parameters before running heavy computations."""

    if instance.table_type != IOT:
        raise NotImplementable("Splitting sectors is currently supported only for IOT databases.")

    _classic_split_row_layouts(instance)

    if not getattr(instance, "to_split_sectors", []):
        raise WrongInput(
            "No sectors are marked as 'Split' in the add-sectors workbook. "
            "Set 'Add or Split' to 'Split' for at least one new sector before using split=True."
        )

    if not cvxlab_path:
        raise WrongInput(
            "cvxlab_path is required when split=True so MARIO can generate the CVXLab model directory."
        )

    if input_data_files_type not in {"xlsx", "csv"}:
        raise WrongInput("input_data_files_type should be either 'xlsx' or 'csv'.")

    if not Path(cvxlab_path).exists():
        raise FileNotFoundError(
            f"Directory where to create the CVXLab model '{cvxlab_path}' does not exist."
        )


def prepare_split_support(instance) -> dict[str, pd.DataFrame]:
    """Normalize and validate split-specific workbook data."""

    split_info = getattr(instance, "split_info", None)
    if not split_info:
        raise LackOfInput(
            "Split-support sheets are not loaded. Read the add-sectors workbook before using split=True."
        )

    normalized = {name: frame.copy() for name, frame in split_info.items()}
    split_sectors = set(getattr(instance, "to_split_sectors", []))
    db_regions = set(instance.get_index(MI["r"]))

    parent_map = _sector_to_parent_map(instance)
    missing_parents = [sector for sector in split_sectors if not parent_map.get(sector)]
    if missing_parents:
        raise WrongInput(
            "All split sectors need a parent sector in the add-sectors master sheet. "
            f"Missing parent for: {sorted(missing_parents)}"
        )

    output_sheet = normalized[ADD_SECTOR_SPLIT_OUTPUT_SHEET]
    trade_sheet = normalized[ADD_SECTOR_SPLIT_TRADE_SHEET]
    exclusion_sheet = normalized[ADD_SECTOR_SPLIT_EXCLUSION_SHEET]
    tolerance_sheet = normalized[ADD_SECTOR_SPLIT_TOLERANCE_SHEET]

    output_sector_col = ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["sector"]
    output_region_col = ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["region"]
    output_quantity_col = ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["quantity"]
    output_unit_col = ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["unit"]

    trade_sector_col = ADD_SECTOR_SPLIT_TRADE_COLUMNS["sector_from"]
    trade_region_from_col = ADD_SECTOR_SPLIT_TRADE_COLUMNS["region_from"]
    trade_region_to_col = ADD_SECTOR_SPLIT_TRADE_COLUMNS["region_to"]
    trade_quantity_col = ADD_SECTOR_SPLIT_TRADE_COLUMNS["quantity"]
    trade_unit_col = ADD_SECTOR_SPLIT_TRADE_COLUMNS["unit"]

    exclusion_sector_from_col = ADD_SECTOR_SPLIT_EXCLUSION_COLUMNS["sector_from"]
    exclusion_sector_to_col = ADD_SECTOR_SPLIT_EXCLUSION_COLUMNS["sector_to"]

    tol_name_col = ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["name"]
    tol_value_col = ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["value"]

    output_sheet = output_sheet.dropna(subset=[output_sector_col, output_region_col], how="any")
    trade_sheet = trade_sheet.dropna(
        subset=[trade_sector_col, trade_region_from_col, trade_region_to_col],
        how="any",
    )
    exclusion_sheet = exclusion_sheet.dropna(
        subset=[exclusion_sector_from_col, exclusion_sector_to_col],
        how="all",
    )

    if tolerance_sheet.empty:
        tolerance_sheet = pd.DataFrame(
            ADD_SECTOR_SPLIT_TOLERANCE_DEFAULTS,
            columns=[tol_name_col, tol_value_col],
        )

    output_sheet[output_sector_col] = output_sheet[output_sector_col].astype(str)
    output_sheet[output_region_col] = output_sheet[output_region_col].astype(str)
    trade_sheet[trade_sector_col] = trade_sheet[trade_sector_col].astype(str)
    trade_sheet[trade_region_from_col] = trade_sheet[trade_region_from_col].astype(str)
    trade_sheet[trade_region_to_col] = trade_sheet[trade_region_to_col].astype(str)

    unknown_output_sectors = sorted(set(output_sheet[output_sector_col]).difference(split_sectors))
    unknown_trade_sectors = sorted(set(trade_sheet[trade_sector_col]).difference(split_sectors))
    if unknown_output_sectors:
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_OUTPUT_SHEET}' contains sectors not marked for split: {unknown_output_sectors}"
        )
    if unknown_trade_sectors:
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_TRADE_SHEET}' contains sectors not marked for split: {unknown_trade_sectors}"
        )

    missing_outputs = sorted(split_sectors.difference(set(output_sheet[output_sector_col])))
    if missing_outputs:
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_OUTPUT_SHEET}' is missing total output rows for: {missing_outputs}"
        )

    unknown_output_regions = sorted(set(output_sheet[output_region_col]).difference(db_regions))
    unknown_trade_regions = sorted(
        set(trade_sheet[trade_region_from_col]).union(set(trade_sheet[trade_region_to_col])).difference(db_regions)
    )
    if unknown_output_regions:
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_OUTPUT_SHEET}' contains invalid regions: {unknown_output_regions}"
        )
    if unknown_trade_regions:
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_TRADE_SHEET}' contains invalid regions: {unknown_trade_regions}"
        )

    if (pd.to_numeric(output_sheet[output_quantity_col], errors="coerce") < 0).fillna(False).any():
        raise WrongInput("Split total outputs cannot contain negative quantities.")
    if (pd.to_numeric(trade_sheet[trade_quantity_col], errors="coerce") < 0).fillna(False).any():
        raise WrongInput("Split trades cannot contain negative quantities.")

    tolerance_names = set(
        tolerance_sheet[tol_name_col].dropna().astype(str).str.strip().tolist()
    )
    required_tol_names = {name for name, _ in ADD_SECTOR_SPLIT_TOLERANCE_DEFAULTS}
    if not required_tol_names.issubset(tolerance_names):
        raise WrongInput(
            f"Split sheet '{ADD_SECTOR_SPLIT_TOLERANCE_SHEET}' should define at least {sorted(required_tol_names)}."
        )

    normalized[ADD_SECTOR_SPLIT_OUTPUT_SHEET] = _convert_split_units(
        instance,
        output_sheet,
        sector_column=output_sector_col,
        quantity_column=output_quantity_col,
        unit_column=output_unit_col,
    )
    normalized[ADD_SECTOR_SPLIT_TRADE_SHEET] = _convert_split_units(
        instance,
        trade_sheet,
        sector_column=trade_sector_col,
        quantity_column=trade_quantity_col,
        unit_column=trade_unit_col,
    )
    normalized[ADD_SECTOR_SPLIT_EXCLUSION_SHEET] = exclusion_sheet
    normalized[ADD_SECTOR_SPLIT_TOLERANCE_SHEET] = tolerance_sheet.loc[:, [tol_name_col, tol_value_col]]

    instance.split_info = normalized
    return normalized


def build_split_flow_scenario(
    instance,
    *,
    base_scenario: str = "baseline",
    scenario_label: str = "baseline",
) -> str:
    """Create the deterministic pre-optimization split scenario."""

    split_scenario = f"split_{scenario_label}"
    sector_to_parent_map = _sector_to_parent_map(instance)
    split_output = instance.split_info[ADD_SECTOR_SPLIT_OUTPUT_SHEET]
    sector_col = ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["sector"]
    region_col = ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["region"]
    quantity_col = ADD_SECTOR_SPLIT_OUTPUT_COLUMNS["quantity"]

    old_X = (
        instance.get_block_as_pandas(_ENUM["X"], scenario=base_scenario)
        if instance.has_matrix(_ENUM["X"], scenario=base_scenario)
        else calc_X_from_w(
            calc_w(instance.get_block_as_pandas(_ENUM["z"], scenario=base_scenario)),
            instance.get_block_as_pandas(_ENUM["Y"], scenario=base_scenario),
        )
    )
    X = copy.deepcopy(old_X)

    for sector in getattr(instance, "to_split_sectors", []):
        parent_sector = sector_to_parent_map[sector]
        sector_rows = split_output.loc[split_output[sector_col] == sector, [region_col, quantity_col]]
        for _, row in sector_rows.iterrows():
            region = row[region_col]
            quantity = float(row[quantity_col])
            X.loc[(region, MI["s"], sector), "production"] = quantity

            parent_output = float(old_X.loc[(region, MI["s"], parent_sector), "production"])
            if quantity > parent_output:
                warnings.warn(
                    f"Total output for split sector {sector} in region {region} exceeds the output of "
                    f"its parent sector {parent_sector}. The child output is capped at the parent output."
                )
                X.loc[(region, MI["s"], sector), "production"] = parent_output

    z = instance.get_block_as_pandas(_ENUM["z"], scenario=base_scenario)
    e = instance.get_block_as_pandas(_ENUM["e"], scenario=base_scenario)
    v = instance.get_block_as_pandas(_ENUM["v"], scenario=base_scenario)
    Y = instance.get_block_as_pandas(_ENUM["Y"], scenario=base_scenario).copy()
    EY = instance.get_block_as_pandas(_ENUM["EY"], scenario=base_scenario).copy()
    VY = instance.get_block_as_pandas(_ENUM["VY"], scenario=base_scenario).copy()

    Z = calc_Z(z, X)
    E = calc_E(e, X)
    V = calc_V(v, X)

    for sector in getattr(instance, "to_split_sectors", []):
        parent_sector = sector_to_parent_map[sector]
        for region in instance.get_index(MI["r"]):
            Z.loc[:, (region, MI["s"], parent_sector)] -= Z.loc[:, (region, MI["s"], sector)]
            E.loc[:, (region, MI["s"], parent_sector)] -= E.loc[:, (region, MI["s"], sector)]
            V.loc[:, (region, MI["s"], parent_sector)] -= V.loc[:, (region, MI["s"], sector)]
            child_output = float(X.loc[(region, MI["s"], sector), "production"])
            parent_output = float(X.loc[(region, MI["s"], parent_sector), "production"])
            if child_output < parent_output:
                X.loc[(region, MI["s"], parent_sector), "production"] = parent_output - child_output
            else:
                X.loc[(region, MI["s"], parent_sector), "production"] = 0.0

    negatives = X["production"] < 0
    if negatives.any():
        raise WrongInput(
            "Split total outputs generate negative parent-sector outputs. "
            f"Check rows: {X.loc[negatives].index.tolist()}"
        )

    negative_mask = Z < 0
    if negative_mask.any().any():
        warnings.warn("Negative values found in split matrix Z. They are clipped to zero.")
        Z[negative_mask] = 0.0
        if getattr(instance, "uncertainty_matrix", None) is not None:
            instance.uncertainty_matrix[negative_mask] = instance.uncertainty_values["forced zero"]

    instance.matrices[split_scenario] = {
        _ENUM["Z"]: Z,
        _ENUM["E"]: E,
        _ENUM["V"]: V,
        _ENUM["Y"]: Y,
        _ENUM["EY"]: EY,
        _ENUM["VY"]: VY,
        _ENUM["X"]: X,
    }

    _apply_split_row_hypothesis(
        instance,
        scenario=split_scenario,
        base_scenario=base_scenario,
        old_X=old_X,
    )

    return split_scenario


def _sector_to_parent_map(instance) -> dict[str, str]:
    """Return the mapping between new sectors and their declared parent sector."""

    parent_column = instance.add_sectors_master.columns[
        instance.add_sectors_master.columns.str.startswith(f"Parent {MI['s']}")
    ][0]
    return dict(
        zip(
            instance.add_sectors_master[MI["s"]].astype(str),
            instance.add_sectors_master[parent_column].fillna("").astype(str),
        )
    )


def _convert_split_units(
    instance,
    frame: pd.DataFrame,
    *,
    sector_column: str,
    quantity_column: str,
    unit_column: str,
) -> pd.DataFrame:
    """Convert split-sheet quantities to the database sector units."""

    converted = frame.copy()
    if converted.empty:
        return converted

    ureg = pint.UnitRegistry()
    master_unit_column = [column for column in instance.add_sectors_master.columns if str(column).strip() == "Unit"][0]
    parent_column = instance.add_sectors_master.filter(like=f"Parent {MI['s']}").columns[0]
    master_units = (
        instance.add_sectors_master.loc[:, [MI["s"], master_unit_column]]
        .dropna(subset=[MI["s"]])
        .drop_duplicates(subset=[MI["s"]])
        .set_index(MI["s"])[master_unit_column]
        .to_dict()
    )
    parent_units = {}
    for _, row in instance.add_sectors_master.loc[:, [MI["s"], parent_column]].dropna(subset=[MI["s"]]).iterrows():
        sector = str(row[MI["s"]])
        parent = row[parent_column]
        if pd.isna(parent) or str(parent).strip() == "":
            continue
        parent_units[sector] = instance.units[MI["s"]].loc[str(parent), "unit"]

    quantities = pd.to_numeric(converted[quantity_column], errors="coerce")
    if quantities.isna().any():
        raise WrongInput(f"Invalid numeric quantities found in split sheet column '{quantity_column}'.")

    for idx, row in converted.iterrows():
        sector = str(row[sector_column])
        source_unit = row[unit_column]
        target_unit = master_units.get(sector)
        if pd.isna(target_unit) or str(target_unit).strip() == "":
            target_unit = parent_units.get(sector)
        if (pd.isna(target_unit) or str(target_unit).strip() == "") and not pd.isna(source_unit):
            target_unit = source_unit
        if pd.isna(target_unit) or str(target_unit).strip() == "":
            raise WrongInput(
                f"No target unit is available for split sector '{sector}'. Fill the master sheet unit or provide a parent sector."
            )
        quantity = float(quantities.loc[idx])

        if pd.isna(source_unit) or str(source_unit).strip() == "":
            converted.at[idx, unit_column] = target_unit
            converted.at[idx, quantity_column] = quantity
            continue

        if str(source_unit) == str(target_unit):
            converted.at[idx, quantity_column] = quantity
            converted.at[idx, unit_column] = target_unit
            continue

        try:
            converted_quantity = quantity * ureg(str(source_unit)).to(str(target_unit)).magnitude
        except Exception as exc:  # pragma: no cover - error path exercised in tests through WrongInput
            raise WrongInput(
                f"Split quantity unit '{source_unit}' for sector '{sector}' is not convertible to '{target_unit}'."
            ) from exc

        converted.at[idx, quantity_column] = converted_quantity
        converted.at[idx, unit_column] = target_unit

    return converted


def _apply_split_row_hypothesis(instance, *, scenario: str, base_scenario: str, old_X: pd.DataFrame) -> None:
    """Populate split-sector rows in ``Z`` and ``Y`` after the column hypothesis."""

    sector_to_parent_map = _sector_to_parent_map(instance)
    all_sectors = list(instance.matrices[scenario][_ENUM["X"]].index.get_level_values(2).unique())
    split_sectors = list(getattr(instance, "to_split_sectors", []))
    old_sectors = sorted(set(all_sectors).difference(split_sectors))
    z = instance.get_block_as_pandas(_ENUM["z"], scenario=base_scenario)

    for sector in split_sectors:
        parent_sector = sector_to_parent_map[sector]
        if not parent_sector:
            continue
        for region in instance.get_index(MI["r"]):
            parent_old_output = float(old_X.loc[(region, MI["s"], parent_sector), "production"])
            if parent_old_output == 0:
                continue

            X_cut = instance.matrices[scenario][_ENUM["X"]].loc[(sn, MI["s"], old_sectors)].squeeze()
            z_row = z.loc[(region, MI["s"], parent_sector), (sn, MI["s"], old_sectors)]
            X_cut.index = z_row.index
            new_Z_row = z_row * X_cut
            new_Z_row.name = (region, MI["s"], sector)
            instance.matrices[scenario][_ENUM["Z"]].loc[
                (region, MI["s"], sector),
                (sn, MI["s"], old_sectors),
            ] = new_Z_row

            child_output = float(instance.matrices[scenario][_ENUM["X"]].loc[(region, MI["s"], sector), "production"])
            parent_new_output = float(instance.matrices[scenario][_ENUM["X"]].loc[(region, MI["s"], parent_sector), "production"])

            new_Y_row = (
                instance.matrices[scenario][_ENUM["Y"]].loc[(region, MI["s"], parent_sector), :]
                * child_output
                / parent_old_output
            )
            instance.matrices[scenario][_ENUM["Y"]].loc[(region, MI["s"], sector), :] = new_Y_row
            instance.matrices[scenario][_ENUM["Y"]].loc[(region, MI["s"], parent_sector), :] = (
                instance.matrices[scenario][_ENUM["Y"]].loc[(region, MI["s"], parent_sector), :]
                * parent_new_output
                / parent_old_output
            )


def log_split_scenario(logger, split_scenario: str, sectors: list[str]) -> None:
    """Emit a compact log line for the generated split scenario."""

    log_time(logger, f"Split scenario '{split_scenario}' generated for sectors {sectors}.")
