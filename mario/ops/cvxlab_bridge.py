"""Bridge helpers between MARIO split scenarios and CVXLab."""

from __future__ import annotations

from contextlib import contextmanager
import inspect
import os
import shutil
import sqlite3
import stat
from importlib import resources
from pathlib import Path

import pandas as pd

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.model.conventions import _ENUM, _MASTER_INDEX as MI
from mario.ops.add_sector_specs import (
    ADD_SECTOR_SPLIT_OUTPUT_COLUMNS,
    ADD_SECTOR_SPLIT_OUTPUT_SHEET,
    ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS,
    ADD_SECTOR_SPLIT_TOLERANCE_SHEET,
    ADD_SECTOR_SPLIT_TRADE_COLUMNS,
    ADD_SECTOR_SPLIT_TRADE_SHEET,
)

try:  # pragma: no cover - import failure tested through the public API path
    import cvxlab as cl
except ModuleNotFoundError:  # pragma: no cover - handled by caller
    cl = None


CVXLAB_SPLIT_MODEL_NAME = "mario_add_sector_split"
CVXLAB_INPUT_TYPES = {"xlsx", "csv"}
CVXLAB_TEMPLATE_PACKAGE = "mario.ops.cvxlab_models"
CVXLAB_TEMPLATE_NAME = "Split_sectors"
CVXLAB_RAW_TEXT_COLUMNS = {"description"}
CVXLAB_OPTIMAL_STATUSES = {"optimal", "optimal_inaccurate"}


def create_split_input_data(
    instance,
    *,
    main_dir_path,
    scenario_label: str,
    input_data_files_type: str = "xlsx",
    model_dir_name: str = CVXLAB_SPLIT_MODEL_NAME,
    residue=None,
) -> Path:
    """Generate the CVXLab model directory and input data for split sectors."""

    if cl is None:
        raise ModuleNotFoundError(
            "CVXLab is not installed. Install the 'cvxlab' package to use split=True."
        )
    if input_data_files_type not in CVXLAB_INPUT_TYPES:
        raise WrongInput("input_data_files_type should be either 'xlsx' or 'csv'.")

    _install_cvxlab_runtime_compat()

    model, dest_dir, mapping, flat_matrices = _prepare_split_model_inputs(
        instance,
        main_dir_path=main_dir_path,
        scenario_label=scenario_label,
        model_dir_name=model_dir_name,
        input_data_files_type=input_data_files_type,
    )
    _write_input_data(
        instance,
        model=model,
        dest_dir=dest_dir,
        mapping=mapping,
        flat_matrices=flat_matrices,
        scenario_label=scenario_label,
        input_data_files_type=input_data_files_type,
        residue=residue,
    )
    return dest_dir


def optimize_split_in_cvxlab(
    instance,
    *,
    main_dir_path,
    scenario_label: str,
    input_data_files_type: str = "xlsx",
    solver=None,
    solver_parameters=None,
    model_dir_name: str = CVXLAB_SPLIT_MODEL_NAME,
    residue=None,
) -> dict[str, pd.DataFrame]:
    """Run the split optimization in CVXLab and return optimized MARIO matrices."""

    if cl is None:
        raise ModuleNotFoundError(
            "CVXLab is not installed. Install the 'cvxlab' package to use split=True."
        )

    _install_cvxlab_runtime_compat()

    model, dest_dir, mapping, flat_matrices = _prepare_split_model_inputs(
        instance,
        main_dir_path=main_dir_path,
        scenario_label=scenario_label,
        model_dir_name=model_dir_name,
        input_data_files_type=input_data_files_type,
    )
    _write_input_data(
        instance,
        model=model,
        dest_dir=dest_dir,
        mapping=mapping,
        flat_matrices=flat_matrices,
        scenario_label=scenario_label,
        input_data_files_type=input_data_files_type,
        residue=residue,
    )

    solver = _resolve_split_solver(solver)

    with _model_workdir(dest_dir):
        if hasattr(model, "refresh_database_and_initialize_problem"):
            model.refresh_database_and_initialize_problem(force_overwrite=True)
        else:
            _call_model_method(
                model,
                "load_exogenous_data_to_sqlite_database",
                "_load_exogenous_data_to_sqlite_database",
                force_overwrite=True,
            )
            _call_model_method(
                model,
                "initialize_problems",
                "_initialize_problems",
                force_overwrite=True,
            )

        run_kwargs = {
            "verbose": True,
            "integrated_problems": False,
        }
        if solver is not None:
            run_kwargs["solver"] = solver
        if solver_parameters is not None:
            run_model_signature = inspect.signature(model.run_model).parameters
            if "solver_settings" in run_model_signature:
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
    return _parse_split_results(dest_dir, flat_matrices, residue=residue)


def _resolve_split_solver(solver):
    """Choose a conic-capable default solver for entropy-based split models."""

    if solver is not None:
        return solver

    try:
        import cvxpy as cp
    except ModuleNotFoundError:  # pragma: no cover - CVXLab already requires cvxpy
        return None

    installed = set(cp.installed_solvers())
    for candidate in ("ECOS", "SCS", "CLARABEL"):
        if candidate in installed:
            return candidate
    return None


