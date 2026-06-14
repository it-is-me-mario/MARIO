# -*- coding: utf-8 -*-
"""
the module contains the io file handlings (excel and txt)
"""
import copy
import xlsxwriter
import os
import pandas as pd
from copy import deepcopy as dc

from mario.log_exc.exceptions import NotImplementable
from mario.model.conventions import _MASTER_INDEX, _ENUM
from mario.ops.workbook_specs import (
    ADD_SECTOR_SHEETS,
    HEADER_CELL_FORMAT,
    SHOCK_FLAT_COLUMNS,
)


def _sh_excel(instance, num_shock, directory, clusters):
    """Write the Excel template used to define database shocks."""
    regions = dc(instance.get_index(_MASTER_INDEX["r"]))
    if instance.meta.table == "IOT":
        sectors = dc(instance.get_index(_MASTER_INDEX["s"]))
        activities = commodities = None
    else:
        activities = dc(instance.get_index(_MASTER_INDEX["a"]))
        commodities = dc(instance.get_index(_MASTER_INDEX["c"]))
        sectors = None
    factors = dc(instance.get_index(_MASTER_INDEX["f"]))
    extensions = dc(instance.get_index(_MASTER_INDEX["k"]))
    categories = dc(instance.get_index(_MASTER_INDEX["n"]))
    types = ["Percentage", "Absolute", "Update"]
    yn = ["Yes", "No"]

    cluster_targets = {
        _MASTER_INDEX["r"]: regions,
        _MASTER_INDEX["f"]: factors,
        _MASTER_INDEX["k"]: extensions,
        _MASTER_INDEX["n"]: categories,
    }
    if instance.meta.table == "IOT":
        cluster_targets[_MASTER_INDEX["s"]] = sectors
    else:
        cluster_targets[_MASTER_INDEX["a"]] = activities
        cluster_targets[_MASTER_INDEX["c"]] = commodities

    for key, values in cluster_targets.items():
        clusters_level = clusters.get(key)
        if clusters_level is not None:
            values.extend([*clusters_level])

    def _write_index_column(sheet, column, values):
        for i, value in enumerate(values, start=1):
            sheet.write(f"{column}{i}", value)

    def _should_include_sheet(block_name):
        if instance.meta.table == "IOT":
            return True

        try:
            block = instance.query(block_name)
        except Exception:
            return False

        if block is None or getattr(block, "empty", False):
            return False

        if hasattr(block, "to_numpy"):
            values = block.to_numpy()
        else:
            values = pd.DataFrame(block).to_numpy()

        return bool((values != 0).any())

    def _write_shock_sheet(workbook, header_format, *, sheet_name, columns, validations):
        sheet = workbook.add_worksheet(sheet_name)
        for idx, column in enumerate(columns):
            sheet.write(0, idx, column, header_format)

        for row in range(num_shock):
            excel_row = row + 2
            for col_idx, source in validations.items():
                sheet.data_validation(
                    f"{chr(65 + col_idx)}{excel_row}",
                    {"validate": "list", "source": source},
                )
        return sheet

    # Building the excel file
    file = directory
    workbook = xlsxwriter.Workbook(file)

    # Add a format for the header cells.
    header_format = workbook.add_format(HEADER_CELL_FORMAT)

    # Filling the index indeces sheet
    indeces = workbook.add_worksheet("indeces")
    if instance.meta.table == "IOT":
        _write_index_column(indeces, "A", regions)
        _write_index_column(indeces, "B", sectors)
        _write_index_column(indeces, "C", factors)
        _write_index_column(indeces, "D", extensions)
        _write_index_column(indeces, "E", categories)

        regions_ref = "=indeces!$A$1:$A${}".format(len(regions))
        sectors_ref = "=indeces!$B$1:$B${}".format(len(sectors))
        factors_ref = "=indeces!$C$1:$C${}".format(len(factors))
        extensions_ref = "=indeces!$D$1:$D${}".format(len(extensions))
        categories_ref = "=indeces!$E$1:$E${}".format(len(categories))
    else:
        _write_index_column(indeces, "A", regions)
        _write_index_column(indeces, "B", activities)
        _write_index_column(indeces, "C", commodities)
        _write_index_column(indeces, "D", factors)
        _write_index_column(indeces, "E", extensions)
        _write_index_column(indeces, "F", categories)

        regions_ref = "=indeces!$A$1:$A${}".format(len(regions))
        activities_ref = "=indeces!$B$1:$B${}".format(len(activities))
        commodities_ref = "=indeces!$C$1:$C${}".format(len(commodities))
        factors_ref = "=indeces!$D$1:$D${}".format(len(factors))
        extensions_ref = "=indeces!$E$1:$E${}".format(len(extensions))
        categories_ref = "=indeces!$F$1:$F${}".format(len(categories))

    # Building the main sheet
    main = workbook.add_worksheet("main")

    main.write("A1", "Legend", header_format)
    main.write("B1", "Description", header_format)
    main.write("C1", "Value", header_format)
    main.write("D1", "Unit of measure", header_format)
    main.write("E1", "Sensitivity", header_format)
    main.write("F1", "Min", header_format)
    main.write("G1", "Max", header_format)
    main.write("H1", "Step", header_format)
    main.write("I1", "Affected Parameter", header_format)
    main.write("J1", "Notes", header_format)
    main.write("K1", "References", header_format)

    for i in range(num_shock * 3):
        main.data_validation("E{}".format(i + 2), {"validate": "list", "source": yn})

    if instance.meta.table == "IOT":
        _write_shock_sheet(
            workbook,
            header_format,
            sheet_name=_ENUM.Y,
            columns=[
                SHOCK_FLAT_COLUMNS["region_from"],
                SHOCK_FLAT_COLUMNS["sector_from"],
                SHOCK_FLAT_COLUMNS["region_to"],
                SHOCK_FLAT_COLUMNS["category_to"],
                SHOCK_FLAT_COLUMNS["type"],
                SHOCK_FLAT_COLUMNS["value"],
            ],
            validations={
                0: regions_ref,
                1: sectors_ref,
                2: regions_ref,
                3: categories_ref,
                4: types,
            },
        )
        _write_shock_sheet(
            workbook,
            header_format,
            sheet_name=_ENUM.v,
            columns=[
                SHOCK_FLAT_COLUMNS["factor_from"],
                SHOCK_FLAT_COLUMNS["region_to"],
                SHOCK_FLAT_COLUMNS["sector_to"],
                SHOCK_FLAT_COLUMNS["type"],
                SHOCK_FLAT_COLUMNS["value"],
            ],
            validations={0: factors_ref, 1: regions_ref, 2: sectors_ref, 3: types},
        )
        _write_shock_sheet(
            workbook,
            header_format,
            sheet_name=_ENUM.e,
            columns=[
                SHOCK_FLAT_COLUMNS["satellite_from"],
                SHOCK_FLAT_COLUMNS["region_to"],
                SHOCK_FLAT_COLUMNS["sector_to"],
                SHOCK_FLAT_COLUMNS["type"],
                SHOCK_FLAT_COLUMNS["value"],
            ],
            validations={0: extensions_ref, 1: regions_ref, 2: sectors_ref, 3: types},
        )
        _write_shock_sheet(
            workbook,
            header_format,
            sheet_name=_ENUM.z,
            columns=[
                SHOCK_FLAT_COLUMNS["region_from"],
                SHOCK_FLAT_COLUMNS["sector_from"],
                SHOCK_FLAT_COLUMNS["region_to"],
                SHOCK_FLAT_COLUMNS["sector_to"],
                SHOCK_FLAT_COLUMNS["type"],
                SHOCK_FLAT_COLUMNS["value"],
            ],
            validations={0: regions_ref, 1: sectors_ref, 2: regions_ref, 3: sectors_ref, 4: types},
        )
    else:
        sheet_specs = [
            (
                _ENUM.u,
                "u",
                [
                    SHOCK_FLAT_COLUMNS["region_from"],
                    SHOCK_FLAT_COLUMNS["commodity_from"],
                    SHOCK_FLAT_COLUMNS["region_to"],
                    SHOCK_FLAT_COLUMNS["activity_to"],
                    SHOCK_FLAT_COLUMNS["type"],
                    SHOCK_FLAT_COLUMNS["value"],
                ],
                {0: regions_ref, 1: commodities_ref, 2: regions_ref, 3: activities_ref, 4: types},
            ),
            (
                _ENUM.s,
                "s",
                [
                    SHOCK_FLAT_COLUMNS["region_from"],
                    SHOCK_FLAT_COLUMNS["activity_from"],
                    SHOCK_FLAT_COLUMNS["region_to"],
                    SHOCK_FLAT_COLUMNS["commodity_to"],
                    SHOCK_FLAT_COLUMNS["type"],
                    SHOCK_FLAT_COLUMNS["value"],
                ],
                {0: regions_ref, 1: activities_ref, 2: regions_ref, 3: commodities_ref, 4: types},
            ),
            (
                "Ya",
                "Ya",
                [
                    SHOCK_FLAT_COLUMNS["region_from"],
                    SHOCK_FLAT_COLUMNS["activity_from"],
                    SHOCK_FLAT_COLUMNS["region_to"],
                    SHOCK_FLAT_COLUMNS["category_to"],
                    SHOCK_FLAT_COLUMNS["type"],
                    SHOCK_FLAT_COLUMNS["value"],
                ],
                {0: regions_ref, 1: activities_ref, 2: regions_ref, 3: categories_ref, 4: types},
            ),
            (
                "Yc",
                "Yc",
                [
                    SHOCK_FLAT_COLUMNS["region_from"],
                    SHOCK_FLAT_COLUMNS["commodity_from"],
                    SHOCK_FLAT_COLUMNS["region_to"],
                    SHOCK_FLAT_COLUMNS["category_to"],
                    SHOCK_FLAT_COLUMNS["type"],
                    SHOCK_FLAT_COLUMNS["value"],
                ],
                {0: regions_ref, 1: commodities_ref, 2: regions_ref, 3: categories_ref, 4: types},
            ),
            (
                "va",
                "va",
                [
                    SHOCK_FLAT_COLUMNS["factor_from"],
                    SHOCK_FLAT_COLUMNS["region_to"],
                    SHOCK_FLAT_COLUMNS["activity_to"],
                    SHOCK_FLAT_COLUMNS["type"],
                    SHOCK_FLAT_COLUMNS["value"],
                ],
                {0: factors_ref, 1: regions_ref, 2: activities_ref, 3: types},
            ),
            (
                "vc",
                "vc",
                [
                    SHOCK_FLAT_COLUMNS["factor_from"],
                    SHOCK_FLAT_COLUMNS["region_to"],
                    SHOCK_FLAT_COLUMNS["commodity_to"],
                    SHOCK_FLAT_COLUMNS["type"],
                    SHOCK_FLAT_COLUMNS["value"],
                ],
                {0: factors_ref, 1: regions_ref, 2: commodities_ref, 3: types},
            ),
            (
                "ea",
                "ea",
                [
                    SHOCK_FLAT_COLUMNS["satellite_from"],
                    SHOCK_FLAT_COLUMNS["region_to"],
                    SHOCK_FLAT_COLUMNS["activity_to"],
                    SHOCK_FLAT_COLUMNS["type"],
                    SHOCK_FLAT_COLUMNS["value"],
                ],
                {0: extensions_ref, 1: regions_ref, 2: activities_ref, 3: types},
            ),
            (
                "ec",
                "ec",
                [
                    SHOCK_FLAT_COLUMNS["satellite_from"],
                    SHOCK_FLAT_COLUMNS["region_to"],
                    SHOCK_FLAT_COLUMNS["commodity_to"],
                    SHOCK_FLAT_COLUMNS["type"],
                    SHOCK_FLAT_COLUMNS["value"],
                ],
                {0: extensions_ref, 1: regions_ref, 2: commodities_ref, 3: types},
            ),
        ]

        for block_name, sheet_name, columns, validations in sheet_specs:
            if not _should_include_sheet(block_name):
                continue
            _write_shock_sheet(
                workbook,
                header_format,
                sheet_name=sheet_name,
                columns=columns,
                validations=validations,
            )

    workbook.close()


