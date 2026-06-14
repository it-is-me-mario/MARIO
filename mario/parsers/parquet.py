"""Internal Parquet parser aligned with the generic TXT parser semantics."""

from __future__ import annotations

from pathlib import Path
import logging

import pandas as pd

from mario._optional import require_pyarrow
from mario.internal import ModelState
from mario.log_exc.exceptions import WrongInput
from mario.log_exc.logger import log_time
from mario.parsers.api import build_parser_state
from mario.parsers.base import BaseParser
from mario.parsers.matrix_layouts import (
    build_iot_indexes_from_units_and_y,
    build_sut_indexes_from_units_and_y,
    iot_block_specs_for_matrix_layouts,
    iot_units_from_frame,
    normalize_matrix_layouts,
    sut_block_specs_for_matrix_layouts,
    sut_units_from_frame,
)
from mario.parsers.registry import register_parser
from mario.parsers.tabular import get_index_txt, get_units, rename_index, sort_frames
from mario.parsers.txt import (
    _apply_default_sut_native_public_axes,
    _build_sut_native_index_matrices,
    _find_flat_payload,
    _flat_units_to_legacy,
    _normalize_sut_native_matrix,
    _normalize_iot_matrix,
    _normalize_sut_matrix,
    _sut_native_matrix_names,
    parse_flat_frames,
)
from mario.storage.base import BlockRepository

logger = logging.getLogger(__name__)


_MATRIX_FLOW_FILES = ("Z", "Y", "V", "E", "EY", "VY")
_MATRIX_COEFFICIENT_FILES = ("z", "Y", "v", "e", "EY", "VY")
_MATRIX_REQUIRED_FLOW_FILES = ("Z", "Y", "V", "E", "EY")
_MATRIX_REQUIRED_COEFFICIENT_FILES = ("z", "Y", "v", "e", "EY")


def _flat_matrix_names_for_mode(mode: str) -> tuple[str, ...]:
    """Return the flat matrix names expected for one parser mode."""
    return _MATRIX_COEFFICIENT_FILES if mode == "coefficients" else _MATRIX_FLOW_FILES


def matrix_parquet_parser(path: str, table: str, mode: str):
    """Parse the matrix-per-file parquet layout exported by ``Database.to_parquet``."""
    root = Path(path)
    native_expected, native_required = _sut_native_matrix_names(mode)
    if table == "SUT":
        native_present = {matrix_name for matrix_name in native_expected if (root / f"{matrix_name}.parquet").exists()}
        if native_present.intersection(native_required):
            matrices = {}
            final_demand_axis_names: tuple[str, ...] | None = None
            for matrix_name in native_expected:
                target = root / f"{matrix_name}.parquet"
                if not target.exists():
                    if matrix_name not in native_required:
                        continue
                    raise FileNotFoundError(target)
                matrices[matrix_name], current_fd_axis_names = _normalize_sut_native_matrix(
                    pd.read_parquet(target),
                    matrix_name,
                    {},
                )
                if current_fd_axis_names is not None:
                    if final_demand_axis_names is None:
                        final_demand_axis_names = current_fd_axis_names
                    elif final_demand_axis_names != current_fd_axis_names:
                        raise WrongInput(
                            f"Mixed semantic final-demand axes are not supported: {final_demand_axis_names} and {current_fd_axis_names}."
                        )

            extension_key = "Ea" if mode == "flows" else "ea"
            factor_key = "Va" if mode == "flows" else "va"
            if "EY" not in matrices:
                matrices["EY"] = pd.DataFrame(0, index=matrices[extension_key].index, columns=matrices["Ya"].columns)
            if "VY" not in matrices:
                matrices["VY"] = pd.DataFrame(0, index=matrices[factor_key].index, columns=matrices["Ya"].columns)

            units_path = root / "units.parquet"
            if not units_path.exists():
                raise FileNotFoundError(units_path)
            units_frame = pd.read_parquet(units_path)
            units_frame.columns = ["unit"]
            units_frame.index.names = ["level", "item"]

            _apply_default_sut_native_public_axes(matrices, units_frame, matrix_layouts={})
            sort_frames(matrices)
            indexes = build_sut_indexes_from_units_and_y(
                units_frame,
                _build_sut_native_index_matrices(matrices, mode=mode),
            )
            units = sut_units_from_frame(units_frame)
            return {"baseline": matrices}, indexes, units

    expected = _MATRIX_COEFFICIENT_FILES if mode == "coefficients" else _MATRIX_FLOW_FILES
    required = (
        _MATRIX_REQUIRED_COEFFICIENT_FILES
        if mode == "coefficients"
        else _MATRIX_REQUIRED_FLOW_FILES
    )

    matrices = {}
    final_demand_axis_names: tuple[str, ...] | None = None
    for matrix_name in expected:
        target = root / f"{matrix_name}.parquet"
        if not target.exists():
            if matrix_name not in required:
                continue
            raise FileNotFoundError(target)
        matrices[matrix_name] = pd.read_parquet(target)

    units_path = root / "units.parquet"
    if not units_path.exists():
        raise FileNotFoundError(units_path)
    units_frame = pd.read_parquet(units_path)

    sort_frames(matrices)
    indeces = get_index_txt(
        Z=matrices["z" if mode == "coefficients" else "Z"],
        V=matrices["v" if mode == "coefficients" else "V"],
        Y=matrices["Y"],
        E=matrices["e" if mode == "coefficients" else "E"],
        table=table,
    )
    units = get_units(units_frame, table, indeces)
    rename_index(matrices)
    return {"baseline": matrices}, indeces, units