def _cvxlab_problem_status_values(problem_status) -> list[str]:
    """Normalize CVXLab problem status containers across old and new builds."""

    if problem_status is None:
        return []
    if isinstance(problem_status, dict):
        return [str(status) for status in problem_status.values() if status is not None]
    return [str(problem_status)]


def _cvxlab_problem_solved_optimally(problem_status) -> bool:
    """Return True when every reported CVXLab solve status is optimal enough."""

    statuses = _cvxlab_problem_status_values(problem_status)
    return bool(statuses) and all(status in CVXLAB_OPTIMAL_STATUSES for status in statuses)


def _prepare_split_model_inputs(
    instance,
    *,
    main_dir_path,
    scenario_label: str,
    model_dir_name: str,
    input_data_files_type: str,
):
    dest_dir = _prepare_split_model_directory(main_dir_path=main_dir_path, model_dir_name=model_dir_name)
    mapping = pd.read_excel(dest_dir / "mapping.xlsx", sheet_name=None, index_col=0)

    model = _build_cvxlab_model(
        main_dir_path=main_dir_path,
        model_dir_name=model_dir_name,
        input_data_files_type=input_data_files_type,
    )
    _ensure_sets_file(model, dest_dir=dest_dir)
    _populate_sets_file(instance, dest_dir=dest_dir, scenario_label=scenario_label)
    _ensure_sets_file(model, dest_dir=dest_dir)
    _load_model_coordinates_and_initialize_database(model, dest_dir=dest_dir)

    flat_matrices = _collect_flat_matrices(
        instance,
        scenarios=[f"split_{scenario_label}", "original"],
    )
    return model, dest_dir, mapping, flat_matrices


def _build_cvxlab_model(*, main_dir_path, model_dir_name: str, input_data_files_type: str):
    """Instantiate ``cvxlab.Model`` across old and new constructor signatures."""

    model_signature = inspect.signature(cl.Model.__init__).parameters
    multiple_input_files = input_data_files_type == "csv"
    normalized_root = _normalize_main_dir_path(main_dir_path)

    kwargs = {
        "model_dir_name": model_dir_name,
        "main_dir_path": str(normalized_root),
        "model_settings_from": "xlsx",
        "use_existing_data": False,
        "detailed_validation": True,
        "log_level": "info",
    }

    if "multiple_input_files" in model_signature:
        kwargs["multiple_input_files"] = multiple_input_files

    if "input_data_files_type" in model_signature:
        kwargs["input_data_files_type"] = input_data_files_type
    elif input_data_files_type == "csv":
        raise NotImplementable(
            "The installed CVXLab build does not expose csv input files through "
            "Model(..., input_data_files_type='csv')."
        )

    if "import_custom_operators" in model_signature:
        kwargs["import_custom_operators"] = True
    if "import_custom_constants" in model_signature:
        kwargs["import_custom_constants"] = True
    if "log_format" in model_signature:
        kwargs["log_format"] = "standard"

    with _cvxlab_nullable_settings_compat():
        return cl.Model(**kwargs)


def _is_missing_settings_cell(value) -> bool:
    """Return whether a CVXLab settings cell should be omitted."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _sanitize_symbolic_problem_structure(data):
    """Drop missing or blank symbolic expressions from CVXLab-loaded problems."""

    if not isinstance(data, dict):
        return data

    for value in data.values():
        if isinstance(value, dict):
            _sanitize_symbolic_problem_structure(value)

    for key in ("objective", "expressions"):
        values = data.get(key)
        if isinstance(values, list):
            data[key] = [
                value
                for value in values
                if isinstance(value, str) and value.strip()
            ]

    return data


def _install_cvxlab_runtime_compat() -> None:
    """Patch CVXLab runtime quirks once per process."""

    if cl is None:
        return

    try:
        from cvxlab.backend.problem import Problem
    except Exception:  # pragma: no cover - depends on installed cvxlab internals
        return

    if getattr(Problem.load_symbolic_problem_from_file, "_mario_compat", False):
        return

    original = Problem.load_symbolic_problem_from_file

    def wrapped(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        symbolic_problem = getattr(self, "symbolic_problem", None)
        if symbolic_problem:
            _sanitize_symbolic_problem_structure(symbolic_problem)
        return result

    wrapped._mario_compat = True
    Problem.load_symbolic_problem_from_file = wrapped


def _process_cvxlab_settings_value(column, value, *, skip_process_str: bool = False):
    """Process one CVXLab settings cell with pandas 3 dtype coercions in mind."""
    import cvxlab.support.util_text as cvx_util_text

    processed = value
    if not skip_process_str and column not in CVXLAB_RAW_TEXT_COLUMNS:
        processed = cvx_util_text.process_str(value)
    if column in {"integer", "nonneg", "split_problem"} and isinstance(
        processed, (int, float)
    ):
        return bool(processed)
    return processed


def _pivot_cvxlab_settings_dataframe(
    data: pd.DataFrame,
    primary_key: str | int | None = None,
    secondary_key: str | int | None = None,
    merge_dict: bool = False,
    skip_process_str: bool = False,
) -> dict:
    """Pandas 3-safe variant of CVXLab's settings dataframe pivot helper."""
    import cvxlab.support.util as cvx_util

    data_structure = {}
    primary_key = primary_key or data.columns[0]

    if primary_key not in data.columns:
        raise ValueError(f"Primary key '{primary_key}' not found in DataFrame columns.")

    records = data.to_dict("records")
    columns = list(data.columns)
    for row in records:
        key = row[primary_key]

        if key not in data_structure:
            data_structure[key] = {}

        inner_dict = {}
        for column in columns:
            if column == primary_key:
                continue
            if column == secondary_key:
                break

            value = row[column]
            if not _is_missing_settings_cell(value):
                inner_dict[column] = _process_cvxlab_settings_value(
                    column,
                    value,
                    skip_process_str=skip_process_str,
                )

        if merge_dict:
            data_structure[key] = cvx_util.merge_dicts(
                [data_structure[key], inner_dict]
            )
        else:
            data_structure[key] = inner_dict

    if secondary_key:
        if secondary_key not in data.columns:
            raise ValueError(
                f"Secondary key '{secondary_key}' not found in DataFrame columns."
            )

        secondary_key_index = columns.index(secondary_key)
        secondary_keys_list = columns[secondary_key_index:]

        for row in records:
            outer_key = row[primary_key]
            inner_key = row[secondary_key]
            data_structure[outer_key].setdefault(secondary_key, {})

            inner_dict = {}
            for column in secondary_keys_list:
                if column == secondary_key:
                    continue

                value = row[column]
                if not _is_missing_settings_cell(value):
                    inner_dict[column] = _process_cvxlab_settings_value(column, value)

            data_structure[outer_key][secondary_key][inner_key] = inner_dict

    if None in data_structure:
        return data_structure[None]

    return data_structure