def dataframe_to_xlsx(path, **kwargs):
    """Write arbitrary dataframes to a workbook while preserving labels."""
    file = xlsxwriter.Workbook(path)

    for sheet, data in kwargs.items():
        index_levels = data.index.nlevels
        columns_levels = data.columns.nlevels

        rows_start = columns_levels
        cols_start = index_levels

        sheet = file.add_worksheet(sheet)
        for level in range(index_levels):
            rows = data.index.get_level_values(level).to_list()
            counter = 0
            for row in rows:
                sheet.write(rows_start + counter, level, row)
                counter += 1

        for level in range(columns_levels):
            cols = data.columns.get_level_values(level).to_list()
            counter = 0
            for col in cols:
                sheet.write(level, cols_start + counter, col)
                counter += 1

        for row in range(data.shape[0]):
            for col in range(data.shape[1]):
                sheet.write(rows_start + row, cols_start + col, data.iloc[row, col])

    file.close()


def _iot_historical_terminal_level(matrix_name, side):
    """Return the historical ``Level`` label used by the Excel exporter."""
    if side == "index":
        if matrix_name in {_ENUM.Z, _ENUM.z, _ENUM.Y}:
            return _MASTER_INDEX["s"]
        if matrix_name in {_ENUM.V, _ENUM.v, _ENUM.VY}:
            return _MASTER_INDEX["f"]
        if matrix_name in {_ENUM.E, _ENUM.e, _ENUM.EY}:
            return _MASTER_INDEX["k"]
    elif side == "columns":
        if matrix_name in {_ENUM.Z, _ENUM.z, _ENUM.V, _ENUM.v, _ENUM.E, _ENUM.e}:
            return _MASTER_INDEX["s"]
        if matrix_name in {_ENUM.Y, _ENUM.EY, _ENUM.VY}:
            return _MASTER_INDEX["n"]

    raise NotImplementable(
        f"Historical Excel export does not support matrix {matrix_name!r} on axis {side!r}."
    )


