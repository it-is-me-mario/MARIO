import pandas as pd
import pandas.testing as pdt
import pytest

from mario.internal import ModelState, ModelStateMetadata
from mario.log_exc.exceptions import DataMissing, WrongExcelFormat, WrongInput
from mario.compute.sut_formulas import build_sut_c_from_S_Xa
from mario.model.enums import TableKind
from mario.ops.export import _matrix_to_flat_frame, _trim_flat_frame_columns
from mario.ops.export_specs import (
    FLAT_AXIS_SETS,
    FLAT_UNIT_COLUMNS,
    LEGACY_FLAT_DATA_COLUMNS,
    flat_data_columns_for_sets,
)
from mario.parsers.api import build_database_from_state, build_parser_state
from mario.parsers.excel import parse_state_from_excel
from mario.parsers.parquet import parse_state_from_parquet
from mario.parsers.txt import parse_state_from_txt
from mario.parsers.registry import ParserRegistry, get_parser_registry, register_parser
from mario.parsers.entrypoints import parse_from_excel, parse_from_parquet, parse_from_txt
from mario.parsers.matrix_layouts import sut_block_specs_for_matrix_layouts
from mario.test.mario_test import load_test


def _write_mriot_regional_extensions_workbook(path):
    flows = pd.DataFrame(
        [
            [None, None, None, "r1", "r1", "r2", "r2", "r1", "r2"],
            [None, None, None, "Sector", "Sector", "Sector", "Sector", "Consumption category", "Consumption category"],
            [None, None, None, "s1", "s2", "s1", "s2", "CC", "CC"],
            ["r1", "Sector", "s1", 20, 15, 4, 5, 15, 25],
            ["r1", "Sector", "s2", 10, 54, 5, 5, 20, 45],
            ["r2", "Sector", "s1", 5, 5, 18, 11, 15, 30],
            ["r2", "Sector", "s2", 3, 5, 9, 41, 35, 30],
            [None, "Factor of production", "VA", 46, 60, 48, 61, 0, 0],
            ["r1", "Satellite account", "CO2", 10, 5, 20, 10, 4, 0],
            ["r2", "Satellite account", "CO2", 23, 6, 5, 2, 1, 2],
        ]
    )
    units = pd.DataFrame(
        [
            [None, None, "unit"],
            ["Sector", "s1", "EUR"],
            ["Sector", "s2", "EUR"],
            ["Factor of production", "VA", "EUR"],
            ["Satellite account", "CO2", "ton"],
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        flows.to_excel(writer, sheet_name="flows", header=False, index=False)
        units.to_excel(writer, sheet_name="units", header=False, index=False)


def _write_mriot_regional_explicit_workbook(path):
    flows = pd.DataFrame(
        [
            [None, None, "r1", "r1", "r2", "r2", None, None],
            [None, None, "s1", "s2", "s1", "s2", "hh", "investment"],
            ["r1", "s1", 20, 15, 4, 5, 15, 25],
            ["r1", "s2", 10, 54, 5, 5, 20, 45],
            ["r2", "s1", 5, 5, 18, 11, 15, 30],
            ["r2", "s2", 3, 5, 9, 41, 35, 30],
            [None, "VA", 46, 60, 48, 61, 0, 0],
            ["r1", "CO2", 10, 5, 20, 10, 4, 0],
            ["r2", "CO2", 23, 6, 5, 2, 1, 2],
        ]
    )
    units = pd.DataFrame(
        [
            [None, None, "unit"],
            ["Sector", "s1", "EUR"],
            ["Sector", "s2", "EUR"],
            ["Factor of production", "VA", "EUR"],
            ["Satellite account", "CO2", "ton"],
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        flows.to_excel(writer, sheet_name="flows", header=False, index=False)
        units.to_excel(writer, sheet_name="units", header=False, index=False)


def _write_mriot_regional_extensions_and_factors_explicit_workbook(path):
    flows = pd.DataFrame(
        [
            [None, None, "r1", "r1", "r2", "r2", None, None],
            [None, None, "s1", "s2", "s1", "s2", "hh", "investment"],
            ["r1", "s1", 20, 15, 4, 5, 15, 21],
            ["r1", "s2", 10, 54, 5, 5, 20, 36],
            ["r2", "s1", 5, 5, 18, 11, 15, 19],
            ["r2", "s2", 3, 5, 9, 41, 35, 30],
            ["r1", "taxes", 7, 18, 16, 21, 0, 0],
            ["r1", "capital", 22, 10, 10, 12, 0, 0],
            ["r2", "taxes", 9, 10, 4, 8, 0, 0],
            ["r2", "capital", 4, 13, 7, 20, 0, 0],
            ["r1", "CO2", 13, 2, 15, 6, 3, 0],
            ["r2", "CO2", 20, 9, 10, 6, 1, 2],
        ]
    )
    units = pd.DataFrame(
        [
            [None, None, "unit"],
            ["Sector", "s1", "EUR"],
            ["Sector", "s2", "EUR"],
            ["Factor of production", "taxes", "EUR"],
            ["Factor of production", "capital", "EUR"],
            ["Satellite account", "CO2", "ton"],
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        flows.to_excel(writer, sheet_name="flows", header=False, index=False)
        units.to_excel(writer, sheet_name="units", header=False, index=False)


def _blank_standard_excel_matrix(path, matrix_name, *, partial=False):
    raw = pd.read_excel(path, sheet_name="flows", header=None)
    units = pd.read_excel(path, sheet_name="units", header=None)

    if matrix_name == "EY":
        row_positions = [
            idx for idx in range(3, raw.shape[0]) if raw.iat[idx, 1] == "Satellite account"
        ]
        column_positions = [
            idx for idx in range(3, raw.shape[1]) if raw.iat[1, idx] == "Consumption category"
        ]
    else:
        raise ValueError(f"Unsupported test matrix {matrix_name!r}.")

    if partial:
        raw.iat[row_positions[0], column_positions[0]] = None
    else:
        raw.iloc[row_positions, column_positions] = None

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        raw.to_excel(writer, sheet_name="flows", header=False, index=False)
        units.to_excel(writer, sheet_name="units", header=False, index=False)


def _blank_explicit_excel_matrix(path, matrix_name, *, partial=False):
    raw = pd.read_excel(path, sheet_name="flows", header=None)
    units = pd.read_excel(path, sheet_name="units", header=None)

    if matrix_name == "EY":
        row_positions = [idx for idx in range(2, raw.shape[0]) if raw.iat[idx, 1] == "CO2"]
        column_positions = [
            idx
            for idx in range(2, raw.shape[1])
            if pd.isna(raw.iat[0, idx]) and pd.notna(raw.iat[1, idx])
        ]
    else:
        raise ValueError(f"Unsupported test matrix {matrix_name!r}.")

    if partial:
        raw.iat[row_positions[0], column_positions[0]] = None
    else:
        raw.iloc[row_positions, column_positions] = None

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        raw.to_excel(writer, sheet_name="flows", header=False, index=False)
        units.to_excel(writer, sheet_name="units", header=False, index=False)


def _build_mriot_regional_state(tmp_path):
    path = tmp_path / "mriot_regional.xlsx"
    _write_mriot_regional_extensions_workbook(path)
    return parse_state_from_excel(
        str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"E": "Region", "EY": "Region"},
        name="MRIOT regional extensions",
    )


def _write_units_from_state(state, path, fmt):
    units = pd.concat(
        [
            state.get_units("s").rename_axis(index="item").assign(level="Sector").set_index("level", append=True).reorder_levels(["level", "item"]),
            state.get_units("f").rename_axis(index="item").assign(level="Factor of production").set_index("level", append=True).reorder_levels(["level", "item"]),
            state.get_units("k").rename_axis(index="item").assign(level="Satellite account").set_index("level", append=True).reorder_levels(["level", "item"]),
        ]
    )
    if fmt == "txt":
        units.to_csv(path)
    else:
        units.to_parquet(path)


def _build_custom_sut_unified_blocks():
    productive = pd.MultiIndex.from_tuples(
        [
            ("r1", "Activity", "a1"),
            ("r1", "Activity", "a2"),
            ("r1", "Commodity", "c1"),
            ("r1", "Commodity", "c2"),
        ],
        names=["Region", "Level", "Item"],
    )
    final_demand = pd.MultiIndex.from_tuples(
        [("r1", "Consumption category", "hh")],
        names=["Region", "Level", "Item"],
    )
    factors = pd.MultiIndex.from_tuples(
        [
            ("r1", "a1", "taxes"),
            ("r1", "a1", "capital"),
            ("r1", "a2", "taxes"),
            ("r1", "a2", "capital"),
        ],
        names=["Region", "Activity", "Factor of production"],
    )
    satellites = pd.MultiIndex.from_tuples(
        [
            ("r1", "a1", "CO2"),
            ("r1", "a2", "CO2"),
        ],
        names=["Region", "Activity", "Satellite account"],
    )

    blocks = {
        "Z": pd.DataFrame(
            [
                [0.0, 0.0, 40.0, 10.0],
                [0.0, 0.0, 20.0, 30.0],
                [5.0, 7.0, 0.0, 0.0],
                [3.0, 9.0, 0.0, 0.0],
            ],
            index=productive,
            columns=productive,
        ),
        "Y": pd.DataFrame(
            [[0.0], [0.0], [50.0], [60.0]],
            index=productive,
            columns=final_demand,
        ),
        "V": pd.DataFrame(
            [
                [4.0, 0.0, 0.0, 0.0],
                [6.0, 0.0, 0.0, 0.0],
                [0.0, 5.0, 0.0, 0.0],
                [0.0, 8.0, 0.0, 0.0],
            ],
            index=factors,
            columns=productive,
        ),
        "E": pd.DataFrame(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 2.0, 0.0, 0.0],
            ],
            index=satellites,
            columns=productive,
        ),
        "EY": pd.DataFrame(
            [[0.5], [1.5]],
            index=satellites,
            columns=final_demand,
        ),
        "VY": pd.DataFrame(
            [[0.0], [0.0], [0.0], [0.0]],
            index=factors,
            columns=final_demand,
        ),
    }
    indexes = {
        "r": {"main": ["r1"]},
        "n": {"main": ["hh"]},
        "a": {"main": ["a1", "a2"]},
        "c": {"main": ["c1", "c2"]},
        "s": {"main": ["a1", "a2", "c1", "c2"]},
        "f": {"main": ["taxes", "capital"]},
        "k": {"main": ["CO2"]},
    }
    units = {
        "Activity": pd.DataFrame({"unit": ["EUR", "EUR"]}, index=pd.Index(["a1", "a2"], name="Item")),
        "Commodity": pd.DataFrame({"unit": ["EUR", "EUR"]}, index=pd.Index(["c1", "c2"], name="Item")),
        "Factor of production": pd.DataFrame(
            {"unit": ["EUR", "EUR"]},
            index=pd.Index(["taxes", "capital"], name="Item"),
        ),
        "Satellite account": pd.DataFrame(
            {"unit": ["ton"]},
            index=pd.Index(["CO2"], name="Item"),
        ),
    }
    return blocks, indexes, units


def _build_non_square_sut_split_blocks():
    activity = pd.MultiIndex.from_tuples(
        [("r1", "Activity", "a1")],
        names=["Region", "Level", "Item"],
    )
    commodity = pd.MultiIndex.from_tuples(
        [("r1", "Commodity", "c1"), ("r1", "Commodity", "c2")],
        names=["Region", "Level", "Item"],
    )
    final_demand = pd.MultiIndex.from_tuples(
        [("r1", "Consumption category", "hh")],
        names=["Region", "Level", "Item"],
    )

    blocks = {
        "S": pd.DataFrame([[4.0, 1.0]], index=activity, columns=commodity),
        "U": pd.DataFrame([[2.0], [3.0]], index=commodity, columns=activity),
        "Yc": pd.DataFrame([[1.0], [2.0]], index=commodity, columns=final_demand),
        "Va": pd.DataFrame([[5.0]], index=pd.Index(["taxes"], name="Item"), columns=activity),
        "Vc": pd.DataFrame([[0.0, 0.0]], index=pd.Index(["taxes"], name="Item"), columns=commodity),
        "Ea": pd.DataFrame([[0.5]], index=pd.Index(["CO2"], name="Item"), columns=activity),
        "Ec": pd.DataFrame([[0.0, 0.0]], index=pd.Index(["CO2"], name="Item"), columns=commodity),
        "EY": pd.DataFrame([[0.0]], index=pd.Index(["CO2"], name="Item"), columns=final_demand),
        "VY": pd.DataFrame([[0.0]], index=pd.Index(["taxes"], name="Item"), columns=final_demand),
    }
    indexes = {
        "r": {"main": ["r1"]},
        "n": {"main": ["hh"]},
        "a": {"main": ["a1"]},
        "c": {"main": ["c1", "c2"]},
        "s": {"main": ["a1", "c1", "c2"]},
        "f": {"main": ["taxes"]},
        "k": {"main": ["CO2"]},
    }
    units = {
        "Activity": pd.DataFrame({"unit": ["EUR"]}, index=pd.Index(["a1"], name="Item")),
        "Commodity": pd.DataFrame({"unit": ["EUR", "EUR"]}, index=pd.Index(["c1", "c2"], name="Item")),
        "Factor of production": pd.DataFrame({"unit": ["EUR"]}, index=pd.Index(["taxes"], name="Item")),
        "Satellite account": pd.DataFrame({"unit": ["ton"]}, index=pd.Index(["CO2"], name="Item")),
    }
    return blocks, indexes, units


def _write_matrix_payload_from_blocks(blocks, units, root, fmt):
    root.mkdir(parents=True, exist_ok=True)
    for matrix_name, frame in blocks.items():
        target = root / f"{matrix_name}.{fmt}"
        if fmt == "txt":
            frame.to_csv(target)
        else:
            frame.to_parquet(target)

    combined_units = pd.concat(
        [
            units["Activity"].rename_axis(index="item").assign(level="Activity").set_index("level", append=True).reorder_levels(["level", "item"]),
            units["Commodity"].rename_axis(index="item").assign(level="Commodity").set_index("level", append=True).reorder_levels(["level", "item"]),
            units["Factor of production"].rename_axis(index="item").assign(level="Factor of production").set_index("level", append=True).reorder_levels(["level", "item"]),
            units["Satellite account"].rename_axis(index="item").assign(level="Satellite account").set_index("level", append=True).reorder_levels(["level", "item"]),
        ]
    )
    if fmt == "txt":
        combined_units.to_csv(root / "units.txt")
    else:
        combined_units.to_parquet(root / "units.parquet")


def _flat_units_from_sut_units(units):
    rows = []
    for label in ("Activity", "Commodity", "Factor of production", "Satellite account"):
        for item, unit in units[label].iloc[:, 0].items():
            rows.append((label, item, unit))
    return pd.DataFrame(rows, columns=FLAT_UNIT_COLUMNS)


def _write_flat_payload_from_blocks(blocks, units, root, fmt):
    root.mkdir(parents=True, exist_ok=True)
    data = pd.concat(
        [
            _matrix_to_flat_frame(matrix_name, frame, scenario="baseline")
            for matrix_name, frame in blocks.items()
        ],
        ignore_index=True,
    )
    data = _trim_flat_frame_columns(data)
    if fmt == "txt":
        data.to_csv(root / "data.txt", index=False)
        _flat_units_from_sut_units(units).to_csv(root / "units.txt", index=False)
    else:
        data.to_parquet(root / "data.parquet", index=False)
        _flat_units_from_sut_units(units).to_parquet(root / "units.parquet", index=False)


def _build_custom_sut_database():
    blocks, indexes, units = _build_custom_sut_unified_blocks()
    state = build_parser_state(
        table="SUT",
        matrices={"baseline": blocks},
        indexes=indexes,
        units=units,
        parser_name="tests",
        mode="flows",
        name="custom SUT",
    )
    state.metadata.extra["block_specs"] = sut_block_specs_for_matrix_layouts(
        {"V": ("Region", "Activity"), "E": ("Region", "Activity")}
    )
    return build_database_from_state(state, calc_all=False)


def _write_custom_sut_explicit_no_level_workbook(path):
    database = _build_custom_sut_database()
    Z = database.Z
    Y = database.Y
    V = database.V
    E = database.E
    EY = database.EY
    VY = database.VY

    productive_columns = list(Z.columns)
    final_demand_columns = list(Y.columns)

    rows = [
        [None, None, None]
        + [column[0] for column in productive_columns]
        + [column[0] for column in final_demand_columns],
        [None, None, None]
        + [column[2] for column in productive_columns]
        + ["Final Demand" for _ in final_demand_columns],
    ]

    for row in Z.index:
        rows.append(
            [row[0], row[2], None]
            + Z.loc[row, productive_columns].tolist()
            + Y.loc[row, final_demand_columns].tolist()
        )
    for row in V.index:
        rows.append(
            [row[0], row[1], row[2]]
            + V.loc[row, productive_columns].tolist()
            + VY.loc[row, final_demand_columns].tolist()
        )
    for row in E.index:
        rows.append(
            [row[0], row[1], row[2]]
            + E.loc[row, productive_columns].tolist()
            + EY.loc[row, final_demand_columns].tolist()
        )

    units_rows = [[None, None, "unit"]]
    for set_name in ("Activity", "Commodity", "Factor of production", "Satellite account"):
        for item, unit in database.units[set_name].iloc[:, 0].items():
            units_rows.append([set_name, item, unit])

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="flows", header=False, index=False)
        pd.DataFrame(units_rows).to_excel(writer, sheet_name="units", header=False, index=False)


def test_build_parser_state_falls_back_to_industry_based_for_non_square_sut_pt():
    blocks, indexes, units = _build_non_square_sut_split_blocks()

    state = build_parser_state(
        table="SUT",
        matrices={"baseline": blocks},
        indexes=indexes,
        units=units,
        parser_name="tests",
        mode="flows",
        tech_assumption="PT",
    )

    assert state.metadata.tech_assumption == "industry-based"
    assert any("falling back to industry-based" in note for note in state.metadata.history)

    database = build_database_from_state(state, calc_all=False)
    assert database.tech_assumption == "industry-based"


def test_parse_from_excel_preserves_product_based_sut_assumption_and_exposes_c(tmp_path):
    path = tmp_path / "custom_sut_pt.xlsx"
    _write_custom_sut_explicit_no_level_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="SUT",
        mode="flows",
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        tech_assumption="PT",
        calc_all=False,
    )

    assert database.tech_assumption == "product-based"
    pdt.assert_frame_equal(
        database.c,
        build_sut_c_from_S_Xa(database.S, database.Xa, tech_assumption="PT"),
    )


def test_public_sut_c_is_unavailable_under_industry_based_assumption():
    database = _build_custom_sut_database()

    assert database.tech_assumption == "industry-based"
    with pytest.raises(DataMissing):
        database.resolve("c")


def _flat_units_from_state(state):
    rows = []
    for label, code in (
        ("Sector", "s"),
        ("Factor of production", "f"),
        ("Satellite account", "k"),
    ):
        for item, unit in state.get_units(code).iloc[:, 0].items():
            rows.append((label, item, unit))
    return pd.DataFrame(rows, columns=FLAT_UNIT_COLUMNS)


def _write_matrix_payload_from_state(state, root, fmt):
    root.mkdir(parents=True, exist_ok=True)
    for matrix_name in ("Z", "Y", "V", "E", "EY", "VY"):
        frame = state.get_block(matrix_name)
        target = root / f"{matrix_name}.{fmt}"
        if fmt == "txt":
            frame.to_csv(target)
        else:
            frame.to_parquet(target)
    _write_units_from_state(state, root / f"units.{fmt}", fmt)


def _write_flat_payload_from_state(state, root, fmt):
    root.mkdir(parents=True, exist_ok=True)
    data = pd.concat(
        [
            _matrix_to_flat_frame(matrix_name, state.get_block(matrix_name), scenario="baseline")
            for matrix_name in ("Z", "Y", "V", "E", "EY", "VY")
        ],
        ignore_index=True,
    )
    data = _trim_flat_frame_columns(data)
    if fmt == "txt":
        data.to_csv(root / "data.txt", index=False)
        _flat_units_from_state(state).to_csv(root / "units.txt", index=False)
    else:
        data.to_parquet(root / "data.parquet", index=False)
        _flat_units_from_state(state).to_parquet(root / "units.parquet", index=False)


def _sorted_matrix(frame):
    result = frame.sort_index(axis=0)
    result = result.sort_index(axis=1)
    return result


def _explicit_axis_from_legacy(axis, *, simple_name=None):
    """Normalize one legacy public axis to the explicit no-Level form used by custom exports."""
    if isinstance(axis, pd.MultiIndex):
        if list(axis.names) == ["Region", "Level", "Item"]:
            level_values = tuple(pd.unique(axis.get_level_values("Level")))
            if len(level_values) == 1:
                return pd.MultiIndex.from_tuples(
                    [(region, item) for region, _, item in axis.tolist()],
                    names=["Region", level_values[0]],
                )
        if list(axis.names) == ["Level", "Item"]:
            level_values = tuple(pd.unique(axis.get_level_values("Level")))
            if len(level_values) == 1:
                return pd.Index(axis.get_level_values("Item"), name=level_values[0])
        return axis

    if simple_name is not None:
        return pd.Index(axis.tolist(), name=simple_name)
    return axis


def _explicit_custom_iot_frame(frame, matrix_name):
    """Normalize the legacy custom-IOT public layout to the explicit export layout."""
    result = frame.copy()
    if matrix_name in {"V", "VY"}:
        result.index = _explicit_axis_from_legacy(result.index, simple_name="Factor of production")
    elif matrix_name in {"E", "EY"}:
        result.index = _explicit_axis_from_legacy(result.index, simple_name="Satellite account")
    else:
        result.index = _explicit_axis_from_legacy(result.index)

    if matrix_name in {"Y", "EY", "VY"}:
        result.columns = _explicit_axis_from_legacy(result.columns)
    else:
        result.columns = _explicit_axis_from_legacy(result.columns)
    return result


def test_parse_state_from_excel_iot_preserves_blocks_indexes_and_units():
    state = get_parser_registry().parse(
        "excel",
        path="mario/test/tables/test_IOT_standard.xlsx",
        table="IOT",
        mode="flows",
        name="IOT dataset",
    )
    database = load_test("IOT")

    assert state.table_kind == TableKind.IOT
    assert state.metadata.extra["parser"] == "excel"
    assert set(state.list_matrices()) == {"E", "EY", "V", "VY", "Y", "Z"}
    assert not state.has_matrix("X")
    assert state.get_index("s") == tuple(database._indeces["s"]["main"])

    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)
    pdt.assert_frame_equal(state.get_units("s"), database.units["Sector"])


