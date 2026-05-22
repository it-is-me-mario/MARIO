from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongFormat
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.gtap import (
    build_gtap_mrio_from_csv_frames,
    build_gtap_mrio_from_gdx_containers,
    detect_gtap_layout,
)


def _gtap_csv_frames() -> dict[str, pd.DataFrame]:
    srcxdst = pd.DataFrame(
        [
            {"VAR": "DOM", "COMM": "SEC", "AGENT": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 10.0},
            {"VAR": "DOM", "COMM": "SEC", "AGENT": "HH", "SRC": "R1", "DST": "R1", "VALUE": 3.0},
            {"VAR": "VFOB", "COMM": "SEC", "AGENT": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 1.0},
            {"VAR": "VFOB", "COMM": "SEC", "AGENT": "HH", "SRC": "R1", "DST": "R1", "VALUE": 2.0},
            {"VAR": "MTAX", "COMM": "SEC", "AGENT": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 0.5},
            {"VAR": "MTAX", "COMM": "SEC", "AGENT": "HH", "SRC": "R1", "DST": "R1", "VALUE": 0.2},
            {"VAR": "ITTM", "COMM": "SEC", "AGENT": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 0.7},
            {"VAR": "ITTM", "COMM": "SEC", "AGENT": "HH", "SRC": "R1", "DST": "R1", "VALUE": 0.1},
        ]
    )
    value_tax = pd.DataFrame(
        [
            {"VAR": "ETAX", "COMM": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 0.3},
            {"VAR": "PTAX", "COMM": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 0.4},
        ]
    )
    value_added = pd.DataFrame(
        [
            {"VAR": "VA", "COMM": "LAB", "AGENT": "SEC", "REG": "R1", "VALUE": 5.0},
            {"VAR": "VTAX", "COMM": "PROD", "AGENT": "SEC", "REG": "R1", "VALUE": 0.6},
            {"VAR": "IDTAX", "COMM": "SEC", "AGENT": "SEC", "REG": "R1", "VALUE": 0.8},
            {"VAR": "IDTAX", "COMM": "SEC", "AGENT": "HH", "REG": "R1", "VALUE": 0.9},
            {"VAR": "IMTAX", "COMM": "SEC", "AGENT": "SEC", "REG": "R1", "VALUE": 1.0},
            {"VAR": "IMTAX", "COMM": "SEC", "AGENT": "HH", "REG": "R1", "VALUE": 1.1},
        ]
    )
    emissions = pd.DataFrame(
        [
            {"VAR": "DOM", "EM": "CO2", "COMM": "coal", "AGT": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 2.0},
            {"VAR": "DOM", "EM": "CO2", "COMM": "coal", "AGT": "HH", "SRC": "R1", "DST": "R1", "VALUE": 0.5},
            {"VAR": "IMP", "EM": "CO2", "COMM": "coal", "AGT": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 1.5},
            {"VAR": "IMP", "EM": "CO2", "COMM": "coal", "AGT": "HH", "SRC": "R1", "DST": "R1", "VALUE": 0.2},
        ]
    )
    energy = pd.DataFrame(
        [
            {"VAR": "DOM", "COMM": "coal", "AGT": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 4.0},
            {"VAR": "DOM", "COMM": "coal", "AGT": "HH", "SRC": "R1", "DST": "R1", "VALUE": 0.7},
            {"VAR": "IMP", "COMM": "coal", "AGT": "SEC", "SRC": "R1", "DST": "R1", "VALUE": 1.2},
            {"VAR": "IMP", "COMM": "coal", "AGT": "HH", "SRC": "R1", "DST": "R1", "VALUE": 0.3},
        ]
    )
    return {
        "SRCxDST": srcxdst,
        "V - Tax": value_tax,
        "V": value_added,
        "E+EY - Emissions": emissions,
        "E+EY - Energy": energy,
    }


class _FakeSymbol:
    def __init__(self, records: pd.DataFrame):
        self.records = records


class _FakeContainer:
    def __init__(self, **symbols):
        self.data = symbols


