"""Internal Excel parser built on top of the shared normalizer."""

from __future__ import annotations

from pathlib import Path
import logging

import pandas as pd

from mario.log_exc.logger import log_time
from mario.internal import ModelState
from mario.log_exc.exceptions import WrongExcelFormat, WrongInput
from mario.parsers.api import build_parser_state
from mario.parsers.base import BaseParser
from mario.parsers.matrix_layouts import (
    build_iot_indexes_from_units_and_y,
    coerce_axis_names,
    infer_item_sets_from_units,
    interpret_axis_tokens,
    interpret_iot_final_demand_tokens,
    iot_axis_names,
    iot_block_specs_for_matrix_layouts,
    normalize_matrix_layouts,
    normalize_axis_tokens,
)
from mario.parsers.registry import register_parser
from mario.storage.base import BlockRepository
from mario.parsers.tabular import excel_parser

logger = logging.getLogger(__name__)


class ExcelParser(BaseParser):
    """State parser for generic Excel workbooks following MARIO conventions."""

    name = "excel"

    def parse(
        self,
        path: str,
        table: str,
        mode: str,
        data_sheet: str | int = 0,
        unit_sheet: str | int = "units",
        matrix_layouts: dict[str, object] | None = None,
        *,
        name: str | None = None,
        source: str | None = None,
        year: int | None = None,
        price: str | None = None,
        repository: BlockRepository | None = None,
    ) -> ModelState:
        """Parse a generic Excel workbook into a canonical ``ModelState``."""
        log_time(logger, f"Parser: excel reading {table} {mode} from {path}.", "info")
        normalized_layouts = normalize_matrix_layouts(matrix_layouts)
        if not normalized_layouts:
            matrices, indexes, units = excel_parser(path, table, mode, data_sheet, unit_sheet)
            extra = {}
        elif table == "IOT" and mode == "flows":
            matrices, indexes, units, extra = parse_explicit_iot_excel_layout(
                path=path,
                data_sheet=data_sheet,
                unit_sheet=unit_sheet,
                matrix_layouts=normalized_layouts,
            )
        else:
            raise WrongInput(
                "Unsupported matrix_layouts combination for parse_from_excel."
            )
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
            source_path=path,
            repository=repository,
        )
        state.metadata.extra.update(extra)
        log_time(logger, f"Parser: excel state ready for {table}.", "info")
        return state


def parse_state_from_excel(
    path: str,
    table: str,
    mode: str,
    data_sheet: str | int = 0,
    unit_sheet: str | int = "units",
    matrix_layouts: dict[str, object] | None = None,
    **kwargs,
) -> ModelState:
    """Convenience wrapper around ``ExcelParser`` for internal use."""
    return ExcelParser().parse(
        path=path,
        table=table,
        mode=mode,
        data_sheet=data_sheet,
        unit_sheet=unit_sheet,
        matrix_layouts=matrix_layouts,
        **kwargs,
    )


def _build_units_from_mriot_sheet(
    path: str,
    unit_sheet: str | int,
) -> dict[str, pd.DataFrame]:
    """Read units for the explicit no-Level MRIOT workbook variant."""
    raw_units = pd.read_excel(path, sheet_name=unit_sheet, header=None)
    if raw_units.shape[1] < 3:
        raise WrongExcelFormat("The units sheet must contain at least three columns.")

    body = raw_units.iloc[1:, :3].copy()
    body.columns = ["level", "item", "unit"]
    body = body.dropna(how="all")
    body = body.dropna(subset=["level", "item", "unit"], how="all")
    body = body.dropna(subset=["level", "item"])
    body = body.drop_duplicates(subset=["level", "item"], keep="first")
    body.set_index(["level", "item"], inplace=True)
    return body[["unit"]]


def _compact_tokens(values) -> tuple[object, ...]:
    """Drop empty placeholders from one explicit axis tuple."""
    return tuple(value for value in values if not pd.isna(value) and value != "None" and value != "")