@contextmanager
def _cvxlab_nullable_settings_compat():
    """Patch CVXLab settings parsing while constructing a model under pandas 3."""
    import cvxlab.support.util as cvx_util

    original = cvx_util.pivot_dataframe_to_data_structure
    cvx_util.pivot_dataframe_to_data_structure = _pivot_cvxlab_settings_dataframe
    try:
        yield
    finally:
        cvx_util.pivot_dataframe_to_data_structure = original


def _call_model_method(model, *names, **kwargs):
    """Call the first available CVXLab model method from a list of aliases."""

    for name in names:
        method = getattr(model, name, None)
        if callable(method):
            return method(**kwargs)
    raise AttributeError(f"None of the CVXLab model methods {names} are available.")


@contextmanager
def _model_workdir(model_dir: Path):
    """Temporarily switch cwd to the generated CVXLab model directory."""

    previous = Path.cwd()
    os.chdir(model_dir)
    try:
        yield
    finally:
        os.chdir(previous)


def _prepare_split_model_directory(*, main_dir_path, model_dir_name: str) -> Path:
    """Create a clean split-model directory and copy MARIO-owned template assets."""

    root = _normalize_main_dir_path(main_dir_path)
    dest_dir = root / model_dir_name
    if dest_dir.exists():
        answer = input(
            f"Directory '{dest_dir}' already exists. Overwrite? [y/n]: "
        ).strip().lower()
        if answer != "y":
            raise WrongInput(
                f"Aborted: directory '{dest_dir}' was not overwritten."
            )
        shutil.rmtree(dest_dir, onerror=_handle_remove_readonly)
    dest_dir.mkdir(parents=True, exist_ok=True)

    template_dir = resources.files(CVXLAB_TEMPLATE_PACKAGE) / CVXLAB_TEMPLATE_NAME
    for filename in [
        "mapping.xlsx",
        "model_settings.xlsx",
        "user_defined_constants.py",
        "user_defined_operators.py",
    ]:
        source = template_dir / filename
        target = dest_dir / filename
        shutil.copy2(source, target)
        if filename == "model_settings.xlsx":
            _maybe_rewrite_incompatible_model_settings(target)

    return dest_dir


def _normalize_main_dir_path(main_dir_path) -> Path:
    """Return an absolute CVXLab root path.

    The split bridge temporarily changes the working directory while interacting
    with CVXLab. Relative ``main_dir_path`` values therefore become unsafe,
    because CVXLab stores them in ``model.paths`` and later resolves files such
    as ``sets.xlsx`` against the *current* working directory.

    Normalizing early keeps the generated model directory stable regardless of
    the caller's current cwd or later cwd changes inside the bridge.
    """

    return Path(main_dir_path).expanduser().resolve()


def _maybe_rewrite_incompatible_model_settings(path: Path) -> None:
    """Adapt the copied settings workbook only for older CVXLab builds.

    The packaged template should be copied as-is so user changes to the split
    model are preserved. Some older CVXLab builds, however, do not know the
    ``nonneg`` column in ``structure_variables``. In that case we rewrite only
    the copied file in the generated model directory, leaving the repository
    template untouched.
    """

    drop_nonneg = getattr(cl.Defaults.Labels, "NONNEG_KEY", None) is None
    fill_problem_blanks = hasattr(cl.Model, "refresh_database_and_initialize_problem")
    if not drop_nonneg and not fill_problem_blanks:
        return

    workbook = pd.ExcelFile(path, engine="openpyxl")
    sheets = {
        sheet: pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
        for sheet in workbook.sheet_names
    }
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet, frame in sheets.items():
            if drop_nonneg and sheet == "structure_variables" and "nonneg" in frame.columns:
                frame = frame.drop(columns=["nonneg"])
            if fill_problem_blanks and sheet == "problem":
                for column in ("objective", "expressions"):
                    if column in frame.columns:
                        frame[column] = frame[column].fillna("")
            frame.to_excel(writer, sheet_name=sheet, index=False)