def _gtap_gdx_containers() -> dict[str, _FakeContainer]:
    srcxdst = _FakeContainer(
        comm=_FakeSymbol(pd.DataFrame({"uni": ["SEC"]})),
        REG=_FakeSymbol(pd.DataFrame({"uni": ["R1"]})),
        agt=_FakeSymbol(pd.DataFrame({"uni": ["SEC", "HH"]})),
        VDBA=_FakeSymbol(pd.DataFrame([{"COMM": "SEC", "agt": "SEC", "REG": "R1", "value": 10.0}])),
        VFOB=_FakeSymbol(
            pd.DataFrame(
                [
                    {"COMM": "SEC", "agt": "SEC", "SRC": "R1", "DST": "R1", "value": 1.0},
                    {"COMM": "SEC", "agt": "HH", "SRC": "R1", "DST": "R1", "value": 5.0},
                ]
            )
        ),
        MTAX=_FakeSymbol(
            pd.DataFrame(
                [
                    {"COMM": "SEC", "agt": "SEC", "SRC": "R1", "DST": "R1", "value": 0.5},
                    {"COMM": "SEC", "agt": "HH", "SRC": "R1", "DST": "R1", "value": 0.2},
                ]
            )
        ),
        ITTM=_FakeSymbol(
            pd.DataFrame(
                [
                    {"COMM": "SEC", "agt": "SEC", "SRC": "R1", "DST": "R1", "value": 0.7},
                    {"COMM": "SEC", "agt": "HH", "SRC": "R1", "DST": "R1", "value": 0.1},
                ]
            )
        ),
    )
    value_tax = _FakeContainer(
        ETAX=_FakeSymbol(pd.DataFrame([{"COMM": "SEC", "SRC": "R1", "DST": "R1", "value": 0.3}])),
        PTAX=_FakeSymbol(pd.DataFrame([{"COMM": "SEC", "REG": "R1", "acts": "SEC", "value": 0.4}])),
    )
    value_added = _FakeContainer(
        VA=_FakeSymbol(pd.DataFrame([{"ENDW": "LAB", "acts": "SEC", "DST": "R1", "value": 5.0}])),
        VTAX=_FakeSymbol(pd.DataFrame([{"ENDW": "PROD", "acts": "SEC", "DST": "R1", "value": 0.6}])),
        IDTAX=_FakeSymbol(
            pd.DataFrame(
                [
                    {"COMM": "SEC", "agt": "SEC", "DST": "R1", "value": 0.8},
                    {"COMM": "SEC", "agt": "HH", "DST": "R1", "value": 0.9},
                ]
            )
        ),
        IMTAX=_FakeSymbol(
            pd.DataFrame(
                [
                    {"COMM": "SEC", "agt": "SEC", "DST": "R1", "value": 1.0},
                    {"COMM": "SEC", "agt": "HH", "DST": "R1", "value": 1.1},
                ]
            )
        ),
    )
    emissions = _FakeContainer(
        Emi_COMB=_FakeSymbol(
            pd.DataFrame(
                [
                    {"em": "CO2", "inputs": "coal", "agt": "SEC", "SRC": "R1", "DST": "R1", "source": "DOM", "value": 2.0},
                    {"em": "CO2", "inputs": "coal", "agt": "HH", "SRC": "R1", "DST": "R1", "source": "DOM", "value": 0.5},
                    {"em": "CO2", "inputs": "coal", "agt": "SEC", "SRC": "R1", "DST": "R1", "source": "IMP", "value": 1.5},
                    {"em": "CO2", "inputs": "coal", "agt": "HH", "SRC": "R1", "DST": "R1", "source": "IMP", "value": 0.2},
                ]
            )
        ),
        Emi=_FakeSymbol(
            pd.DataFrame(
                [
                    {"em": "CO2", "inputs": "coal", "agt": "SEC", "SRC": "R1", "DST": "R1", "source": "DOM", "value": 0.4},
                    {"em": "CO2", "inputs": "coal", "agt": "HH", "SRC": "R1", "DST": "R1", "source": "DOM", "value": 0.1},
                    {"em": "CO2", "inputs": "coal", "agt": "SEC", "SRC": "R1", "DST": "R1", "source": "IMP", "value": 0.3},
                    {"em": "CO2", "inputs": "coal", "agt": "HH", "SRC": "R1", "DST": "R1", "source": "IMP", "value": 0.05},
                ]
            )
        ),
        Emi_Proc=_FakeSymbol(
            pd.DataFrame(
                [
                    {"em": "CO2", "comm": "SEC", "acts": "SEC", "REG": "R1", "value": 0.9},
                    {"em": "CO2", "comm": "SEC", "acts": "HH", "REG": "R1", "value": 0.2},
                ]
            )
        ),
    )
    energy = _FakeContainer(
        NRG=_FakeSymbol(
            pd.DataFrame(
                [
                    {"ERG": "coal", "agt": "SEC", "SRC": "R1", "DST": "R1", "SOURCE": "DOM", "value": 4.0},
                    {"ERG": "coal", "agt": "HH", "SRC": "R1", "DST": "R1", "SOURCE": "DOM", "value": 0.7},
                    {"ERG": "coal", "agt": "SEC", "SRC": "R1", "DST": "R1", "SOURCE": "IMP", "value": 1.2},
                    {"ERG": "coal", "agt": "HH", "SRC": "R1", "DST": "R1", "SOURCE": "IMP", "value": 0.3},
                ]
            )
        )
    )
    return {
        "SRCxDST": srcxdst,
        "V": value_added,
        "V-Tax": value_tax,
        "Emissions": emissions,
        "Energy": energy,
    }


