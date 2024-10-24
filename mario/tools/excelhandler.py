# -*- coding: utf-8 -*-
"""
the module contains the io file handlings (excel and txt)
"""
import copy
import xlsxwriter
import os
import pandas as pd
from copy import deepcopy as dc

# import constants
from mario.tools.constants import (
    _FORMAT,
    _MASTER_INDEX,
    _SHOCK_LEVELS,
    _ADD_SECTOR_SHEETS,
    _SHOCKS,
    _ENUM,
)


def _sh_excel(instance, num_shock, directory, clusters):
    # Defining the headers
    levels = _SHOCK_LEVELS[instance.meta.table]

    regions = dc(instance.get_index(_MASTER_INDEX["r"]))
    sectors = (
        dc(instance.get_index(_MASTER_INDEX["s"]))
        if instance.meta.table == "IOT"
        else dc(instance.get_index(_MASTER_INDEX["a"]))
        + dc(instance.get_index(_MASTER_INDEX["c"]))
    )
    factors = dc(instance.get_index(_MASTER_INDEX["f"]))
    extensions = dc(instance.get_index(_MASTER_INDEX["k"]))
    categories = dc(instance.get_index(_MASTER_INDEX["n"]))
    types = ["Percentage", "Absolute", "Update"]
    yn = ["Yes", "No"]

    # Define a map to add the clusters to the references
    _map = {
        _MASTER_INDEX["r"]: regions,
        _MASTER_INDEX["f"]: factors,
        _MASTER_INDEX["k"]: extensions,
        _MASTER_INDEX["n"]: categories,
        _MASTER_INDEX["s"]: sectors,
        _MASTER_INDEX["a"]: sectors,
        _MASTER_INDEX["c"]: sectors,
    }

    for key, value in _map.items():
        clusters_level = clusters.get(key)

        # if the level is specificed, add the clusters to the list
        if clusters_level is not None:
            value.extend([*clusters_level])

    # Building the excel file
    file = directory
    workbook = xlsxwriter.Workbook(file)

    # Add a format for the header cells.
    header_format = workbook.add_format(_FORMAT)

    # Filling the index indeces sheet
    indeces = workbook.add_worksheet("indeces")

    # regions
    for i in range(len(regions)):
        indeces.write("A{}".format(i + 1), regions[i])
    # sectors
    for i in range(len(sectors)):
        indeces.write("B{}".format(i + 1), sectors[i])
    # factors
    for i in range(len(factors)):
        indeces.write("C{}".format(i + 1), factors[i])
    # extensions
    for i in range(len(extensions)):
        indeces.write("D{}".format(i + 1), extensions[i])
    # demand categories
    for i in range(len(categories)):
        indeces.write("E{}".format(i + 1), categories[i])

    regions_ref = "=indeces!$A$1:$A${}".format(len(regions))
    sectors_ref = "=indeces!$B$1:$B${}".format(len(sectors))
    factors_ref = "=indeces!$C$1:$C${}".format(len(factors))
    extensions_ref = "=indeces!$D$1:$D${}".format(len(extensions))
    categories_ref = "=indeces!$E$1:$E${}".format(len(categories))

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

    # Building the Y sheet
    Y = workbook.add_worksheet(_ENUM.Y)
    Y.write("A1", _SHOCKS["r_reg"], header_format)
    Y.write("B1", _SHOCKS["r_lev"], header_format)
    Y.write("C1", _SHOCKS["r_sec"], header_format)
    Y.write("D1", _SHOCKS["c_reg"], header_format)
    Y.write("E1", _SHOCKS["d_cat"], header_format)
    Y.write("F1", _SHOCKS["type"], header_format)
    Y.write("G1", _SHOCKS["value"], header_format)

    for i in range(num_shock):
        Y.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": regions_ref}
        )
        Y.data_validation("B{}".format(i + 2), {"validate": "list", "source": levels})
        Y.data_validation(
            "C{}".format(i + 2), {"validate": "list", "source": sectors_ref}
        )
        Y.data_validation(
            "D{}".format(i + 2), {"validate": "list", "source": regions_ref}
        )
        Y.data_validation(
            "E{}".format(i + 2), {"validate": "list", "source": categories_ref}
        )
        Y.data_validation("F{}".format(i + 2), {"validate": "list", "source": types})

    # Building the V sheet
    V = workbook.add_worksheet(_ENUM.v)
    V.write("A1", _SHOCKS["r_sec"], header_format)
    V.write("B1", _SHOCKS["c_reg"], header_format)
    V.write("C1", _SHOCKS["c_lev"], header_format)
    V.write("D1", _SHOCKS["c_sec"], header_format)
    V.write("E1", _SHOCKS["type"], header_format)
    V.write("F1", _SHOCKS["value"], header_format)

    for i in range(num_shock):
        V.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": factors_ref}
        )
        V.data_validation(
            "B{}".format(i + 2), {"validate": "list", "source": regions_ref}
        )
        V.data_validation("C{}".format(i + 2), {"validate": "list", "source": levels})
        V.data_validation(
            "D{}".format(i + 2), {"validate": "list", "source": sectors_ref}
        )
        V.data_validation("E{}".format(i + 2), {"validate": "list", "source": types})

    # Building the E sheet
    E = workbook.add_worksheet(_ENUM.e)
    E.write("A1", _SHOCKS["r_sec"], header_format)
    E.write("B1", _SHOCKS["c_reg"], header_format)
    E.write("C1", _SHOCKS["c_lev"], header_format)
    E.write("D1", _SHOCKS["c_sec"], header_format)
    E.write("E1", _SHOCKS["type"], header_format)
    E.write("F1", _SHOCKS["value"], header_format)

    for i in range(num_shock):
        E.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": extensions_ref}
        )
        E.data_validation(
            "B{}".format(i + 2), {"validate": "list", "source": regions_ref}
        )
        E.data_validation("C{}".format(i + 2), {"validate": "list", "source": levels})
        E.data_validation(
            "D{}".format(i + 2), {"validate": "list", "source": sectors_ref}
        )
        E.data_validation("E{}".format(i + 2), {"validate": "list", "source": types})

    # Building the Z sheet
    Z = workbook.add_worksheet(_ENUM.z)
    Z.write("A1", _SHOCKS["r_reg"], header_format)
    Z.write("B1", _SHOCKS["r_lev"], header_format)
    Z.write("C1", _SHOCKS["r_sec"], header_format)
    Z.write("D1", _SHOCKS["c_reg"], header_format)
    Z.write("E1", _SHOCKS["c_lev"], header_format)
    Z.write("F1", _SHOCKS["c_sec"], header_format)
    Z.write("G1", _SHOCKS["type"], header_format)
    Z.write("H1", _SHOCKS["value"], header_format)
    for i in range(num_shock):
        Z.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": regions_ref}
        )
        Z.data_validation("B{}".format(i + 2), {"validate": "list", "source": levels})
        Z.data_validation(
            "C{}".format(i + 2), {"validate": "list", "source": sectors_ref}
        )
        Z.data_validation(
            "D{}".format(i + 2), {"validate": "list", "source": regions_ref}
        )
        Z.data_validation("E{}".format(i + 2), {"validate": "list", "source": levels})
        Z.data_validation(
            "F{}".format(i + 2), {"validate": "list", "source": sectors_ref}
        )
        Z.data_validation("G{}".format(i + 2), {"validate": "list", "source": types})

    workbook.close()