def test_parse_from_excel_sut_returns_split_native_baseline_blocks():
    database = parse_from_excel(
        path="mario/test/tables/test_SUT_standard.xlsx",
        table="SUT",
        mode="flows",
        name="SUT dataset",
    )

    assert not database.is_hybrid
    assert "Z" not in database["baseline"]
    assert "X" not in database["baseline"]
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"} <= set(database["baseline"])


def test_parser_authoring_api_builds_database_from_state():
    state = parse_state_from_excel(
        "mario/test/tables/test_IOT_standard.xlsx",
        table="IOT",
        mode="flows",
        name="IOT dataset",
    )
    database = build_database_from_state(state, calc_all=False)

    assert database.table_type == "IOT"
    assert set(database["baseline"]) == {"E", "EY", "V", "VY", "Y", "Z"}
    pdt.assert_frame_equal(database.Z, state.get_block("Z"))


def test_parse_state_from_excel_sut_promotes_split_native_blocks():
    state = parse_state_from_excel(
        "mario/test/tables/test_SUT_standard.xlsx",
        table="SUT",
        mode="flows",
        name="SUT dataset",
    )
    database = load_test("SUT")

    assert state.table_kind == TableKind.SUT
    assert not state.has_matrix("Z")
    assert not state.has_matrix("X")
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"} <= set(state.list_matrices())
    assert "Xa" not in state.list_matrices()
    assert "Xc" not in state.list_matrices()
    assert state.get_index("a") == tuple(database._indeces["a"]["main"])

    pdt.assert_frame_equal(state.compute("Z"), database.Z)
    pdt.assert_frame_equal(state.compute("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("V"), database.V)
    pdt.assert_frame_equal(state.compute("E"), database.E)
    pdt.assert_frame_equal(state.compute("Xa"), database.Xa)
    pdt.assert_frame_equal(state.compute("Xc"), database.Xc)
    pdt.assert_frame_equal(state.compute("X"), database.X)
    pdt.assert_frame_equal(state.get_units("a"), database.units["Activity"])


def test_to_excel_exports_custom_sut_layouts_and_parse_from_excel_roundtrips_them(tmp_path):
    database = _build_custom_sut_database()

    export_path = tmp_path / "custom_sut.xlsx"
    database.to_excel(path=str(export_path), flows=True, coefficients=False)

    exported = pd.read_excel(export_path, sheet_name="flows", header=None)
    assert tuple(exported.iloc[0, 3:7]) == ("r1", "r1", "r1", "r1")
    assert tuple(exported.iloc[1, 3:7]) == ("a1", "a2", "c1", "c2")
    left_rows = {tuple(row) for row in exported.iloc[:, 0:3].dropna(how="all").itertuples(index=False, name=None)}
    assert ("r1", "a1", "taxes") in left_rows
    assert ("r1", "a1", "CO2") in left_rows

    roundtrip = parse_from_excel(
        path=str(export_path),
        table="SUT",
        mode="flows",
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        calc_all=False,
    )

    assert roundtrip.V.index.names == ["Region", "Activity", "Factor of production"]
    assert roundtrip.E.index.names == ["Region", "Activity", "Satellite account"]
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.Z), _sorted_matrix(database.Z))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.V), _sorted_matrix(database.V))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.E), _sorted_matrix(database.E))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.Y), _sorted_matrix(database.Y))