def parse_explicit_iot_excel_layout(
    *,
    path: str,
    data_sheet: str | int,
    unit_sheet: str | int,
    matrix_layouts: dict[str, tuple[str, ...]],
):
    """Parse a no-Level flat IOT workbook driven by ``units`` and ``matrix_layouts``."""
    raw = pd.read_excel(path, sheet_name=data_sheet, header=None)
    raw = raw.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if raw.empty:
        raise WrongExcelFormat("The Excel data sheet is empty.")

    units_frame = _build_units_from_mriot_sheet(path, unit_sheet)
    item_sets = infer_item_sets_from_units(units_frame)
    row_meta_cols = 0
    first_row = raw.iloc[0, :]
    while row_meta_cols < raw.shape[1] and pd.isna(first_row.iloc[row_meta_cols]):
        row_meta_cols += 1
    if row_meta_cols == 0:
        raise WrongExcelFormat("Unable to detect the row-metadata columns of the explicit Excel layout.")

    header_rows = 0
    while header_rows < raw.shape[0]:
        prefix = raw.iloc[header_rows, :row_meta_cols]
        if prefix.notna().any():
            break
        header_rows += 1
    if header_rows == 0:
        raise WrongExcelFormat("Unable to detect the explicit header rows of the Excel layout.")

    columns_raw = raw.iloc[:header_rows, row_meta_cols:].T
    raw_column_tokens = [_compact_tokens(row) for row in columns_raw.itertuples(index=False, name=None)]

    productive_positions: list[int] = []
    final_demand_positions: list[int] = []
    productive_columns: list[tuple] = []
    productive_public_columns: list[tuple] = []
    productive_public_axis_names: tuple[str, ...] | None = None
    final_demand_columns: list[tuple] = []
    final_demand_public_columns: list[tuple] = []
    final_demand_axis_names: tuple[str, ...] | None = None
    final_demand_public_axis_names: tuple[str, ...] | None = None
    for position, tokens in enumerate(raw_column_tokens):
        try:
            productive_tuple, _, productive_public_tuple, productive_public_names = interpret_axis_tokens(
                tokens,
                iot_axis_names("Z", "to", matrix_layouts),
                matrix_name="Z",
                side="to",
            )
        except WrongInput:
            productive_tuple = None
            productive_public_tuple = None
            productive_public_names = None
        try:
            (
                final_demand_tuple,
                current_fd_axis_names,
                final_demand_public_tuple,
                current_fd_public_axis_names,
            ) = interpret_iot_final_demand_tokens(tokens)
        except WrongInput:
            final_demand_tuple = None
            current_fd_axis_names = None
            final_demand_public_tuple = None
            current_fd_public_axis_names = None

        if productive_tuple is None and final_demand_tuple is None:
            raise WrongExcelFormat(
                f"Unable to interpret explicit column {tokens}. Expected either productive or final-demand semantics."
            )

        terminal = (productive_tuple or final_demand_tuple)[-1]
        if terminal in item_sets:
            if item_sets[terminal] != "Sector":
                raise WrongExcelFormat(
                    f"Explicit productive columns should terminate in Sector items, got {terminal!r} -> {item_sets[terminal]!r}."
                )
            productive_positions.append(position)
            productive_columns.append(productive_tuple)
            productive_public_columns.append(productive_public_tuple)
            if productive_public_axis_names is None:
                productive_public_axis_names = productive_public_names
            elif productive_public_axis_names != productive_public_names:
                raise WrongExcelFormat(
                    f"Mixed productive column layouts are not supported: {productive_public_axis_names} and {productive_public_names}."
                )
        else:
            if final_demand_axis_names is None:
                final_demand_axis_names = current_fd_axis_names
            elif final_demand_axis_names != current_fd_axis_names:
                raise WrongExcelFormat(
                    f"Mixed final-demand column layouts are not supported: {final_demand_axis_names} and {current_fd_axis_names}."
                )
            if final_demand_public_axis_names is None:
                final_demand_public_axis_names = current_fd_public_axis_names
            elif final_demand_public_axis_names != current_fd_public_axis_names:
                raise WrongExcelFormat(
                    f"Mixed public final-demand column layouts are not supported: {final_demand_public_axis_names} and {current_fd_public_axis_names}."
                )
            final_demand_positions.append(position)
            final_demand_columns.append(final_demand_tuple)
            final_demand_public_columns.append(final_demand_public_tuple)

    if not productive_positions or not final_demand_positions:
        raise WrongExcelFormat("The explicit Excel layout should contain both productive and final-demand columns.")

    body = raw.iloc[header_rows:, :].reset_index(drop=True)
    row_meta = body.iloc[:, :row_meta_cols]
    values = body.iloc[:, row_meta_cols:].reset_index(drop=True)

    sector_rows: list[dict[str, object]] = []
    factor_rows: list[dict[str, object]] = []
    satellite_rows: list[dict[str, object]] = []
    for position, raw_tokens in enumerate(
        _compact_tokens(row) for row in row_meta.itertuples(index=False, name=None)
    ):
        tokens = raw_tokens
        if not tokens:
            continue
        try:
            sector_tuple, _, sector_public_tuple, sector_public_names = interpret_axis_tokens(
                tokens,
                iot_axis_names("Z", "from", matrix_layouts),
                matrix_name="Z",
                side="from",
            )
        except WrongInput:
            sector_tuple = None
            sector_public_tuple = None
            sector_public_names = None
        try:
            factor_tuple, _, factor_public_tuple, factor_public_names = interpret_axis_tokens(
                tokens,
                iot_axis_names("V", "from", matrix_layouts),
                matrix_name="V",
                side="from",
            )
        except WrongInput:
            factor_tuple = None
            factor_public_tuple = None
            factor_public_names = None
        try:
            (
                satellite_tuple,
                _,
                satellite_public_tuple,
                satellite_public_names,
            ) = interpret_axis_tokens(
                tokens,
                iot_axis_names("E", "from", matrix_layouts),
                matrix_name="E",
                side="from",
            )
        except WrongInput:
            satellite_tuple = None
            satellite_public_tuple = None
            satellite_public_names = None

        if sector_tuple is not None and item_sets.get(sector_tuple[-1]) == "Sector":
            sector_rows.append(
                {
                    "semantic": sector_tuple,
                    "public": sector_public_tuple,
                    "position": position,
                    "public_names": sector_public_names,
                }
            )
        elif factor_tuple is not None and item_sets.get(factor_tuple[-1]) == "Factor of production":
            factor_rows.append(
                {
                    "semantic": factor_tuple,
                    "public": factor_public_tuple,
                    "position": position,
                    "public_names": factor_public_names,
                }
            )
        elif satellite_tuple is not None and item_sets.get(satellite_tuple[-1]) == "Satellite account":
            satellite_rows.append(
                {
                    "semantic": satellite_tuple,
                    "public": satellite_public_tuple,
                    "position": position,
                    "public_names": satellite_public_names,
                }
            )
        else:
            raise WrongExcelFormat(
                f"Unable to classify explicit row {tokens}. The terminal item should be listed in units."
            )

    if not sector_rows or not factor_rows or not satellite_rows:
        raise WrongExcelFormat("Explicit IOT layout should contain sector, factor, and satellite rows.")

    def _matrix_from(row_info, column_positions, matrix_name):
        frame = values.iloc[[item["position"] for item in row_info], column_positions].copy().astype(float)
        row_public_names = row_info[0]["public_names"]
        row_public_labels = [item["public"] for item in row_info]
        frame.index = coerce_axis_names(pd.MultiIndex.from_tuples(row_public_labels), row_public_names)
        if matrix_name in {"Y", "EY", "VY"}:
            if len(final_demand_public_axis_names) == 1:
                frame.columns = pd.Index(
                    [value[0] for value in final_demand_public_columns],
                    name=final_demand_public_axis_names[0],
                )
            else:
                frame.columns = pd.MultiIndex.from_tuples(
                    final_demand_public_columns,
                    names=list(final_demand_public_axis_names),
                )
        else:
            frame.columns = coerce_axis_names(
                pd.MultiIndex.from_tuples(productive_public_columns),
                productive_public_axis_names,
            )
        return frame

    matrices = {
        "Z": _matrix_from(sector_rows, productive_positions, "Z"),
        "Y": _matrix_from(sector_rows, final_demand_positions, "Y"),
        "V": _matrix_from(factor_rows, productive_positions, "V"),
        "VY": _matrix_from(factor_rows, final_demand_positions, "VY"),
        "E": _matrix_from(satellite_rows, productive_positions, "E"),
        "EY": _matrix_from(satellite_rows, final_demand_positions, "EY"),
    }

    indexes = build_iot_indexes_from_units_and_y(units_frame, matrices)
    extra = {
        "block_specs": iot_block_specs_for_matrix_layouts(
            matrix_layouts,
            final_demand_axis_names=final_demand_axis_names,
        )
    }
    units = {
        label: frame.copy(deep=True)
        for label, frame in (
            ("Sector", units_frame.loc[["Sector"]].droplevel(0)),
            ("Factor of production", units_frame.loc[["Factor of production"]].droplevel(0)),
            ("Satellite account", units_frame.loc[["Satellite account"]].droplevel(0)),
        )
    }
    return {"baseline": matrices}, indexes, units, extra


register_parser("excel", ExcelParser())