def dataframe_to_xlsx(path, **kwargs):
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


def wrirte_matrices(sheet, Z, V, E, Y, EY, flow_format, header_format):
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

    # Filling EY
    for row in range(EY.shape[0]):
        for col in range(EY.shape[1]):
            sheet.write(
                Z.shape[0] + 3 + V.shape[0] + row,
                Z.shape[1] + 3 + col,
                EY.iloc[row, col],
                flow_format,
            )

    # Filling zeros
    for row in range(Z.shape[0] + 3, Z.shape[0] + V.shape[0] + 3):
        for col in range(Z.shape[1] + 3, Z.shape[1] + Y.shape[1] + 3):
            sheet.write(row, col, 0, flow_format)


def database_excel(instance, flows, coefficients, directory, scenario):
    file = directory
    workbook = xlsxwriter.Workbook(file)

    # Add a format for the header cells.
    header_format = workbook.add_format(_FORMAT)

    if flows:
        data = instance.query(
            matrices=[_ENUM.V, _ENUM.E, _ENUM.Z, _ENUM.Y, _ENUM.EY],
            scenarios=scenario,
        )

        V = data[_ENUM.V]
        E = data[_ENUM.E]
        Z = data[_ENUM.Z]
        Y = data[_ENUM.Y]
        EY = data[_ENUM.EY]

        V_index = V.index.to_list()
        V.index = [["-"] * len(V_index), [_MASTER_INDEX["f"]] * len(V_index), V_index]

        E_index = E.index.to_list()
        E.index = [["-"] * len(E_index), [_MASTER_INDEX["k"]] * len(E_index), E_index]

        # Filling the index indeces sheet
        flows = workbook.add_worksheet("flows")
        flow_format = workbook.add_format({"num_format": "0.0;-0.0;-"})

        wrirte_matrices(flows, Z, V, E, Y, EY, flow_format, header_format)

    if coefficients:
        matrices = [_ENUM.v, _ENUM.e, _ENUM.z, _ENUM.Y, _ENUM.EY]
        data = instance.query(
            matrices=matrices,
            scenarios=scenario,
        )

        V = data[_ENUM.v]
        E = data[_ENUM.e]
        Z = data[_ENUM.z]
        Y = data[_ENUM.Y]
        EY = data[_ENUM.EY]

        V_index = V.index.to_list()
        V.index = [["-"] * len(V_index), [_MASTER_INDEX["f"]] * len(V_index), V_index]

        E_index = E.index.to_list()
        E.index = [["-"] * len(E_index), [_MASTER_INDEX["k"]] * len(E_index), E_index]

        # Filling the index indeces sheet
        coefficients = workbook.add_worksheet("coefficients")
        coeff_format = workbook.add_format({"num_format": "0.000;-0.000;-"})

        wrirte_matrices(coefficients, Z, V, E, Y, EY, coeff_format, header_format)

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
    if flows:
        flows = instance.query(
            matrices=[_ENUM.V, _ENUM.E, _ENUM.Z, _ENUM.Y, _ENUM.X, _ENUM.EY],
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
            matrices=[_ENUM.v, _ENUM.e, _ENUM.z, _ENUM.Y, _ENUM.EY],
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
    workbook = xlsxwriter.Workbook(path)

    # Add a format for the header cells.
    header_format = workbook.add_format(_FORMAT)

    for key, matrix in matrices.items:
        sheet = workbook.add_worksheet(key)

        if key in ["e", "v"]:
            row_count = 4
            for row in matrix.index.to_list():
                sheet.write("A{}".format(row_count), row, header_format)
                row_count += 1


def _add_sector_sut(instance, sectors, regions, path, item, num_validation=30):
    file = xlsxwriter.Workbook(path)
    header_format = file.add_format(_FORMAT)

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

    demand = file.add_worksheet(_ADD_SECTOR_SHEETS["fd"]["sheet"])

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

    factors = file.add_worksheet(_ADD_SECTOR_SHEETS["fp"]["sheet"])

    for region in range(len(regions)):
        factors.write(0, region + 1, regions[region], header_format)
        factors.write(1, region + 1, item, header_format)
        factors.write(2, region + 1, sectors[region], header_format)

    factors.write("A3", "Factor", header_format)

    for i in range(num_validation):
        factors.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": factors_ref}
        )

    extensions = file.add_worksheet(_ADD_SECTOR_SHEETS["sa"]["sheet"])

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
        _ADD_SECTOR_SHEETS["it"]["sheet"]
        if item == _MASTER_INDEX["c"]
        else _ADD_SECTOR_SHEETS["if"]["sheet"]
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

    lower_z = file.add_worksheet(_ADD_SECTOR_SHEETS["of"]["sheet"])

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

    units = file.add_worksheet(_ADD_SECTOR_SHEETS["un"]["sheet"])

    units.write("B1", "unit", header_format)
    _ = 2
    for row in set(sectors):
        units.write("A{}".format(_), row, header_format)
        _ += 1

    file.close()