def test_parse_from_excel_supports_custom_sut_coefficient_workbooks(tmp_path):
    database = _build_custom_sut_database()

    export_path = tmp_path / "custom_sut_coeffs.xlsx"
    database.to_excel(path=str(export_path), flows=False, coefficients=True)

    roundtrip = parse_from_excel(
        path=str(export_path),
        table="SUT",
        mode="coefficients",
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        calc_all=False,
    )

    assert roundtrip.v.index.names == ["Region", "Activity", "Factor of production"]
    assert roundtrip.e.index.names == ["Region", "Activity", "Satellite account"]
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.z), _sorted_matrix(database.z))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.v), _sorted_matrix(database.v))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.e), _sorted_matrix(database.e))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.Y), _sorted_matrix(database.Y))


def test_parse_from_excel_supports_explicit_no_level_sut_productive_axes(tmp_path):
    path = tmp_path / "custom_sut_explicit_no_level.xlsx"
    _write_custom_sut_explicit_no_level_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="SUT",
        mode="flows",
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        calc_all=False,
    )

    assert database.Z.index.names == ["Region", "Level", "Item"]
    assert database.Z.columns.names == ["Region", "Level", "Item"]
    assert database.V.index.names == ["Region", "Activity", "Factor of production"]
    assert database.E.index.names == ["Region", "Activity", "Satellite account"]
    assert database.Y.columns.get_level_values("Item").tolist() == ["Final Demand"]
    assert database.Y.columns.get_level_values("Level").tolist() == ["Consumption category"]

    expected = _build_custom_sut_database()
    expected_y = expected.Y.copy()
    expected_y.columns = pd.MultiIndex.from_tuples(
        [(region, "Consumption category", "Final Demand") for region, _, _ in expected_y.columns.tolist()],
        names=["Region", "Level", "Item"],
    )

    pdt.assert_frame_equal(_sorted_matrix(database.Z), _sorted_matrix(expected.Z))
    pdt.assert_frame_equal(_sorted_matrix(database.V), _sorted_matrix(expected.V))
    pdt.assert_frame_equal(_sorted_matrix(database.E), _sorted_matrix(expected.E))
    pdt.assert_frame_equal(_sorted_matrix(database.Y), _sorted_matrix(expected_y))


