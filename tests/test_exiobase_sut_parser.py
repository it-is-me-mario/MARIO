import json

import pandas as pd
import pandas.testing as pdt
import pytest

from mario import parse_exiobase_sut
from mario.log_exc.exceptions import WrongInput
from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.views import concat_sut_V, concat_sut_Y, concat_sut_Z
from mario.model.conventions import _MASTER_INDEX
from mario.model.enums import TableKind
from mario.parsers.exiobase import parse_state_exiobase_sut
from mario.parsers import exiobase_sut as exiobase_sut_parser
from mario.parsers.exiobase_sut import detect_exiobase_sut_layout
from mario.parsers.specs import EXIO_FACTOR_ROWS


def _write_frame(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t")


def _commodity_index():
    return pd.MultiIndex.from_tuples(
        [("IT", "prod_a"), ("IT", "prod_b")],
        names=["region", "sector"],
    )


def _activity_index():
    return pd.MultiIndex.from_tuples(
        [("IT", "act_a"), ("IT", "act_b")],
        names=["region", "sector"],
    )


def _fd_index():
    return pd.MultiIndex.from_tuples(
        [("IT", "Households"), ("IT", "Exports")],
        names=["region", "category"],
    )


def _write_exiobase_sut(root):
    commodities = _commodity_index()
    activities = _activity_index()
    final_demand = _fd_index()

    supply = pd.DataFrame(
        [[11.0, 12.0], [13.0, 14.0]],
        index=commodities,
        columns=activities,
    )
    use = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0]],
        index=commodities,
        columns=activities,
    )
    fd = pd.DataFrame(
        [[21.0, 22.0], [23.0, 24.0]],
        index=commodities,
        columns=final_demand,
    )
    value_added = pd.DataFrame(
        [[31.0, 32.0], [33.0, 34.0]],
        index=pd.Index(["Labour", "Capital"], name="factor"),
        columns=activities,
    )

    _write_frame(root / "supply.csv", supply)
    _write_frame(root / "use.csv", use)
    _write_frame(root / "final_demand.csv", fd)
    _write_frame(root / "value_added.csv", value_added)
    (root / "meta.json").write_text(
        json.dumps(
            {
                "year": 2011,
                "currency": "Euro",
                "price": "current",
                "vers": "20210125",
            }
        )
    )


def _write_matching_exiobase_iot(root):
    activities = _activity_index()
    final_demand = _fd_index()

    Z = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0]],
        index=activities,
        columns=activities,
    )
    Y = pd.DataFrame(
        [[5.0, 6.0], [7.0, 8.0]],
        index=activities,
        columns=final_demand,
    )
    top_units = pd.DataFrame(
        {"sector": ["act_a", "act_b"], "unit": ["EUR", "EUR"]},
        index=pd.Index(["IT", "IT"], name="region"),
    )
    factor_rows = EXIO_FACTOR_ROWS
    factor_F = pd.DataFrame(
        [[float(i), float(i + 0.5)] for i in range(1, len(factor_rows) + 1)],
        index=factor_rows,
        columns=activities,
    )
    factor_FY = pd.DataFrame(
        [[float(i + 10), float(i + 10.5)] for i in range(1, len(factor_rows) + 1)],
        index=factor_rows,
        columns=final_demand,
    )
    ext_F = pd.DataFrame(
        [[101.0, 102.0], [201.0, 202.0]],
        index=["CO2", "Water use"],
        columns=activities,
    )
    ext_FY = pd.DataFrame(
        [[11.0, 12.0], [21.0, 22.0]],
        index=["CO2", "Water use"],
        columns=final_demand,
    )
    factor_units = pd.DataFrame(
        {"unit": ["EUR"] * len(factor_rows)},
        index=pd.Index(factor_rows, name="stressor"),
    )
    ext_units = pd.DataFrame(
        {"unit": ["kg", "m3"]},
        index=pd.Index(["CO2", "Water use"], name="stressor"),
    )

    _write_frame(root / "Z.txt", Z)
    _write_frame(root / "Y.txt", Y)
    _write_frame(root / "unit.txt", top_units)
    _write_frame(root / "satellite" / "F.txt", pd.concat([factor_F, ext_F], axis=0))
    _write_frame(root / "satellite" / "F_Y.txt", pd.concat([factor_FY, ext_FY], axis=0))
    _write_frame(root / "satellite" / "unit.txt", pd.concat([factor_units, ext_units], axis=0))
    (root / "metadata.json").write_text(
        json.dumps(
            {
                "description": "Data for 2011",
                "name": "EXIO_IOT_2011_ixi",
                "system": "ixi",
                "version": "v3.81",
                "history": [],
            }
        )
    )
    (root / "file_parameters.json").write_text(
        json.dumps({"files": {}, "systemtype": "IOSystem"})
    )


def test_detect_exiobase_sut_layout_reads_meta_json(tmp_path):
    root = tmp_path / "Exiobase 3.8.2 - MRSUT_2011_ixi"
    _write_exiobase_sut(root)

    layout = detect_exiobase_sut_layout(root)

    assert layout.version == "3.8.2"
    assert layout.year == 2011
    assert layout.system == "ixi"
    assert layout.currency == "Euro"
    assert layout.price == "current"