def _axis_labels(axis):
    """Return raw axis tuples and public names from a pandas axis."""
    if isinstance(axis, pd.MultiIndex):
        return [tuple(value) for value in axis.tolist()], tuple(axis.names)
    return [(value,) for value in axis.tolist()], (axis.name,)


def _to_historical_iot_axis(axis, *, matrix_name, side):
    """Convert one IOT axis to the historical ``Region/Level/Item`` layout."""
    raw_values, names = _axis_labels(axis)
    clean_names = tuple(name if name is not None else "Item" for name in names)
    historical_names = (_MASTER_INDEX["r"], "Level", "Item")
    terminal_level = _iot_historical_terminal_level(matrix_name, side)

    if clean_names == historical_names:
        return pd.MultiIndex.from_tuples(raw_values, names=list(historical_names))

    tuples = []
    for value in raw_values:
        if len(value) == 2 and clean_names == (_MASTER_INDEX["r"], terminal_level):
            tuples.append((value[0], terminal_level, value[1]))
            continue
        if len(value) == 1 and clean_names in {(terminal_level,), ("Item",), (None,)}:
            tuples.append(("-", terminal_level, value[0]))
            continue
        if len(value) == 2 and clean_names == ("Level", "Item"):
            tuples.append(("-", value[0], value[1]))
            continue
        if len(value) == 2 and clean_names == (_MASTER_INDEX["r"], "Item"):
            tuples.append((value[0], terminal_level, value[1]))
            continue
        raise NotImplementable(
            "Historical Excel export supports only classic or by-region IOT axes. "
            f"Matrix {matrix_name!r} on {side!r} has axis names {clean_names} and values like {value}."
        )

    return pd.MultiIndex.from_tuples(tuples, names=list(historical_names))


def _prepare_iot_excel_export_frame(frame, *, matrix_name):
    """Return one IOT matrix with historical public axes for Excel export."""
    exported = frame.copy(deep=True)
    exported.index = _to_historical_iot_axis(
        exported.index,
        matrix_name=matrix_name,
        side="index",
    )
    exported.columns = _to_historical_iot_axis(
        exported.columns,
        matrix_name=matrix_name,
        side="columns",
    )
    return exported


def _reindex_iot_excel_export_frame(frame, *, index=None, columns=None, label):
    """Reindex one export block only when its labels match exactly."""
    if index is not None:
        missing = index.difference(frame.index)
        extra = frame.index.difference(index)
        if len(missing) or len(extra):
            raise NotImplementable(
                f"Excel export cannot align {label} rows because labels do not match exactly."
            )
        frame = frame.loc[index, :]

    if columns is not None:
        missing = columns.difference(frame.columns)
        extra = frame.columns.difference(columns)
        if len(missing) or len(extra):
            raise NotImplementable(
                f"Excel export cannot align {label} columns because labels do not match exactly."
            )
        frame = frame.loc[:, columns]

    return frame


def _align_iot_excel_export_blocks(Z, V, E, Y, EY, VY):
    """Align dependent IOT blocks to the row and column order shown in Excel."""
    V = _reindex_iot_excel_export_frame(V, columns=Z.columns, label="V")
    E = _reindex_iot_excel_export_frame(E, columns=Z.columns, label="E")
    Y = _reindex_iot_excel_export_frame(Y, index=Z.index, label="Y")
    VY = _reindex_iot_excel_export_frame(VY, index=V.index, columns=Y.columns, label="VY")
    EY = _reindex_iot_excel_export_frame(EY, index=E.index, columns=Y.columns, label="EY")
    return Z, V, E, Y, EY, VY


def _is_historical_iot_axis(axis, *, matrix_name, side):
    """Return whether one IOT axis already fits the historical Excel surface."""
    _, names = _axis_labels(axis)
    clean_names = tuple(name if name is not None else "Item" for name in names)
    terminal_level = _iot_historical_terminal_level(matrix_name, side)
    historical_names = (_MASTER_INDEX["r"], "Level", "Item")

    if clean_names == historical_names:
        return True

    if side == "index" and matrix_name in {_ENUM.V, _ENUM.v, _ENUM.VY, _ENUM.E, _ENUM.e, _ENUM.EY}:
        return len(clean_names) == 1 and clean_names[0] in {terminal_level, "Item"}

    return False


def _needs_explicit_iot_excel_export(matrices):
    """Return whether the queried IOT blocks require explicit no-Level export."""
    for matrix_name, frame in matrices.items():
        if matrix_name not in {_ENUM.Z, _ENUM.z, _ENUM.Y, _ENUM.V, _ENUM.v, _ENUM.E, _ENUM.e, _ENUM.EY, _ENUM.VY}:
            continue
        if not _is_historical_iot_axis(frame.index, matrix_name=matrix_name, side="index"):
            return True
        if not _is_historical_iot_axis(frame.columns, matrix_name=matrix_name, side="columns"):
            return True
    return False


def _pad_axis_tokens(tokens, *, total_levels, axis_names):
    """Pad one axis tuple for explicit Excel export while preserving region-first semantics."""
    values = tuple(tokens)
    if len(values) >= total_levels:
        return values

    clean_names = tuple(name if name is not None else "Item" for name in axis_names)
    pad = (None,) * (total_levels - len(values))
    if clean_names and clean_names[0] == _MASTER_INDEX["r"]:
        return values + pad
    return pad + values


