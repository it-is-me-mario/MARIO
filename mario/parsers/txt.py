"""Internal TXT parser built on top of the shared normalizer."""

from __future__ import annotations

from pathlib import Path
import logging

import pandas as pd

from mario.log_exc.logger import log_time
from mario.internal import ModelState
from mario.log_exc.exceptions import WrongInput
from mario.parsers.api import build_parser_state
from mario.parsers.base import BaseParser
from mario.parsers.matrix_layouts import (
    build_iot_indexes_from_units_and_y,
    build_sut_indexes_from_units_and_y,
    interpret_axis_tokens,
    interpret_iot_axis,
    interpret_iot_final_demand_tokens,
    iot_axis_names,
    iot_block_specs_for_matrix_layouts,
    iot_units_from_frame,
    normalize_matrix_layouts,
    sut_axis_names,
    sut_block_specs_for_matrix_layouts,
    sut_units_from_frame,
)
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.views import concat_sut_E, concat_sut_V, concat_sut_Y, concat_sut_Z, concat_sut_e, concat_sut_v, concat_sut_z
from mario.parsers.registry import register_parser
from mario.ops.export_specs import (
    FLAT_AXIS_SETS,
    FLAT_DATA_COLUMNS,
    FLAT_UNIT_COLUMNS,
    LEGACY_FLAT_DATA_COLUMNS,
)
from mario.model.conventions import _MASTER_INDEX
from mario.storage.base import BlockRepository
from mario.parsers.tabular import (
    TEXT_BUNDLE_FORMATS,
    detect_text_bundle_format,
    get_index_txt,
    get_units,
    normalize_text_bundle_format,
    rename_index,
    sort_frames,
    txt_parser,
)

logger = logging.getLogger(__name__)


_FLAT_FLOW_MATRICES = ("Z", "Y", "V", "E", "EY", "VY")
_FLAT_COEFFICIENT_MATRICES = ("z", "Y", "v", "e", "EY", "VY")
_FLAT_REQUIRED_FLOW_MATRICES = ("Z", "Y", "V", "E", "EY")
_FLAT_REQUIRED_COEFFICIENT_MATRICES = ("z", "Y", "v", "e", "EY")
_FLAT_ROW_SIMPLE = {"V", "v", "E", "e", "EY", "VY"}


def _flat_matrix_names_for_mode(mode: str) -> tuple[str, ...]:
    """Return the flat matrix names expected for one parser mode."""
    return _FLAT_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_FLOW_MATRICES


def _resolve_text_bundle_root(path: str | Path, mode: str) -> Path:
    """Resolve one text bundle root, auto-entering the mode subfolder when present."""
    root = Path(path)
    if root.name.lower() == mode:
        return root

    candidate = root / mode
    if candidate.is_dir():
        return candidate

    return root


def _find_flat_payload(path: Path, stem: str, suffixes: set[str]) -> Path:
    """Resolve one flat payload file by stem regardless of file extension."""
    candidates = [
        item
        for item in path.iterdir()
        if item.is_file() and item.stem == stem and item.suffix in suffixes
    ]
    if not candidates:
        expected = ", ".join(sorted(suffixes))
        raise FileNotFoundError(f"No {stem!r} payload found in {path} with suffixes {expected}.")
    if len(candidates) > 1:
        raise ValueError(f"More than one flat payload matches {stem!r}: {candidates}")
    return candidates[0]


def _allowed_text_suffixes(_format: str | None) -> set[str]:
    """Return the allowed file suffixes for one text parser request."""
    normalized = normalize_text_bundle_format(_format)
    if normalized is None:
        return {f".{suffix}" for suffix in TEXT_BUNDLE_FORMATS}
    return {f".{normalized}"}


def _flat_axis_columns(side: str) -> list[str]:
    """Return the canonical column names for one flat axis."""
    suffix = "from" if side == "from" else "to"
    return [f"{item}_{suffix}" for item in FLAT_AXIS_SETS]


def _legacy_flat_axis_columns(side: str) -> list[str]:
    """Return the legacy flat column names for one axis."""
    suffix = "from" if side == "from" else "to"
    return [f"Region_{suffix}", f"Level_{suffix}", f"Item_{suffix}"]


def _compact_flat_tokens(values) -> tuple[object, ...]:
    """Drop empty placeholders from one flat axis tuple."""
    compact = []
    for value in values:
        if value == "" or pd.isna(value):
            continue
        compact.append(value)
    return tuple(compact)


def _coerce_legacy_flat_data(data: pd.DataFrame) -> pd.DataFrame:
    """Map the historical flat schema to the new set-specific schema."""
    renamed = data[["Scenario", "Matrix", "Value"]].copy()
    for side in ("from", "to"):
        for set_name in FLAT_AXIS_SETS:
            renamed[f"{set_name}_{side}"] = ""

        legacy_columns = _legacy_flat_axis_columns(side)
        for idx, row in data[legacy_columns].iterrows():
            region, level_name, item = row.tolist()
            if region not in ("", None) and not pd.isna(region):
                renamed.at[idx, f"{_MASTER_INDEX['r']}_{side}"] = region
            if level_name in ("", None) or pd.isna(level_name):
                level_name = _infer_legacy_level_name(data.at[idx, "Matrix"], side)
            if level_name not in ("", None) and not pd.isna(level_name):
                renamed.at[idx, f"{level_name}_{side}"] = item

    return renamed[list(FLAT_DATA_COLUMNS)]


