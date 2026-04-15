from mario.compute.catalog import CATALOG_OPEN_QUESTIONS, COMPUTE_CATALOG, get_matrix_spec
from mario.model.enums import TableKind
from mario.model.labels import (
    INDEX_LABELS,
    ITEM_LABEL,
    PRODUCTION_LABEL,
    TableSchemaLabels,
    get_table_schema_labels,
)


def test_model_labels_still_derive_from_settings():
    schema = get_table_schema_labels("IOT")

    assert isinstance(schema, TableSchemaLabels)
    assert INDEX_LABELS["r"] == "Region"
    assert INDEX_LABELS["s"] == "Sector"
    assert schema.dimension_labels == (
        "Factor of production",
        "Satellite account",
        "Consumption category",
        "Region",
        "Sector",
    )


def test_catalog_covers_iot_and_sut_blocks():
    assert len(COMPUTE_CATALOG[TableKind.IOT]) == 18
    assert len(COMPUTE_CATALOG[TableKind.SUT]) == 49

    sut_wcc = get_matrix_spec("SUT", "wcc")
    sut_c = get_matrix_spec("SUT", "c")
    sut_xc = get_matrix_spec("SUT", "Xc")
    iot_p = get_matrix_spec("IOT", "p")
    iot_vy = get_matrix_spec("IOT", "VY")

    assert len(sut_wcc.strategies) == 2
    assert sut_c.axes.rows == (INDEX_LABELS["r"], INDEX_LABELS["c"], ITEM_LABEL)
    assert sut_c.axes.cols == (INDEX_LABELS["r"], INDEX_LABELS["a"], ITEM_LABEL)
    assert {strategy.function for strategy in sut_c.strategies} == {
        "build_sut_c_from_S_Xa",
        "build_sut_c_from_s",
    }
    assert sut_xc.axes.cols == (PRODUCTION_LABEL,)
    assert {strategy.function for strategy in iot_p.strategies} == {
        "build_iot_p_from_v_z",
        "build_iot_p_from_v_w",
    }
    assert iot_vy.strategies[-1].function == "build_zero_VY_from_V_Y"


def test_catalog_keeps_known_compute_todos_visible():
    sut_w = get_matrix_spec(TableKind.SUT, "w")
    sut_m = get_matrix_spec(TableKind.SUT, "M")
    sut_f = get_matrix_spec(TableKind.SUT, "F")
    sut_b = get_matrix_spec(TableKind.SUT, "b")

    assert len(CATALOG_OPEN_QUESTIONS) == 4
    assert "spreadsheet typo" in sut_w.strategies[0].notes[0]
    assert sut_w.todo == CATALOG_OPEN_QUESTIONS[0]
    assert sut_m.todo == CATALOG_OPEN_QUESTIONS[1]
    assert sut_f.todo == CATALOG_OPEN_QUESTIONS[2]
    assert sut_b.todo == CATALOG_OPEN_QUESTIONS[3]