def _handle_remove_readonly(func, path, exc_info) -> None:
    """Allow recursive deletion of previously generated model directories."""

    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _ensure_sets_file(model, *, dest_dir: Path) -> Path:
    """Ensure the model-specific CVXLab ``sets.xlsx`` file exists.

    The split workflow relies on the ``Split_sectors`` model files copied in the
    generated model directory. In the historical MARIO flow, CVXLab first
    created the blank workbook implied by those model settings and only after
    that MARIO filled it with sector, region and tolerance values.

    Different CVXLab builds expose that generation step differently, so the
    bridge makes sure the workbook exists before it tries to populate it.
    """

    sets_file = dest_dir / cl.Defaults.ConfigFiles.SETS_FILE
    if sets_file.exists():
        return sets_file

    database = getattr(getattr(model, "core", None), "database", None)
    creator = getattr(database, "create_blank_sets_xlsx_file", None)
    if callable(creator):
        with _model_workdir(dest_dir):
            creator()

    if not sets_file.exists():
        raise FileNotFoundError(
            f"CVXLab did not provide the required sets workbook '{sets_file.name}' in '{dest_dir}'."
        )
    return sets_file


def _load_model_coordinates_and_initialize_database(model, *, dest_dir: Path) -> None:
    """Load coordinates and initialize the blank database following the historical split flow.

    MARIO intentionally avoids ``initialize_model_environment()`` here. That
    higher-level helper assumes the whole CVXLab environment already exists,
    while the add-sector workflow needs to:

    1. create the model-specific ``sets.xlsx`` workbook,
    2. populate it with MARIO split data,
    3. only then load coordinates and initialize blank input tables.

    This mirrors the legacy workflow used by the original split model assets and
    keeps MARIO responsible for the pre-solve data preparation.
    """

    with _model_workdir(dest_dir):
        _call_model_method(model, "load_model_coordinates", "_load_model_coordinates")
        _call_model_method(
            model,
            "initialize_blank_data_structure",
            "_initialize_blank_data_structure",
        )