def matrix_parquet_parser_with_layouts(
    path: str,
    *,
    table: str,
    mode: str,
    matrix_layouts: dict[str, tuple[str, ...]],
):
    """Parse matrix-per-file parquet payloads with semantic matrix layouts."""
    root = Path(path)
    native_expected, native_required = _sut_native_matrix_names(mode)
    if table == "SUT":
        native_present = {matrix_name for matrix_name in native_expected if (root / f"{matrix_name}.parquet").exists()}
        if native_present.intersection(native_required):
            matrices = {}
            final_demand_axis_names: tuple[str, ...] | None = None
            for matrix_name in native_expected:
                target = root / f"{matrix_name}.parquet"
                if not target.exists():
                    if matrix_name not in native_required:
                        continue
                    raise FileNotFoundError(target)
                matrices[matrix_name], current_fd_axis_names = _normalize_sut_native_matrix(
                    pd.read_parquet(target),
                    matrix_name,
                    matrix_layouts,
                )
                if current_fd_axis_names is not None:
                    if final_demand_axis_names is None:
                        final_demand_axis_names = current_fd_axis_names
                    elif final_demand_axis_names != current_fd_axis_names:
                        raise WrongInput(
                            f"Mixed semantic final-demand axes are not supported: {final_demand_axis_names} and {current_fd_axis_names}."
                        )

            if "EY" not in matrices:
                matrices["EY"] = pd.DataFrame(0, index=matrices["Ea" if mode == "flows" else "ea"].index, columns=matrices["Ya"].columns)
            if "VY" not in matrices:
                matrices["VY"] = pd.DataFrame(0, index=matrices["Va" if mode == "flows" else "va"].index, columns=matrices["Ya"].columns)

            units_path = root / "units.parquet"
            if not units_path.exists():
                raise FileNotFoundError(units_path)
            units_frame = pd.read_parquet(units_path)
            units_frame.columns = ["unit"]
            units_frame.index.names = ["level", "item"]

            _apply_default_sut_native_public_axes(matrices, units_frame, matrix_layouts=matrix_layouts)
            sort_frames(matrices)
            indexes = build_sut_indexes_from_units_and_y(
                units_frame,
                _build_sut_native_index_matrices(matrices, mode=mode),
            )
            units = sut_units_from_frame(units_frame)
            extra = {
                "block_specs": sut_block_specs_for_matrix_layouts(
                    matrix_layouts,
                    final_demand_axis_names=final_demand_axis_names or ("Region", "Consumption category"),
                )
            }
            return {"baseline": matrices}, indexes, units, extra

    expected = _MATRIX_COEFFICIENT_FILES if mode == "coefficients" else _MATRIX_FLOW_FILES
    required = (
        _MATRIX_REQUIRED_COEFFICIENT_FILES
        if mode == "coefficients"
        else _MATRIX_REQUIRED_FLOW_FILES
    )

    matrices = {}
    final_demand_axis_names: tuple[str, ...] | None = None
    for matrix_name in expected:
        target = root / f"{matrix_name}.parquet"
        if not target.exists():
            if matrix_name not in required:
                continue
            raise FileNotFoundError(target)
        normalizer = _normalize_iot_matrix if table == "IOT" else _normalize_sut_matrix
        matrices[matrix_name], current_fd_axis_names = normalizer(
            pd.read_parquet(target),
            matrix_name,
            matrix_layouts,
        )
        if current_fd_axis_names is not None:
            if final_demand_axis_names is None:
                final_demand_axis_names = current_fd_axis_names
            elif final_demand_axis_names != current_fd_axis_names:
                raise WrongInput(
                    f"Mixed semantic final-demand axes are not supported: {final_demand_axis_names} and {current_fd_axis_names}."
                )

    if "EY" not in matrices:
        matrices["EY"] = pd.DataFrame(0, index=matrices["E"].index, columns=matrices["Y"].columns)
    if "VY" not in matrices:
        matrices["VY"] = pd.DataFrame(0, index=matrices["V"].index, columns=matrices["Y"].columns)

    units_path = root / "units.parquet"
    if not units_path.exists():
        raise FileNotFoundError(units_path)
    units_frame = pd.read_parquet(units_path)
    units_frame.columns = ["unit"]
    units_frame.index.names = ["level", "item"]

    sort_frames(matrices)
    if table == "IOT":
        indexes = build_iot_indexes_from_units_and_y(units_frame, matrices)
        units = iot_units_from_frame(units_frame)
        extra = {
            "block_specs": iot_block_specs_for_matrix_layouts(
                matrix_layouts,
                final_demand_axis_names=final_demand_axis_names or ("Region", "Consumption category"),
            )
        }
    else:
        indexes = build_sut_indexes_from_units_and_y(units_frame, matrices)
        units = sut_units_from_frame(units_frame)
        extra = {
            "block_specs": sut_block_specs_for_matrix_layouts(
                matrix_layouts,
                final_demand_axis_names=final_demand_axis_names or ("Region", "Consumption category"),
            )
        }
    return {"baseline": matrices}, indexes, units, extra


