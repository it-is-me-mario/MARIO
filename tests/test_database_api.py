import pandas as pd
import pandas.testing as pdt

from mario.log_exc.logger import set_log_verbosity
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.primitives import calc_w, calc_z
from mario.compute.views import (
    concat_sut_e,
    concat_sut_f,
    concat_sut_p,
    concat_sut_v,
    extract_ea_from_e,
    extract_ec_from_e,
    extract_fa_from_f,
    extract_fc_from_f,
    extract_pa_from_p,
    extract_pc_from_p,
    extract_va_from_v,
    extract_vc_from_v,
)
from mario.settings.settings import (
    reset_settings,
    set_compute_method,
    set_linear_solver,
    set_linear_strategy,
)
from mario.test.mario_test import load_test
from mario.model.conventions import _ENUM, _MASTER_INDEX
from mario.ops.workbook_specs import SHOCK_COLUMNS, SHOCK_FLAT_COLUMNS


def test_calc_all_iot_uses_catalog_path_for_missing_blocks():
    database = load_test("IOT")
    assert _ENUM.X not in database["baseline"]

    database.calc_all([_ENUM.w])

    expected_z = calc_z(database.Z, database.X)
    expected_w = calc_w(expected_z)

    pdt.assert_frame_equal(database.z, expected_z)
    pdt.assert_frame_equal(database.w, expected_w)


def test_calc_all_iot_solve_method_resolves_f_without_materializing_w():
    database = load_test("IOT")
    assert _ENUM.w not in database["baseline"]

    database.calc_all([_ENUM.f], compute_method="solve", linear_solver="scipy")

    expected_z = calc_z(database.Z, database.X)
    expected_w = calc_w(expected_z)
    expected_f = database.e.dot(expected_w)

    pdt.assert_frame_equal(database.f, expected_f)
    assert _ENUM.w not in database["baseline"]


def test_dotted_access_logs_selected_iot_runtime_method(capsys):
    try:
        reset_settings()
        set_compute_method("solve")
        set_linear_solver("scipy")
        set_linear_strategy("auto")
        set_log_verbosity("info", capture_warnings=False, include_dependency_logs=False)

        database = load_test("IOT")
        _ = database.f

        captured = capsys.readouterr().out
        assert "build_iot_f_from_e_z" in captured
        assert "compute_method=solve" in captured
        assert "runtime=solve" in captured
        assert "Compute: solving IOT linear system" not in captured
    finally:
        reset_settings()


def test_dotted_access_logs_selected_sut_runtime_method(capsys):
    try:
        reset_settings()
        set_compute_method("solve")
        set_linear_solver("scipy")
        set_linear_strategy("auto")
        set_log_verbosity("info", capture_warnings=False, include_dependency_logs=False)

        database = load_test("SUT")
        _ = database.f

        captured = capsys.readouterr().out
        assert "runtime=solve" in captured
        assert "Compute: solving SUT linear system" not in captured
        assert (
            "build_sut_fa_from_ea_s_u" in captured
            or "build_sut_fc_from_ea_s_u" in captured
        )
    finally:
        reset_settings()


def test_debug_logs_include_linear_strategy_details_for_solve_backend(capsys):
    try:
        reset_settings()
        set_compute_method("solve")
        set_linear_solver("scipy")
        set_linear_strategy("auto")
        set_log_verbosity("debug", capture_warnings=False, include_dependency_logs=False)

        database = load_test("IOT")
        _ = database.f

        captured = capsys.readouterr().out
        assert "Compute: solving IOT linear system" in captured
        assert "linear_solver=scipy" in captured
        assert "linear_strategy=" in captured
    finally:
        reset_settings()


def test_calc_all_sut_resolves_unified_blocks_from_split_dependencies():
    database = load_test("SUT")
    assert _ENUM.X not in database["baseline"]

    database.calc_all([_ENUM.z, _ENUM.u, _ENUM.s, _ENUM.w])

    expected_z = calc_z(database.Z, database.X)
    expected_u = expected_z.loc[
        (slice(None), _MASTER_INDEX["c"], slice(None)),
        (slice(None), _MASTER_INDEX["a"], slice(None)),
    ]
    expected_s = expected_z.loc[
        (slice(None), _MASTER_INDEX["a"], slice(None)),
        (slice(None), _MASTER_INDEX["c"], slice(None)),
    ]
    expected_w = calc_w(expected_z)

    pdt.assert_frame_equal(database.z, expected_z)
    pdt.assert_frame_equal(database.u, expected_u)
    pdt.assert_frame_equal(database.s, expected_s)
    pdt.assert_frame_equal(database.w, expected_w)
    assert {"wcc", "wca", "wac", "waa"}.issubset(set(database["baseline"]))