def test_parse_state_from_excel_supports_mriot_regional_extensions_layout(tmp_path):
    path = tmp_path / "mriot_regional.xlsx"
    _write_mriot_regional_extensions_workbook(path)

    state = parse_state_from_excel(
        str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"E": "Region", "EY": "Region"},
        name="MRIOT regional extensions",
    )

    assert state.table_kind == TableKind.IOT
    assert {"Z", "Y", "V", "VY", "E", "EY"} <= set(state.list_matrices())
    assert state.metadata.extra["parser"] == "excel"
    assert len(state.metadata.extra["block_specs"]) == 5
    assert "operators" not in state.metadata.extra

    extension = state.get_block("E")
    assert extension.index.names == ["Region", "Level", "Item"]
    assert tuple(extension.index.get_level_values(1)) == ("Satellite account", "Satellite account")
    assert tuple(extension.index.get_level_values(0)) == ("r1", "r2")
    assert tuple(state.get_units("k").index) == ("CO2",)


def test_parse_from_excel_registers_regional_extension_specs_and_operators(tmp_path):
    path = tmp_path / "mriot_regional.xlsx"
    _write_mriot_regional_extensions_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"E": "Region", "EY": "Region"},
        calc_all=False,
        name="MRIOT regional extensions",
    )

    assert "E" in database["baseline"]
    assert "EY" in database["baseline"]
    assert "E" in database.available_matrices()
    assert "e" in database.available_matrices()
    assert "f" in database.available_matrices()
    assert database.E.index.names == ["Region", "Level", "Item"]

    spec = database.get_block_spec("E")
    assert tuple(axis.id for axis in spec.row_axes) == ("Region", "Satellite account")
    pdt.assert_frame_equal(
        database.e,
        database.E.divide(database.X.iloc[:, 0], axis="columns"),
    )
    pdt.assert_frame_equal(
        database.f,
        database.e.dot(database.w),
    )


def test_parse_from_excel_accepts_tuple_matrix_layouts(tmp_path):
    path = tmp_path / "mriot_regional.xlsx"
    _write_mriot_regional_extensions_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"E": ("Region",), "EY": ["Region"]},
        calc_all=False,
        name="MRIOT regional extensions",
    )

    assert database.E.index.names == ["Region", "Level", "Item"]


def test_parse_from_excel_accepts_matrix_layout_alias(tmp_path):
    path = tmp_path / "mriot_regional_v_alias.xlsx"
    _write_mriot_regional_extensions_and_factors_explicit_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layout={"V": "Region"},
        calc_all=False,
        name="MRIOT regional factors alias",
    )

    assert database.V.index.names == ["Region", "Factor of production"]


def test_parse_from_excel_rejects_conflicting_matrix_layout_aliases(tmp_path):
    path = tmp_path / "mriot_regional_v_conflict.xlsx"
    _write_mriot_regional_extensions_and_factors_explicit_workbook(path)

    with pytest.raises(WrongInput, match="Use only one of 'matrix_layouts' or its alias 'matrix_layout'"):
        parse_from_excel(
            path=str(path),
            table="IOT",
            mode="flows",
            matrix_layouts={"V": "Region"},
            matrix_layout={"V": "Region"},
            calc_all=False,
        )


def test_parse_from_excel_accepts_fully_empty_standard_excel_matrices(tmp_path):
    path = tmp_path / "standard_iot.xlsx"
    load_test("IOT").to_excel(path=str(path), flows=True, coefficients=False)
    _blank_standard_excel_matrix(path, "EY")

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        calc_all=False,
    )

    assert (database.EY == 0).all().all()


def test_parse_from_excel_rejects_partially_empty_standard_excel_matrices(tmp_path):
    path = tmp_path / "standard_iot_partial.xlsx"
    load_test("IOT").to_excel(path=str(path), flows=True, coefficients=False)
    _blank_standard_excel_matrix(path, "EY", partial=True)

    with pytest.raises(WrongExcelFormat, match="partially empty|non-numeric"):
        parse_from_excel(
            path=str(path),
            table="IOT",
            mode="flows",
            calc_all=False,
        )


def test_parse_from_excel_accepts_fully_empty_explicit_excel_matrices(tmp_path):
    path = tmp_path / "mriot_explicit_empty_ey.xlsx"
    _write_mriot_regional_explicit_workbook(path)
    _blank_explicit_excel_matrix(path, "EY")

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"E": "Region", "EY": "Region"},
        calc_all=False,
    )

    assert (database.EY == 0).all().all()


def test_parse_from_excel_rejects_partially_empty_explicit_excel_matrices(tmp_path):
    path = tmp_path / "mriot_explicit_partial_ey.xlsx"
    _write_mriot_regional_explicit_workbook(path)
    _blank_explicit_excel_matrix(path, "EY", partial=True)

    with pytest.raises(WrongExcelFormat, match="partially empty|non-numeric"):
        parse_from_excel(
            path=str(path),
            table="IOT",
            mode="flows",
            matrix_layouts={"E": "Region", "EY": "Region"},
            calc_all=False,
        )


@pytest.mark.parametrize(
    ("table", "writer", "matrix_layouts"),
    [
        ("IOT", _write_mriot_regional_extensions_workbook, {"E": "Activity"}),
        ("IOT", _write_mriot_regional_extensions_workbook, {"Z": "Region"}),
        ("SUT", _write_custom_sut_explicit_no_level_workbook, {"E": "Sector"}),
    ],
)
def test_parse_from_excel_rejects_invalid_matrix_layouts(tmp_path, table, writer, matrix_layouts):
    path = tmp_path / f"invalid_{table.lower()}_layout.xlsx"
    writer(path)

    with pytest.raises(WrongInput):
        parse_from_excel(
            path=str(path),
            table=table,
            mode="flows",
            matrix_layouts=matrix_layouts,
            calc_all=False,
        )


