"""Direct parsers for the EXIOBASE 3.3.18 hybrid HSUT and HIOT layouts."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.model.conventions import _MASTER_INDEX
from mario.utils import delete_duplicates, rename_index, sort_frames

logger = logging.getLogger(__name__)

HYBRID_SOURCE = (
    "Merciai, Stefano, & Schmidt, Jannick. (2021). "
    "EXIOBASE HYBRID v3 - 2011 (3.3.18) [Data set]. Zenodo. "
    "https://doi.org/10.5281/zenodo.7244919"
)

_HYBRID_SUT_EXTENSION_FILES = {
    "resource": {"activity": "resource_act", "final_demand": "resource_FD", "index_depth": 2},
    "Land": {"activity": "Land_act", "final_demand": "Land_FD", "index_depth": 2},
    "Emiss": {"activity": "Emiss_act", "final_demand": "Emiss_FD", "index_depth": 3},
    "Emis_unreg_w": {"activity": "Emis_unreg_w_act", "final_demand": "Emis_unreg_w_FD", "index_depth": 3},
    "Unreg_w": {"activity": "Unreg_w_act", "final_demand": "Unreg_w_FD", "index_depth": 2},
    "waste_sup": {"activity": "waste_sup_act", "final_demand": "waste_sup_FD", "index_depth": 2},
    "waste_use": {"activity": "waste_use_act", "final_demand": "waste_use_FD", "index_depth": 2},
    "pack_sup_waste": {"activity": "pack_sup_waste_act", "final_demand": "pack_sup_waste_fd", "index_depth": 2},
    "pack_use_waste": {"activity": "pack_use_waste_act", "final_demand": "pack_use_waste_fd", "index_depth": 2},
    "mach_sup_waste": {"activity": "mach_sup_waste_act", "final_demand": "mach_sup_waste_fd", "index_depth": 2},
    "mach_use_waste": {"activity": "mach_use_waste_act", "final_demand": "mach_use_waste_fd", "index_depth": 2},
    "stock_addition": {"activity": "stock_addition_act", "final_demand": "stock_addition_fd", "index_depth": 2},
    "crop_res": {"activity": "crop_res_act", "final_demand": "crop_res_FD", "index_depth": 2},
}

_HYBRID_IOT_EXTENSION_FILES = {
    key: value
    for key, value in _HYBRID_SUT_EXTENSION_FILES.items()
    if key != "Unreg_w"
}


@dataclass(frozen=True)
class ExiobaseHybridLayout:
    """Filesystem layout and metadata for one EXIOBASE hybrid bundle."""

    root: Path
    year: int = 2011
    version: str = "3.3.18"

    @property
    def source(self) -> str:
        """Return the canonical citation string used in MARIO metadata."""
        return HYBRID_SOURCE


def detect_exiobase_hybrid_layout(path: str | Path) -> ExiobaseHybridLayout:
    """Validate one EXIOBASE hybrid bundle directory."""
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise WrongInput("EXIOBASE hybrid parsing expects a directory path.")

    layout = ExiobaseHybridLayout(root=root)
    log_time(
        logger,
        f"Parser: detected EXIOBASE hybrid layout version={layout.version} year={layout.year}.",
        "debug",
    )
    return layout


def _require_files(root: Path, file_names: tuple[str, ...], *, label: str) -> None:
    """Require a set of files for one parser branch."""
    missing = [name for name in file_names if not (root / name).exists()]
    if missing:
        raise WrongInput(f"Missing required EXIOBASE hybrid {label} files: {missing}")


def _metadata_workbook(root: Path) -> Path:
    """Return the hybrid classification workbook under either supported filename."""
    for file_name in ("Classifications_v_3_3_18.xlsx", "metadata.xlsx"):
        candidate = root / file_name
        if candidate.exists():
            return candidate

    raise WrongInput(
        "Missing required EXIOBASE hybrid metadata workbook. "
        "Expected 'Classifications_v_3_3_18.xlsx' or 'metadata.xlsx'."
    )


def _read_hybrid_csv(path: Path) -> pd.DataFrame:
    """Read one hybrid CSV matrix with its native 5x4 EXIOBASE headers."""
    log_time(logger, f"Parser: reading {path.name}.", "debug")
    return pd.read_csv(path, index_col=[0, 1, 2, 3, 4], header=[0, 1, 2, 3]).fillna(0)


def _read_hybrid_extension_sheet(path: Path, *, sheet_name: str, index_depth: int) -> pd.DataFrame:
    """Read one hybrid extension sheet."""
    log_time(logger, f"Parser: reading sheet {sheet_name} from {path.name}.", "debug")
    return pd.read_excel(
        path,
        sheet_name=sheet_name,
        index_col=list(range(index_depth)),
        header=[0, 1, 2, 3],
    ).fillna(0)


def _drop_unnamed_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop metadata columns that are not part of the numeric matrix payload."""
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame

    keep = ~frame.columns.get_level_values(0).astype(str).str.startswith("Unnamed:")
    return frame.loc[:, keep]