def test_calc_linkages_supports_sut_specific_ghosh_blocks():
    database = load_test("SUT")

    linkages = database.calc_linkages(multi_mode=False)

    assert list(linkages.columns) == [
        "Total Forward",
        "Total Backward",
        "Direct Forward",
        "Direct Backward",
    ]
    assert len(linkages) == len(database.query(_ENUM.z))
    assert {"bu", "bs", "gcc", "gca", "gac", "gaa"}.issubset(set(database["baseline"]))
    assert _ENUM.b not in database["baseline"]
    assert _ENUM.g not in database["baseline"]


def test_query_and_get_data_auto_calc():
    database = load_test("IOT")

    queried = database.query(matrices=[_ENUM.w], scenarios=["baseline"])
    data = database.get_data(
        matrices=[_ENUM.p],
        scenarios=["baseline"],
        units=True,
        indeces=True,
        auto_calc=True,
        format="dict",
    )

    assert isinstance(queried, pd.DataFrame)
    pdt.assert_frame_equal(queried, database.w)
    assert _ENUM.w in database["baseline"]
    pdt.assert_frame_equal(data["baseline"][_ENUM.p], database.p)
    assert "units" in data["baseline"]
    assert "indeces" in data["baseline"]


def test_query_relative_difference_shape_is_preserved():
    database = load_test("IOT")
    database.clone_scenario("baseline", "policy")
    database.matrices["policy"][_ENUM.Z] = database.Z * 2

    diff = database.query(
        matrices=[_ENUM.Z],
        scenarios=["policy"],
        base_scenario="baseline",
        type="relative",
    )

    expected = (
        database.matrices["policy"][_ENUM.Z]
        - database.matrices["baseline"][_ENUM.Z]
    ) / database.matrices["baseline"][_ENUM.Z]
    pdt.assert_frame_equal(diff, expected)


