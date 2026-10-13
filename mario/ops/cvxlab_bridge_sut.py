"""Bridge between the SUT split priors of MARIO and CVXLab.

The IOT bridge (:mod:`mario.ops.cvxlab_bridge`) maps one MARIO matrix to one
CVXLab table through a ``mapping.xlsx`` file. The SUT split model is simpler to
feed directly: every CVXLab input table is named after a prior (``U0``, ``M0``,
``Y0``, ``V0``), an original aggregated matrix (``Uold``, ``Mold``, ``Yold``,
``Vold``), a mask (``Zero_U``, ``Zero_M``) or an identity block, and its
coordinates are the set names declared in the packaged ``Split_sut`` model.
"""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pandas as pd

from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX as MI
from mario.ops.add_sector_specs import (
    ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS,
    ADD_SECTOR_SPLIT_TOLERANCE_SHEET,
)
from mario.ops.add_sector_split_sut import SutSplitPriors, SutSplitStructure
from mario.ops.cvxlab_bridge import (
    CVXLAB_INPUT_TYPES,
    _build_cvxlab_model,
    _cvxlab_input_storage,
    _cvxlab_problem_solved_optimally,
    _ensure_sets_file,
    _install_cvxlab_runtime_compat,
    _load_model_coordinates_and_initialize_database,
    _model_workdir,
    _prepare_split_model_directory,
    _read_blank_input_data,
    _resolve_split_solver,
    _write_input_data_files,
    _call_model_method,
    cl,
)


