import pytest

from mario.log_exc.exceptions import WrongInput
from mario.test.mario_test import load_test


def test_load_test_uses_standard_default_and_keeps_legacy_alias():
    database = load_test("IOT")
    legacy = load_test("IOT", layout="legacy")

    assert database.table_type == "IOT"
    assert database.Z.shape == (6, 6)
    assert legacy.Z.shape == database.Z.shape
    assert database.get_index("Region") == ["Reg1", "Reg2"]


def test_load_test_supports_standard_and_special_variants():
    iot_standard = load_test("IOT", layout="standard")
    iot_special = load_test("IOT", layout="special")
    sut_standard = load_test("SUT", layout="standard")
    sut_special = load_test("SUT", layout="special")

    assert iot_standard.Z.shape == (6, 6)
    assert iot_special.Z.shape == (6, 6)
    assert tuple(iot_special.V.index.names) == ("Region", "Sector", "Factor of production")
    assert tuple(iot_special.E.index.names) == ("Region", "Satellite account")

    assert sut_standard.Z.shape == (8, 8)
    assert sut_special.Z.shape == (8, 8)
    assert tuple(sut_special.E.index.names) == ("Region", "Commodity", "Satellite account")


def test_load_test_rejects_unknown_layout():
    with pytest.raises(WrongInput):
        load_test("IOT", layout="unknown")
