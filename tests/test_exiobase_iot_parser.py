import json

import pandas as pd
import pytest

from mario import parse_exiobase_3
from mario.log_exc.exceptions import WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.exiobase_iot import detect_exiobase_iot_layout
from mario.parsers.specs import EXIO_FACTOR_ROWS


def _write_frame(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t")


def _sector_index():
    return pd.MultiIndex.from_tuples(
        [("AT", "sec_a"), ("AT", "sec_b")],
        names=["region", "sector"],
    )


def _fd_index():
    return pd.MultiIndex.from_tuples(
        [("AT", "Households"), ("AT", "Exports")],
        names=["region", "category"],
    )


def _base_top_level_frames():
    sectors = _sector_index()
    fd = _fd_index()

    Z = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], index=sectors, columns=sectors)
    Y = pd.DataFrame([[5.0, 6.0], [7.0, 8.0]], index=sectors, columns=fd)
    units = pd.DataFrame(
        {"sector": ["sec_a", "sec_b"], "unit": ["M.EUR", "M.EUR"]},
        index=pd.Index(["AT", "AT"], name="region"),
    )
    return Z, Y, units


def _factor_frames():
    sectors = _sector_index()
    fd = _fd_index()
    factor_rows = EXIO_FACTOR_ROWS
    F = pd.DataFrame(
        [[float(i), float(i + 0.5)] for i in range(1, len(factor_rows) + 1)],
        index=factor_rows,
        columns=sectors,
    )
    FY = pd.DataFrame(
        [[float(i + 10), float(i + 10.5)] for i in range(1, len(factor_rows) + 1)],
        index=factor_rows,
        columns=fd,
    )
    units = pd.DataFrame(
        {"unit": ["M.EUR"] * len(factor_rows)},
        index=pd.Index(factor_rows, name="stressor"),
    )
    return F, FY, units


def _extension_frames():
    sectors = _sector_index()
    fd = _fd_index()
    rows = ["CO2", "Water use"]
    F = pd.DataFrame([[1.0, 0.5], [2.0, 2.5]], index=rows, columns=sectors)
    FY = pd.DataFrame([[0.1, 0.2], [0.3, 0.4]], index=rows, columns=fd)
    units = pd.DataFrame({"unit": ["kg", "m3"]}, index=pd.Index(rows, name="stressor"))
    return F, FY, units


def _write_metadata(root, version, description="EXIOBASE version 3.x.x - ixi for 2011"):
    metadata = {
        "description": description,
        "name": "EXIO_IOT_2011_ixi",
        "system": "ixi",
        "version": version,
        "history": [],
    }
    (root / "metadata.json").write_text(json.dumps(metadata))
    (root / "file_parameters.json").write_text(json.dumps({"files": {}, "systemtype": "IOSystem"}))


def _write_legacy_exiobase(root):
    Z, Y, units = _base_top_level_frames()
    factor_F, factor_FY, factor_units = _factor_frames()
    ext_F, ext_FY, ext_units = _extension_frames()

    _write_frame(root / "Z.txt", Z)
    _write_frame(root / "Y.txt", Y)
    _write_frame(root / "unit.txt", units)
    _write_frame(root / "satellite" / "F.txt", pd.concat([factor_F, ext_F], axis=0))
    _write_frame(root / "satellite" / "F_Y.txt", pd.concat([factor_FY, ext_FY], axis=0))
    _write_frame(root / "satellite" / "unit.txt", pd.concat([factor_units, ext_units], axis=0))
    _write_metadata(root, "v3.81", description="Data for 2011")


def _write_split_exiobase(root, *, version="3.10.1", extension_dir="labour"):
    Z, Y, units = _base_top_level_frames()
    factor_F, factor_FY, factor_units = _factor_frames()
    ext_F, ext_FY, ext_units = _extension_frames()

    _write_frame(root / "Z.txt", Z)
    _write_frame(root / "Y.txt", Y)
    _write_frame(root / "unit.txt", units)
    _write_frame(root / "factor_inputs" / "F.txt", factor_F)
    _write_frame(root / "factor_inputs" / "F_Y.txt", factor_FY)
    _write_frame(root / "factor_inputs" / "unit.txt", factor_units)
    _write_frame(root / extension_dir / "F.txt", ext_F)
    _write_frame(root / extension_dir / "F_Y.txt", ext_FY)
    _write_frame(root / extension_dir / "unit.txt", ext_units)
    _write_metadata(root, version)


def test_detect_exiobase_iot_layout_reads_metadata_and_layout(tmp_path):
    root = tmp_path / "Exiobase 3.10.1 - IOT_2011_ixi"
    _write_split_exiobase(root, version="3.10.1", extension_dir="labour")

    layout = detect_exiobase_iot_layout(root)

    assert layout.version == "3.10.1"
    assert layout.year == 2011
    assert layout.factor_directory == "factor_inputs"
    assert layout.extension_directories == ("labour",)


def test_parse_exiobase_3_parses_legacy_satellite_bundle(tmp_path):
    root = tmp_path / "Exiobase 3.8.2 - IOT_2011_ixi"
    _write_legacy_exiobase(root)

    db = parse_exiobase_3(str(root), calc_all=False)

    assert db.meta.year == 2011
    assert db.meta.name == "EXIO_IOT_2011_ixi"
    assert "version 3.8.2" in db.meta.source
    assert db.matrices["baseline"].keys() >= {"Z", "Y", "V", "E", "EY"}
    assert "X" not in db.matrices["baseline"]
    assert db.get_index(_MASTER_INDEX["f"]) == EXIO_FACTOR_ROWS
    assert db.get_index(_MASTER_INDEX["k"]) == ["CO2", "Water use"]
    assert db.units[_MASTER_INDEX["s"]].loc["sec_a", "unit"] == "M.EUR"


def test_parse_exiobase_3_parses_split_extensions_without_version_argument(tmp_path):
    root = tmp_path / "Exiobase 3.10.1 - IOT_2011_ixi"
    _write_split_exiobase(root, version="3.10.1", extension_dir="labour")

    db = parse_exiobase_3(str(root), calc_all=False)

    assert db.meta.year == 2011
    assert db.meta.name == "EXIO_IOT_2011_ixi"
    assert "version 3.10.1" in db.meta.source
    assert db.get_index(_MASTER_INDEX["f"]) == EXIO_FACTOR_ROWS
    assert db.get_index(_MASTER_INDEX["k"]) == ["CO2", "Water use"]
    assert db.units[_MASTER_INDEX["k"]].loc["CO2", "unit"] == "kg"


def test_parse_exiobase_3_rejects_explicit_version_mismatch(tmp_path):
    root = tmp_path / "Exiobase 3.10.1 - IOT_2011_ixi"
    _write_split_exiobase(root, version="3.10.1", extension_dir="employment")

    with pytest.raises(WrongInput):
        parse_exiobase_3(str(root), version="3.8.2", calc_all=False)