CVXLAB_SUT_SPLIT_MODEL_NAME = "mario_add_sector_split_sut"
CVXLAB_SUT_TEMPLATE_NAME = "Split_sut"
CVXLAB_SUT_TEMPLATE_FILES = (
    "model_settings.xlsx",
    "user_defined_constants.py",
    "user_defined_operators.py",
)
CVXLAB_SUT_RESULT_TABLES = ("U", "M", "Y", "V")


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------
def _populate_sut_sets_file(instance, structure: SutSplitStructure, *, dest_dir: Path) -> None:
    """Fill ``sets.xlsx`` with the regions, items and categories of the split."""

    sets_file = dest_dir / cl.Defaults.ConfigFiles.SETS_FILE
    sets = pd.read_excel(sets_file, sheet_name=None)

    def with_category(sheet_name: str, items: list[str], category) -> pd.DataFrame:
        frame = sets[sheet_name]
        data = {frame.columns[0]: items}
        if len(frame.columns) > 1:
            data[frame.columns[1]] = [category(item) for item in items]
        return pd.DataFrame(data)

    tolerances = instance.split_info[ADD_SECTOR_SPLIT_TOLERANCE_SHEET]
    tolerance_names = tolerances[ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["name"]].astype(str).tolist()

    for sheet_name in list(sets):
        first_column = sets[sheet_name].columns[0]
        if sheet_name in {"_set_COMMODITY_FROM", "_set_COMMODITY_TO"}:
            sets[sheet_name] = with_category(sheet_name, structure.all_commodities, structure.commodity_category)
        elif sheet_name in {"_set_ACTIVITY_FROM", "_set_ACTIVITY_TO"}:
            sets[sheet_name] = with_category(sheet_name, structure.all_activities, structure.activity_category)
        elif sheet_name in {"_set_REGION_FROM", "_set_REGION_TO"}:
            sets[sheet_name] = pd.DataFrame({first_column: structure.regions})
        elif sheet_name == "_set_CONS_CATEG":
            sets[sheet_name] = pd.DataFrame({first_column: list(instance.get_index(MI["n"]))})
        elif sheet_name == "_set_FACTOR":
            sets[sheet_name] = pd.DataFrame({first_column: list(instance.get_index(MI["f"]))})
        elif sheet_name == "_set_SCALAR":
            frame = pd.DataFrame({first_column: tolerance_names})
            for column in sets[sheet_name].columns:
                if column != first_column and column.endswith("_tolerance"):
                    frame[column] = tolerance_names
            sets[sheet_name] = frame

    with pd.ExcelWriter(sets_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        for sheet_name, frame in sets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


# ---------------------------------------------------------------------------
# Input data
# ---------------------------------------------------------------------------
_ROW_COLUMN_NAMES = {
    "U": (["region_from_Name", "commodity_from_Name"], ["region_to_Name", "activity_to_Name"]),
    "M": (["region_from_Name", "activity_from_Name"], ["region_to_Name", "commodity_to_Name"]),
    "Y": (["region_from_Name", "commodity_from_Name"], ["region_to_Name", "cons_categ_Name"]),
    "V": (["factor_Name"], ["region_to_Name", "activity_to_Name"]),
}


def _long_values(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Return ``frame`` in long form with the CVXLab coordinate names."""

    row_names, column_names = _ROW_COLUMN_NAMES[kind]
    frame = frame.copy()
    frame.index = frame.index.set_names(row_names)
    frame.columns = frame.columns.set_names(column_names)
    series = frame.stack(list(range(frame.columns.nlevels)), future_stack=True).rename("values")
    return series.reset_index()


def _fill_table(table: pd.DataFrame, source: pd.DataFrame | None) -> pd.DataFrame:
    """Overlay ``source['values']`` on the blank CVXLab table by coordinate columns."""

    table = table.drop(columns="values", errors="ignore")
    if source is None:
        return table.assign(values=0.0)
    keys = [column for column in table.columns if column in source.columns and column != "id"]
    merged = table.merge(source[keys + ["values"]], on=keys, how="left")
    merged["values"] = pd.to_numeric(merged["values"], errors="coerce").fillna(0.0)
    return merged


def _zero_below(frame: pd.DataFrame, residue) -> pd.DataFrame:
    if residue is None:
        return frame
    return frame.where(frame.abs() >= float(residue), 0.0)


def _identity_table(table: pd.DataFrame, aggregate, *, child_col: str, parent_col: str) -> pd.DataFrame:
    """Identity block mapping parent and new items (``child_col``) to their parent (``parent_col``)."""

    table = table.copy()
    table["values"] = [
        1.0 if aggregate(child) == parent else 0.0
        for child, parent in zip(table[child_col], table[parent_col])
    ]
    return table


def build_sut_split_input_tables(
    priors: SutSplitPriors,
    blank: dict[str, pd.DataFrame],
    *,
    residue=None,
) -> dict[str, pd.DataFrame]:
    """Fill the blank CVXLab input tables with the priors of the SUT split."""

    structure = priors.structure
    original = priors.original
    tables = {name: frame.copy() for name, frame in blank.items()}

    sources = {
        "Uold": _long_values(_zero_below(original.U, residue), "U"),
        "Mold": _long_values(_zero_below(original.M, residue), "M"),
        "Yold": _long_values(_zero_below(original.Y, residue), "Y"),
        "Vold": _long_values(_zero_below(original.V, residue), "V"),
        "U0": _long_values(_zero_below(priors.U0, residue), "U"),
        "M0": _long_values(_zero_below(priors.M0, residue), "M"),
        "Y0": _long_values(_zero_below(priors.Y0, residue), "Y"),
        "V0": _long_values(_zero_below(priors.V0, residue), "V"),
        "Zero_U": _long_values(priors.zero_U.astype(float), "U"),
        "Zero_M": _long_values(priors.zero_M.astype(float), "M"),
    }
    xnew = priors.Xnew.rename("values").reset_index()
    xnew.columns = ["region_to_Name", "activity_to_Name", "values"]
    sources["Xnew"] = xnew

    for name, source in sources.items():
        if name in tables:
            tables[name] = _fill_table(tables[name], source)

    if "I_act_p_pn" in tables:
        tables["I_act_p_pn"] = _identity_table(
            tables["I_act_p_pn"],
            structure.aggregate_activity,
            child_col="activity_to_Name",
            parent_col="activity_from_Name",
        )
    if "I_com_p_pn" in tables:
        tables["I_com_p_pn"] = _identity_table(
            tables["I_com_p_pn"],
            structure.aggregate_commodity,
            child_col="commodity_from_Name",
            parent_col="commodity_to_Name",
        )
    return tables


def _prepare_sut_split_model_inputs(
    instance,
    *,
    main_dir_path,
    model_dir_name: str,
    input_data_files_type: str,
):
    dest_dir = _prepare_split_model_directory(
        main_dir_path=main_dir_path,
        model_dir_name=model_dir_name,
        template_name=CVXLAB_SUT_TEMPLATE_NAME,
        template_files=CVXLAB_SUT_TEMPLATE_FILES,
    )
    model = _build_cvxlab_model(
        main_dir_path=main_dir_path,
        model_dir_name=model_dir_name,
        input_data_files_type=input_data_files_type,
    )
    _ensure_sets_file(model, dest_dir=dest_dir)
    _populate_sut_sets_file(instance, instance.sut_split_structure, dest_dir=dest_dir)
    _load_model_coordinates_and_initialize_database(model, dest_dir=dest_dir)
    return model, dest_dir


def _write_sut_input_data(instance, *, model, dest_dir: Path, residue=None) -> None:
    file_extension, multiple_input_files = _cvxlab_input_storage(model)
    blank = _read_blank_input_data(
        dest_dir=dest_dir,
        file_extension=file_extension,
        multiple_input_files=multiple_input_files,
    )
    tables = build_sut_split_input_tables(instance.sut_split_priors, blank, residue=residue)
    _write_input_data_files(
        dest_dir=dest_dir,
        input_data=tables,
        file_extension=file_extension,
        multiple_input_files=multiple_input_files,
    )


def create_sut_split_input_data(
    instance,
    *,
    main_dir_path,
    input_data_files_type: str = "xlsx",
    model_dir_name: str = CVXLAB_SUT_SPLIT_MODEL_NAME,
    residue=None,
) -> Path:
    """Generate the CVXLab model directory and input data for a SUT split."""

    if cl is None:
        raise ModuleNotFoundError("CVXLab is not installed. Install the 'cvxlab' package to use split=True.")
    if input_data_files_type not in CVXLAB_INPUT_TYPES:
        raise WrongInput("input_data_files_type should be either 'xlsx' or 'csv'.")

    _install_cvxlab_runtime_compat()
    model, dest_dir = _prepare_sut_split_model_inputs(
        instance,
        main_dir_path=main_dir_path,
        model_dir_name=model_dir_name,
        input_data_files_type=input_data_files_type,
    )
    _write_sut_input_data(instance, model=model, dest_dir=dest_dir, residue=residue)
    return dest_dir


# ---------------------------------------------------------------------------
# Optimization
# ---------------------------------------------------------------------------
def optimize_sut_split_in_cvxlab(
    instance,
    *,
    main_dir_path,
    input_data_files_type: str = "xlsx",
    solver=None,
    solver_parameters=None,
    model_dir_name: str = CVXLAB_SUT_SPLIT_MODEL_NAME,
    residue=None,
) -> dict[str, pd.DataFrame]:
    """Run the SUT split optimization in CVXLab and return the optimized two-level blocks."""

    if cl is None:
        raise ModuleNotFoundError("CVXLab is not installed. Install the 'cvxlab' package to use split=True.")

    _install_cvxlab_runtime_compat()
    model, dest_dir = _prepare_sut_split_model_inputs(
        instance,
        main_dir_path=main_dir_path,
        model_dir_name=model_dir_name,
        input_data_files_type=input_data_files_type,
    )
    _write_sut_input_data(instance, model=model, dest_dir=dest_dir, residue=residue)
    solver = _resolve_split_solver(solver)

    with _model_workdir(dest_dir):
        if hasattr(model, "refresh_database_and_initialize_problem"):
            model.refresh_database_and_initialize_problem(force_overwrite=True)
        else:
            _call_model_method(
                model, "load_exogenous_data_to_sqlite_database", "_load_exogenous_data_to_sqlite_database",
                force_overwrite=True,
            )
            _call_model_method(model, "initialize_problems", "_initialize_problems", force_overwrite=True)

        run_kwargs = {"verbose": True, "integrated_problems": False}
        if solver is not None:
            run_kwargs["solver"] = solver
        if solver_parameters is not None:
            if "solver_settings" in inspect.signature(model.run_model).parameters:
                if solver == "MOSEK":
                    run_kwargs["mosek_params"] = solver_parameters
                else:
                    run_kwargs["solver_settings"] = solver_parameters

        model.run_model(**run_kwargs)
        if not _cvxlab_problem_solved_optimally(model.core.problem.problem_status):
            raise WrongInput(
                "CVXLab split optimization did not solve optimally. Check the generated model directory for details."
            )
        model.load_results_to_database(force_overwrite=True)

    return parse_sut_split_results(instance.sut_split_priors, dest_dir, residue=residue)


def _read_result_tables(dest_dir: Path) -> dict[str, pd.DataFrame]:
    connection = sqlite3.connect(Path(dest_dir) / cl.Defaults.ConfigFiles.SQLITE_DATABASE_FILE)
    try:
        return {
            name: pd.read_sql_query(f"SELECT * FROM {name}", connection).drop(columns=["id"], errors="ignore")
            for name in CVXLAB_SUT_RESULT_TABLES
        }
    finally:
        connection.close()


def _wide(table: pd.DataFrame, row_names: list[str], column_names: list[str]) -> pd.DataFrame:
    wide = table.set_index(row_names + column_names)["values"].unstack(column_names)
    return wide


def parse_sut_split_results(priors: SutSplitPriors, dest_dir: Path, *, residue=None) -> dict[str, pd.DataFrame]:
    """Combine the solved blocks with the untouched stable blocks into full two-level frames.

    The optimization only produces the cells involving parent or new items; the
    ``stable x stable`` cells keep the original values.
    """

    structure, original = priors.structure, priors.original
    tables = _read_result_tables(dest_dir)
    if residue is not None:
        threshold = float(residue)
        for name, table in tables.items():
            table["values"] = table["values"].where(table["values"] >= threshold, 0.0)

    # solvers return tiny negative values (about -1e-11) for cells that are zero
    for table in tables.values():
        values = table["values"]
        noise = (values < 0) & (values > -1e-6 * max(float(values.abs().max()), 1.0))
        table["values"] = values.mask(noise, 0.0)

    act = pd.MultiIndex.from_product([structure.regions, structure.all_activities], names=["Region", "Item"])
    com = pd.MultiIndex.from_product([structure.regions, structure.all_commodities], names=["Region", "Item"])

    def solved(name: str, kind: str, index, columns, base: pd.DataFrame) -> pd.DataFrame:
        row_names, column_names = _ROW_COLUMN_NAMES[kind]
        result = base.reindex(index=index, columns=columns).fillna(0.0)
        table = tables[name].dropna(subset=["values"])
        if table.empty:
            return result
        wide = _wide(table, row_names, column_names)
        wide.index = wide.index.set_names(["Region", "Item"]) if wide.index.nlevels == 2 else wide.index
        wide.columns = wide.columns.set_names(["Region", "Item"])
        wide = wide.reindex(index=result.index, columns=result.columns)
        mask = wide.notna()
        values = result.to_numpy().copy()
        values[mask.to_numpy()] = wide.to_numpy()[mask.to_numpy()]
        return pd.DataFrame(values, index=result.index, columns=result.columns)

    U = solved("U", "U", com, act, original.U)
    M = solved("M", "M", act, com, original.M)
    Y = solved("Y", "Y", com, original.Y.columns, original.Y)
    V_table = tables["V"].dropna(subset=["values"])
    V = original.V.reindex(columns=act).fillna(0.0)
    if not V_table.empty:
        wide = V_table.set_index(["factor_Name", "region_to_Name", "activity_to_Name"])["values"].unstack(
            ["region_to_Name", "activity_to_Name"]
        )
        wide.columns = wide.columns.set_names(["Region", "Item"])
        wide.index = wide.index.set_names(V.index.name)
        wide = wide.reindex(index=V.index, columns=V.columns)
        mask = wide.notna().to_numpy()
        values = V.to_numpy().copy()
        values[mask] = wide.to_numpy()[mask]
        V = pd.DataFrame(values, index=V.index, columns=V.columns)

    return {"U": U, "M": M, "Y": Y, "V": V}