def test_parse_from_excel_keeps_explicit_public_axes_without_level(tmp_path):
    path = tmp_path / "mriot_explicit.xlsx"
    _write_mriot_regional_explicit_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"E": "Region", "EY": "Region"},
        calc_all=False,
        name="MRIOT explicit regional extensions",
    )

    assert database.E.index.names == ["Region", "Satellite account"]
    assert database.Y.columns.names == ["Consumption category"]
    assert tuple(axis.id for axis in database.get_block_spec("E").row_axes) == (
        "Region",
        "Satellite account",
    )


def test_to_excel_exports_custom_iot_layout_without_level(tmp_path):
    path = tmp_path / "mriot_regional_v_e_explicit.xlsx"
    _write_mriot_regional_extensions_and_factors_explicit_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
        calc_all=False,
        name="MRIOT regional factors and extensions",
    )

    export_path = tmp_path / "exported.xlsx"
    database.to_excel(path=str(export_path), flows=True, coefficients=True)

    exported = pd.read_excel(export_path, sheet_name="flows", header=None)
    assert tuple(exported.iloc[0, 2:6]) == ("r1", "r1", "r2", "r2")
    assert exported.iloc[0, 6] != exported.iloc[0, 6]
    assert exported.iloc[0, 7] != exported.iloc[0, 7]
    assert tuple(exported.iloc[1, 2:8]) == ("s1", "s2", "s1", "s2", "hh", "investment")
    assert tuple(exported.iloc[6, 0:2]) == ("r1", "taxes")
    assert tuple(exported.iloc[10, 0:2]) == ("r1", "CO2")

    roundtrip = parse_from_excel(
        path=str(export_path),
        table="IOT",
        mode="flows",
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
        calc_all=False,
    )
    pdt.assert_frame_equal(roundtrip.Z, database.Z)
    pdt.assert_frame_equal(roundtrip.V, database.V)
    pdt.assert_frame_equal(roundtrip.E, database.E)
    pdt.assert_frame_equal(roundtrip.Y, database.Y)


def test_to_excel_aligns_iot_ey_and_vy_to_exported_row_order(tmp_path):
    path = tmp_path / "mriot_regional_v_e_alignment.xlsx"
    _write_mriot_regional_extensions_and_factors_explicit_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
        calc_all=False,
        name="MRIOT regional factors and extensions",
    )

    v_order = list(reversed(database.V.index.tolist()))
    e_order = list(reversed(database.E.index.tolist()))
    database.matrices["baseline"]["V"] = database.V.loc[v_order, :]
    database.matrices["baseline"]["E"] = database.E.loc[e_order, :]

    database.matrices["baseline"]["VY"] = database.VY.copy()
    database.matrices["baseline"]["EY"] = database.EY.copy()

    export_path = tmp_path / "exported_alignment.xlsx"
    database.to_excel(path=str(export_path), flows=True, coefficients=False)

    roundtrip = parse_from_excel(
        path=str(export_path),
        table="IOT",
        mode="flows",
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
        calc_all=False,
    )

    pdt.assert_frame_equal(_sorted_matrix(roundtrip.Z), _sorted_matrix(database.Z))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.V), _sorted_matrix(database.V))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.E), _sorted_matrix(database.E))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.Y), _sorted_matrix(database.Y))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.VY), _sorted_matrix(database.VY))
    pdt.assert_frame_equal(_sorted_matrix(roundtrip.EY), _sorted_matrix(database.EY))


def test_parse_state_from_txt_supports_matrix_layouts_on_matrix_payloads(tmp_path):
    state = _build_mriot_regional_state(tmp_path)
    root = tmp_path / "txt_matrix_layout"
    _write_matrix_payload_from_state(state, root, "txt")

    parsed = parse_state_from_txt(
        path=str(root),
        table="IOT",
        mode="flows",
        sep=",",
        matrix_layouts={"E": "Region", "EY": "Region"},
        name="IOT txt custom layout",
    )

    assert parsed.get_block("E").index.names == ["Region", "Level", "Item"]
    pdt.assert_frame_equal(_sorted_matrix(parsed.get_block("Z")), _sorted_matrix(state.get_block("Z")))
    pdt.assert_frame_equal(_sorted_matrix(parsed.get_block("E")), _sorted_matrix(state.get_block("E")))


def test_parse_state_from_txt_supports_matrix_layouts_on_flat_payloads(tmp_path):
    state = _build_mriot_regional_state(tmp_path)
    root = tmp_path / "txt_flat_layout"
    _write_flat_payload_from_state(state, root, "txt")

    parsed = parse_state_from_txt(
        path=str(root),
        table="IOT",
        mode="flows",
        sep=",",
        flat=True,
        matrix_layouts={"E": "Region", "EY": "Region"},
        name="IOT flat txt custom layout",
    )

    assert parsed.get_block("E").index.names == ["Region", "Satellite account"]
    pdt.assert_frame_equal(
        _sorted_matrix(parsed.get_block("Y")),
        _sorted_matrix(_explicit_custom_iot_frame(state.get_block("Y"), "Y")),
    )
    pdt.assert_frame_equal(
        _sorted_matrix(parsed.get_block("E")),
        _sorted_matrix(_explicit_custom_iot_frame(state.get_block("E"), "E")),
    )


def test_parse_state_from_txt_supports_legacy_sparse_coefficient_payloads_with_matrix_layouts(tmp_path):
    data = pd.DataFrame(
        [
            ("baseline", "v", "r", "", "taxes", "r", "", "s1", 0.235294),
            ("baseline", "v", "r", "", "taxes", "r", "", "s2", 0.225296),
            ("baseline", "v", "r", "", "capital", "r", "", "s1", 0.281046),
            ("baseline", "v", "r", "", "capital", "r", "", "s2", 0.217391),
            ("baseline", "e", "r", "", "CO2", "r", "", "s1", 0.379085),
            ("baseline", "e", "r", "", "CO2", "r", "", "s2", 0.090909),
            ("baseline", "Y", "r", "", "s1", "r", "", "hh", 70.0),
            ("baseline", "Y", "r", "", "s2", "r", "", "hh", 121.0),
            ("baseline", "EY", "r", "", "CO2", "r", "", "hh", 4.0),
            ("baseline", "z", "r", "", "s1", "r", "", "s1", 0.307190),
            ("baseline", "z", "r", "", "s1", "r", "", "s2", 0.142292),
            ("baseline", "z", "r", "", "s2", "r", "", "s1", 0.176471),
            ("baseline", "z", "r", "", "s2", "r", "", "s2", 0.415020),
        ],
        columns=LEGACY_FLAT_DATA_COLUMNS,
    )
    units = pd.DataFrame(
        [
            ("Sector", "s1", "EUR"),
            ("Sector", "s2", "EUR"),
            ("Factor of production", "taxes", "EUR"),
            ("Factor of production", "capital", "EUR"),
            ("Satellite account", "CO2", "ton"),
        ],
        columns=FLAT_UNIT_COLUMNS,
    )

    root = tmp_path / "legacy_sparse_coeffs"
    root.mkdir()
    data.to_csv(root / "data.txt", index=False)
    units.to_csv(root / "units.txt", index=False)

    parsed = parse_state_from_txt(
        path=str(root),
        table="IOT",
        mode="coefficients",
        sep=",",
        flat=True,
        matrix_layouts={
            "e": ("Region",),
            "v": ("Region", "Sector"),
            "EY": ("Region",),
        },
        name="legacy sparse coefficients",
    )

    assert parsed.get_block("v").index.names == ["Region", "Sector", "Factor of production"]
    assert parsed.get_block("e").index.names == ["Region", "Satellite account"]
    assert not parsed.get_block("v").isna().any().any()
    assert parsed.get_block("v").loc[("r", "s1", "taxes"), ("r", "s1")] == pytest.approx(0.235294)
    assert parsed.get_block("v").loc[("r", "s1", "taxes"), ("r", "s2")] == 0
    assert parsed.get_block("v").loc[("r", "s2", "capital"), ("r", "s2")] == pytest.approx(0.217391)
    assert parsed.get_block("e").loc[("r", "CO2"), ("r", "s2")] == pytest.approx(0.090909)


def test_parse_state_from_txt_iot_roundtrip_preserves_blocks(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",")

    state = parse_state_from_txt(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT txt dataset",
        sep=",",
    )

    assert state.table_kind == TableKind.IOT
    assert set(state.list_matrices()) == {"E", "EY", "V", "VY", "Y", "Z"}
    assert not state.has_matrix("X")
    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)