def _commodity_axis(raw_axis: pd.MultiIndex) -> pd.MultiIndex:
    """Build the canonical SUT commodity axis from hybrid raw rows."""
    return pd.MultiIndex.from_arrays(
        [
            raw_axis.get_level_values(0),
            [_MASTER_INDEX["c"]] * len(raw_axis),
            raw_axis.get_level_values(1),
        ]
    )


def _activity_axis(raw_axis: pd.MultiIndex) -> pd.MultiIndex:
    """Build the canonical SUT activity axis from hybrid raw columns."""
    return pd.MultiIndex.from_arrays(
        [
            raw_axis.get_level_values(0),
            [_MASTER_INDEX["a"]] * len(raw_axis),
            raw_axis.get_level_values(1),
        ]
    )


def _sector_axis(raw_axis: pd.MultiIndex) -> pd.MultiIndex:
    """Build the canonical IOT sector axis from hybrid product rows."""
    return pd.MultiIndex.from_arrays(
        [
            raw_axis.get_level_values(0),
            [_MASTER_INDEX["s"]] * len(raw_axis),
            raw_axis.get_level_values(1),
        ]
    )


def _final_demand_axis(raw_axis: pd.MultiIndex) -> pd.MultiIndex:
    """Build the canonical final-demand axis from hybrid raw columns."""
    return pd.MultiIndex.from_arrays(
        [
            raw_axis.get_level_values(0),
            [_MASTER_INDEX["n"]] * len(raw_axis),
            raw_axis.get_level_values(1),
        ]
    )


def _unit_table_from_raw_axis(raw_axis: pd.MultiIndex, *, item_level: int, unit_level: int) -> pd.DataFrame:
    """Build one item->unit table preserving first occurrence order."""
    units: dict[str, str] = {}
    for item, unit in zip(raw_axis.get_level_values(item_level), raw_axis.get_level_values(unit_level)):
        units.setdefault(item, unit)
    return pd.DataFrame({"unit": list(units.values())}, index=pd.Index(list(units.keys())))


def _none_unit_table(items: list[str]) -> pd.DataFrame:
    """Build a ``None`` unit table for items without one meaningful unit."""
    return pd.DataFrame({"unit": ["None"] * len(items)}, index=pd.Index(items))


def _normalize_extensions(
    extensions: list[str] | tuple[str, ...] | str | None,
    *,
    available: dict[str, dict[str, object]],
) -> tuple[str, ...]:
    """Normalize one extension request against the available parser config."""
    if extensions in (None, []):
        return ()

    if extensions == "all":
        return tuple(available)

    requested = tuple(extensions)
    difference = sorted(set(requested).difference(set(available)))
    if difference:
        raise WrongInput(
            f"Following items are not valid for extensions: {difference}. "
            f"Valid items are: {sorted(available)}"
        )
    return requested


def _extension_labels_and_units(index: pd.Index | pd.MultiIndex, extension: str) -> tuple[pd.Index, list[str]]:
    """Decorate extension row labels to preserve uniqueness across extension groups."""
    if isinstance(index, pd.MultiIndex) and index.nlevels == 3:
        labels = (
            index.get_level_values(0).astype(str)
            + " ("
            + index.get_level_values(2).astype(str)
            + f" - {extension})"
        )
        units = index.get_level_values(1).astype(str).tolist()
    elif isinstance(index, pd.MultiIndex) and index.nlevels == 2:
        labels = index.get_level_values(0).astype(str) + f" ({extension})"
        units = index.get_level_values(1).astype(str).tolist()
    else:
        labels = pd.Index(index).astype(str) + f" ({extension})"
        units = ["None"] * len(labels)

    return pd.Index(labels.tolist(), name=None), units