def _coerce_sparse_flat_data(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize one set-specific flat payload that only includes a subset of sets."""
    required = {"Scenario", "Matrix", "Value"}
    valid_axis = {
        f"{set_name}_{side}"
        for set_name in FLAT_AXIS_SETS
        for side in ("from", "to")
    }

    columns = set(data.columns)
    if not required.issubset(columns):
        raise ValueError(
            f"Flat data file should expose at least {sorted(required)}, got {list(data.columns)}."
        )

    extra = sorted(columns.difference(required).difference(valid_axis))
    if extra:
        raise ValueError(
            f"Flat data file exposes unsupported columns {extra}. "
            f"Valid set-specific columns are {sorted(valid_axis)}."
        )

    normalized = data.copy()
    for column in FLAT_DATA_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""

    return normalized[list(FLAT_DATA_COLUMNS)]


def _read_flat_text_data(path: str, sep: str, *, _format: str | None, mode: str) -> pd.DataFrame:
    """Read one flat text payload from either ``data.*`` or per-matrix files."""
    root = Path(path)
    suffixes = _allowed_text_suffixes(_format)

    try:
        data_path = _find_flat_payload(root, "data", suffixes)
    except FileNotFoundError:
        frames = []
        for matrix_name in _flat_matrix_names_for_mode(mode):
            try:
                matrix_path = _find_flat_payload(root, matrix_name, suffixes)
            except FileNotFoundError:
                continue
            frames.append(pd.read_csv(matrix_path, sep=sep, keep_default_na=False))
        if not frames:
            expected = ", ".join(sorted(suffixes))
            raise FileNotFoundError(
                f"No flat payload found in {path!r}. Expected either data.* or one or more matrix files with suffixes {expected}."
            )
        return pd.concat(frames, ignore_index=True, sort=False)

    return pd.read_csv(data_path, sep=sep, keep_default_na=False)


def _read_flat_text_frames(path: str, sep: str, *, _format: str | None, mode: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the flat long-format data and unit tables."""
    root = Path(path)
    suffixes = _allowed_text_suffixes(_format)
    units_path = _find_flat_payload(root, "units", suffixes)

    data = _read_flat_text_data(path, sep, _format=_format, mode=mode)
    units = pd.read_csv(units_path, sep=sep, keep_default_na=False)

    expected_data = list(FLAT_DATA_COLUMNS)
    legacy_data = list(LEGACY_FLAT_DATA_COLUMNS)
    expected_units = list(FLAT_UNIT_COLUMNS)
    if list(data.columns) == legacy_data:
        data = _coerce_legacy_flat_data(data)
    else:
        try:
            data = _coerce_sparse_flat_data(data)
        except ValueError as exc:
            if list(data.columns) == expected_data:
                pass
            else:
                raise ValueError(
                    f"Flat data file should expose columns {expected_data}, one valid subset of them, "
                    f"or legacy {legacy_data}. Got {list(data.columns)}."
                ) from exc
    if list(data.columns) != expected_data:
        raise ValueError(
            f"Flat data normalization should produce columns {expected_data}, got {list(data.columns)}."
        )
    if list(units.columns) != expected_units:
        raise ValueError(f"Flat units file should expose columns {expected_units}, got {list(units.columns)}.")
    return data, units


def _reindex_from_ordered_tuples(frame: pd.DataFrame, rows: list[tuple], columns: list[tuple]) -> pd.DataFrame:
    """Reindex one pivoted flat matrix to preserve file order."""
    row_index = pd.MultiIndex.from_tuples(rows, names=_flat_axis_columns("from"))
    column_index = pd.MultiIndex.from_tuples(columns, names=_flat_axis_columns("to"))
    return frame.reindex(index=row_index, columns=column_index)


def _final_demand_expected_names(subset: pd.DataFrame, *, side: str) -> tuple[str, ...]:
    """Return the semantic final-demand axis names for one flat subset."""
    region_column = f"{_MASTER_INDEX['r']}_{side}"
    if region_column in subset.columns and subset[region_column].replace("", pd.NA).dropna().empty:
        return (_MASTER_INDEX["n"],)
    return (_MASTER_INDEX["r"], _MASTER_INDEX["n"])


def _infer_legacy_level_name(matrix_name: str, side: str) -> str:
    """Infer one missing legacy ``Level`` marker from matrix semantics."""
    if side == "from":
        if matrix_name in {"V", "v", "VY"}:
            return _MASTER_INDEX["f"]
        if matrix_name in {"E", "e", "EY"}:
            return _MASTER_INDEX["k"]
        if matrix_name in {"Z", "z", "Y"}:
            return _MASTER_INDEX["s"]
    else:
        if matrix_name in {"Y", "EY", "VY"}:
            return _MASTER_INDEX["n"]
        if matrix_name in {"Z", "z", "V", "v", "E", "e"}:
            return _MASTER_INDEX["s"]
    return ""


def _tuple_from_set_columns(
    row: pd.Series,
    expected_names: tuple[str, ...],
    *,
    side: str,
    borrow_from_other_side: bool = False,
) -> tuple[object, ...]:
    """Collect axis values from set-specific flat columns following expected semantic order."""
    values = []
    other_side = "to" if side == "from" else "from"
    for name in expected_names:
        column = f"{name}_{side}"
        value = row[column] if column in row else ""
        if (value == "" or pd.isna(value)) and borrow_from_other_side:
            other_column = f"{name}_{other_side}"
            other_value = row[other_column] if other_column in row else ""
            if other_value != "" and not pd.isna(other_value):
                value = other_value
        if value == "" or pd.isna(value):
            continue
        values.append(value)
    return tuple(values)


def _nonempty_flat_axis_tokens(row: pd.Series, *, side: str) -> list[tuple[str, object]]:
    """Return the non-empty set/value pairs present on one flat axis."""
    tokens = []
    for set_name in FLAT_AXIS_SETS:
        column = f"{set_name}_{side}"
        value = row[column] if column in row else ""
        if value == "" or pd.isna(value):
            continue
        tokens.append((set_name, value))
    return tokens


def _legacy_public_axis_label(row: pd.Series, *, side: str, matrix_name: str):
    """Convert one set-specific flat axis back to the public MARIO layout."""
    tokens = _nonempty_flat_axis_tokens(row, side=side)
    if not tokens:
        raise WrongInput(
            f"Flat payload axis {side!r} for matrix {matrix_name!r} does not contain any set values."
        )

    if len(tokens) == 1:
        set_name, value = tokens[0]
        if (side == "from" and matrix_name in _FLAT_ROW_SIMPLE) or (
            side == "to" and matrix_name in {"Y", "EY", "VY"} and set_name == _MASTER_INDEX["n"]
        ):
            return value
        return (set_name, value)

    if len(tokens) == 2 and tokens[0][0] == _MASTER_INDEX["r"]:
        region, (level_name, item) = tokens[0][1], tokens[1]
        return (region, level_name, item)

    raise WrongInput(
        f"Standard flat parsing does not know how to rebuild axis {side!r} for matrix {matrix_name!r} from tokens {tokens}."
    )


def _tokens_for_expected_row(row: pd.Series, expected_names: tuple[str, ...], *, side: str) -> tuple[object, ...]:
    """Extract one flat axis tuple following the expected semantic names."""
    return tuple(
        value
        for value in (
            row[f"{name}_{side}"] if f"{name}_{side}" in row else ""
            for name in expected_names
        )
        if value != "" and not pd.isna(value)
    )


def _legacy_sut_final_demand_public(tokens: tuple[object, ...]) -> tuple[object, ...]:
    """Convert semantic final-demand tokens back to the public SUT 3-level layout."""
    semantic, semantic_names, _, _ = interpret_iot_final_demand_tokens(tokens)
    if semantic_names == ("Region", "Consumption category"):
        return (semantic[0], "Consumption category", semantic[1])
    return ("-", "Consumption category", semantic[0])


def _sut_unified_tokens_from_flat(row: pd.Series, *, side: str) -> tuple[object, ...]:
    """Extract one unified SUT productive tuple from flat set-specific columns."""
    region = row.get(f"{_MASTER_INDEX['r']}_{side}", "")
    activity = row.get(f"{_MASTER_INDEX['a']}_{side}", "")
    commodity = row.get(f"{_MASTER_INDEX['c']}_{side}", "")

    if region not in ("", None) and not pd.isna(region):
        if activity not in ("", None) and not pd.isna(activity):
            return (region, _MASTER_INDEX["a"], activity)
        if commodity not in ("", None) and not pd.isna(commodity):
            return (region, _MASTER_INDEX["c"], commodity)

    raise WrongInput(
        f"Unable to rebuild a unified SUT productive axis from flat columns on side {side!r}."
    )


def _build_public_axis(labels, *, side: str, matrix_name: str):
    """Build one public pandas axis from ordered flat labels."""
    if not labels:
        return pd.Index([], dtype=object)

    first = labels[0]
    if not isinstance(first, tuple):
        name = "Item"
        if side == "to" and matrix_name in {"Y", "EY", "VY"}:
            name = _MASTER_INDEX["n"]
        return pd.Index(labels, name=name)

    width = len(first)
    if width == 2:
        return pd.MultiIndex.from_tuples(labels, names=["Level", "Item"])
    if width == 3:
        return pd.MultiIndex.from_tuples(labels, names=[_MASTER_INDEX["r"], "Level", "Item"])

    raise WrongInput(
        f"Unsupported public flat axis arity {width} for matrix {matrix_name!r}."
    )


def _flat_matrix_to_frame(data: pd.DataFrame, matrix_name: str) -> pd.DataFrame:
    """Reconstruct one canonical legacy matrix from the flat long format."""
    subset = data.loc[data["Matrix"] == matrix_name].copy()
    if subset.empty:
        raise ValueError(f"Matrix {matrix_name!r} is not present in the flat payload.")

    subset["Value"] = pd.to_numeric(subset["Value"], errors="raise")
    subset["from_key"] = [
        _legacy_public_axis_label(row, side="from", matrix_name=matrix_name)
        for _, row in subset.iterrows()
    ]
    subset["to_key"] = [
        _legacy_public_axis_label(row, side="to", matrix_name=matrix_name)
        for _, row in subset.iterrows()
    ]

    row_order = list(dict.fromkeys(subset["from_key"].tolist()))
    column_order = list(dict.fromkeys(subset["to_key"].tolist()))

    frame = subset.pivot(index="from_key", columns="to_key", values="Value")
    frame = frame.reindex(index=row_order, columns=column_order)
    frame = frame.fillna(0)
    frame.index = _build_public_axis(row_order, side="from", matrix_name=matrix_name)
    frame.columns = _build_public_axis(column_order, side="to", matrix_name=matrix_name)
    return frame


def _flat_units_to_legacy(units: pd.DataFrame) -> pd.DataFrame:
    """Convert the flat unit table back to the historical multi-index layout."""
    values = units.copy()
    values.columns = ["level", "item", "unit"]
    values.set_index(["level", "item"], inplace=True)
    return values


def _normalize_iot_matrix(frame: pd.DataFrame, matrix_name: str, matrix_layouts: dict[str, tuple[str, ...]]) -> pd.DataFrame:
    """Normalize one IOT matrix axis layout according to ``matrix_layouts``."""
    normalized = frame.copy()
    normalized.index, _, _ = interpret_iot_axis(
        normalized.index,
        matrix_name,
        "from",
        matrix_layouts,
    )
    normalized.columns, semantic_col_names, _ = interpret_iot_axis(
        normalized.columns,
        matrix_name,
        "to",
        matrix_layouts,
    )
    if matrix_name in {"Y", "EY", "VY"}:
        return normalized, semantic_col_names
    return normalized, None


def _normalize_sut_unified_axis(index) -> pd.MultiIndex:
    """Normalize one unified SUT productive axis to ``Region/Level/Item``."""
    if not isinstance(index, pd.MultiIndex) or index.nlevels != 3:
        raise WrongInput("Unified SUT productive axes must expose three levels.")
    return pd.MultiIndex.from_tuples(index.tolist(), names=["Region", "Level", "Item"])


def _interpret_sut_extension_axis(index, matrix_name: str, matrix_layouts: dict[str, tuple[str, ...]]):
    """Interpret one SUT factor/satellite row axis under ``matrix_layouts``."""
    raw_values = index.tolist() if isinstance(index, pd.MultiIndex) else [(value,) for value in index.tolist()]
    semantic_values: list[tuple[object, ...]] = []
    public_values: list[tuple[object, ...]] = []
    semantic_names: tuple[str, ...] | None = None
    public_names: tuple[str, ...] | None = None
    expected_names = sut_axis_names(matrix_name, "from", matrix_layouts)

    for value in raw_values:
        current_semantic, current_semantic_names, current_public, current_public_names = interpret_axis_tokens(
            value,
            expected_names,
            matrix_name=matrix_name,
            side="from",
        )
        if semantic_names is None:
            semantic_names = current_semantic_names
            public_names = current_public_names
        semantic_values.append(current_semantic)
        public_values.append(current_public)

    assert semantic_names is not None
    assert public_names is not None
    if len(public_names) == 1:
        return pd.Index([value[0] for value in public_values], name=public_names[0]), semantic_names, public_names
    return pd.MultiIndex.from_tuples(public_values, names=list(public_names)), semantic_names, public_names


def _normalize_sut_matrix(frame: pd.DataFrame, matrix_name: str, matrix_layouts: dict[str, tuple[str, ...]]) -> pd.DataFrame:
    """Normalize one SUT matrix axis layout according to ``matrix_layouts``."""
    normalized = frame.copy()

    if matrix_name in {"Z", "z", "Y"}:
        normalized.index = _normalize_sut_unified_axis(normalized.index)
    elif matrix_name in {"V", "v", "VY", "E", "e", "EY"}:
        normalized.index, _, _ = _interpret_sut_extension_axis(
            normalized.index,
            matrix_name,
            matrix_layouts,
        )

    if matrix_name in {"Y", "EY", "VY"}:
        raw_values = normalized.columns.tolist() if isinstance(normalized.columns, pd.MultiIndex) else [
            (value,) for value in normalized.columns.tolist()
        ]
        public_values: list[tuple[object, ...]] = []
        public_names: tuple[str, ...] | None = None
        semantic_col_names: tuple[str, ...] | None = None
        for value in raw_values:
            current_semantic, current_semantic_names, current_public, current_public_names = (
                interpret_iot_final_demand_tokens(value)
            )
            if public_names is None:
                public_names = current_public_names
                semantic_col_names = current_semantic_names
            public_values.append(current_public)

        assert public_names is not None
        assert semantic_col_names is not None
        if len(public_names) == 1:
            normalized.columns = pd.Index([value[0] for value in public_values], name=public_names[0])
        else:
            normalized.columns = pd.MultiIndex.from_tuples(public_values, names=list(public_names))
        return normalized, semantic_col_names

    normalized.columns = _normalize_sut_unified_axis(normalized.columns)
    return normalized, None


_SUT_NATIVE_FLOW_MATRICES = ("U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY")
_SUT_NATIVE_REQUIRED_FLOW_MATRICES = ("U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec")
_SUT_NATIVE_COEFFICIENT_MATRICES = ("u", "s", "Ya", "Yc", "va", "vc", "ea", "ec", "EY", "VY")
_SUT_NATIVE_REQUIRED_COEFFICIENT_MATRICES = ("u", "s", "Ya", "Yc", "va", "vc", "ea", "ec")


def _sut_native_matrix_names(mode: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return native SUT matrix names for one parser mode."""
    if mode == "coefficients":
        return _SUT_NATIVE_COEFFICIENT_MATRICES, _SUT_NATIVE_REQUIRED_COEFFICIENT_MATRICES
    return _SUT_NATIVE_FLOW_MATRICES, _SUT_NATIVE_REQUIRED_FLOW_MATRICES


def _looks_like_sut_native_matrix_bundle(path: Path, *, suffixes: set[str], mode: str) -> bool:
    """Return whether one matrix-per-file bundle contains native SUT block files."""
    expected, required = _sut_native_matrix_names(mode)
    present = {
        matrix_name
        for matrix_name in expected
        if any((path / f"{matrix_name}{suffix}").exists() for suffix in suffixes)
    }
    return bool(present.intersection(required))


def _normalize_sut_native_matrix(
    frame: pd.DataFrame,
    matrix_name: str,
    matrix_layouts: dict[str, tuple[str, ...]],
) -> tuple[pd.DataFrame, tuple[str, ...] | None]:
    """Normalize one native split SUT matrix."""
    normalized = frame.copy()

    if matrix_name in {"U", "S", "u", "s", "Ya", "Yc"}:
        normalized.index = _normalize_sut_unified_axis(normalized.index)
    elif matrix_name in {"Va", "Vc", "va", "vc", "VY"}:
        normalized.index, _, _ = _interpret_sut_extension_axis(
            normalized.index,
            "V",
            matrix_layouts,
        )
    elif matrix_name in {"Ea", "Ec", "ea", "ec", "EY"}:
        normalized.index, _, _ = _interpret_sut_extension_axis(
            normalized.index,
            "E",
            matrix_layouts,
        )

    if matrix_name in {"U", "u"}:
        normalized.columns = _normalize_sut_unified_axis(normalized.columns)
        return normalized, None
    if matrix_name in {"S", "s"}:
        normalized.columns = _normalize_sut_unified_axis(normalized.columns)
        return normalized, None
    if matrix_name in {"Va", "Vc", "Ea", "Ec", "va", "vc", "ea", "ec"}:
        normalized.columns = _normalize_sut_unified_axis(normalized.columns)
        return normalized, None

    raw_values = normalized.columns.tolist() if isinstance(normalized.columns, pd.MultiIndex) else [
        (value,) for value in normalized.columns.tolist()
    ]
    public_values: list[tuple[object, ...]] = []
    public_names: tuple[str, ...] | None = None
    semantic_col_names: tuple[str, ...] | None = None
    for value in raw_values:
        current_semantic, current_semantic_names, current_public, current_public_names = (
            interpret_iot_final_demand_tokens(value)
        )
        if public_names is None:
            public_names = current_public_names
            semantic_col_names = current_semantic_names
        public_values.append(current_public)

    assert public_names is not None
    assert semantic_col_names is not None
    if len(public_names) == 1:
        normalized.columns = pd.Index([value[0] for value in public_values], name=public_names[0])
    else:
        normalized.columns = pd.MultiIndex.from_tuples(public_values, names=list(public_names))
    return normalized, semantic_col_names


def _sut_native_matrix_read_plan(matrix_name: str, matrix_layouts: dict[str, tuple[str, ...]]) -> tuple[int, tuple[int, ...], str]:
    """Return row/header parsing hints for one native SUT matrix file."""
    if matrix_name in {"U", "S", "u", "s", "Ya", "Yc"}:
        row_levels = 3
    elif matrix_name in {"Va", "Vc", "va", "vc", "VY"}:
        row_levels = len(sut_axis_names("V", "from", matrix_layouts))
    else:
        row_levels = len(sut_axis_names("E", "from", matrix_layouts))

    if matrix_name in {"Ya", "Yc", "EY", "VY"}:
        header_candidates = (1, 2, 3)
    else:
        header_candidates = (3,)
    return row_levels, header_candidates, matrix_name


def _read_sut_native_matrix_text_with_layout(
    path: Path,
    *,
    matrix_name: str,
    sep: str,
    matrix_layouts: dict[str, tuple[str, ...]],
    suffixes: set[str],
) -> tuple[pd.DataFrame, tuple[str, ...] | None]:
    """Read one native split SUT matrix text payload."""
    file_path = _find_flat_payload(path, matrix_name, suffixes)
    row_levels, header_candidates, _ = _sut_native_matrix_read_plan(matrix_name, matrix_layouts)

    attempts = []
    for index_levels in (row_levels, row_levels + 1):
        for header_levels in header_candidates:
            candidate = (index_levels, header_levels)
            if candidate not in attempts:
                attempts.append(candidate)

    last_error = None
    successful_reads: list[tuple[tuple[int, ...], pd.DataFrame, tuple[str, ...] | None]] = []
    for index_levels, header_levels in attempts:
        try:
            frame = pd.read_csv(
                file_path,
                sep=sep,
                index_col=list(range(index_levels)),
                header=list(range(header_levels)),
                keep_default_na=False,
            )
            normalized, final_demand_axis_names = _normalize_sut_native_matrix(
                frame,
                matrix_name,
                matrix_layouts,
            )
            successful_reads.append(
                (
                    (
                        len(final_demand_axis_names or ()),
                        normalized.columns.nlevels if isinstance(normalized.columns, pd.MultiIndex) else 1,
                        header_levels,
                        -abs(index_levels - row_levels),
                    ),
                    normalized,
                    final_demand_axis_names,
                )
            )
        except Exception as exc:  # pragma: no cover - diagnostic fallback path
            last_error = exc

    if successful_reads:
        successful_reads.sort(key=lambda item: item[0], reverse=True)
        _, normalized, final_demand_axis_names = successful_reads[0]
        return normalized, final_demand_axis_names

    raise WrongInput(
        f"Unable to read {file_path.name} as a native SUT matrix payload. Last parser error: {last_error}"
    )


def _build_sut_native_index_matrices(matrices: dict[str, pd.DataFrame], *, mode: str) -> dict[str, pd.DataFrame]:
    """Build temporary unified SUT matrices from native split blocks for index extraction."""
    ordering_inputs = {
        key: value
        for key, value in matrices.items()
        if key in {"U", "S", "u", "s", "Ya", "Yc", "Va", "Vc", "va", "vc", "Ea", "Ec", "ea", "ec"}
    }
    ordering = SUTUnifiedOrderingPolicy.from_blocks(**ordering_inputs)
    if mode == "coefficients":
        z_key, v_key, e_key = "z", "v", "e"
        index_matrices = {
            "z": concat_sut_z(matrices["u"], matrices["s"], ordering),
            "v": concat_sut_v(matrices["va"], matrices["vc"], ordering),
            "e": concat_sut_e(matrices["ea"], matrices["ec"], ordering),
        }
    else:
        z_key, v_key, e_key = "Z", "V", "E"
        index_matrices = {
            "Z": concat_sut_Z(matrices["U"], matrices["S"], ordering),
            "V": concat_sut_V(matrices["Va"], matrices["Vc"], ordering),
            "E": concat_sut_E(matrices["Ea"], matrices["Ec"], ordering),
        }

    ya = matrices["Ya"]
    yc = matrices["Yc"]
    index_matrices["Y"] = concat_sut_Y(ya, yc, ordering)
    index_matrices["EY"] = matrices["EY"]
    index_matrices["VY"] = matrices["VY"]
    return index_matrices


def _apply_default_sut_native_public_axes(
    matrices: dict[str, pd.DataFrame],
    units_frame: pd.DataFrame,
    *,
    matrix_layouts: dict[str, tuple[str, ...]],
) -> None:
    """Match legacy public row labels when native SUT payloads use default layouts."""
    if matrix_layouts:
        return

    factor_order = (
        units_frame.loc[["Factor of production"]].droplevel(0).index.tolist()
        if "Factor of production" in units_frame.index.get_level_values(0)
        else []
    )
    satellite_order = (
        units_frame.loc[["Satellite account"]].droplevel(0).index.tolist()
        if "Satellite account" in units_frame.index.get_level_values(0)
        else []
    )

    for matrix_name in ("Va", "Vc", "va", "vc", "VY"):
        frame = matrices.get(matrix_name)
        if frame is None or isinstance(frame.index, pd.MultiIndex):
            continue
        order = [item for item in factor_order if item in frame.index]
        if order:
            matrices[matrix_name] = frame.loc[order, :]
        matrices[matrix_name].index = pd.Index(matrices[matrix_name].index.tolist(), name="Item")

    for matrix_name in ("Ea", "Ec", "ea", "ec", "EY"):
        frame = matrices.get(matrix_name)
        if frame is None or isinstance(frame.index, pd.MultiIndex):
            continue
        order = [item for item in satellite_order if item in frame.index]
        if order:
            matrices[matrix_name] = frame.loc[order, :]
        matrices[matrix_name].index = pd.Index(matrices[matrix_name].index.tolist(), name="Item")


def parse_sut_native_text_frames_with_layouts(
    path: str,
    *,
    mode: str,
    sep: str,
    matrix_layouts: dict[str, tuple[str, ...]],
    _format: str | None = None,
):
    """Parse native split SUT matrix-per-file txt/csv payloads."""
    root = Path(path)
    suffixes = _allowed_text_suffixes(_format)
    expected_matrices, required_matrices = _sut_native_matrix_names(mode)

    matrices = {}
    final_demand_axis_names: tuple[str, ...] | None = None
    for matrix_name in expected_matrices:
        try:
            matrices[matrix_name], current_fd_axis_names = _read_sut_native_matrix_text_with_layout(
                root,
                matrix_name=matrix_name,
                sep=sep,
                matrix_layouts=matrix_layouts,
                suffixes=suffixes,
            )
            if current_fd_axis_names is not None:
                if final_demand_axis_names is None:
                    final_demand_axis_names = current_fd_axis_names
                elif final_demand_axis_names != current_fd_axis_names:
                    raise WrongInput(
                        f"Mixed semantic final-demand axes are not supported: {final_demand_axis_names} and {current_fd_axis_names}."
                    )
        except FileNotFoundError:
            if matrix_name not in required_matrices:
                continue
            raise

    extension_matrix = matrices.get("Ea", matrices.get("ea"))
    factor_matrix = matrices.get("Va", matrices.get("va"))
    final_demand_matrix = matrices["Ya"] if "Ya" in matrices else matrices["Yc"]
    if "EY" not in matrices:
        matrices["EY"] = pd.DataFrame(0, index=extension_matrix.index, columns=final_demand_matrix.columns)
    if "VY" not in matrices:
        matrices["VY"] = pd.DataFrame(0, index=factor_matrix.index, columns=final_demand_matrix.columns)

    units_path = _find_flat_payload(root, "units", suffixes)
    units_frame = pd.read_csv(units_path, sep=sep, index_col=[0, 1], header=[0], keep_default_na=False)
    units_frame.columns = ["unit"]
    units_frame.index.names = ["level", "item"]

    _apply_default_sut_native_public_axes(matrices, units_frame, matrix_layouts=matrix_layouts)
    sort_frames(matrices)
    indexes = build_sut_indexes_from_units_and_y(units_frame, _build_sut_native_index_matrices(matrices, mode=mode))
    units = sut_units_from_frame(units_frame)
    extra = {
        "block_specs": sut_block_specs_for_matrix_layouts(
            matrix_layouts,
            final_demand_axis_names=final_demand_axis_names or ("Region", "Consumption category"),
        )
    }
    return {"baseline": matrices}, indexes, units, extra


def _read_matrix_text_with_layout(
    path: Path,
    *,
    matrix_name: str,
    sep: str,
    matrix_layouts: dict[str, tuple[str, ...]],
    suffixes: set[str],
) -> tuple[pd.DataFrame, tuple[str, ...] | None]:
    """Read one matrix-per-file txt/csv payload with either legacy or explicit axes."""
    file_path = _find_flat_payload(path, matrix_name, suffixes)
    row_levels = len(iot_axis_names(matrix_name, "from", matrix_layouts))
    if matrix_name in {"Y", "EY", "VY"}:
        col_levels = 1
        header_candidates = (1, 2, 3)
    else:
        col_levels = len(iot_axis_names(matrix_name, "to", matrix_layouts))
        header_candidates = (col_levels + 1, col_levels)

    attempts = []
    for index_levels in (row_levels, row_levels + 1):
        for header_levels in header_candidates:
            candidate = (index_levels, header_levels)
            if candidate not in attempts:
                attempts.append(candidate)

    last_error = None
    for index_levels, header_levels in attempts:
        try:
            frame = pd.read_csv(
                file_path,
                sep=sep,
                index_col=list(range(index_levels)),
                header=list(range(header_levels)),
                keep_default_na=False,
            )
            return _normalize_iot_matrix(frame, matrix_name, matrix_layouts)
        except Exception as exc:  # pragma: no cover - diagnostic fallback path
            last_error = exc

    raise WrongInput(
        f"Unable to read {file_path.name} with matrix_layouts. Last parser error: {last_error}"
    )


def parse_iot_text_frames_with_layouts(
    path: str,
    *,
    mode: str,
    sep: str,
    matrix_layouts: dict[str, tuple[str, ...]],
    _format: str | None = None,
):
    """Parse matrix-per-file txt/csv payloads using semantic matrix layouts."""
    root = Path(path)
    suffixes = _allowed_text_suffixes(_format)
    expected_matrices = _FLAT_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_FLOW_MATRICES
    required_matrices = _FLAT_REQUIRED_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_REQUIRED_FLOW_MATRICES

    matrices = {}
    final_demand_axis_names: tuple[str, ...] | None = None

    def _merge_final_demand_axes(
        existing: tuple[str, ...] | None,
        current: tuple[str, ...] | None,
    ) -> tuple[str, ...] | None:
        if current is None:
            return existing
        if existing is None or existing == current:
            return current if existing is None else existing

        shorter, longer = (
            (existing, current)
            if len(existing) <= len(current)
            else (current, existing)
        )
        if longer[-len(shorter) :] == shorter:
            return longer

        raise WrongInput(
            f"Mixed semantic final-demand axes are not supported: {existing} and {current}."
        )

    for matrix_name in expected_matrices:
        try:
            matrices[matrix_name], current_fd_axis_names = _read_matrix_text_with_layout(
                root,
                matrix_name=matrix_name,
                sep=sep,
                matrix_layouts=matrix_layouts,
                suffixes=suffixes,
            )
            final_demand_axis_names = _merge_final_demand_axes(
                final_demand_axis_names,
                current_fd_axis_names,
            )
        except FileNotFoundError:
            if matrix_name not in required_matrices:
                continue
            raise

    if "EY" not in matrices:
        matrices["EY"] = pd.DataFrame(0, index=matrices["E"].index, columns=matrices["Y"].columns)
    if "VY" not in matrices:
        matrices["VY"] = pd.DataFrame(0, index=matrices["V"].index, columns=matrices["Y"].columns)

    units_path = _find_flat_payload(root, "units", suffixes)
    units_frame = pd.read_csv(units_path, sep=sep, index_col=[0, 1], header=[0], keep_default_na=False)
    units_frame.columns = ["unit"]
    units_frame.index.names = ["level", "item"]

    sort_frames(matrices)
    indexes = build_iot_indexes_from_units_and_y(units_frame, matrices)
    units = iot_units_from_frame(units_frame)
    extra = {
        "block_specs": iot_block_specs_for_matrix_layouts(
            matrix_layouts,
            final_demand_axis_names=final_demand_axis_names or ("Region", "Consumption category"),
        )
    }
    return {"baseline": matrices}, indexes, units, extra


def _read_sut_matrix_text_with_layout(
    path: Path,
    *,
    matrix_name: str,
    sep: str,
    matrix_layouts: dict[str, tuple[str, ...]],
    suffixes: set[str],
) -> tuple[pd.DataFrame, tuple[str, ...] | None]:
    """Read one matrix-per-file txt/csv payload with SUT semantic matrix layouts."""
    file_path = _find_flat_payload(path, matrix_name, suffixes)

    if matrix_name in {"Z", "z", "Y"}:
        row_levels = 3
    else:
        row_levels = len(sut_axis_names(matrix_name, "from", matrix_layouts))

    if matrix_name in {"Y", "EY", "VY"}:
        header_candidates = (1, 2, 3)
    else:
        header_candidates = (3,)

    attempts = []
    for index_levels in (row_levels, row_levels + 1):
        for header_levels in header_candidates:
            candidate = (index_levels, header_levels)
            if candidate not in attempts:
                attempts.append(candidate)

    last_error = None
    successful_reads: list[tuple[tuple[int, ...], pd.DataFrame, tuple[str, ...] | None]] = []
    for index_levels, header_levels in attempts:
        try:
            frame = pd.read_csv(
                file_path,
                sep=sep,
                index_col=list(range(index_levels)),
                header=list(range(header_levels)),
                keep_default_na=False,
            )
            normalized, final_demand_axis_names = _normalize_sut_matrix(
                frame,
                matrix_name,
                matrix_layouts,
            )
            successful_reads.append(
                (
                    (
                        len(final_demand_axis_names or ()),
                        normalized.columns.nlevels if isinstance(normalized.columns, pd.MultiIndex) else 1,
                        header_levels,
                        -abs(index_levels - row_levels),
                    ),
                    normalized,
                    final_demand_axis_names,
                )
            )
        except Exception as exc:  # pragma: no cover - diagnostic fallback path
            last_error = exc

    if successful_reads:
        successful_reads.sort(key=lambda item: item[0], reverse=True)
        _, normalized, final_demand_axis_names = successful_reads[0]
        return normalized, final_demand_axis_names

    raise WrongInput(
        f"Unable to read {file_path.name} with SUT matrix_layouts. Last parser error: {last_error}"
    )


def parse_sut_text_frames_with_layouts(
    path: str,
    *,
    mode: str,
    sep: str,
    matrix_layouts: dict[str, tuple[str, ...]],
    _format: str | None = None,
):
    """Parse matrix-per-file txt/csv SUT payloads using semantic matrix layouts."""
    root = Path(path)
    suffixes = _allowed_text_suffixes(_format)
    if _looks_like_sut_native_matrix_bundle(root, suffixes=suffixes, mode=mode):
        return parse_sut_native_text_frames_with_layouts(
            path,
            mode=mode,
            sep=sep,
            matrix_layouts=matrix_layouts,
            _format=_format,
        )
    expected_matrices = _FLAT_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_FLOW_MATRICES
    required_matrices = _FLAT_REQUIRED_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_REQUIRED_FLOW_MATRICES

    matrices = {}
    final_demand_axis_names: tuple[str, ...] | None = None
    for matrix_name in expected_matrices:
        try:
            matrices[matrix_name], current_fd_axis_names = _read_sut_matrix_text_with_layout(
                root,
                matrix_name=matrix_name,
                sep=sep,
                matrix_layouts=matrix_layouts,
                suffixes=suffixes,
            )
            if current_fd_axis_names is not None:
                if final_demand_axis_names is None:
                    final_demand_axis_names = current_fd_axis_names
                elif final_demand_axis_names != current_fd_axis_names:
                    raise WrongInput(
                        f"Mixed semantic final-demand axes are not supported: {final_demand_axis_names} and {current_fd_axis_names}."
                    )
        except FileNotFoundError:
            if matrix_name not in required_matrices:
                continue
            raise

    if "EY" not in matrices:
        matrices["EY"] = pd.DataFrame(0, index=matrices["E"].index, columns=matrices["Y"].columns)
    if "VY" not in matrices:
        matrices["VY"] = pd.DataFrame(0, index=matrices["V"].index, columns=matrices["Y"].columns)

    units_path = _find_flat_payload(root, "units", suffixes)
    units_frame = pd.read_csv(units_path, sep=sep, index_col=[0, 1], header=[0], keep_default_na=False)
    units_frame.columns = ["unit"]
    units_frame.index.names = ["level", "item"]

    sort_frames(matrices)
    indexes = build_sut_indexes_from_units_and_y(units_frame, matrices)
    units = sut_units_from_frame(units_frame)
    extra = {
        "block_specs": sut_block_specs_for_matrix_layouts(
            matrix_layouts,
            final_demand_axis_names=final_demand_axis_names or ("Region", "Consumption category"),
        )
    }
    return {"baseline": matrices}, indexes, units, extra


def parse_flat_frames(
    data: pd.DataFrame,
    unit_table: pd.DataFrame,
    table: str,
    mode: str,
    matrix_layouts: dict[str, tuple[str, ...]] | None = None,
):
    """Parse canonical flat frames into MARIO matrices, indexes and units."""
    if list(data.columns) == list(LEGACY_FLAT_DATA_COLUMNS):
        data = _coerce_legacy_flat_data(data)
    else:
        data = _coerce_sparse_flat_data(data)

    native_expected_matrices, native_required_matrices = _sut_native_matrix_names(mode)
    has_native_sut_matrices = table == "SUT" and bool(set(data["Matrix"]).intersection(native_required_matrices))

    if has_native_sut_matrices:
        matrices = {}
        final_demand_axis_names: tuple[str, ...] | None = None
        active_layouts = matrix_layouts or {}
        for matrix_name in native_expected_matrices:
            subset = data.loc[data["Matrix"] == matrix_name].copy()
            if subset.empty:
                if matrix_name in native_required_matrices:
                    raise ValueError(f"Flat payload is missing required matrix {matrix_name!r}.")
                continue

            subset["Value"] = pd.to_numeric(subset["Value"], errors="raise")
            if matrix_name in {"U", "S", "u", "s", "Ya", "Yc"}:
                subset["from_key"] = [
                    _sut_unified_tokens_from_flat(row, side="from")
                    for _, row in subset.iterrows()
                ]
                subset["from_public_key"] = subset["from_key"]
            else:
                expected_from = sut_axis_names(
                    "V" if matrix_name in {"Va", "Vc", "va", "vc", "VY"} else "E",
                    "from",
                    active_layouts,
                )
                semantic_matrix = "V" if matrix_name in {"Va", "Vc", "va", "vc", "VY"} else "E"
                subset["from_key"] = [
                    interpret_axis_tokens(
                        _tuple_from_set_columns(row, expected_from, side="from"),
                        expected_from,
                        matrix_name=semantic_matrix,
                        side="from",
                    )[0]
                    for _, row in subset.iterrows()
                ]
                subset["from_public_key"] = [
                    interpret_axis_tokens(
                        _tuple_from_set_columns(row, expected_from, side="from"),
                        expected_from,
                        matrix_name=semantic_matrix,
                        side="from",
                    )[2]
                    for _, row in subset.iterrows()
                ]

            if matrix_name in {"Ya", "Yc", "EY", "VY"}:
                subset["to_key"] = [
                    interpret_iot_final_demand_tokens(
                        _tokens_for_expected_row(
                            row,
                            _final_demand_expected_names(subset, side="to"),
                            side="to",
                        )
                    )[0]
                    for _, row in subset.iterrows()
                ]
                subset["to_public_key"] = [
                    _legacy_sut_final_demand_public(
                        _tokens_for_expected_row(
                            row,
                            _final_demand_expected_names(subset, side="to"),
                            side="to",
                        )
                    )
                    for _, row in subset.iterrows()
                ]
                if final_demand_axis_names is None and not subset.empty:
                    final_demand_axis_names = interpret_iot_final_demand_tokens(
                        _tokens_for_expected_row(
                            subset.iloc[0],
                            _final_demand_expected_names(subset, side="to"),
                            side="to",
                        )
                    )[1]
            else:
                subset["to_key"] = [
                    _sut_unified_tokens_from_flat(row, side="to")
                    for _, row in subset.iterrows()
                ]
                subset["to_public_key"] = subset["to_key"]

            row_order = list(dict.fromkeys(subset["from_key"].tolist()))
            column_order = list(dict.fromkeys(subset["to_key"].tolist()))
            row_public_order = list(dict.fromkeys(subset["from_public_key"].tolist()))
            column_public_order = list(dict.fromkeys(subset["to_public_key"].tolist()))
            frame = subset.pivot(index="from_key", columns="to_key", values="Value")
            frame = frame.reindex(index=row_order, columns=column_order)
            frame = frame.fillna(0)

            if matrix_name in {"U", "S", "u", "s", "Ya", "Yc"}:
                frame.index = pd.MultiIndex.from_tuples(row_public_order, names=["Region", "Level", "Item"])
            else:
                semantic_matrix = "V" if matrix_name in {"Va", "Vc", "va", "vc", "VY"} else "E"
                expected_from = sut_axis_names(semantic_matrix, "from", active_layouts)
                row_sample = interpret_axis_tokens(
                    _tuple_from_set_columns(subset.iloc[0], expected_from, side="from"),
                    expected_from,
                    matrix_name=semantic_matrix,
                    side="from",
                )
                row_public_names = row_sample[3]
                if len(row_public_names) == 1:
                    frame.index = pd.Index([value[0] for value in row_public_order], name=row_public_names[0])
                else:
                    frame.index = pd.MultiIndex.from_tuples(row_public_order, names=list(row_public_names))

            if matrix_name in {"Ya", "Yc", "EY", "VY"}:
                frame.columns = pd.MultiIndex.from_tuples(
                    column_public_order,
                    names=["Region", "Level", "Item"],
                )
            else:
                frame.columns = pd.MultiIndex.from_tuples(column_public_order, names=["Region", "Level", "Item"])
            matrices[matrix_name] = frame

        extension_matrix = matrices.get("Ea", matrices.get("ea"))
        factor_matrix = matrices.get("Va", matrices.get("va"))
        final_demand_matrix = matrices["Ya"] if "Ya" in matrices else matrices["Yc"]
        if "EY" not in matrices:
            matrices["EY"] = pd.DataFrame(0, index=extension_matrix.index, columns=final_demand_matrix.columns)
        if "VY" not in matrices:
            matrices["VY"] = pd.DataFrame(0, index=factor_matrix.index, columns=final_demand_matrix.columns)

        units_frame = _flat_units_to_legacy(unit_table)
        _apply_default_sut_native_public_axes(matrices, units_frame, matrix_layouts=active_layouts)
        sort_frames(matrices)
        indexes = build_sut_indexes_from_units_and_y(
            units_frame,
            _build_sut_native_index_matrices(matrices, mode=mode),
        )
        units = sut_units_from_frame(units_frame)
        extra = {
            "block_specs": sut_block_specs_for_matrix_layouts(
                active_layouts,
                final_demand_axis_names=final_demand_axis_names or ("Region", "Consumption category"),
            )
        }
        return {"baseline": matrices}, indexes, units, extra

    if matrix_layouts:
        if table == "IOT":
            expected_matrices = (
                _FLAT_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_FLOW_MATRICES
            )
            required_matrices = (
                _FLAT_REQUIRED_COEFFICIENT_MATRICES
                if mode == "coefficients"
                else _FLAT_REQUIRED_FLOW_MATRICES
            )

            matrices = {}
            final_demand_axis_names: tuple[str, ...] | None = None
            final_demand_public_axis_names: tuple[str, ...] | None = None
            for matrix_name in expected_matrices:
                subset = data.loc[data["Matrix"] == matrix_name].copy()
                if subset.empty:
                    if matrix_name in required_matrices:
                        raise ValueError(f"Flat payload is missing required matrix {matrix_name!r}.")
                    continue

                subset["Value"] = pd.to_numeric(subset["Value"], errors="raise")
                expected_from = iot_axis_names(matrix_name, "from", matrix_layouts)
                subset["from_key"] = [
                    interpret_axis_tokens(
                        _tuple_from_set_columns(
                            row,
                            expected_from,
                            side="from",
                            borrow_from_other_side=True,
                        ),
                        expected_from,
                        matrix_name=matrix_name,
                        side="from",
                    )[0]
                    for _, row in subset.iterrows()
                ]
                subset["from_public_key"] = [
                    interpret_axis_tokens(
                        _tuple_from_set_columns(
                            row,
                            expected_from,
                            side="from",
                            borrow_from_other_side=True,
                        ),
                        expected_from,
                        matrix_name=matrix_name,
                        side="from",
                    )[2]
                    for _, row in subset.iterrows()
                ]
                expected_to = iot_axis_names(matrix_name, "to", matrix_layouts)
                subset["to_key"] = [
                    (
                        interpret_iot_final_demand_tokens(
                            _tokens_for_expected_row(
                                row,
                                _final_demand_expected_names(subset, side="to"),
                                side="to",
                            )
                        )[0]
                        if matrix_name in {"Y", "EY", "VY"}
                        else interpret_axis_tokens(
                            _tokens_for_expected_row(row, expected_to, side="to"),
                            expected_to,
                            matrix_name=matrix_name,
                            side="to",
                        )[0]
                    )
                    for _, row in subset.iterrows()
                ]
                subset["to_public_key"] = [
                    (
                        interpret_iot_final_demand_tokens(
                            _tokens_for_expected_row(
                                row,
                                _final_demand_expected_names(subset, side="to"),
                                side="to",
                            )
                        )[2]
                        if matrix_name in {"Y", "EY", "VY"}
                        else interpret_axis_tokens(
                            _tokens_for_expected_row(row, expected_to, side="to"),
                            expected_to,
                            matrix_name=matrix_name,
                            side="to",
                        )[2]
                    )
                    for _, row in subset.iterrows()
                ]
                if matrix_name in {"Y", "EY", "VY"} and final_demand_axis_names is None and not subset.empty:
                    final_demand_axis_names = interpret_iot_final_demand_tokens(
                        _tokens_for_expected_row(
                            subset.iloc[0],
                            _final_demand_expected_names(subset, side="to"),
                            side="to",
                        )
                    )[1]
                if matrix_name in {"Y", "EY", "VY"} and not subset.empty:
                    final_demand_public_axis_names = interpret_iot_final_demand_tokens(
                        _tokens_for_expected_row(
                            subset.iloc[0],
                            _final_demand_expected_names(subset, side="to"),
                            side="to",
                        )
                    )[3]

                row_order = list(dict.fromkeys(subset["from_key"].tolist()))
                column_order = list(dict.fromkeys(subset["to_key"].tolist()))
                row_public_order = list(dict.fromkeys(subset["from_public_key"].tolist()))
                column_public_order = list(dict.fromkeys(subset["to_public_key"].tolist()))
                frame = subset.pivot(index="from_key", columns="to_key", values="Value")
                frame = frame.reindex(index=row_order, columns=column_order)
                frame = frame.fillna(0)
                expected_to = (
                    final_demand_axis_names
                    if matrix_name in {"Y", "EY", "VY"}
                    else expected_to
                )
                row_sample = interpret_axis_tokens(
                    _tuple_from_set_columns(
                        subset.iloc[0],
                        expected_from,
                        side="from",
                        borrow_from_other_side=True,
                    ),
                    expected_from,
                    matrix_name=matrix_name,
                    side="from",
                )
                row_public_names = row_sample[3]
                if len(row_public_names) == 1:
                    frame.index = pd.Index([value[0] for value in row_public_order], name=row_public_names[0])
                else:
                    frame.index = pd.MultiIndex.from_tuples(row_public_order, names=list(row_public_names))

                if matrix_name in {"Y", "EY", "VY"}:
                    if len(final_demand_public_axis_names) == 1:
                        frame.columns = pd.Index(
                            [value[0] for value in column_public_order],
                            name=final_demand_public_axis_names[0],
                        )
                    else:
                        frame.columns = pd.MultiIndex.from_tuples(
                            column_public_order,
                            names=list(final_demand_public_axis_names),
                        )
                else:
                    col_sample = interpret_axis_tokens(
                        _tokens_for_expected_row(subset.iloc[0], expected_to, side="to"),
                        expected_to,
                        matrix_name=matrix_name,
                        side="to",
                    )
                    col_public_names = col_sample[3]
                    if len(col_public_names) == 1:
                        frame.columns = pd.Index([value[0] for value in column_public_order], name=col_public_names[0])
                    else:
                        frame.columns = pd.MultiIndex.from_tuples(
                            column_public_order,
                            names=list(col_public_names),
                        )
                matrices[matrix_name] = frame

            extension_matrix = matrices.get("E", matrices.get("e"))
            factor_matrix = matrices.get("V", matrices.get("v"))
            if "EY" not in matrices:
                matrices["EY"] = pd.DataFrame(0, index=extension_matrix.index, columns=matrices["Y"].columns)
            if "VY" not in matrices:
                matrices["VY"] = pd.DataFrame(0, index=factor_matrix.index, columns=matrices["Y"].columns)

            sort_frames(matrices)
            units_frame = _flat_units_to_legacy(unit_table)
            index_matrices = dict(matrices)
            for legacy_name, coefficient_name in (("Z", "z"), ("V", "v"), ("E", "e")):
                if legacy_name not in index_matrices and coefficient_name in index_matrices:
                    index_matrices[legacy_name] = index_matrices[coefficient_name]
            indexes = build_iot_indexes_from_units_and_y(units_frame, index_matrices)
            units = iot_units_from_frame(units_frame)
            extra = {
                "block_specs": iot_block_specs_for_matrix_layouts(
                    matrix_layouts,
                    final_demand_axis_names=final_demand_axis_names or ("Region", "Consumption category"),
                )
            }
            return {"baseline": matrices}, indexes, units, extra

        if table == "SUT":
            expected_matrices = (
                _FLAT_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_FLOW_MATRICES
            )
            required_matrices = (
                _FLAT_REQUIRED_COEFFICIENT_MATRICES
                if mode == "coefficients"
                else _FLAT_REQUIRED_FLOW_MATRICES
            )

            matrices = {}
            for matrix_name in expected_matrices:
                subset = data.loc[data["Matrix"] == matrix_name].copy()
                if subset.empty:
                    if matrix_name in required_matrices:
                        raise ValueError(f"Flat payload is missing required matrix {matrix_name!r}.")
                    continue

                subset["Value"] = pd.to_numeric(subset["Value"], errors="raise")
                if matrix_name in {"Z", "z", "Y"}:
                    subset["from_key"] = [
                        _sut_unified_tokens_from_flat(row, side="from")
                        for _, row in subset.iterrows()
                    ]
                    subset["from_public_key"] = subset["from_key"]
                else:
                    expected_from = sut_axis_names(matrix_name, "from", matrix_layouts)
                    subset["from_key"] = [
                        interpret_axis_tokens(
                            _tuple_from_set_columns(
                                row,
                                expected_from,
                                side="from",
                            ),
                            expected_from,
                            matrix_name=matrix_name,
                            side="from",
                        )[0]
                        for _, row in subset.iterrows()
                    ]
                    subset["from_public_key"] = [
                        interpret_axis_tokens(
                            _tuple_from_set_columns(
                                row,
                                expected_from,
                                side="from",
                            ),
                            expected_from,
                            matrix_name=matrix_name,
                            side="from",
                        )[2]
                        for _, row in subset.iterrows()
                    ]

                if matrix_name in {"Y", "EY", "VY"}:
                    subset["to_key"] = [
                        interpret_iot_final_demand_tokens(
                            _tokens_for_expected_row(
                                row,
                                _final_demand_expected_names(subset, side="to"),
                                side="to",
                            )
                        )[0]
                        for _, row in subset.iterrows()
                    ]
                    subset["to_public_key"] = [
                        _legacy_sut_final_demand_public(
                            _tokens_for_expected_row(
                                row,
                                _final_demand_expected_names(subset, side="to"),
                                side="to",
                            )
                        )
                        for _, row in subset.iterrows()
                    ]
                else:
                    subset["to_key"] = [
                        _sut_unified_tokens_from_flat(row, side="to")
                        for _, row in subset.iterrows()
                    ]
                    subset["to_public_key"] = subset["to_key"]

                row_order = list(dict.fromkeys(subset["from_key"].tolist()))
                column_order = list(dict.fromkeys(subset["to_key"].tolist()))
                row_public_order = list(dict.fromkeys(subset["from_public_key"].tolist()))
                column_public_order = list(dict.fromkeys(subset["to_public_key"].tolist()))
                frame = subset.pivot(index="from_key", columns="to_key", values="Value")
                frame = frame.reindex(index=row_order, columns=column_order)
                frame = frame.fillna(0)

                if matrix_name in {"Z", "z", "Y"}:
                    frame.index = pd.MultiIndex.from_tuples(row_public_order, names=["Region", "Level", "Item"])
                else:
                    expected_from = sut_axis_names(matrix_name, "from", matrix_layouts)
                    row_sample = interpret_axis_tokens(
                        _tuple_from_set_columns(subset.iloc[0], expected_from, side="from"),
                        expected_from,
                        matrix_name=matrix_name,
                        side="from",
                    )
                    row_public_names = row_sample[3]
                    if len(row_public_names) == 1:
                        frame.index = pd.Index([value[0] for value in row_public_order], name=row_public_names[0])
                    else:
                        frame.index = pd.MultiIndex.from_tuples(row_public_order, names=list(row_public_names))

                if matrix_name in {"Y", "EY", "VY"}:
                    frame.columns = pd.MultiIndex.from_tuples(
                        column_public_order,
                        names=["Region", "Level", "Item"],
                    )
                else:
                    frame.columns = pd.MultiIndex.from_tuples(column_public_order, names=["Region", "Level", "Item"])
                matrices[matrix_name] = frame

            extension_matrix = matrices.get("E", matrices.get("e"))
            factor_matrix = matrices.get("V", matrices.get("v"))
            if "EY" not in matrices:
                matrices["EY"] = pd.DataFrame(0, index=extension_matrix.index, columns=matrices["Y"].columns)
            if "VY" not in matrices:
                matrices["VY"] = pd.DataFrame(0, index=factor_matrix.index, columns=matrices["Y"].columns)

            sort_frames(matrices)
            units_frame = _flat_units_to_legacy(unit_table)
            index_matrices = dict(matrices)
            for legacy_name, coefficient_name in (("Z", "z"), ("V", "v"), ("E", "e")):
                if legacy_name not in index_matrices and coefficient_name in index_matrices:
                    index_matrices[legacy_name] = index_matrices[coefficient_name]
            indexes = build_sut_indexes_from_units_and_y(units_frame, index_matrices)
            units = sut_units_from_frame(units_frame)
            extra = {
                "block_specs": sut_block_specs_for_matrix_layouts(
                    matrix_layouts,
                    final_demand_axis_names=(
                        _final_demand_expected_names(
                            data.loc[data["Matrix"].isin({"Y", "EY", "VY"})],
                            side="to",
                        )
                        if not data.loc[data["Matrix"].isin({"Y", "EY", "VY"})].empty
                        else ("Region", "Consumption category")
                    ),
                )
            }
            return {"baseline": matrices}, indexes, units, extra

        raise WrongInput("matrix_layouts are currently supported only for IOT or SUT flat payloads.")

    expected_matrices = (
        _FLAT_COEFFICIENT_MATRICES if mode == "coefficients" else _FLAT_FLOW_MATRICES
    )
    required_matrices = (
        _FLAT_REQUIRED_COEFFICIENT_MATRICES
        if mode == "coefficients"
        else _FLAT_REQUIRED_FLOW_MATRICES
    )

    matrices = {
        matrix_name: _flat_matrix_to_frame(data, matrix_name)
        for matrix_name in expected_matrices
        if matrix_name in set(data["Matrix"])
    }
    if set(required_matrices) - set(matrices):
        missing = sorted(set(required_matrices) - set(matrices))
        raise ValueError(f"Flat payload is missing required matrices: {missing}")

    sort_frames(matrices)
    indeces = get_index_txt(
        Z=matrices["z" if mode == "coefficients" else "Z"],
        V=matrices["v" if mode == "coefficients" else "V"],
        Y=matrices["Y"],
        E=matrices["e" if mode == "coefficients" else "E"],
        table=table,
    )
    units = get_units(_flat_units_to_legacy(unit_table), table, indeces)
    rename_index(matrices)
    return {"baseline": matrices}, indeces, units


def flat_txt_parser(
    path: str,
    table: str,
    mode: str,
    sep: str,
    matrix_layouts: dict[str, tuple[str, ...]] | None = None,
    _format: str | None = None,
):
    """Parse the canonical flat long-format txt/csv export."""
    log_time(logger, f"Parser: reading {mode} from flat txt files.", "info")
    data, unit_table = _read_flat_text_frames(path, sep, _format=_format, mode=mode)
    return parse_flat_frames(data, unit_table, table, mode, matrix_layouts=matrix_layouts)


class TxtParser(BaseParser):
    """State parser for generic directory-based TXT or CSV database dumps."""

    name = "txt"

    def parse(
        self,
        path: str,
        table: str,
        mode: str,
        *,
        sep: str = ",",
        _format: str | None = None,
        flat: bool = False,
        matrix_layouts: dict[str, object] | None = None,
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        tech_assumption: str | None = None,
        repository: BlockRepository | None = None,
    ) -> ModelState:
        """Parse a folder of text files into a canonical ``ModelState``."""
        resolved_path = _resolve_text_bundle_root(path, mode)
        layout = "flat" if flat else "matrix"
        requested_format = normalize_text_bundle_format(_format)
        if requested_format is None:
            try:
                bundle_format = detect_text_bundle_format(str(resolved_path), txt_parser_id[mode])
            except Exception:
                bundle_format = "txt/csv"
        else:
            bundle_format = requested_format
        log_time(
            logger,
            f"Parser: txt reading {table} {mode} from {resolved_path} in {layout} mode ({bundle_format}).",
            "info",
        )
        normalized_layouts = normalize_matrix_layouts(matrix_layouts, table=table)
        if normalized_layouts:
            if flat:
                matrices, indexes, units, extra = flat_txt_parser(
                    str(resolved_path),
                    table,
                    mode,
                    sep,
                    matrix_layouts=normalized_layouts,
                    _format=requested_format,
                )
            elif table == "SUT":
                matrices, indexes, units, extra = parse_sut_text_frames_with_layouts(
                    str(resolved_path),
                    mode=mode,
                    sep=sep,
                    matrix_layouts=normalized_layouts,
                    _format=requested_format,
                )
            else:
                matrices, indexes, units, extra = parse_iot_text_frames_with_layouts(
                    str(resolved_path),
                    mode=mode,
                    sep=sep,
                    matrix_layouts=normalized_layouts,
                    _format=requested_format,
                )
        else:
            if flat:
                matrices, indexes, units, extra = flat_txt_parser(
                    str(resolved_path),
                    table,
                    mode,
                    sep,
                    _format=requested_format,
                )
            elif table == "SUT" and _looks_like_sut_native_matrix_bundle(
                resolved_path,
                suffixes=_allowed_text_suffixes(requested_format),
                mode=mode,
            ):
                matrices, indexes, units, extra = parse_sut_native_text_frames_with_layouts(
                    str(resolved_path),
                    mode=mode,
                    sep=sep,
                    matrix_layouts={},
                    _format=requested_format,
                )
            else:
                matrices, indexes, units = txt_parser(
                    str(resolved_path),
                    table,
                    mode,
                    sep,
                    requested_format,
                )
                extra = {}
        state = build_parser_state(
            table=table,
            matrices=matrices,
            indexes=indexes,
            units=units,
            parser_name=self.name,
            mode=mode,
            name=name,
            source=source or str(resolved_path),
            year=year,
            price=price,
            tech_assumption=tech_assumption,
            source_path=str(resolved_path),
            repository=repository,
        )
        state.metadata.extra.update(extra)
        log_time(logger, f"Parser: txt state ready for {table}.", "info")
        return state


def parse_state_from_txt(
    path: str,
    table: str,
    mode: str,
    *,
    sep: str = ",",
    _format: str | None = None,
    flat: bool = False,
    matrix_layouts: dict[str, object] | None = None,
    **kwargs,
) -> ModelState:
    """Convenience wrapper around ``TxtParser`` for internal use."""
    return TxtParser().parse(
        path=path,
        table=table,
        mode=mode,
        sep=sep,
        _format=_format,
        flat=flat,
        matrix_layouts=matrix_layouts,
        **kwargs,
    )


register_parser("txt", TxtParser())