def test_parse_state_from_txt_iot_csv_roundtrip_preserves_blocks(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", _format="csv")

    state = parse_state_from_txt(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT csv dataset",
        sep=",",
        _format="csv",
    )

    assert (tmp_path / "flows" / "Z.csv").exists()
    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)


def test_to_txt_matrix_exports_custom_iot_layouts_without_level_markers(tmp_path):
    path = tmp_path / "mriot_regional_v_e_explicit.xlsx"
    _write_mriot_regional_extensions_and_factors_explicit_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
        calc_all=False,
    )
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=False)

    z_matrix = pd.read_csv(tmp_path / "flows" / "Z.txt", header=None, keep_default_na=False)
    y_matrix = pd.read_csv(tmp_path / "flows" / "Y.txt", header=None, keep_default_na=False)
    assert tuple(z_matrix.iloc[0, 2:6]) == ("r1", "r1", "r2", "r2")
    assert tuple(y_matrix.iloc[0, 2:4]) == ("hh", "investment")


def test_to_txt_roundtrip_preserves_custom_sut_matrix_layouts(tmp_path):
    database = _build_custom_sut_database()
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=False)

    assert (tmp_path / "flows" / "U.txt").exists()
    assert (tmp_path / "flows" / "S.txt").exists()
    assert not (tmp_path / "flows" / "Z.txt").exists()

    parsed = parse_from_txt(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        sep=",",
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        calc_all=False,
    )

    pdt.assert_frame_equal(_sorted_matrix(parsed.Z), _sorted_matrix(database.Z))
    pdt.assert_frame_equal(_sorted_matrix(parsed.V), _sorted_matrix(database.V))
    pdt.assert_frame_equal(_sorted_matrix(parsed.E), _sorted_matrix(database.E))
    pdt.assert_frame_equal(_sorted_matrix(parsed.Y), _sorted_matrix(database.Y))


def test_parse_from_txt_sut_roundtrip_returns_split_native_blocks(tmp_path):
    database = load_test("SUT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",")

    assert (tmp_path / "flows" / "U.txt").exists()
    assert (tmp_path / "flows" / "S.txt").exists()
    assert not (tmp_path / "flows" / "Z.txt").exists()

    parsed = parse_from_txt(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        sep=",",
        name="SUT txt dataset",
    )

    assert "Z" not in parsed["baseline"]
    assert "X" not in parsed["baseline"]
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"} <= set(parsed["baseline"])
    pdt.assert_frame_equal(parsed.Z, database.Z)
    pdt.assert_frame_equal(parsed.Y, database.Y)
    pdt.assert_frame_equal(parsed.V, database.V)
    pdt.assert_frame_equal(parsed.E, database.E)


def test_parse_from_txt_auto_detects_flows_subfolder_from_root_path(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",")

    parsed = parse_from_txt(
        path=str(tmp_path),
        table="IOT",
        mode="flows",
        sep=",",
        calc_all=False,
    )

    pdt.assert_frame_equal(_sorted_matrix(parsed.Z), _sorted_matrix(database.Z))
    pdt.assert_frame_equal(_sorted_matrix(parsed.V), _sorted_matrix(database.V))
    pdt.assert_frame_equal(_sorted_matrix(parsed.E), _sorted_matrix(database.E))
    pdt.assert_frame_equal(_sorted_matrix(parsed.Y), _sorted_matrix(database.Y))


def test_parse_from_txt_auto_detects_coefficients_subfolder_from_root_path(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=False, coefficients=True, sep=",")

    parsed = parse_from_txt(
        path=str(tmp_path),
        table="IOT",
        mode="coefficients",
        sep=",",
        calc_all=False,
    )

    pdt.assert_frame_equal(_sorted_matrix(parsed.z), _sorted_matrix(database.z))
    pdt.assert_frame_equal(_sorted_matrix(parsed.v), _sorted_matrix(database.v))
    pdt.assert_frame_equal(_sorted_matrix(parsed.e), _sorted_matrix(database.e))
    pdt.assert_frame_equal(_sorted_matrix(parsed.Y), _sorted_matrix(database.Y))


def test_parse_state_from_txt_supports_sut_matrix_layouts_on_matrix_payloads(tmp_path):
    blocks, _, units = _build_custom_sut_unified_blocks()
    root = tmp_path / "sut_txt_matrix_layout"
    _write_matrix_payload_from_blocks(blocks, units, root, "txt")

    parsed = parse_state_from_txt(
        path=str(root),
        table="SUT",
        mode="flows",
        sep=",",
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        name="SUT txt custom layout",
    )

    assert parsed.compute("V").index.names == ["Region", "Activity", "Factor of production"]
    assert parsed.compute("E").index.names == ["Region", "Activity", "Satellite account"]
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("Z")), _sorted_matrix(blocks["Z"]))
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("V")), _sorted_matrix(blocks["V"]))
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("E")), _sorted_matrix(blocks["E"]))


def test_parse_state_from_txt_supports_sut_matrix_layouts_on_flat_payloads(tmp_path):
    blocks, _, units = _build_custom_sut_unified_blocks()
    root = tmp_path / "sut_txt_flat_layout"
    _write_flat_payload_from_blocks(blocks, units, root, "txt")

    parsed = parse_state_from_txt(
        path=str(root),
        table="SUT",
        mode="flows",
        sep=",",
        flat=True,
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        name="SUT flat txt custom layout",
    )

    assert parsed.compute("V").index.names == ["Region", "Activity", "Factor of production"]
    assert parsed.compute("E").index.names == ["Region", "Activity", "Satellite account"]
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("Y")), _sorted_matrix(blocks["Y"]))
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("V")), _sorted_matrix(blocks["V"]))
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("E")), _sorted_matrix(blocks["E"]))


def test_to_txt_flat_exports_canonical_schema(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)

    data = pd.read_csv(tmp_path / "flows" / "data.txt", sep=",", keep_default_na=False)
    units = pd.read_csv(tmp_path / "flows" / "units.txt", sep=",", keep_default_na=False)

    assert list(data.columns) == list(
        flat_data_columns_for_sets(
            from_sets=("Region", "Sector", "Factor of production", "Satellite account"),
            to_sets=("Region", "Sector", "Consumption category"),
        )
    )
    assert list(units.columns) == list(FLAT_UNIT_COLUMNS)
    assert set(data["Matrix"]) == {"Z", "Y", "V", "E", "EY", "VY"}
    assert set(data["Scenario"]) == {"baseline"}


def test_parse_state_from_txt_iot_flat_roundtrip_preserves_blocks(tmp_path):
    database = load_test("IOT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)

    state = parse_state_from_txt(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT flat txt dataset",
        sep=",",
        flat=True,
    )

    assert state.table_kind == TableKind.IOT
    assert set(state.list_matrices()) == {"E", "EY", "V", "VY", "Y", "Z"}
    assert not state.has_matrix("X")
    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)


def test_parse_state_from_txt_iot_flat_csv_roundtrip_preserves_blocks(tmp_path):
    database = load_test("IOT")
    database.to_txt(
        path=tmp_path,
        flows=True,
        coefficients=False,
        sep=",",
        flat=True,
        _format="csv",
    )

    state = parse_state_from_txt(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT flat csv dataset",
        sep=",",
        flat=True,
        _format="csv",
    )

    assert (tmp_path / "flows" / "data.csv").exists()
    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)


def test_to_txt_flat_separate_files_exports_trimmed_matrix_payloads(tmp_path):
    database = load_test("IOT")
    database.to_txt(
        path=tmp_path,
        flows=True,
        coefficients=False,
        sep=",",
        flat=True,
        separate_files=True,
    )

    assert (tmp_path / "flows" / "data.txt").exists()
    assert (tmp_path / "flows" / "units.txt").exists()
    assert (tmp_path / "flows" / "Z.txt").exists()
    assert (tmp_path / "flows" / "Y.txt").exists()
    assert (tmp_path / "flows" / "V.txt").exists()

    z_data = pd.read_csv(tmp_path / "flows" / "Z.txt", sep=",", keep_default_na=False)
    y_data = pd.read_csv(tmp_path / "flows" / "Y.txt", sep=",", keep_default_na=False)
    assert list(z_data.columns) == list(
        flat_data_columns_for_sets(from_sets=("Region", "Sector"), to_sets=("Region", "Sector"))
    )
    assert list(y_data.columns) == list(
        flat_data_columns_for_sets(
            from_sets=("Region", "Sector"),
            to_sets=("Region", "Consumption category"),
        )
    )