def _gtap_gdx_containers_with_string_metadata() -> dict[str, _FakeContainer]:
    containers = _gtap_gdx_containers()
    for container in containers.values():
        for symbol in container.data.values():
            records = symbol.records.copy()
            records["element_text"] = pd.Series(["meta"] * len(records), dtype="string")
            symbol.records = records
    return containers


def _write_gtap_csv_bundle(path: Path) -> None:
    frames = _gtap_csv_frames()
    mapping = {
        "SRCxDST": "GSDFSRCxDST.csv",
        "V - Tax": "GSDFXTAX.csv",
        "V": "GSDF.csv",
        "E+EY - Emissions": "GSDFEMI.csv",
        "E+EY - Energy": "GSDFNRG.csv",
    }
    for key, filename in mapping.items():
        frames[key].to_csv(path / filename, index=False)


def test_build_gtap_mrio_from_csv_frames_returns_canonical_blocks():
    matrices, indeces, units = build_gtap_mrio_from_csv_frames(_gtap_csv_frames())
    base = matrices["baseline"]

    assert set(base) == {"Z", "Y", "V", "VY", "E", "EY"}
    assert base["Z"].shape == (1, 1)
    assert base["Y"].shape == (1, 1)
    assert base["V"].shape[1] == 1
    assert base["VY"].shape[1] == 1
    assert float(base["Z"].iloc[0, 0]) == 11.0
    assert float(base["Y"].iloc[0, 0]) == 5.0
    assert float(base["V"].loc["VAAD_REG_LAB"].iloc[0]) == 5.0
    assert float(base["VY"].loc["DTAX_REG_SEC"].iloc[0]) == 0.9
    assert "EMI_CO2_dms_coal" in indeces["k"]["main"]
    assert units[_MASTER_INDEX["k"]].loc["EMI_CO2_dms_coal", "unit"] == "M ton"


def test_build_gtap_mrio_from_gdx_containers_returns_canonical_blocks():
    matrices, indeces, units = build_gtap_mrio_from_gdx_containers(_gtap_gdx_containers())
    base = matrices["baseline"]

    assert set(base) == {"Z", "Y", "V", "VY", "E", "EY"}
    assert base["Z"].shape == (1, 1)
    assert base["Y"].shape == (1, 1)
    assert float(base["Z"].iloc[0, 0]) == 11.0
    assert float(base["Y"].iloc[0, 0]) == 5.0
    assert float(base["VY"].loc["ITAX_REG_SEC"].iloc[0]) == 1.1
    assert "E_P_CO2_REG_SEC" in indeces["k"]["main"]
    assert units[_MASTER_INDEX["k"]].loc["ENE_dms_coal", "unit"] == "M toe"


def test_build_gtap_mrio_from_gdx_containers_tolerates_string_metadata_columns():
    matrices, indeces, units = build_gtap_mrio_from_gdx_containers(
        _gtap_gdx_containers_with_string_metadata()
    )
    base = matrices["baseline"]

    assert set(base) == {"Z", "Y", "V", "VY", "E", "EY"}
    assert float(base["Z"].iloc[0, 0]) == 11.0
    assert indeces["s"]["main"] == ["SEC"]
    assert units[_MASTER_INDEX["f"]].loc["VAAD_REG_LAB", "unit"] == "M USD"


def test_detect_gtap_layout_prefers_csv_when_both_bundles_exist(tmp_path):
    _write_gtap_csv_bundle(tmp_path)
    for filename in ["GSDFSRCxDST.gdx", "GSDF.gdx", "GSDFXTAX.gdx", "GSDFEMI.gdx", "GSDFNRG.gdx"]:
        (tmp_path / filename).write_text("placeholder")

    layout = detect_gtap_layout(tmp_path)

    assert layout.input_format == "csv"
    assert layout.variant == "power"
    assert layout.layout == "MRIO"


def test_public_parse_gtap_builds_iot_database_from_local_csv_bundle(tmp_path):
    _write_gtap_csv_bundle(tmp_path)

    database = mario.parse_gtap(str(tmp_path), calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.source is not None
    assert database.get_index(_MASTER_INDEX["r"]) == ["R1"]
    assert database.VY.shape == (4, 1)


def test_public_parse_gtap_gdx_invalid_bundle_fails_cleanly(tmp_path):
    for filename in ["GSDFSRCxDST.gdx", "GSDF.gdx", "GSDFXTAX.gdx", "GSDFEMI.gdx", "GSDFNRG.gdx"]:
        (tmp_path / filename).write_text("placeholder")

    expected = ModuleNotFoundError if not _gams_available() else WrongFormat
    with pytest.raises(expected):
        mario.parse_gtap(str(tmp_path), input_format="gdx", calc_all=False)


def _gams_available() -> bool:
    try:
        from gams import transfer as _  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True