def _read_flat_parquet_data(path: str, *, mode: str) -> pd.DataFrame:
    """Read one flat parquet payload from either ``data.parquet`` or per-matrix files."""
    root = Path(path)
    data_path = root / "data.parquet"
    if data_path.exists():
        return pd.read_parquet(data_path)

    frames = []
    for matrix_name in _flat_matrix_names_for_mode(mode):
        target = root / f"{matrix_name}.parquet"
        if not target.exists():
            continue
        frames.append(pd.read_parquet(target))
    if not frames:
        raise FileNotFoundError(
            f"No flat parquet payload found in {path!r}. Expected either data.parquet or one or more matrix parquet files."
        )
    return pd.concat(frames, ignore_index=True, sort=False)


def flat_parquet_parser(
    path: str,
    table: str,
    mode: str,
    matrix_layouts: dict[str, tuple[str, ...]] | None = None,
):
    """Parse the flat parquet layout exported by ``Database.to_parquet(flat=True)``."""
    root = Path(path)
    units_path = _find_flat_payload(root, "units", {".parquet"})
    data = _read_flat_parquet_data(path, mode=mode)
    units = pd.read_parquet(units_path)
    return parse_flat_frames(data, units, table, mode, matrix_layouts=matrix_layouts)


class ParquetParser(BaseParser):
    """State parser for directory-based parquet database dumps."""

    name = "parquet"

    def parse(
        self,
        path: str,
        table: str,
        mode: str,
        *,
        flat: bool = False,
        matrix_layouts: dict[str, object] | None = None,
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        tech_assumption: str | None = None,
        repository: BlockRepository | None = None,
    ) -> ModelState:
        """Parse a folder of parquet files into a canonical ``ModelState``."""
        require_pyarrow(feature="Parquet parsing", error_type=WrongInput)
        layout = "flat" if flat else "matrix"
        log_time(
            logger,
            f"Parser: parquet reading {table} {mode} from {path} in {layout} mode.",
            "info",
        )
        normalized_layouts = normalize_matrix_layouts(matrix_layouts, table=table)
        if normalized_layouts:
            if flat:
                matrices, indexes, units, extra = flat_parquet_parser(
                    path,
                    table,
                    mode,
                    matrix_layouts=normalized_layouts,
                )
            else:
                matrices, indexes, units, extra = matrix_parquet_parser_with_layouts(
                    path,
                    table=table,
                    mode=mode,
                    matrix_layouts=normalized_layouts,
                )
        else:
            parser = flat_parquet_parser if flat else matrix_parquet_parser
            parsed = parser(path, table, mode)
            if len(parsed) == 4:
                matrices, indexes, units, extra = parsed
            else:
                matrices, indexes, units = parsed
                extra = {}
            extra = {}
        state = build_parser_state(
            table=table,
            matrices=matrices,
            indexes=indexes,
            units=units,
            parser_name=self.name,
            mode=mode,
            name=name,
            source=source or str(Path(path)),
            year=year,
            price=price,
            tech_assumption=tech_assumption,
            source_path=path,
            repository=repository,
        )
        state.metadata.extra.update(extra)
        log_time(logger, f"Parser: parquet state ready for {table}.", "info")
        return state


def parse_state_from_parquet(
    path: str,
    table: str,
    mode: str,
    *,
    flat: bool = False,
    matrix_layouts: dict[str, object] | None = None,
    **kwargs,
) -> ModelState:
    """Convenience wrapper around ``ParquetParser`` for internal use."""
    return ParquetParser().parse(
        path=path,
        table=table,
        mode=mode,
        flat=flat,
        matrix_layouts=matrix_layouts,
        **kwargs,
    )


register_parser("parquet", ParquetParser())