def _populate_sets_file(instance, *, dest_dir: Path, scenario_label: str) -> None:
    """Fill the CVXLab ``sets.xlsx`` file with the sets needed by the split model."""

    sets_file = dest_dir / cl.Defaults.ConfigFiles.SETS_FILE
    sets = pd.read_excel(sets_file, sheet_name=None)

    split_scenario = f"split_{scenario_label}"
    sectors = instance.get_index(MI["s"])
    regions = instance.get_index(MI["r"])
    factors = instance.get_index(MI["f"])
    cons_categories = instance.matrices[split_scenario][_ENUM["Y"]].columns.get_level_values(2).unique().tolist()
    tolerance_sheet = instance.split_info[ADD_SECTOR_SPLIT_TOLERANCE_SHEET]
    tolerance_names = tolerance_sheet[ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["name"]].astype(str).tolist()

    parent_map = dict(
        zip(
            instance.add_sectors_master[MI["s"]].astype(str),
            instance.add_sectors_master.filter(like=f"Parent {MI['s']}").iloc[:, 0].fillna("").astype(str),
        )
    )
    new_sectors = set(getattr(instance, "to_split_sectors", []))
    parent_sectors = {parent for sector, parent in parent_map.items() if sector in new_sectors and parent}
    stable_sectors = [sector for sector in sectors if sector not in new_sectors and sector not in parent_sectors]

    for sheet_name, frame in sets.items():
        first_column = frame.columns[0]
        if sheet_name == "_set_SECTOR_FROM":
            frame = pd.DataFrame({first_column: sectors})
            if "sector_from_category" in sets[sheet_name].columns:
                frame["sector_from_category"] = [
                    "new" if sector in new_sectors else "parent" if sector in parent_sectors else "stable"
                    for sector in sectors
                ]
            sets[sheet_name] = frame
        elif sheet_name == "_set_SECTOR_TO":
            frame = pd.DataFrame({first_column: sectors})
            if "sector_to_category" in sets[sheet_name].columns:
                frame["sector_to_category"] = [
                    "new" if sector in new_sectors else "parent" if sector in parent_sectors else "stable"
                    for sector in sectors
                ]
            sets[sheet_name] = frame
        elif sheet_name == "_set_REGION_FROM":
            sets[sheet_name] = pd.DataFrame({first_column: regions})
        elif sheet_name == "_set_REGION_TO":
            sets[sheet_name] = pd.DataFrame({first_column: regions})
        elif sheet_name == "_set_CONS_CATEG":
            sets[sheet_name] = pd.DataFrame({first_column: cons_categories})
        elif sheet_name == "_set_FACTOR":
            sets[sheet_name] = pd.DataFrame({first_column: factors})
        elif sheet_name == "_set_SCALAR":
            frame = pd.DataFrame({first_column: tolerance_names})
            extra_columns = [column for column in sets[sheet_name].columns if column != first_column]
            for column in extra_columns:
                if column.endswith("_tolerance"):
                    frame[column] = tolerance_names
            sets[sheet_name] = frame

    with pd.ExcelWriter(sets_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        for sheet_name, frame in sets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


def _collect_flat_matrices(instance, *, scenarios: list[str]) -> dict[str, pd.DataFrame]:
    """Collect the semantically named flat matrices expected by the split mapping."""

    result = {name: [] for name in ("Z", "Y", "V", "X")}
    for scenario in scenarios:
        if scenario.startswith("split_"):
            result["Z"].append(_flatten_Z(instance.matrices[scenario][_ENUM["Z"]], scenario))
            result["Y"].append(_flatten_Y(instance.matrices[scenario][_ENUM["Y"]], scenario))
            result["V"].append(_flatten_V(instance.matrices[scenario][_ENUM["V"]], scenario))
            result["X"].append(_flatten_X(instance.matrices[scenario][_ENUM["X"]], scenario))
        else:
            Z = instance.get_block_as_pandas(_ENUM["Z"], scenario=scenario)
            Y = instance.get_block_as_pandas(_ENUM["Y"], scenario=scenario)
            V = instance.get_block_as_pandas(_ENUM["V"], scenario=scenario)
            X = (
                instance.get_block_as_pandas(_ENUM["X"], scenario=scenario)
                if instance.has_matrix(_ENUM["X"], scenario=scenario)
                else None
            )
            result["Z"].append(_flatten_Z(Z, scenario))
            result["Y"].append(_flatten_Y(Y, scenario))
            result["V"].append(_flatten_V(V, scenario))
            if X is not None:
                result["X"].append(_flatten_X(X, scenario))

    return {name: pd.concat(frames, ignore_index=True) for name, frames in result.items() if frames}


def _flatten_Z(frame: pd.DataFrame, scenario: str) -> pd.DataFrame:
    frame = frame.copy()
    frame.index.names = ["r_from", "l_from", "s_from"]
    frame.columns.names = ["r_to", "l_to", "s_to"]
    flat = (
        frame.stack(list(range(frame.columns.nlevels)), future_stack=True)
        .rename("Value")
        .to_frame()
        .reset_index()
    )
    flat.columns = [
        "Region_from",
        "Level_from",
        "Sector_from",
        "Region_to",
        "Level_to",
        "Sector_to",
        "Value",
    ]
    flat.insert(0, "Scenario", scenario)
    return flat.drop(columns=["Level_from", "Level_to"])


def _flatten_Y(frame: pd.DataFrame, scenario: str) -> pd.DataFrame:
    frame = frame.copy()
    frame.index.names = ["r_from", "l_from", "s_from"]
    frame.columns.names = ["r_to", "l_to", "n_to"]
    flat = (
        frame.stack(list(range(frame.columns.nlevels)), future_stack=True)
        .rename("Value")
        .to_frame()
        .reset_index()
    )
    flat.columns = [
        "Region_from",
        "Level_from",
        "Sector_from",
        "Region_to",
        "Level_to",
        "Consumption category_to",
        "Value",
    ]
    flat.insert(0, "Scenario", scenario)
    return flat.drop(columns=["Level_from", "Level_to"])


def _flatten_V(frame: pd.DataFrame, scenario: str) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns.names = ["r_to", "l_to", "s_to"]
    frame.index.name = "f_from"
    flat = (
        frame.stack(list(range(frame.columns.nlevels)), future_stack=True)
        .rename("Value")
        .to_frame()
        .reset_index()
    )
    flat.columns = [
        "Factor of production_from",
        "Region_to",
        "Level_to",
        "Sector_to",
        "Value",
    ]
    flat.insert(0, "Scenario", scenario)
    return flat.drop(columns=["Level_to"])


def _flatten_X(frame: pd.DataFrame, scenario: str) -> pd.DataFrame:
    frame = frame.copy()
    frame.index.names = ["r_from", "l_from", "s_from"]
    flat = frame.reset_index().copy()
    flat.columns = ["Region_from", "Level_from", "Sector_from", "Value"]
    flat.insert(0, "Scenario", scenario)
    return flat.drop(columns=["Level_from"])


def _write_input_data(
    instance,
    *,
    model,
    dest_dir: Path,
    mapping: dict[str, pd.DataFrame],
    flat_matrices: dict[str, pd.DataFrame],
    scenario_label: str,
    input_data_files_type: str,
    residue=None,
) -> None:
    """Fill the blank CVXLab input data with MARIO split data."""
    split_scenario = f"split_{scenario_label}"
    file_extension, multiple_input_files = _cvxlab_input_storage(model)
    input_data = _read_blank_input_data(
        dest_dir=dest_dir,
        file_extension=file_extension,
        multiple_input_files=multiple_input_files,
    )

    matrix_map = dict(zip(mapping["matrices"].index.to_list(), mapping["matrices"]["cvxlab"]))
    set_map = dict(zip(mapping["sets"].index.to_list(), mapping["sets"]["cvxlab"]))

    for mario_matrix_name, mario_df in flat_matrices.items():
        if mario_matrix_name not in matrix_map or pd.isna(matrix_map[mario_matrix_name]):
            continue
        cvxlab_table = matrix_map[mario_matrix_name]
        mario_df = mario_df[mario_df["Scenario"] == f"split_{scenario_label}"].copy()
        input_data[cvxlab_table] = _merge_cvxlab_input_table(
            input_data[cvxlab_table],
            _rename_flat_columns(mario_df, set_map),
            table_name=cvxlab_table,
        )

    old_matrices_config = {
        "Z": ("Zold", ["region_from_Name", "region_to_Name", "sector_from_Name", "sector_to_Name"]),
        "Y": ("Yold", ["region_from_Name", "sector_from_Name", "region_to_Name", "cons_categ_Name"]),
        "V": ("Vold", ["factor_Name", "region_to_Name", "sector_to_Name"]),
    }
    for mario_name, (target_name, join_cols) in old_matrices_config.items():
        original_df = _rename_flat_columns(
            flat_matrices[mario_name].query("Scenario == 'original'").copy(),
            set_map,
        )
        merged = _merge_cvxlab_input_table(
            input_data[target_name],
            original_df,
            join_cols=join_cols,
            table_name=target_name,
        )

        fallback_df = _rename_flat_columns(
            flat_matrices[mario_name].query("Scenario == @split_scenario").copy(),
            set_map,
        )
        if not fallback_df.empty:
            merged = merged.merge(
                fallback_df[join_cols + ["values"]],
                on=join_cols,
                how="left",
                suffixes=("", "_fallback"),
            )
            merged["values"] = merged["values"].fillna(merged.pop("values_fallback"))

        input_data[target_name] = merged

    identity_table = "I_p_pn" if "I_p_pn" in input_data else "I_sp_spn"
    input_data[identity_table]["values"] = (
        input_data[identity_table]["sector_from_Name"].map(_split_parent_lookup(instance))
        == input_data[identity_table]["sector_to_Name"]
    ).astype(int)

    tolerance_sheet = instance.split_info[ADD_SECTOR_SPLIT_TOLERANCE_SHEET].copy()
    input_data["tol"]["values"] = tolerance_sheet[ADD_SECTOR_SPLIT_TOLERANCE_COLUMNS["value"]].astype(float).tolist()

    trade_sheet = instance.split_info[ADD_SECTOR_SPLIT_TRADE_SHEET].copy()
    trade_sheet = trade_sheet.rename(
        columns={
            ADD_SECTOR_SPLIT_TRADE_COLUMNS["quantity"]: "values",
            ADD_SECTOR_SPLIT_TRADE_COLUMNS["sector_from"]: "sector_from_Name",
            ADD_SECTOR_SPLIT_TRADE_COLUMNS["region_from"]: "region_from_Name",
            ADD_SECTOR_SPLIT_TRADE_COLUMNS["region_to"]: "region_to_Name",
        }
    )
    trade_sheet = trade_sheet.loc[:, ["region_from_Name", "region_to_Name", "sector_from_Name", "values"]]

    input_data["Trade"] = _merge_cvxlab_input_table(
        input_data["Trade"],
        trade_sheet,
        join_cols=["region_from_Name", "region_to_Name", "sector_from_Name"],
        table_name="Trade",
    )
    input_data["Trade"]["values"] = input_data["Trade"]["values"].fillna(0.0)
    same_region = (
        input_data["Trade"]["region_from_Name"] == input_data["Trade"]["region_to_Name"]
    )
    input_data["Trade"].loc[same_region, "values"] = 0.0

    selector = input_data["Trade_selector"].copy()
    selector["values"] = 0
    split_sectors = set(getattr(instance, "to_split_sectors", []))
    for idx, row in selector.iterrows():
        mask = (
            (trade_sheet["region_from_Name"] == row["region_from_Name"])
            & (trade_sheet["region_to_Name"] == row["region_to_Name"])
            & (trade_sheet["sector_from_Name"] == row["sector_from_Name"])
        )
        if (
            row["region_from_Name"] != row["region_to_Name"]
            and row["sector_from_Name"] in split_sectors
            and mask.any()
        ):
            selector.at[idx, "values"] = 1
    input_data["Trade_selector"] = selector

    #Remove values below the residue threshold, if specified.
    if residue is not None:
        threshold = float(residue)
        for table_name, df in input_data.items():
            if table_name in {"Trade_selector", "tol"} or "values" not in df.columns:
                continue
            input_data[table_name] = df.assign(values=df["values"].where(df["values"] >= threshold, 0))

    _write_input_data_files(
        dest_dir=dest_dir,
        input_data=input_data,
        file_extension=file_extension,
        multiple_input_files=multiple_input_files,
    )


def _cvxlab_input_storage(model) -> tuple[str, bool]:
    """Read input-file storage settings from the CVXLab model instance."""

    settings = getattr(model, "settings", {})
    file_extension = settings.get("input_data_files_type", "xlsx")
    multiple_input_files = bool(settings.get("multiple_input_files", False))
    return file_extension, multiple_input_files


def _read_blank_input_data(
    *,
    dest_dir: Path,
    file_extension: str,
    multiple_input_files: bool,
) -> dict[str, pd.DataFrame]:
    """Load the blank CVXLab input data just generated by CVXLab."""

    input_dir = dest_dir / cl.Defaults.ConfigFiles.INPUT_DATA_DIR
    if multiple_input_files:
        files = sorted(input_dir.glob(f"*.{file_extension}"))
        if not files:
            raise FileNotFoundError(
                f"No CVXLab input files with extension '.{file_extension}' found in '{input_dir}'."
            )
        data = {}
        for file_path in files:
            if file_extension == "csv":
                data[file_path.stem] = pd.read_csv(file_path)
            else:
                data[file_path.stem] = pd.read_excel(file_path)
        return data

    input_file = input_dir / _single_input_file_name(file_extension)
    if file_extension != "xlsx":
        raise NotImplementable(
            "Single-file CVXLab input mode is currently supported only for xlsx files."
        )
    return pd.read_excel(input_file, sheet_name=None)


def _write_input_data_files(
    *,
    dest_dir: Path,
    input_data: dict[str, pd.DataFrame],
    file_extension: str,
    multiple_input_files: bool,
) -> None:
    """Persist MARIO-updated CVXLab input data in the format expected by the model."""

    input_dir = dest_dir / cl.Defaults.ConfigFiles.INPUT_DATA_DIR
    if multiple_input_files:
        for table_name, frame in input_data.items():
            output_file = input_dir / f"{table_name}.{file_extension}"
            if file_extension == "csv":
                frame.to_csv(output_file, index=False)
            elif file_extension == "xlsx":
                with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                    frame.to_excel(writer, sheet_name=table_name, index=False)
            else:
                raise WrongInput(f"Unsupported CVXLab input data file type '{file_extension}'.")
        return

    if file_extension != "xlsx":
        raise NotImplementable(
            "Single-file CVXLab input mode is currently supported only for xlsx files."
        )
    input_file = input_dir / _single_input_file_name(file_extension)
    with pd.ExcelWriter(input_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        for sheet_name, frame in input_data.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


def _single_input_file_name(file_extension: str) -> str:
    """Return the single input-data filename for old and new CVXLab defaults."""

    config = cl.Defaults.ConfigFiles
    file_name = getattr(config, "INPUT_DATA_FILE", None)
    if file_name:
        stem = Path(file_name).stem
        return f"{stem}.{file_extension}"

    file_name = getattr(config, "INPUT_DATA_FILE_NAME", "input_data")
    return f"{file_name}.{file_extension}"


def _rename_flat_columns(frame: pd.DataFrame, set_map: dict[str, str]) -> pd.DataFrame:
    """Translate MARIO flat headers into the CVXLab naming convention."""

    renamed = frame.rename(columns=set_map).rename(columns={"Value": "values"})
    renamed.columns = [f"{column}_Name" if column != "values" else column for column in renamed.columns]
    return renamed


def _merge_cvxlab_input_table(
    base: pd.DataFrame,
    updates: pd.DataFrame,
    *,
    join_cols: list[str] | None = None,
    table_name: str | None = None,
) -> pd.DataFrame:
    """Overlay MARIO values on one blank CVXLab input table."""

    if join_cols is None:
        join_cols = [column for column in updates.columns if column in base.columns and column != "values"]

    missing_coordinate_cols = [
        column
        for column in updates.columns
        if column not in base.columns and column not in {"values", "scenarios_Name"}
    ]
    if join_cols and missing_coordinate_cols and updates.duplicated(subset=join_cols).any():
        target = f" '{table_name}'" if table_name else ""
        missing = ", ".join(sorted(missing_coordinate_cols))
        raise NotImplementable(
            "The installed CVXLab build generated an input table"
            f"{target} without the coordinates required by MARIO's split bridge: {missing}. "
            "This CVXLab model/database layout is incompatible with the current split workflow."
        )

    merged = base.merge(updates[join_cols + ["values"]], on=join_cols, how="left")
    if "values_x" in merged.columns and "values_y" in merged.columns:
        merged = merged.drop(columns=["values_x"]).rename(columns={"values_y": "values"})
    return merged


def _split_parent_lookup(instance) -> dict[str, str]:
    """Return the child->parent map used by the split optimization model."""

    parent_column = instance.add_sectors_master.filter(like=f"Parent {MI['s']}").columns[0]
    mapping = dict(
        zip(
            instance.add_sectors_master[MI["s"]].astype(str),
            instance.add_sectors_master[parent_column].fillna("").astype(str),
        )
    )
    for parent in set(mapping.values()):
        if parent:
            mapping[parent] = parent
    return mapping


def _parse_split_results(dest_dir: Path, flat_matrices: dict[str, pd.DataFrame], residue=None) -> dict[str, pd.DataFrame]:
    """Parse optimized split results back into MARIO matrices."""

    conn = sqlite3.connect(Path(dest_dir) / cl.Defaults.ConfigFiles.SQLITE_DATABASE_FILE)
    db_Z_supply = pd.read_sql_query("SELECT * FROM Z_supply", conn).drop(columns=["id"])
    db_Z_use = pd.read_sql_query("SELECT * FROM Z_use", conn).drop(columns=["id"])
    db_Y = pd.read_sql_query("SELECT * FROM Y", conn).drop(columns=["id"])
    db_V = pd.read_sql_query("SELECT * FROM V", conn).drop(columns=["id"])
    conn.close()

    #Remove values below the residue threshold, if specified.
    if residue is not None:
        print(f"Applying residue threshold: {residue}")
        threshold = float(residue)
        db_Z_supply["values"] = db_Z_supply["values"].where(db_Z_supply["values"] >= threshold, 0)
        db_Z_use["values"] = db_Z_use["values"].where(db_Z_use["values"] >= threshold, 0)
        db_Y["values"] = db_Y["values"].where(db_Y["values"] >= threshold, 0)
        db_V["values"] = db_V["values"].where(db_V["values"] >= threshold, 0)

    mapping = pd.read_excel(Path(dest_dir) / "mapping.xlsx", sheet_name=None, index_col=0)
    set_map = dict(zip(mapping["sets"].index.to_list(), mapping["sets"]["cvxlab"]))
    sets = pd.read_excel(Path(dest_dir) / cl.Defaults.ConfigFiles.SETS_FILE, sheet_name=None)
    sectors_df = sets["_set_SECTOR_FROM"]
    sectors_stable = sectors_df[sectors_df["sector_from_category"] == "stable"]["sector_from_Name"].tolist()
    sector_order = sectors_df["sector_from_Name"].tolist()

    available_scenarios = set(flat_matrices["Z"]["Scenario"].unique())
    scenario_to_extract = "original" if "original" in available_scenarios else "baseline"
    flat_Zold = _rename_flat_columns(
        flat_matrices["Z"].query("Scenario == @scenario_to_extract").drop(columns=["Scenario"]).copy(),
        set_map,
    )

    Znew = pd.concat(
        [
            db_Z_supply,
            db_Z_use,
            flat_Zold[
                flat_Zold["sector_from_Name"].isin(sectors_stable)
                & flat_Zold["sector_to_Name"].isin(sectors_stable)
            ],
        ],
        ignore_index=True,
    )
    Znew = Znew.set_index(
        ["region_from_Name", "sector_from_Name", "region_to_Name", "sector_to_Name"]
    )["values"].unstack(["region_to_Name", "sector_to_Name"])
    Znew.index = pd.MultiIndex.from_tuples(
        [(idx[0], MI["s"], idx[1]) for idx in Znew.index],
        names=["Region", "Level", "Item"],
    )
    Znew.columns = pd.MultiIndex.from_tuples(
        [(col[0], MI["s"], col[1]) for col in Znew.columns],
        names=["Region", "Level", "Item"],
    )
    Znew = Znew.reindex(
        columns=sorted(
            Znew.columns,
            key=lambda x: (x[0], sector_order.index(x[2]) if x[2] in sector_order else float("inf")),
        )
    )

    flat_Yold = _rename_flat_columns(
        flat_matrices["Y"].query("Scenario == @scenario_to_extract").drop(columns=["Scenario"]).copy(),
        set_map,
    )
    Ynew = pd.concat(
        [
            db_Y,
            flat_Yold[flat_Yold["sector_from_Name"].isin(sectors_stable)],
        ],
        ignore_index=True,
    )
    Ynew = Ynew.set_index(
        ["region_from_Name", "sector_from_Name", "region_to_Name", "cons_categ_Name"]
    )["values"].unstack(["region_to_Name", "cons_categ_Name"])
    Ynew.index = pd.MultiIndex.from_tuples(
        [(idx[0], MI["s"], idx[1]) for idx in Ynew.index],
        names=["Region", "Level", "Item"],
    )
    Ynew.columns = pd.MultiIndex.from_tuples(
        [(col[0], MI["n"], col[1]) for col in Ynew.columns],
        names=["Region", "Level", "Item"],
    )

    flat_V = _rename_flat_columns(
        flat_matrices["V"].query("Scenario == @scenario_to_extract").drop(columns=["Scenario"]).copy(),
        set_map,
    )
    if "values" not in flat_V.columns and "Value" in flat_V.columns:
        flat_V = flat_V.rename(columns={"Value": "values"})
    V = pd.concat(
        [
            db_V.rename(columns={"factor_Name": "Factor_of_production"}),
            flat_V[
                flat_V["sector_to_Name"].isin(sectors_stable)
            ].rename(
                columns={
                    "factor_Name": "Factor_of_production",
                }
            ),
        ],
        ignore_index=True,
    )
    V = V.set_index(["Factor_of_production", "region_to_Name", "sector_to_Name"])["values"].unstack(
        ["region_to_Name", "sector_to_Name"]
    )
    V.index.name = "Item"
    V.columns = pd.MultiIndex.from_tuples(
        [(col[0], MI["s"], col[1]) for col in V.columns],
        names=["Region", "Level", "Item"],
    )
    V = V.reindex(
        columns=sorted(
            V.columns,
            key=lambda x: (x[0], sector_order.index(x[2]) if x[2] in sector_order else float("inf")),
        )
    )

    return {
        _ENUM["Z"]: Znew,
        _ENUM["Y"]: Ynew,
        _ENUM["V"]: V,
    }