def _add_sector_iot(instance, sectors, regions, path, num_validation=30):
    file = xlsxwriter.Workbook(path)
    header_format = file.add_format(_FORMAT)

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

    self_consumption = file.add_worksheet(_ADD_SECTOR_SHEETS["sf"]["sheet"])

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

    inputs_from = file.add_worksheet(_ADD_SECTOR_SHEETS["if"]["sheet"])

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

    inputs_to = file.add_worksheet(_ADD_SECTOR_SHEETS["it"]["sheet"])

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

    factors = file.add_worksheet(_ADD_SECTOR_SHEETS["fp"]["sheet"])

    for region in range(len(regions)):
        factors.write(0, region + 1, regions[region], header_format)
        factors.write(1, region + 1, _MASTER_INDEX["s"], header_format)
        factors.write(2, region + 1, sectors[region], header_format)

    factors.write("A3", "Factor", header_format)

    for i in range(num_validation):
        factors.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": factors_ref}
        )

    extensions = file.add_worksheet(_ADD_SECTOR_SHEETS["sa"]["sheet"])

    for region in range(len(regions)):
        extensions.write(0, region + 1, regions[region], header_format)
        extensions.write(1, region + 1, _MASTER_INDEX["s"], header_format)
        extensions.write(2, region + 1, sectors[region], header_format)

    extensions.write("A3", "Extension", header_format)

    for i in range(num_validation):
        extensions.data_validation(
            "A{}".format(i + 2), {"validate": "list", "source": extensions_ref}
        )

    demand = file.add_worksheet(_ADD_SECTOR_SHEETS["fd"]["sheet"])

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

    units = file.add_worksheet(_ADD_SECTOR_SHEETS["un"]["sheet"])

    units.write("B1", "unit", header_format)
    _ = 2
    for row in set(sectors):
        units.write("A{}".format(_), row, header_format)
        _ += 1

    file.close()