def _empty_extensions(columns: pd.MultiIndex, fd_columns: pd.MultiIndex) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return placeholder extension blocks and units."""
    index = pd.Index(["-"], name=None)
    E = pd.DataFrame(np.zeros((1, len(columns))), index=index, columns=columns)
    EY = pd.DataFrame(np.zeros((1, len(fd_columns))), index=index, columns=fd_columns)
    units = pd.DataFrame({"unit": ["None"]}, index=index)
    return E, EY, units


def _parse_extension_bundle(
    workbook: Path,
    *,
    configs: dict[str, dict[str, object]],
    requested: tuple[str, ...],
    raw_activity_columns: pd.MultiIndex,
    activity_columns: pd.MultiIndex,
    raw_fd_columns: pd.MultiIndex,
    final_demand_columns: pd.MultiIndex,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Parse selected extension sheets from one hybrid workbook."""
    if not requested:
        return _empty_extensions(activity_columns, final_demand_columns)

    E_frames: list[pd.DataFrame] = []
    EY_frames: list[pd.DataFrame] = []
    unit_labels: list[str] = []
    unit_values: list[str] = []

    for extension in requested:
        config = configs[extension]
        act = _read_hybrid_extension_sheet(
            workbook,
            sheet_name=config["activity"],
            index_depth=config["index_depth"],
        )
        fd = _read_hybrid_extension_sheet(
            workbook,
            sheet_name=config["final_demand"],
            index_depth=config["index_depth"],
        )

        act = act.reindex(columns=raw_activity_columns, fill_value=0)
        act.columns = activity_columns
        fd = fd.reindex(columns=raw_fd_columns, fill_value=0)
        fd.columns = final_demand_columns

        labels, units = _extension_labels_and_units(act.index, extension)
        act.index = labels
        fd.index = labels

        E_frames.append(act)
        EY_frames.append(fd)
        unit_labels.extend(labels.tolist())
        unit_values.extend(units)

    units = pd.DataFrame({"unit": unit_values}, index=pd.Index(unit_labels))
    E = pd.concat(E_frames, axis=0)
    EY = pd.concat(EY_frames, axis=0)
    return E, EY, units