def test_parse_exiobase_sut_keeps_split_native_blocks_demand_driven(tmp_path):
    root = tmp_path / "Exiobase 3.8.2 - MRSUT_2011_ixi"
    _write_exiobase_sut(root)

    db = parse_exiobase_sut(str(root), calc_all=False)

    assert db.meta.year == 2011
    assert db.meta.price == "current"
    assert "version 3.8.2" in db.meta.source
    assert db.units[_MASTER_INDEX["a"]].loc["act_a", "unit"] == "EUR"
    assert db.units[_MASTER_INDEX["c"]].loc["prod_a", "unit"] == "EUR"
    assert set(db.matrices["baseline"]) == {"EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"}
    assert "Z" not in db.matrices["baseline"]
    assert "Y" not in db.matrices["baseline"]
    assert "V" not in db.matrices["baseline"]

    ordering = SUTUnifiedOrderingPolicy.from_blocks(
        U=db.U,
        S=db.S,
        Ya=db.Ya,
        Yc=db.Yc,
        Va=db.Va,
        Vc=db.Vc,
    )
    expected_Z = concat_sut_Z(db.U, db.S, ordering)
    expected_Y = concat_sut_Y(db.Ya, db.Yc, ordering)
    expected_V = concat_sut_V(db.Va, db.Vc, ordering)

    pdt.assert_frame_equal(db.Z, expected_Z)
    pdt.assert_frame_equal(db.Y, expected_Y)
    pdt.assert_frame_equal(db.V, expected_V)
    assert {"Z", "Y", "V"} <= set(db.matrices["baseline"])


def test_parse_exiobase_sut_can_import_extensions_from_matching_iot(tmp_path):
    sut_root = tmp_path / "Exiobase 3.8.2 - MRSUT_2011_ixi"
    iot_root = tmp_path / "Exiobase 3.8.2 - IOT_2011_ixi"
    _write_exiobase_sut(sut_root)
    _write_matching_exiobase_iot(iot_root)

    db = parse_exiobase_sut(
        str(sut_root),
        add_extensions=str(iot_root),
        calc_all=False,
    )

    expected_ea = pd.DataFrame(
        [[101.0, 102.0], [201.0, 202.0]],
        index=pd.Index(["CO2", "Water use"], name="Item"),
        columns=pd.MultiIndex.from_tuples(
            [
                ("IT", _MASTER_INDEX["a"], "act_a"),
                ("IT", _MASTER_INDEX["a"], "act_b"),
            ],
            names=["Region", "Level", "Item"],
        ),
    )
    expected_ey = pd.DataFrame(
        [[11.0, 12.0], [21.0, 22.0]],
        index=pd.Index(["CO2", "Water use"], name="Item"),
        columns=pd.MultiIndex.from_tuples(
            [
                ("IT", _MASTER_INDEX["n"], "Households"),
                ("IT", _MASTER_INDEX["n"], "Exports"),
            ],
            names=["Region", "Level", "Item"],
        ),
    )

    pdt.assert_frame_equal(db.Ea, expected_ea)
    pdt.assert_frame_equal(db.EY, expected_ey)
    assert (db.Ec == 0).all().all()
    assert db.get_index(_MASTER_INDEX["k"]) == ["CO2", "Water use"]
    assert db.units[_MASTER_INDEX["k"]].loc["CO2", "unit"] == "kg"


def test_parse_exiobase_sut_rejects_invalid_extension_path_before_reading_sut(tmp_path, monkeypatch):
    sut_root = tmp_path / "Exiobase 3.8.2 - MRSUT_2011_ixi"
    _write_exiobase_sut(sut_root)

    def _unexpected_read(*args, **kwargs):
        raise AssertionError("SUT matrices should not be read when add_extensions is invalid")

    monkeypatch.setattr(exiobase_sut_parser, "_read_numeric_matrix", _unexpected_read)

    with pytest.raises((WrongInput, FileNotFoundError)):
        parse_exiobase_sut(
            str(sut_root),
            add_extensions=str(tmp_path / "missing_iot"),
            calc_all=False,
        )


def test_parse_state_exiobase_sut_builds_internal_split_native_state(tmp_path):
    root = tmp_path / "Exiobase 3.8.2 - MRSUT_2011_ixi"
    _write_exiobase_sut(root)

    state = parse_state_exiobase_sut(str(root))

    assert state.table_kind == TableKind.SUT
    assert not state.has_block("Z")
    assert {"EY", "Ea", "Ec", "S", "U", "Va", "Vc", "Ya", "Yc"} <= set(state.list_blocks())

    ordering = SUTUnifiedOrderingPolicy.from_blocks(
        U=state.get_block("U"),
        S=state.get_block("S"),
        Ya=state.get_block("Ya"),
        Yc=state.get_block("Yc"),
        Va=state.get_block("Va"),
        Vc=state.get_block("Vc"),
    )
    pdt.assert_frame_equal(
        state.compute("Z"),
        concat_sut_Z(state.get_block("U"), state.get_block("S"), ordering),
    )