def test_database_api_accepts_new_sut_split_matrices():
    database = load_test("SUT")

    queried = database.query(matrices=["fa"], scenarios=["baseline"])
    payload = database.get_data(
        matrices=["va", "vc", "ea", "ec", "fa", "fc", "pa", "pc"],
        scenarios=["baseline"],
        format="dict",
    )

    ordering = SUTUnifiedOrderingPolicy.from_blocks(X=database.X, Y=database.Y)
    pdt.assert_frame_equal(queried, database.fa)
    pdt.assert_frame_equal(concat_sut_v(database.va, database.vc, ordering), database.v)
    pdt.assert_frame_equal(concat_sut_e(database.ea, database.ec, ordering), database.e)
    pdt.assert_frame_equal(concat_sut_f(database.fa, database.fc, ordering), database.f)
    pdt.assert_frame_equal(concat_sut_p(database.pa, database.pc, ordering), database.p)
    pdt.assert_frame_equal(
        payload["baseline"]["va"], extract_va_from_v(database.v, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["vc"], extract_vc_from_v(database.v, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["ea"], extract_ea_from_e(database.e, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["ec"], extract_ec_from_e(database.e, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["fa"], extract_fa_from_f(database.f, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["fc"], extract_fc_from_f(database.f, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["pa"], extract_pa_from_p(database.p, ordering)
    )
    pdt.assert_frame_equal(
        payload["baseline"]["pc"], extract_pc_from_p(database.p, ordering)
    )


def test_set_clusters_normalizes_names_and_preserves_copy_semantics():
    database = load_test("IOT")

    database.set_clusters(
        clusters={"region": {"EU": ["Reg1", "Reg2"]}},
        s={"Primary": ["Agriculture"]},
    )

    stored = database.clusters
    assert stored == {
        "Region": {"EU": ["Reg1", "Reg2"]},
        "Sector": {"Primary": ["Agriculture"]},
    }

    stored["Region"]["EU"].append("dummy")
    assert database.clusters["Region"]["EU"] == ["Reg1", "Reg2"]


def test_default_clusters_include_all_for_every_set():
    database = load_test("IOT")

    defaults = database.default_clusters

    assert set(defaults) == set(database.sets)
    for set_name in database.sets:
        assert defaults[set_name]["all"] == database.get_index(set_name)


def test_default_region_clusters_include_country_converter_groups_when_possible():
    database = load_test("IOT")
    database._indeces["r"]["main"] = ["ITA", "FRA"]

    region_clusters = database.default_clusters["Region"]

    assert "continent:Europe" in region_clusters
    assert "ITA" in region_clusters["continent:Europe"]


def test_default_region_clusters_use_manual_adb_overrides_for_nonstandard_codes():
    database = load_test("IOT")
    database._indeces["r"]["main"] = ["GER", "UKG", "SWI", "TAP"]
    database.meta._add_attribute(source="ADB MRIO test payload")

    region_clusters = database.default_clusters["Region"]

    assert region_clusters["all"] == ["GER", "UKG", "SWI", "TAP"]
    assert "continent:Europe" in region_clusters
    assert set(["GER", "UKG", "SWI"]).issubset(region_clusters["continent:Europe"])
    assert "continent:Asia" in region_clusters
    assert "TAP" in region_clusters["continent:Asia"]
    assert set(["GER", "UKG"]).issubset(region_clusters["G7"])


def test_available_clusters_merge_defaults_and_user_clusters():
    database = load_test("IOT")
    database.set_clusters(clusters={"region": {"EU custom": ["Reg1", "Reg2"]}})

    available = database.available_clusters

    assert "all" in available["Region"]
    assert available["Region"]["EU custom"] == ["Reg1", "Reg2"]


def test_get_shock_excel_uses_stored_clusters(tmp_path):
    database = load_test("IOT")
    database.set_clusters(clusters={"region": {"EU": ["Reg1", "Reg2"]}})
    path = tmp_path / "clustered_shock.xlsx"

    database.get_shock_excel(path=str(path), num_shock=2)

    indeces = pd.read_excel(path, sheet_name="indeces", header=None)
    assert "EU" in indeces.iloc[:, 0].dropna().tolist()


def test_shock_calc_uses_stored_clusters(tmp_path):
    database = load_test("IOT")
    database.set_clusters(clusters={"region": {"EU": ["Reg1", "Reg2"]}})
    path = tmp_path / "clustered_iot_shock.xlsx"

    base = database.z.copy()
    col = base.columns[0]
    row_items = [
        ("Reg1", row[1], row[2])
        for row in base.index
        if row[0] == "Reg1"
    ]
    row_item = row_items[0][2]
    updated = 0.222

    z_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: "EU",
                SHOCK_FLAT_COLUMNS["sector_from"]: row_item,
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["sector_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        z_sheet.to_excel(writer, sheet_name=_ENUM.z, index=False)

    database.shock_calc(str(path), z=True, scenario="cluster shock")

    shocked = database.query(_ENUM.z, scenarios=["cluster shock"])
    for region in ["Reg1", "Reg2"]:
        assert shocked.loc[(region, _MASTER_INDEX["s"], row_item), col] == updated


def test_get_shock_excel_still_accepts_legacy_cluster_kwargs(tmp_path):
    database = load_test("IOT")
    path = tmp_path / "legacy_clustered_shock.xlsx"

    database.get_shock_excel(path=str(path), num_shock=2, Region={"EU": ["Reg1", "Reg2"]})

    indeces = pd.read_excel(path, sheet_name="indeces", header=None)
    assert "EU" in indeces.iloc[:, 0].dropna().tolist()


def test_build_new_instance_preserves_stored_clusters():
    database = load_test("IOT")
    database.set_clusters(clusters={"region": {"EU": ["Reg1", "Reg2"]}})

    new = database.build_new_instance("baseline")

    assert new.clusters == {"Region": {"EU": ["Reg1", "Reg2"]}}


def test_get_shock_excel_for_sut_writes_only_nonzero_split_sheets(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_shock.xlsx"

    database.get_shock_excel(path=str(path), num_shock=2)

    with pd.ExcelFile(path) as workbook:
        assert set(workbook.sheet_names) == {"indeces", "main", _ENUM.u, _ENUM.s, "Yc", "va", "ea"}
        assert _ENUM.z not in workbook.sheet_names
        assert "Ya" not in workbook.sheet_names
        assert "vc" not in workbook.sheet_names
        assert "ec" not in workbook.sheet_names

        u_sheet = pd.read_excel(workbook, _ENUM.u)
        assert list(u_sheet.columns) == [
            SHOCK_FLAT_COLUMNS["region_from"],
            SHOCK_FLAT_COLUMNS["commodity_from"],
            SHOCK_FLAT_COLUMNS["region_to"],
            SHOCK_FLAT_COLUMNS["activity_to"],
            SHOCK_FLAT_COLUMNS["type"],
            SHOCK_FLAT_COLUMNS["value"],
        ]


def test_get_shock_excel_for_iot_uses_flat_columns_without_levels(tmp_path):
    database = load_test("IOT")
    path = tmp_path / "iot_shock.xlsx"

    database.get_shock_excel(path=str(path), num_shock=2)

    with pd.ExcelFile(path) as workbook:
        indeces = pd.read_excel(workbook, "indeces", header=None)
        assert "all" in indeces.iloc[:, 0].dropna().tolist()

        z_sheet = pd.read_excel(workbook, _ENUM.z)
        assert list(z_sheet.columns) == [
            SHOCK_FLAT_COLUMNS["region_from"],
            SHOCK_FLAT_COLUMNS["sector_from"],
            SHOCK_FLAT_COLUMNS["region_to"],
            SHOCK_FLAT_COLUMNS["sector_to"],
            SHOCK_FLAT_COLUMNS["type"],
            SHOCK_FLAT_COLUMNS["value"],
        ]


def test_shock_calc_for_sut_reads_split_u_sheet(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_u_shock.xlsx"

    base_u = database.u.copy()
    row = base_u.index[0]
    col = base_u.columns[0]
    updated = 0.123456

    u_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["commodity_from"]: row[2],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["activity_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        u_sheet.to_excel(writer, sheet_name=_ENUM.u, index=False)

    database.shock_calc(str(path), z=True, scenario="split shock")

    expected = base_u.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.u, scenarios=["split shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_sut_reads_split_Yc_sheet(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_yc_shock.xlsx"

    base = database.query("Yc").copy()
    row = base.index[0]
    col = base.columns[0]
    updated = 42.0

    yc_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["commodity_from"]: row[2],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["category_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        yc_sheet.to_excel(writer, sheet_name="Yc", index=False)

    database.shock_calc(str(path), Y=True, scenario="split Y shock")

    expected = base.copy()
    expected.loc[row, col] = updated
    shocked = database.query("Yc", scenarios=["split Y shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_iot_accepts_flat_z_sheet(tmp_path):
    database = load_test("IOT")
    path = tmp_path / "iot_flat_z_shock.xlsx"

    base = database.z.copy()
    row = base.index[0]
    col = base.columns[0]
    updated = 0.789

    z_sheet = pd.DataFrame(
        [
            {
                SHOCK_FLAT_COLUMNS["region_from"]: row[0],
                SHOCK_FLAT_COLUMNS["sector_from"]: row[2],
                SHOCK_FLAT_COLUMNS["region_to"]: col[0],
                SHOCK_FLAT_COLUMNS["sector_to"]: col[2],
                SHOCK_FLAT_COLUMNS["type"]: "Update",
                SHOCK_FLAT_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        z_sheet.to_excel(writer, sheet_name=_ENUM.z, index=False)

    database.shock_calc(str(path), z=True, scenario="flat iot shock")

    expected = base.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.z, scenarios=["flat iot shock"])

    pdt.assert_frame_equal(shocked, expected)


def test_shock_calc_for_sut_accepts_legacy_z_sheet(tmp_path):
    database = load_test("SUT")
    path = tmp_path / "sut_legacy_z_shock.xlsx"

    base_u = database.u.copy()
    row = base_u.index[0]
    col = base_u.columns[0]
    updated = 0.654321

    z_sheet = pd.DataFrame(
        [
            {
                SHOCK_COLUMNS["r_reg"]: row[0],
                SHOCK_COLUMNS["r_lev"]: row[1],
                SHOCK_COLUMNS["r_sec"]: row[2],
                SHOCK_COLUMNS["c_reg"]: col[0],
                SHOCK_COLUMNS["c_lev"]: col[1],
                SHOCK_COLUMNS["c_sec"]: col[2],
                SHOCK_COLUMNS["type"]: "Update",
                SHOCK_COLUMNS["value"]: updated,
            }
        ]
    )

    with pd.ExcelWriter(path) as writer:
        z_sheet.to_excel(writer, sheet_name=_ENUM.z, index=False)

    database.shock_calc(str(path), z=True, scenario="legacy shock")

    expected = base_u.copy()
    expected.loc[row, col] = updated
    shocked = database.query(_ENUM.u, scenarios=["legacy shock"])

    pdt.assert_frame_equal(shocked, expected)