def _write_header_value(sheet, row, col, value, header_format):
    """Write one header token while preserving blank placeholders."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        sheet.write_blank(row, col, None, header_format)
    else:
        sheet.write(row, col, value, header_format)


def _write_explicit_iot_matrices(sheet, Z, V, E, Y, EY, VY, value_format, header_format):
    """Write the explicit no-Level IOT workbook layout."""
    row_meta_cols = max(Z.index.nlevels, V.index.nlevels, E.index.nlevels)
    header_rows = max(Z.columns.nlevels, Y.columns.nlevels)

    productive_columns, productive_names = _axis_labels(Z.columns)
    final_demand_columns, final_demand_names = _axis_labels(Y.columns)

    for col_offset, tokens in enumerate(productive_columns):
        padded = _pad_axis_tokens(
            tokens,
            total_levels=header_rows,
            axis_names=productive_names,
        )
        for row_offset, value in enumerate(padded):
            _write_header_value(
                sheet,
                row_offset,
                row_meta_cols + col_offset,
                value,
                header_format,
            )

    for col_offset, tokens in enumerate(final_demand_columns):
        padded = _pad_axis_tokens(
            tokens,
            total_levels=header_rows,
            axis_names=final_demand_names,
        )
        for row_offset, value in enumerate(padded):
            _write_header_value(
                sheet,
                row_offset,
                row_meta_cols + Z.shape[1] + col_offset,
                value,
                header_format,
            )

    block_specs = [
        (Z, 0),
        (V, Z.shape[0]),
        (E, Z.shape[0] + V.shape[0]),
    ]
    for frame, row_offset_base in block_specs:
        labels, names = _axis_labels(frame.index)
        for row_offset, tokens in enumerate(labels):
            padded = _pad_axis_tokens(
                tokens,
                total_levels=row_meta_cols,
                axis_names=names,
            )
            for col_offset, value in enumerate(padded):
                _write_header_value(
                    sheet,
                    header_rows + row_offset_base + row_offset,
                    col_offset,
                    value,
                    header_format,
                )

    for row in range(Z.shape[0]):
        for col in range(Z.shape[1]):
            sheet.write(header_rows + row, row_meta_cols + col, Z.iloc[row, col], value_format)

    for row in range(V.shape[0]):
        for col in range(V.shape[1]):
            sheet.write(header_rows + Z.shape[0] + row, row_meta_cols + col, V.iloc[row, col], value_format)

    for row in range(E.shape[0]):
        for col in range(E.shape[1]):
            sheet.write(header_rows + Z.shape[0] + V.shape[0] + row, row_meta_cols + col, E.iloc[row, col], value_format)

    for row in range(Y.shape[0]):
        for col in range(Y.shape[1]):
            sheet.write(header_rows + row, row_meta_cols + Z.shape[1] + col, Y.iloc[row, col], value_format)

    for row in range(VY.shape[0]):
        for col in range(VY.shape[1]):
            sheet.write(header_rows + Z.shape[0] + row, row_meta_cols + Z.shape[1] + col, VY.iloc[row, col], value_format)

    for row in range(EY.shape[0]):
        for col in range(EY.shape[1]):
            sheet.write(header_rows + Z.shape[0] + V.shape[0] + row, row_meta_cols + Z.shape[1] + col, EY.iloc[row, col], value_format)


def wrirte_matrices(sheet, Z, V, E, Y, EY, VY, flow_format, header_format):
    """Write the canonical MARIO block layout to one worksheet."""
    row_counter = 0
    col_counter = 0
    # indeces
    for row in range(Z.shape[0]):
        sheet.write(
            "A{}".format(row + 4), Z.index.get_level_values(0)[row], header_format
        )
        sheet.write(
            "B{}".format(row + 4), Z.index.get_level_values(1)[row], header_format
        )
        sheet.write(
            "C{}".format(row + 4), Z.index.get_level_values(2)[row], header_format
        )
        row_counter += 1

    # columns
    for row in range(Z.shape[1]):
        sheet.write(0, row + 3, Z.columns.get_level_values(0)[row], header_format)
        sheet.write(1, row + 3, Z.columns.get_level_values(1)[row], header_format)
        sheet.write(2, row + 3, Z.columns.get_level_values(2)[row], header_format)
        col_counter += 1

    for row in range(Z.shape[0]):
        for col in range(Z.shape[1]):
            sheet.write(row + 3, col + 3, Z.iloc[row, col], flow_format)

    # Filling the V
    row_v_counter = row_counter
    for row in range(V.shape[0]):
        sheet.write(
            "A{}".format(row + 4 + row_counter),
            V.index.get_level_values(0)[row],
            header_format,
        )
        sheet.write(
            "B{}".format(row + 4 + row_counter),
            V.index.get_level_values(1)[row],
            header_format,
        )
        sheet.write(
            "C{}".format(row + 4 + row_counter),
            V.index.get_level_values(2)[row],
            header_format,
        )
        row_v_counter += 1

    for row in range(V.shape[0]):
        for col in range(V.shape[1]):
            sheet.write(row + 3 + row_counter, col + 3, V.iloc[row, col], flow_format)

    # Filling the E
    for row in range(E.shape[0]):
        sheet.write(
            "A{}".format(row + 4 + row_v_counter),
            E.index.get_level_values(0)[row],
            header_format,
        )
        sheet.write(
            "B{}".format(row + 4 + row_v_counter),
            E.index.get_level_values(1)[row],
            header_format,
        )
        sheet.write(
            "C{}".format(row + 4 + row_v_counter),
            E.index.get_level_values(2)[row],
            header_format,
        )

    for row in range(E.shape[0]):
        for col in range(E.shape[1]):
            sheet.write(row + 3 + row_v_counter, col + 3, E.iloc[row, col], flow_format)

    # Filling Y
    # columns
    for row in range(Y.shape[1]):
        sheet.write(
            0, row + 3 + col_counter, Y.columns.get_level_values(0)[row], header_format
        )
        sheet.write(
            1, row + 3 + col_counter, Y.columns.get_level_values(1)[row], header_format
        )
        sheet.write(
            2, row + 3 + col_counter, Y.columns.get_level_values(2)[row], header_format
        )

    for row in range(Y.shape[0]):
        for col in range(Y.shape[1]):
            sheet.write(row + 3, col + 3 + col_counter, Y.iloc[row, col], flow_format)

    # Filling VY
    for row in range(VY.shape[0]):
        for col in range(VY.shape[1]):
            sheet.write(
                Z.shape[0] + 3 + row,
                Z.shape[1] + 3 + col,
                VY.iloc[row, col],
                flow_format,
            )

    # Filling EY
    for row in range(EY.shape[0]):
        for col in range(EY.shape[1]):
            sheet.write(
                Z.shape[0] + 3 + V.shape[0] + row,
                Z.shape[1] + 3 + col,
                EY.iloc[row, col],
                flow_format,
            )


def _row_tokens_for_explicit_sut_export(label, *, productive: bool) -> list[object | None]:
    """Return the explicit SUT row tokens written to the Excel export."""
    if isinstance(label, tuple):
        values = list(label)
    else:
        values = [label]

    if productive and len(values) == 3:
        return [values[0], values[2], None]

    return values + [None] * max(0, 3 - len(values))


def _write_explicit_sut_matrices(
    sheet,
    U,
    S,
    Va,
    Vc,
    Ea,
    Ec,
    Ya,
    Yc,
    EY,
    VY,
    flow_format,
    header_format,
):
    """Write one native split SUT workbook without materializing unified Z/Y."""
    activity_columns = list(U.columns)
    commodity_columns = list(S.columns)
    productive_columns = activity_columns + commodity_columns
    final_demand_columns = list(Ya.columns)

    for col, column in enumerate(productive_columns, start=3):
        sheet.write(0, col, column[0], header_format)
        sheet.write(1, col, column[2], header_format)

    for offset, column in enumerate(final_demand_columns, start=3 + len(productive_columns)):
        sheet.write(0, offset, column[0], header_format)
        sheet.write(1, offset, column[2], header_format)

    blank_activity = [None] * len(activity_columns)
    blank_commodity = [None] * len(commodity_columns)

    def _write_body_row(row_number, tokens, productive_values, final_demand_values):
        for col, value in enumerate(tokens):
            if value is not None:
                sheet.write(row_number, col, value, header_format)
        for col, value in enumerate(productive_values, start=3):
            if value is not None:
                sheet.write(row_number, col, value, flow_format)
        for col, value in enumerate(final_demand_values, start=3 + len(productive_columns)):
            if value is not None:
                sheet.write(row_number, col, value, flow_format)

    row_number = 2
    for row in U.index:
        _write_body_row(
            row_number,
            _row_tokens_for_explicit_sut_export(row, productive=True),
            U.loc[row, activity_columns].tolist() + blank_commodity,
            Yc.loc[row, final_demand_columns].tolist(),
        )
        row_number += 1

    for row in S.index:
        _write_body_row(
            row_number,
            _row_tokens_for_explicit_sut_export(row, productive=True),
            blank_activity + S.loc[row, commodity_columns].tolist(),
            Ya.loc[row, final_demand_columns].tolist(),
        )
        row_number += 1

    for row in Va.index:
        _write_body_row(
            row_number,
            _row_tokens_for_explicit_sut_export(row, productive=False),
            Va.loc[row, activity_columns].tolist() + Vc.loc[row, commodity_columns].tolist(),
            VY.loc[row, final_demand_columns].tolist(),
        )
        row_number += 1

    for row in Ea.index:
        _write_body_row(
            row_number,
            _row_tokens_for_explicit_sut_export(row, productive=False),
            Ea.loc[row, activity_columns].tolist() + Ec.loc[row, commodity_columns].tolist(),
            EY.loc[row, final_demand_columns].tolist(),
        )
        row_number += 1


def database_excel(instance, flows, coefficients, directory, scenario):
    """Export one scenario to the standard MARIO Excel workbook format."""
    file = directory
    workbook = xlsxwriter.Workbook(file)

    # Add a format for the header cells.
    header_format = workbook.add_format(HEADER_CELL_FORMAT)

    if flows:
        flows = workbook.add_worksheet("flows")
        flow_format = workbook.add_format({"num_format": "0.0;-0.0;-"})
        if instance.table_type == "SUT":
            data = instance.query(
                matrices=["U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", _ENUM.EY, _ENUM.VY],
                scenarios=scenario,
            )
            _write_explicit_sut_matrices(
                flows,
                data["U"],
                data["S"],
                data["Va"],
                data["Vc"],
                data["Ea"],
                data["Ec"],
                data["Ya"],
                data["Yc"],
                data[_ENUM.EY],
                data[_ENUM.VY],
                flow_format,
                header_format,
            )
        else:
            data = instance.query(
                matrices=[_ENUM.V, _ENUM.E, _ENUM.Z, _ENUM.Y, _ENUM.EY, _ENUM.VY],
                scenarios=scenario,
            )
            data[_ENUM.Z], data[_ENUM.V], data[_ENUM.E], data[_ENUM.Y], data[_ENUM.EY], data[_ENUM.VY] = _align_iot_excel_export_blocks(
                data[_ENUM.Z],
                data[_ENUM.V],
                data[_ENUM.E],
                data[_ENUM.Y],
                data[_ENUM.EY],
                data[_ENUM.VY],
            )

            if _needs_explicit_iot_excel_export(data):
                _write_explicit_iot_matrices(
                    flows,
                    data[_ENUM.Z],
                    data[_ENUM.V],
                    data[_ENUM.E],
                    data[_ENUM.Y],
                    data[_ENUM.EY],
                    data[_ENUM.VY],
                    flow_format,
                    header_format,
                )
            else:
                Z = _prepare_iot_excel_export_frame(data[_ENUM.Z], matrix_name=_ENUM.Z)
                Y = _prepare_iot_excel_export_frame(data[_ENUM.Y], matrix_name=_ENUM.Y)
                V = _prepare_iot_excel_export_frame(data[_ENUM.V], matrix_name=_ENUM.V)
                E = _prepare_iot_excel_export_frame(data[_ENUM.E], matrix_name=_ENUM.E)
                EY = _prepare_iot_excel_export_frame(data[_ENUM.EY], matrix_name=_ENUM.EY)
                VY = _prepare_iot_excel_export_frame(data[_ENUM.VY], matrix_name=_ENUM.VY)
                wrirte_matrices(flows, Z, V, E, Y, EY, VY, flow_format, header_format)

    if coefficients:
        coefficients = workbook.add_worksheet("coefficients")
        coeff_format = workbook.add_format({"num_format": "0.000;-0.000;-"})
        if instance.table_type == "SUT":
            data = instance.query(
                matrices=["u", "s", "Ya", "Yc", "va", "vc", "ea", "ec", _ENUM.EY, _ENUM.VY],
                scenarios=scenario,
            )
            _write_explicit_sut_matrices(
                coefficients,
                data["u"],
                data["s"],
                data["va"],
                data["vc"],
                data["ea"],
                data["ec"],
                data["Ya"],
                data["Yc"],
                data[_ENUM.EY],
                data[_ENUM.VY],
                coeff_format,
                header_format,
            )
        else:
            matrices = [_ENUM.v, _ENUM.e, _ENUM.z, _ENUM.Y, _ENUM.EY, _ENUM.VY]
            data = instance.query(
                matrices=matrices,
                scenarios=scenario,
            )
            data[_ENUM.z], data[_ENUM.v], data[_ENUM.e], data[_ENUM.Y], data[_ENUM.EY], data[_ENUM.VY] = _align_iot_excel_export_blocks(
                data[_ENUM.z],
                data[_ENUM.v],
                data[_ENUM.e],
                data[_ENUM.Y],
                data[_ENUM.EY],
                data[_ENUM.VY],
            )

            if _needs_explicit_iot_excel_export(data):
                _write_explicit_iot_matrices(
                    coefficients,
                    data[_ENUM.z],
                    data[_ENUM.v],
                    data[_ENUM.e],
                    data[_ENUM.Y],
                    data[_ENUM.EY],
                    data[_ENUM.VY],
                    coeff_format,
                    header_format,
                )
            else:
                Z = _prepare_iot_excel_export_frame(data[_ENUM.z], matrix_name=_ENUM.z)
                Y = _prepare_iot_excel_export_frame(data[_ENUM.Y], matrix_name=_ENUM.Y)
                V = _prepare_iot_excel_export_frame(data[_ENUM.v], matrix_name=_ENUM.v)
                E = _prepare_iot_excel_export_frame(data[_ENUM.e], matrix_name=_ENUM.e)
                EY = _prepare_iot_excel_export_frame(data[_ENUM.EY], matrix_name=_ENUM.EY)
                VY = _prepare_iot_excel_export_frame(data[_ENUM.VY], matrix_name=_ENUM.VY)
                wrirte_matrices(coefficients, Z, V, E, Y, EY, VY, coeff_format, header_format)

    units = workbook.add_worksheet("units")

    data = instance.units
    units.write("C1", "unit", header_format)

    counter = 2

    if instance.table_type == "SUT":
        keys = [
            _MASTER_INDEX["a"],
            _MASTER_INDEX["c"],
            _MASTER_INDEX["f"],
            _MASTER_INDEX["k"],
        ]
    else:
        keys = [_MASTER_INDEX["s"], _MASTER_INDEX["f"], _MASTER_INDEX["k"]]

    for key in keys:
        item = data[key]
        for row in range(item.shape[0]):
            units.write("A{}".format(counter), key, header_format)
            units.write("B{}".format(counter), item.index[row], header_format)
            try:
                units.write("C{}".format(counter), item.iloc[row, 0])
            except TypeError:
                units.write("C{}".format(counter), "None")

            counter += 1

    workbook.close()


def database_txt(instance, flows, coefficients, path, scenario, _format, sep):
    """Export one scenario to a directory tree of delimited text files."""
    if flows:
        flows = instance.query(
            matrices=[_ENUM.V, _ENUM.E, _ENUM.Z, _ENUM.Y, _ENUM.X, _ENUM.EY, _ENUM.VY],
            scenarios=[scenario],
        )
        if not os.path.exists(r"{}/{}".format(path, "flows")):
            os.mkdir(r"{}/{}".format(path, "flows"))

        for key, value in flows.items():
            if os.path.exists(r"{}/{}/{}.{}".format(path, "flows", key, _format)):
                os.remove(r"{}/{}/{}.{}".format(path, "flows", key, _format))

            value.to_csv(
                r"{}/{}/{}.{}".format(path, "flows", key, _format),
                header=True,
                index=True,
                sep=sep,
                mode="a",
            )

    if coefficients:
        coefficients = instance.query(
            matrices=[_ENUM.v, _ENUM.e, _ENUM.z, _ENUM.Y, _ENUM.EY, _ENUM.VY],
            scenarios=[scenario],
        )

        if not os.path.exists(r"{}/{}".format(path, "coefficients")):
            os.mkdir(r"{}/{}".format(path, "coefficients"))

        for key, value in coefficients.items():
            if os.path.exists(
                r"{}/{}/{}.{}".format(path, "coefficients", key, _format)
            ):
                os.remove(r"{}/{}/{}.{}".format(path, "coefficients", key, _format))
            value.to_csv(
                r"{}/{}/{}.{}".format(path, "coefficients", key, _format),
                header=True,
                index=True,
                sep=sep,
                mode="a",
            )

    units = copy.deepcopy(instance.units)
    _units = pd.DataFrame()
    _index = []

    if instance.table_type == "SUT":
        keys = [
            _MASTER_INDEX["a"],
            _MASTER_INDEX["c"],
            _MASTER_INDEX["f"],
            _MASTER_INDEX["k"],
        ]
    else:
        keys = [_MASTER_INDEX["s"], _MASTER_INDEX["f"], _MASTER_INDEX["k"]]

    for key in keys:
        value = units[key]
        _index += [key] * value.shape[0]
        _units = pd.concat([_units, value])

    _units.index = [_index, _units.index]

    unit_dirs = []
    if coefficients:
        unit_dirs += ["coefficients"]
    if flows:
        unit_dirs += ["flows"]

    for unit_dir in unit_dirs:
        if not os.path.exists(r"{}/{}".format(path, unit_dir)):
            os.mkdir(r"{}/{}".format(path, unit_dir))

        if os.path.exists(r"{}/{}/units.{}".format(path, unit_dir, _format)):
            os.remove(r"{}/{}/units.{}".format(path, unit_dir, _format))

        _units.to_csv(
            r"{}/{}/units.{}".format(path, unit_dir, _format),
            header=True,
            index=True,
            sep=sep,
            mode="a",
        )


def add_sector_writer(matrices, path):
    """Write helper workbook content for add-sector templates."""
    workbook = xlsxwriter.Workbook(path)

    # Add a format for the header cells.
    header_format = workbook.add_format(HEADER_CELL_FORMAT)

    for key, matrix in matrices.items:
        sheet = workbook.add_worksheet(key)

        if key in ["e", "v"]:
            row_count = 4
            for row in matrix.index.to_list():
                sheet.write("A{}".format(row_count), row, header_format)
                row_count += 1


def _add_sector_sut(instance, sectors, regions, path, item, num_validation=30):
    """Write the SUT add-sector workbook with validation lists."""
    file = xlsxwriter.Workbook(path)
    header_format = file.add_format(HEADER_CELL_FORMAT)

    len_sectors = len(sectors)
    len_regions = len(regions)

    regions = regions * len_sectors
    regions.sort()

    sectors = sectors * len_regions

    indeces = file.add_worksheet("indeces")

    if item == _MASTER_INDEX["c"]:
        counter_item = _MASTER_INDEX["a"]
    else:
        counter_item = _MASTER_INDEX["c"]

    to_print = {
        "A": instance.get_index(_MASTER_INDEX["r"]),
        "B": instance.get_index(_MASTER_INDEX["c"]),
        "C": instance.get_index(_MASTER_INDEX["a"]),
        "D": [_MASTER_INDEX["a"]],
        "E": [_MASTER_INDEX["c"]],
        "F": instance.get_index(_MASTER_INDEX["n"]),
        "G": instance.get_index(_MASTER_INDEX["f"]),
        "H": instance.get_index(_MASTER_INDEX["k"]),
        "I": [_MASTER_INDEX["n"]],
    }

    for column, _indeces in to_print.items():
        for row in range(len(_indeces)):
            indeces.write("{}{}".format(column, row + 1), _indeces[row])

    regions_ref = "=indeces!$A$1:$A${}".format(len(to_print["A"]))
    commodity_ref = "=indeces!$B$1:$B${}".format(len(to_print["B"]))
    activities_ref = "=indeces!$C$1:$C${}".format(len(to_print["C"]))
    a_categories_ref = "=indeces!$D$1:$D${}".format(len(to_print["D"]))
    c_categories_ref = "=indeces!$E$1:$E${}".format(len(to_print["E"]))
    demand_ref = "=indeces!$F$1:$F${}".format(len(to_print["F"]))
    factors_ref = "=indeces!$G$1:$G${}".format(len(to_print["G"]))
    extensions_ref = "=indeces!$H$1:$H${}".format(len(to_print["H"]))
    consumption_ref = "=indeces!$I$1:$I${}".format(len(to_print["I"]))

    demand = file.add_worksheet(ADD_SECTOR_SHEETS["fd"]["sheet"])

    demand.write("C1", "Region", header_format)
    demand.write("C2", "Level", header_format)
    demand.write("C3", "Category", header_format)

    for region in range(len(regions)):
        demand.write(region + 3, 0, regions[region], header_format)
        demand.write(region + 3, 1, item, header_format)
        demand.write(region + 3, 2, sectors[region], header_format)

    demand.data_validation(
        0, 3, 0, 3 + num_validation, {"validate": "list", "source": regions_ref}
    )
    demand.data_validation(
        1, 3, 1, 3 + num_validation, {"validate": "list", "source": consumption_ref}
    )
    demand.data_validation(
        2, 3, 2, 3 + num_validation, {"validate": "list", "source": demand_ref}
    )

    factors = file.add_worksheet(ADD_SECTOR_SHEETS["fp"]["sheet"])

    for region in range(len(regions)):
        factors.write(0, region + 1, regions[region], header_format)
        factors.write(1, region + 1, item, header_format)
        factors.write(2, region + 1, sectors[region], header_format)

    factors.write("A3", "Factor", header_format)

    for i in range(num_validation):
        factors.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": factors_ref}
        )

    extensions = file.add_worksheet(ADD_SECTOR_SHEETS["sa"]["sheet"])

    for region in range(len(regions)):
        extensions.write(0, region + 1, regions[region], header_format)
        extensions.write(1, region + 1, item, header_format)
        extensions.write(2, region + 1, sectors[region], header_format)

    extensions.write("A3", "Extension", header_format)

    for i in range(num_validation):
        extensions.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": extensions_ref}
        )

    upper_z = file.add_worksheet(
        ADD_SECTOR_SHEETS["it"]["sheet"]
        if item == _MASTER_INDEX["c"]
        else ADD_SECTOR_SHEETS["if"]["sheet"]
    )

    if item == _MASTER_INDEX["a"]:
        for region in range(len(regions)):
            upper_z.write(0, region + 3, regions[region], header_format)
            upper_z.write(1, region + 3, _MASTER_INDEX["a"], header_format)
            upper_z.write(2, region + 3, sectors[region], header_format)

        upper_z.write("A3", "Region", header_format)
        upper_z.write("B3", "Category", header_format)
        upper_z.write("C3", _MASTER_INDEX["c"], header_format)

        for i in range(num_validation):
            upper_z.data_validation(
                "A{}".format(i + 2), {"validate": "list", "source": regions_ref}
            )
            upper_z.data_validation(
                "B{}".format(i + 2), {"validate": "list", "source": c_categories_ref}
            )
            upper_z.data_validation(
                "C{}".format(i + 2), {"validate": "list", "source": commodity_ref}
            )

    else:
        upper_z.write("C1", "Region", header_format)
        upper_z.write("C2", "Category", header_format)
        upper_z.write("C3", _MASTER_INDEX["a"], header_format)

        for region in range(len(regions)):
            upper_z.write(region + 3, 0, regions[region], header_format)
            upper_z.write(region + 3, 1, _MASTER_INDEX["c"], header_format)
            upper_z.write(region + 3, 2, sectors[region], header_format)

        upper_z.data_validation(
            0, 3, 0, 3 + num_validation, {"validate": "list", "source": regions_ref}
        )
        upper_z.data_validation(
            1,
            3,
            1,
            3 + num_validation,
            {"validate": "list", "source": a_categories_ref},
        )
        upper_z.data_validation(
            2, 3, 2, 3 + num_validation, {"validate": "list", "source": activities_ref}
        )

    lower_z = file.add_worksheet(ADD_SECTOR_SHEETS["of"]["sheet"])

    if item == _MASTER_INDEX["c"]:
        for region in range(len(regions)):
            lower_z.write(0, region + 3, regions[region], header_format)
            lower_z.write(1, region + 3, _MASTER_INDEX["c"], header_format)
            lower_z.write(2, region + 3, sectors[region], header_format)

        lower_z.write("A3", "Region", header_format)
        lower_z.write("B3", "Category", header_format)
        lower_z.write("C3", _MASTER_INDEX["a"], header_format)

        for i in range(num_validation):
            lower_z.data_validation(
                "A{}".format(i + 2), {"validate": "list", "source": regions_ref}
            )
            lower_z.data_validation(
                "B{}".format(i + 2), {"validate": "list", "source": a_categories_ref}
            )
            lower_z.data_validation(
                "C{}".format(i + 2), {"validate": "list", "source": activities_ref}
            )

    else:
        lower_z.write("C1", "Region", header_format)
        lower_z.write("C2", "Category", header_format)
        lower_z.write("C3", _MASTER_INDEX["c"], header_format)

        for region in range(len(regions)):
            lower_z.write(region + 3, 0, regions[region], header_format)
            lower_z.write(region + 3, 1, _MASTER_INDEX["a"], header_format)
            lower_z.write(region + 3, 2, sectors[region], header_format)

        lower_z.data_validation(
            0, 3, 0, 3 + num_validation, {"validate": "list", "source": regions_ref}
        )
        lower_z.data_validation(
            1,
            3,
            1,
            3 + num_validation,
            {"validate": "list", "source": c_categories_ref},
        )
        lower_z.data_validation(
            2, 3, 2, 3 + num_validation, {"validate": "list", "source": commodity_ref}
        )

    units = file.add_worksheet(ADD_SECTOR_SHEETS["un"]["sheet"])

    units.write("B1", "unit", header_format)
    _ = 2
    for row in set(sectors):
        units.write("A{}".format(_), row, header_format)
        _ += 1

    file.close()


def _add_sector_iot(instance, sectors, regions, path, num_validation=30):
    """Write the IOT add-sector workbook with validation lists."""
    file = xlsxwriter.Workbook(path)
    header_format = file.add_format(HEADER_CELL_FORMAT)

    to_print = {
        "A": instance.get_index(_MASTER_INDEX["r"]),
        "B": [_MASTER_INDEX["s"]],
        "C": instance.get_index(_MASTER_INDEX["s"]),
        "D": instance.get_index(_MASTER_INDEX["f"]),
        "E": instance.get_index(_MASTER_INDEX["k"]),
        "F": instance.get_index(_MASTER_INDEX["n"]),
        "G": [_MASTER_INDEX["n"]],
    }

    indeces = file.add_worksheet("indeces")

    for column, _indeces in to_print.items():
        for row in range(len(_indeces)):
            indeces.write("{}{}".format(column, row + 1), _indeces[row])

    regions_ref = "=indeces!$A$1:$A${}".format(len(to_print["A"]))
    categories_ref = "=indeces!$B$1:$B${}".format(len(to_print["B"]))
    sectors_ref = "=indeces!$C$1:$C${}".format(len(to_print["C"]))
    factors_ref = "=indeces!$D$1:$D${}".format(len(to_print["D"]))
    extensions_ref = "=indeces!$E$1:$E${}".format(len(to_print["E"]))
    demand_ref = "=indeces!$F$1:$F${}".format(len(to_print["F"]))
    consumption_ref = "=indeces!$G$1:$G${}".format(len(to_print["G"]))

    self_consumption = file.add_worksheet(ADD_SECTOR_SHEETS["sf"]["sheet"])

    len_sectors = len(sectors)
    len_regions = len(regions)

    regions = regions * len_sectors
    regions.sort()

    sectors = sectors * len_regions

    for region in range(len(regions)):
        self_consumption.write(region + 3, 0, regions[region], header_format)
        self_consumption.write(region + 3, 1, _MASTER_INDEX["s"], header_format)
        self_consumption.write(region + 3, 2, sectors[region], header_format)

        self_consumption.write(0, region + 3, regions[region], header_format)
        self_consumption.write(1, region + 3, _MASTER_INDEX["s"], header_format)
        self_consumption.write(2, region + 3, sectors[region], header_format)

    inputs_from = file.add_worksheet(ADD_SECTOR_SHEETS["if"]["sheet"])

    for region in range(len(regions)):
        inputs_from.write(0, region + 3, regions[region], header_format)
        inputs_from.write(1, region + 3, _MASTER_INDEX["s"], header_format)
        inputs_from.write(2, region + 3, sectors[region], header_format)

    inputs_from.write("A3", "Region", header_format)
    inputs_from.write("B3", "Category", header_format)
    inputs_from.write("C3", "Sector", header_format)

    for i in range(num_validation):
        inputs_from.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": regions_ref}
        )
        inputs_from.data_validation(
            "B{}".format(i + 2), {"validate": "list", "source": categories_ref}
        )
        inputs_from.data_validation(
            "C{}".format(i + 2), {"validate": "list", "source": sectors_ref}
        )

    inputs_to = file.add_worksheet(ADD_SECTOR_SHEETS["it"]["sheet"])

    inputs_to.write("C1", "Region", header_format)
    inputs_to.write("C2", "Category", header_format)
    inputs_to.write("C3", "Sector", header_format)

    for region in range(len(regions)):
        inputs_to.write(region + 3, 0, regions[region], header_format)
        inputs_to.write(region + 3, 1, _MASTER_INDEX["s"], header_format)
        inputs_to.write(region + 3, 2, sectors[region], header_format)

    inputs_to.data_validation(
        0, 3, 0, 3 + num_validation, {"validate": "list", "source": regions_ref}
    )
    inputs_to.data_validation(
        1, 3, 1, 3 + num_validation, {"validate": "list", "source": categories_ref}
    )
    inputs_to.data_validation(
        2, 3, 2, 3 + num_validation, {"validate": "list", "source": sectors_ref}
    )

    factors = file.add_worksheet(ADD_SECTOR_SHEETS["fp"]["sheet"])

    for region in range(len(regions)):
        factors.write(0, region + 1, regions[region], header_format)
        factors.write(1, region + 1, _MASTER_INDEX["s"], header_format)
        factors.write(2, region + 1, sectors[region], header_format)

    factors.write("A3", "Factor", header_format)

    for i in range(num_validation):
        factors.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": factors_ref}
        )

    extensions = file.add_worksheet(ADD_SECTOR_SHEETS["sa"]["sheet"])

    for region in range(len(regions)):
        extensions.write(0, region + 1, regions[region], header_format)
        extensions.write(1, region + 1, _MASTER_INDEX["s"], header_format)
        extensions.write(2, region + 1, sectors[region], header_format)

    extensions.write("A3", "Extension", header_format)

    for i in range(num_validation):
        extensions.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": extensions_ref}
        )

    demand = file.add_worksheet(ADD_SECTOR_SHEETS["fd"]["sheet"])

    demand.write("C1", "Region", header_format)
    demand.write("C2", "Level", header_format)
    demand.write("C3", "Category", header_format)

    for region in range(len(regions)):
        demand.write(region + 3, 0, regions[region], header_format)
        demand.write(region + 3, 1, _MASTER_INDEX["s"], header_format)
        demand.write(region + 3, 2, sectors[region], header_format)

    demand.data_validation(
        0, 3, 0, 3 + num_validation, {"validate": "list", "source": regions_ref}
    )
    demand.data_validation(
        1, 3, 1, 3 + num_validation, {"validate": "list", "source": consumption_ref}
    )

    demand.data_validation(
        2, 3, 2, 3 + num_validation, {"validate": "list", "source": demand_ref}
    )

    units = file.add_worksheet(ADD_SECTOR_SHEETS["un"]["sheet"])

    units.write("B1", "unit", header_format)
    _ = 2
    for row in set(sectors):
        units.write("A{}".format(_), row, header_format)
        _ += 1

    file.close()