def test_parse_state_from_txt_iot_flat_separate_files_roundtrip_preserves_blocks(tmp_path):
    database = load_test("IOT")
    database.to_txt(
        path=tmp_path,
        flows=True,
        coefficients=False,
        sep=",",
        flat=True,
        separate_files=True,
    )
    (tmp_path / "flows" / "data.txt").unlink()

    state = parse_state_from_txt(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT flat txt split dataset",
        sep=",",
        flat=True,
    )

    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)


def test_to_txt_flat_roundtrip_preserves_custom_iot_layouts_without_level_values(tmp_path):
    path = tmp_path / "mriot_regional_v_e_explicit.xlsx"
    _write_mriot_regional_extensions_and_factors_explicit_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
        calc_all=False,
    )
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)

    data = pd.read_csv(tmp_path / "flows" / "data.txt", sep=",", keep_default_na=False)
    z_rows = data.loc[data["Matrix"] == "Z"]
    assert "Activity_from" not in data.columns
    assert "Commodity_from" not in data.columns
    assert "Activity_to" not in data.columns
    assert "Commodity_to" not in data.columns
    assert set(z_rows["Region_from"]) == {"r1", "r2"}
    assert set(z_rows["Sector_from"]) == {"s1", "s2"}

    parsed = parse_from_txt(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        sep=",",
        flat=True,
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
    )

    pdt.assert_frame_equal(_sorted_matrix(parsed.Z), _sorted_matrix(database.Z))
    pdt.assert_frame_equal(_sorted_matrix(parsed.V), _sorted_matrix(database.V))
    pdt.assert_frame_equal(_sorted_matrix(parsed.E), _sorted_matrix(database.E))
    pdt.assert_frame_equal(_sorted_matrix(parsed.Y), _sorted_matrix(database.Y))


def test_parse_from_txt_sut_flat_roundtrip_uses_native_export_and_split_parse(tmp_path):
    database = load_test("SUT")
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)

    data = pd.read_csv(tmp_path / "flows" / "data.txt", sep=",", keep_default_na=False)
    parsed = parse_from_txt(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        sep=",",
        name="SUT flat txt dataset",
        flat=True,
    )

    assert set(data["Matrix"]) == {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"}
    assert "Z" not in parsed["baseline"]
    assert "X" not in parsed["baseline"]
    assert {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"} <= set(parsed["baseline"])
    pdt.assert_frame_equal(parsed.Z, database.Z)
    pdt.assert_frame_equal(parsed.Y, database.Y)
    pdt.assert_frame_equal(parsed.V, database.V)
    pdt.assert_frame_equal(parsed.E, database.E)


def test_to_txt_flat_roundtrip_preserves_custom_sut_layouts(tmp_path):
    database = _build_custom_sut_database()
    database.to_txt(path=tmp_path, flows=True, coefficients=False, sep=",", flat=True)

    data = pd.read_csv(tmp_path / "flows" / "data.txt", sep=",", keep_default_na=False)
    assert set(data["Matrix"]) == {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"}
    assert "Sector_from" not in data.columns
    assert "Activity_from" in data.columns
    assert "Commodity_from" in data.columns
    assert "Factor of production_from" in data.columns
    assert "Satellite account_from" in data.columns

    parsed = parse_from_txt(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        sep=",",
        flat=True,
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        calc_all=False,
    )

    pdt.assert_frame_equal(_sorted_matrix(parsed.Z), _sorted_matrix(database.Z))
    pdt.assert_frame_equal(_sorted_matrix(parsed.V), _sorted_matrix(database.V))
    pdt.assert_frame_equal(_sorted_matrix(parsed.E), _sorted_matrix(database.E))
    pdt.assert_frame_equal(_sorted_matrix(parsed.Y), _sorted_matrix(database.Y))


def test_to_parquet_flat_exports_canonical_schema(tmp_path):
    pytest.importorskip("pyarrow")

    database = load_test("IOT")
    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=True)

    data = pd.read_parquet(tmp_path / "flows" / "data.parquet")
    units = pd.read_parquet(tmp_path / "flows" / "units.parquet")

    assert list(data.columns) == list(
        flat_data_columns_for_sets(
            from_sets=("Region", "Sector", "Factor of production", "Satellite account"),
            to_sets=("Region", "Sector", "Consumption category"),
        )
    )
    assert list(units.columns) == list(FLAT_UNIT_COLUMNS)
    assert set(data["Matrix"]) == {"Z", "Y", "V", "E", "EY", "VY"}


def test_to_parquet_flat_separate_files_exports_trimmed_matrix_payloads(tmp_path):
    pytest.importorskip("pyarrow")

    database = load_test("IOT")
    database.to_parquet(
        path=tmp_path,
        flows=True,
        coefficients=False,
        flat=True,
        separate_files=True,
    )

    assert (tmp_path / "flows" / "data.parquet").exists()
    assert (tmp_path / "flows" / "units.parquet").exists()
    assert (tmp_path / "flows" / "Z.parquet").exists()
    assert (tmp_path / "flows" / "Y.parquet").exists()
    assert (tmp_path / "flows" / "V.parquet").exists()

    z_data = pd.read_parquet(tmp_path / "flows" / "Z.parquet")
    y_data = pd.read_parquet(tmp_path / "flows" / "Y.parquet")
    assert list(z_data.columns) == list(
        flat_data_columns_for_sets(from_sets=("Region", "Sector"), to_sets=("Region", "Sector"))
    )
    assert list(y_data.columns) == list(
        flat_data_columns_for_sets(
            from_sets=("Region", "Sector"),
            to_sets=("Region", "Consumption category"),
        )
    )


def test_parse_state_from_parquet_iot_flat_separate_files_roundtrip_preserves_blocks(tmp_path):
    pytest.importorskip("pyarrow")

    database = load_test("IOT")
    database.to_parquet(
        path=tmp_path,
        flows=True,
        coefficients=False,
        flat=True,
        separate_files=True,
    )
    (tmp_path / "flows" / "data.parquet").unlink()

    state = parse_state_from_parquet(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT flat parquet split dataset",
        flat=True,
    )

    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)


def test_parse_state_from_parquet_iot_matrix_roundtrip_preserves_blocks(tmp_path):
    pytest.importorskip("pyarrow")

    database = load_test("IOT")
    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=False)

    state = parse_state_from_parquet(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT parquet dataset",
    )

    assert state.table_kind == TableKind.IOT
    assert set(state.list_matrices()) == {"E", "EY", "V", "VY", "Y", "Z"}
    assert not state.has_matrix("X")
    pdt.assert_frame_equal(state.get_block("Z"), database.Z)
    pdt.assert_frame_equal(state.get_block("Y"), database.Y)
    pdt.assert_frame_equal(state.compute("X"), database.X)


def test_to_parquet_matrix_exports_sparse_backed_flow_blocks(tmp_path):
    pytest.importorskip("pyarrow")

    database = load_test("IOT")
    expected_blocks = {
        matrix_name: database.matrices["baseline"][matrix_name].copy()
        for matrix_name in ("Z", "Y", "V", "E", "EY", "VY")
    }

    for matrix_name, frame in expected_blocks.items():
        database.matrices["baseline"][matrix_name] = frame.astype(
            pd.SparseDtype("float64", 0.0)
        )

    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=False)

    state = parse_state_from_parquet(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        name="IOT sparse parquet dataset",
    )

    for matrix_name, expected in expected_blocks.items():
        pdt.assert_frame_equal(state.get_block(matrix_name), expected)


def test_to_parquet_flat_roundtrip_preserves_custom_iot_layouts_without_level_values(tmp_path):
    pytest.importorskip("pyarrow")

    path = tmp_path / "mriot_regional_v_e_explicit.xlsx"
    _write_mriot_regional_extensions_and_factors_explicit_workbook(path)

    database = parse_from_excel(
        path=str(path),
        table="IOT",
        mode="flows",
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
        calc_all=False,
    )
    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=True)

    data = pd.read_parquet(tmp_path / "flows" / "data.parquet")
    z_rows = data.loc[data["Matrix"] == "Z"]
    assert "Activity_from" not in data.columns
    assert "Commodity_from" not in data.columns
    assert "Activity_to" not in data.columns
    assert "Commodity_to" not in data.columns
    assert set(z_rows["Region_from"]) == {"r1", "r2"}
    assert set(z_rows["Sector_from"]) == {"s1", "s2"}

    parsed = parse_from_parquet(
        path=str(tmp_path / "flows"),
        table="IOT",
        mode="flows",
        flat=True,
        matrix_layouts={"V": "Region", "E": "Region", "EY": "Region"},
    )

    pdt.assert_frame_equal(_sorted_matrix(parsed.Z), _sorted_matrix(database.Z))
    pdt.assert_frame_equal(_sorted_matrix(parsed.V), _sorted_matrix(database.V))
    pdt.assert_frame_equal(_sorted_matrix(parsed.E), _sorted_matrix(database.E))
    pdt.assert_frame_equal(_sorted_matrix(parsed.Y), _sorted_matrix(database.Y))