def _parse_value_added(
    root: Path,
    *,
    raw_activity_columns: pd.MultiIndex,
    target_columns: pd.MultiIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse the hybrid HIOT ``VA_act`` sheet and map its row labels and units."""
    workbook = root / "MR_HIOT_2011_v3_3_18_extensions.xlsx"
    metadata = _metadata_workbook(root)

    if not workbook.exists():
        V = pd.DataFrame(np.zeros((1, len(target_columns))), index=["-"], columns=target_columns)
        units = pd.DataFrame({"unit": ["None"]}, index=["-"])
        log_time(
            logger,
            "Parser: hybrid value added metadata is missing; using placeholder V block.",
            "warning",
        )
        return V, units

    va = pd.read_excel(workbook, sheet_name="VA_act", index_col=[0], header=[0, 1, 2, 3]).fillna(0)
    va = _drop_unnamed_columns(va).reindex(columns=raw_activity_columns, fill_value=0)
    va.columns = target_columns

    value_added_meta = pd.read_excel(metadata, sheet_name="Value_added")
    labels = dict(zip(value_added_meta["Code 1"], value_added_meta["Category name"]))
    units = dict(zip(value_added_meta["Code 1"], value_added_meta["Unit"]))

    row_labels = [labels.get(code, code) for code in va.index]
    row_units = [units.get(code, "None") for code in va.index]

    va.index = pd.Index(row_labels)
    unit_table = pd.DataFrame({"unit": row_units}, index=pd.Index(row_labels))
    return va, unit_table


def _read_principal_product_axis(root: Path, raw_activity_columns: pd.MultiIndex) -> pd.MultiIndex:
    """Read the activity->product correspondence used by the hybrid HIOT."""
    principal = pd.read_csv(root / "MR_HIOT_2011_v3_3_18_principal_production.csv", header=[0, 1, 2, 3])
    if principal.shape[1] != len(raw_activity_columns):
        raise WrongInput("The hybrid principal production file does not match the HIOT columns.")

    mapped = pd.MultiIndex.from_arrays(
        [
            raw_activity_columns.get_level_values(0),
            principal.iloc[0].tolist(),
            principal.iloc[1].tolist(),
            principal.iloc[2].tolist(),
            principal.iloc[3].tolist(),
        ]
    )
    return mapped


def parse_exiobase_hybrid_sut(
    path: str | Path,
    *,
    extensions: list[str] | tuple[str, ...] | str | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], ExiobaseHybridLayout]:
    """Parse the EXIOBASE 3.3.18 hybrid HSUT into split-native MARIO blocks."""
    layout = detect_exiobase_hybrid_layout(path)
    _require_files(
        layout.root,
        (
            "MR_HSUP_2011_v3_3_18.csv",
            "MR_HUSE_2011_v3_3_18.csv",
            "MR_HSUTs_2011_v3_3_18_FD.csv",
            "MR_HSUTs_2011_v3_3_18_extensions.xlsx",
            "MR_HIOT_2011_v3_3_18_extensions.xlsx",
        ),
        label="HSUT",
    )
    _metadata_workbook(layout.root)
    requested_extensions = _normalize_extensions(extensions, available=_HYBRID_SUT_EXTENSION_FILES)
    log_time(logger, f"Parser: reading EXIOBASE hybrid HSUT from {layout.root}.", "info")

    supply = _read_hybrid_csv(layout.root / "MR_HSUP_2011_v3_3_18.csv")
    use = _read_hybrid_csv(layout.root / "MR_HUSE_2011_v3_3_18.csv")
    final_demand = _read_hybrid_csv(layout.root / "MR_HSUTs_2011_v3_3_18_FD.csv")

    commodity_axis = _commodity_axis(use.index)
    activity_axis = _activity_axis(supply.columns)
    final_demand_axis = _final_demand_axis(final_demand.columns)

    U = use.copy()
    U.index = commodity_axis
    U.columns = activity_axis

    S = supply.copy().T
    S.index = activity_axis
    S.columns = commodity_axis

    Yc = final_demand.copy()
    Yc.index = commodity_axis
    Yc.columns = final_demand_axis

    Ya = pd.DataFrame(np.zeros((len(activity_axis), len(final_demand_axis))), index=activity_axis, columns=final_demand_axis)

    Va, factor_units = _parse_value_added(
        layout.root,
        raw_activity_columns=supply.columns,
        target_columns=activity_axis,
    )
    Vc = pd.DataFrame(np.zeros((len(Va.index), len(commodity_axis))), index=Va.index, columns=commodity_axis)

    Ea, EY, extension_units = _parse_extension_bundle(
        layout.root / "MR_HSUTs_2011_v3_3_18_extensions.xlsx",
        configs=_HYBRID_SUT_EXTENSION_FILES,
        requested=requested_extensions,
        raw_activity_columns=supply.columns,
        activity_columns=activity_axis,
        raw_fd_columns=final_demand.columns,
        final_demand_columns=final_demand_axis,
    )
    Ec = pd.DataFrame(np.zeros((len(Ea.index), len(commodity_axis))), index=Ea.index, columns=commodity_axis)

    matrices = {
        "baseline": {
            "U": U,
            "S": S,
            "Ya": Ya,
            "Yc": Yc,
            "Va": Va,
            "Vc": Vc,
            "Ea": Ea,
            "Ec": Ec,
            "EY": EY,
        }
    }

    activity_items = delete_duplicates(list(activity_axis.get_level_values(2)))
    commodity_items = delete_duplicates(list(commodity_axis.get_level_values(2)))
    units = {
        _MASTER_INDEX["a"]: _none_unit_table(activity_items),
        _MASTER_INDEX["c"]: _unit_table_from_raw_axis(use.index, item_level=1, unit_level=4),
        _MASTER_INDEX["f"]: factor_units,
        _MASTER_INDEX["k"]: extension_units,
    }
    indeces = {
        "r": {"main": delete_duplicates(list(commodity_axis.get_level_values(0)))},
        "n": {"main": delete_duplicates(list(final_demand_axis.get_level_values(2)))},
        "k": {"main": list(Ea.index)},
        "f": {"main": list(Va.index)},
        "a": {"main": activity_items},
        "c": {"main": commodity_items},
        "s": {"main": activity_items + commodity_items},
    }

    rename_index(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: EXIOBASE hybrid HSUT parsed with "
            f"{len(activity_items)} activities, "
            f"{len(commodity_items)} commodities, "
            f"{len(Va.index)} factor rows and "
            f"{len(Ea.index)} extension rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout


def parse_exiobase_hybrid_iot(
    path: str | Path,
    *,
    extensions: list[str] | tuple[str, ...] | str | None = None,
) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict[str, list[str]]], dict[str, pd.DataFrame], ExiobaseHybridLayout]:
    """Parse the EXIOBASE 3.3.18 hybrid HIOT into unified MARIO IOT blocks."""
    layout = detect_exiobase_hybrid_layout(path)
    _require_files(
        layout.root,
        (
            "MR_HIOT_2011_v3_3_18_by_product_technology.csv",
            "MR_HIOT_2011_v3_3_18_FD.csv",
            "MR_HIOT_2011_v3_3_18_principal_production.csv",
            "MR_HIOT_2011_v3_3_18_extensions.xlsx",
        ),
        label="HIOT",
    )
    _metadata_workbook(layout.root)
    requested_extensions = _normalize_extensions(extensions, available=_HYBRID_IOT_EXTENSION_FILES)
    log_time(logger, f"Parser: reading EXIOBASE hybrid HIOT from {layout.root}.", "info")

    Z = _read_hybrid_csv(layout.root / "MR_HIOT_2011_v3_3_18_by_product_technology.csv")
    Y = _read_hybrid_csv(layout.root / "MR_HIOT_2011_v3_3_18_FD.csv")
    raw_product_index = Z.index

    mapped_product_columns = _read_principal_product_axis(layout.root, Z.columns)
    if not mapped_product_columns.equals(raw_product_index):
        raise WrongInput("The hybrid principal production mapping does not match the HIOT product axis.")

    sector_axis = _sector_axis(raw_product_index)
    final_demand_axis = _final_demand_axis(Y.columns)

    V, factor_units = _parse_value_added(
        layout.root,
        raw_activity_columns=Z.columns,
        target_columns=sector_axis,
    )
    E, EY, extension_units = _parse_extension_bundle(
        layout.root / "MR_HIOT_2011_v3_3_18_extensions.xlsx",
        configs=_HYBRID_IOT_EXTENSION_FILES,
        requested=requested_extensions,
        raw_activity_columns=Z.columns,
        activity_columns=sector_axis,
        raw_fd_columns=Y.columns,
        final_demand_columns=final_demand_axis,
    )

    Z.index = sector_axis
    Z.columns = sector_axis
    Y.index = sector_axis
    Y.columns = final_demand_axis
    V.columns = sector_axis
    E.columns = sector_axis
    EY.columns = final_demand_axis

    matrices = {"baseline": {"Z": Z, "V": V, "E": E, "Y": Y, "EY": EY}}
    sector_items = delete_duplicates(list(sector_axis.get_level_values(2)))
    units = {
        _MASTER_INDEX["s"]: _unit_table_from_raw_axis(raw_product_index, item_level=1, unit_level=4),
        _MASTER_INDEX["f"]: factor_units,
        _MASTER_INDEX["k"]: extension_units,
    }
    indeces = {
        "r": {"main": delete_duplicates(list(sector_axis.get_level_values(0)))},
        "n": {"main": delete_duplicates(list(final_demand_axis.get_level_values(2)))},
        "k": {"main": list(E.index)},
        "f": {"main": list(V.index)},
        "s": {"main": sector_items},
    }

    rename_index(matrices["baseline"])
    sort_frames(matrices["baseline"])
    log_time(
        logger,
        (
            "Parser: EXIOBASE hybrid HIOT parsed with "
            f"{len(sector_items)} sectors, "
            f"{len(V.index)} factor rows and "
            f"{len(E.index)} extension rows."
        ),
        "info",
    )
    return matrices, indeces, units, layout
