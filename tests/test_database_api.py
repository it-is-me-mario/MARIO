import pandas as pd
import pandas.testing as pdt

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
from mario.test.mario_test import load_test
from mario.model.conventions import _ENUM, _MASTER_INDEX


def test_calc_all_iot_uses_catalog_path_for_missing_blocks():
    database = load_test("IOT")
    assert _ENUM.X not in database["baseline"]

    database.calc_all([_ENUM.w])

    expected_z = calc_z(database.Z, database.X)
    expected_w = calc_w(expected_z)

    pdt.assert_frame_equal(database.z, expected_z)
    pdt.assert_frame_equal(database.w, expected_w)


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