def test_to_parquet_flat_roundtrip_preserves_custom_sut_layouts(tmp_path):
    pytest.importorskip("pyarrow")

    database = _build_custom_sut_database()
    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=True)

    data = pd.read_parquet(tmp_path / "flows" / "data.parquet")
    assert set(data["Matrix"]) == {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"}
    assert "Sector_from" not in data.columns
    assert "Activity_from" in data.columns
    assert "Commodity_from" in data.columns

    parsed = parse_from_parquet(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        flat=True,
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        calc_all=False,
    )

    pdt.assert_frame_equal(_sorted_matrix(parsed.Z), _sorted_matrix(database.Z))
    pdt.assert_frame_equal(_sorted_matrix(parsed.V), _sorted_matrix(database.V))
    pdt.assert_frame_equal(_sorted_matrix(parsed.E), _sorted_matrix(database.E))
    pdt.assert_frame_equal(_sorted_matrix(parsed.Y), _sorted_matrix(database.Y))


def test_parse_state_from_parquet_supports_matrix_layouts_on_matrix_payloads(tmp_path):
    pytest.importorskip("pyarrow")

    state = _build_mriot_regional_state(tmp_path)
    root = tmp_path / "parquet_matrix_layout"
    _write_matrix_payload_from_state(state, root, "parquet")

    parsed = parse_state_from_parquet(
        path=str(root),
        table="IOT",
        mode="flows",
        matrix_layouts={"E": "Region", "EY": "Region"},
        name="IOT parquet custom layout",
    )

    assert parsed.get_block("E").index.names == ["Region", "Level", "Item"]
    pdt.assert_frame_equal(_sorted_matrix(parsed.get_block("Z")), _sorted_matrix(state.get_block("Z")))
    pdt.assert_frame_equal(_sorted_matrix(parsed.get_block("E")), _sorted_matrix(state.get_block("E")))


def test_parse_state_from_parquet_supports_matrix_layouts_on_flat_payloads(tmp_path):
    pytest.importorskip("pyarrow")

    state = _build_mriot_regional_state(tmp_path)
    root = tmp_path / "parquet_flat_layout"
    _write_flat_payload_from_state(state, root, "parquet")

    parsed = parse_state_from_parquet(
        path=str(root),
        table="IOT",
        mode="flows",
        flat=True,
        matrix_layouts={"E": "Region", "EY": "Region"},
        name="IOT flat parquet custom layout",
    )

    assert parsed.get_block("E").index.names == ["Region", "Satellite account"]
    pdt.assert_frame_equal(
        _sorted_matrix(parsed.get_block("Y")),
        _sorted_matrix(_explicit_custom_iot_frame(state.get_block("Y"), "Y")),
    )
    pdt.assert_frame_equal(
        _sorted_matrix(parsed.get_block("E")),
        _sorted_matrix(_explicit_custom_iot_frame(state.get_block("E"), "E")),
    )


@pytest.mark.parametrize("flat", [False, True], ids=["matrix", "flat"])
def test_parse_from_parquet_sut_roundtrip_preserves_split_native_blocks_without_nans(tmp_path, flat):
    pytest.importorskip("pyarrow")

    database = load_test("SUT")
    expected_blocks = {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"}

    original_nan_blocks = [
        matrix_name
        for matrix_name in expected_blocks
        if database["baseline"][matrix_name].isna().any().any()
    ]
    assert original_nan_blocks == []

    database.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=flat)

    parsed = parse_from_parquet(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        flat=flat,
        name=f"SUT {'flat' if flat else 'matrix'} parquet dataset",
    )

    assert "Z" not in parsed["baseline"]
    assert "X" not in parsed["baseline"]
    assert expected_blocks <= set(parsed["baseline"])

    parsed_nan_blocks = [
        matrix_name
        for matrix_name in expected_blocks
        if parsed["baseline"][matrix_name].isna().any().any()
    ]
    assert parsed_nan_blocks == []

    for matrix_name in expected_blocks:
        pdt.assert_frame_equal(
            _sorted_matrix(parsed["baseline"][matrix_name]),
            _sorted_matrix(database["baseline"][matrix_name]),
        )

    pdt.assert_frame_equal(parsed.Z, database.Z)
    pdt.assert_frame_equal(parsed.Y, database.Y)
    pdt.assert_frame_equal(parsed.V, database.V)
    pdt.assert_frame_equal(parsed.E, database.E)


def test_parse_from_parquet_sut_matrix_roundtrip_after_region_style_aggregation_has_no_nans(tmp_path):
    pytest.importorskip("pyarrow")

    database = load_test("SUT")
    expected_blocks = {"U", "S", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY", "VY"}
    aggregated = database.aggregate(
        io={
            "Activity": pd.DataFrame(
                {"Aggregation": ["All"] * len(database.activities)},
                index=database.activities,
            ),
            "Commodity": pd.DataFrame(
                {"Aggregation": ["All"] * len(database.commodities)},
                index=database.commodities,
            ),
        },
        ignore_nan=True,
        levels=["Activity", "Commodity"],
        inplace=False,
        zero_output_epsilon=None,
    )

    for matrix_name in expected_blocks:
        assert not aggregated["baseline"][matrix_name].isna().any().any()

    aggregated.to_parquet(path=tmp_path, flows=True, coefficients=False, flat=False)

    parsed = parse_from_parquet(
        path=str(tmp_path / "flows"),
        table="SUT",
        mode="flows",
        flat=False,
        name="SUT aggregated parquet dataset",
        calc_all=False,
    )

    parsed_nan_blocks = [
        matrix_name
        for matrix_name in expected_blocks
        if parsed["baseline"][matrix_name].isna().any().any()
    ]
    assert parsed_nan_blocks == []

    pdt.assert_frame_equal(parsed.Z, aggregated.Z)
    pdt.assert_frame_equal(parsed.Y, aggregated.Y)
    pdt.assert_frame_equal(parsed.V, aggregated.V)
    pdt.assert_frame_equal(parsed.E, aggregated.E)


def test_parse_state_from_parquet_supports_sut_matrix_layouts_on_matrix_payloads(tmp_path):
    pytest.importorskip("pyarrow")

    blocks, _, units = _build_custom_sut_unified_blocks()
    root = tmp_path / "sut_parquet_matrix_layout"
    _write_matrix_payload_from_blocks(blocks, units, root, "parquet")

    parsed = parse_state_from_parquet(
        path=str(root),
        table="SUT",
        mode="flows",
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        name="SUT parquet custom layout",
    )

    assert parsed.compute("V").index.names == ["Region", "Activity", "Factor of production"]
    assert parsed.compute("E").index.names == ["Region", "Activity", "Satellite account"]
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("Z")), _sorted_matrix(blocks["Z"]))
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("V")), _sorted_matrix(blocks["V"]))
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("E")), _sorted_matrix(blocks["E"]))


def test_parse_state_from_parquet_supports_sut_matrix_layouts_on_flat_payloads(tmp_path):
    pytest.importorskip("pyarrow")

    blocks, _, units = _build_custom_sut_unified_blocks()
    root = tmp_path / "sut_parquet_flat_layout"
    _write_flat_payload_from_blocks(blocks, units, root, "parquet")

    parsed = parse_state_from_parquet(
        path=str(root),
        table="SUT",
        mode="flows",
        flat=True,
        matrix_layouts={"V": ("Region", "Activity"), "E": ("Region", "Activity")},
        name="SUT flat parquet custom layout",
    )

    assert parsed.compute("V").index.names == ["Region", "Activity", "Factor of production"]
    assert parsed.compute("E").index.names == ["Region", "Activity", "Satellite account"]
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("Y")), _sorted_matrix(blocks["Y"]))
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("V")), _sorted_matrix(blocks["V"]))
    pdt.assert_frame_equal(_sorted_matrix(parsed.compute("E")), _sorted_matrix(blocks["E"]))


def test_parser_registry_supports_third_party_registration():
    registry = ParserRegistry()

    @register_parser("dummy", registry=registry)
    def parse_dummy(**kwargs):
        return ModelState(
            metadata=ModelStateMetadata(
                table_kind=TableKind.IOT,
                name=kwargs.get("name"),
            )
        )

    state = registry.parse("dummy", name="custom")

    assert isinstance(state, ModelState)
    assert state.metadata.name == "custom"
    assert registry.names() == ("dummy",)
