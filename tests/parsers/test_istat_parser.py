from __future__ import annotations

import io
from pathlib import Path
import zipfile

import pandas as pd
import numpy as np
import pytest

import mario
from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.model.conventions import _MASTER_INDEX
from mario.parsers.istat import (
    build_istat_iot_from_frame,
    build_istat_sut_from_frames,
    detect_istat_iot_layout,
    detect_istat_sut_layout,
)


def _blank_frame(rows: int, cols: int) -> pd.DataFrame:
    return pd.DataFrame([[None] * cols for _ in range(rows)])


def _istat_iot_frame() -> pd.DataFrame:
    frame = _blank_frame(14, 10)
    frame.iat[1, 1] = "Anno"
    frame.iat[2, 1] = 2020
    frame.iat[4, 0] = "PRODOTTI (CPA* 2)"
    frame.iat[5, 1] = "PRODOTTI (CPA*2)"
    frame.iat[4, 2] = "Agricoltura"
    frame.iat[5, 2] = "R01"
    frame.iat[4, 3] = "Manifatture"
    frame.iat[5, 3] = "R02"
    frame.iat[4, 4] = "Totale  (1)"
    frame.iat[5, 4] = "R"
    frame.iat[4, 5] = "Spesa per consumi finali delle famiglie"
    frame.iat[4, 6] = "Esportazioni"
    frame.iat[4, 7] = "Spesa per consumi finali"
    frame.iat[4, 8] = "Totale impieghi finali (2)"
    frame.iat[4, 9] = "Totale impieghi (1) + (2)"

    frame.iat[6, 0] = "R01"
    frame.iat[6, 1] = "Agricoltura"
    frame.iloc[6, 2:10] = [10.0, 1.0, 11.0, 2.0, 3.0, 5.0, 10.0, 21.0]
    frame.iat[7, 0] = "R02"
    frame.iat[7, 1] = "Manifatture"
    frame.iloc[7, 2:10] = [4.0, 20.0, 24.0, 6.0, 7.0, 13.0, 26.0, 50.0]
    frame.iat[8, 0] = "R"
    frame.iat[8, 1] = "Consumi intermedi ai prezzi base"
    frame.iat[9, 1] = "Imposte meno contributi ai prodotti"
    frame.iloc[9, 2:4] = [1.0, 2.0]
    frame.iat[10, 1] = "Valore aggiunto ai prezzi base"
    frame.iloc[10, 2:4] = [3.0, 4.0]
    frame.iat[11, 1] = "Importazioni cif"
    frame.iloc[11, 2:4] = [5.0, 6.0]
    frame.iat[12, 1] = "Produzione ai prezzi base"
    frame.iloc[12, 2:4] = [14.0, 24.0]
    frame.iat[13, 1] = "(a) nota"
    return frame


def _istat_supply_frame() -> pd.DataFrame:
    frame = _blank_frame(10, 10)
    frame.iat[1, 1] = "Anno"
    frame.iat[2, 1] = 2020
    frame.iat[4, 0] = "BRANCHE (NACE)"
    frame.iat[5, 0] = "Codice"
    frame.iat[5, 1] = "PRODOTTI (CPA)"
    frame.iat[4, 2] = "Agricoltura"
    frame.iat[5, 2] = "V01"
    frame.iat[4, 3] = "Manifatture"
    frame.iat[5, 3] = "V02"
    frame.iat[4, 4] = "Totale Impieghi intermedi (1)"
    frame.iat[5, 4] = "V"

    frame.iat[6, 0] = "R01"
    frame.iat[6, 1] = "Prodotto A"
    frame.iloc[6, 2:5] = [10.0, 1.0, 11.0]
    frame.iat[7, 0] = "R02"
    frame.iat[7, 1] = "Prodotto B"
    frame.iloc[7, 2:5] = [2.0, 20.0, 22.0]
    frame.iat[8, 0] = "R"
    frame.iat[8, 1] = "Consumi intermedi ai prezzi base"
    frame.iat[9, 1] = "(a) nota"
    return frame


def _istat_use_frame() -> pd.DataFrame:
    frame = _blank_frame(16, 10)
    frame.iat[1, 1] = "Anno"
    frame.iat[2, 1] = 2020
    frame.iat[4, 0] = "BRANCHE (NACE)"
    frame.iat[5, 1] = "PRODOTTI (CPA)"
    frame.iat[4, 2] = "Agricoltura"
    frame.iat[5, 2] = "V01"
    frame.iat[4, 3] = "Manifatture"
    frame.iat[5, 3] = "V02"
    frame.iat[4, 4] = "Totale Impieghi intermedi (1)"
    frame.iat[5, 4] = "V"
    frame.iat[4, 5] = "Spesa per consumi finali delle famiglie"
    frame.iat[4, 6] = "Esportazioni"
    frame.iat[4, 7] = "Spesa per consumi finali"
    frame.iat[4, 8] = "Totale impieghi finali (2)"
    frame.iat[4, 9] = "Totale impieghi (1) + (2)"

    frame.iat[6, 0] = "R01"
    frame.iat[6, 1] = "Prodotto A"
    frame.iloc[6, 2:10] = [3.0, 1.0, 4.0, 5.0, 6.0, 11.0, 11.0, 15.0]
    frame.iat[7, 0] = "R02"
    frame.iat[7, 1] = "Prodotto B"
    frame.iloc[7, 2:10] = [2.0, 4.0, 6.0, 7.0, 8.0, 15.0, 15.0, 21.0]
    frame.iat[8, 0] = "R"
    frame.iat[8, 1] = "Consumi intermedi ai prezzi base"
    frame.iat[9, 1] = "Tasse meno contributi ai prodotti"
    frame.iloc[9, 2:4] = [0.5, 0.7]
    frame.iat[10, 1] = "Valore aggiunto ai prezzi base"
    frame.iloc[10, 2:4] = [4.0, 5.0]
    frame.iat[11, 1] = "Produzione ai prezzi base"
    frame.iloc[11, 2:4] = [7.5, 10.7]
    frame.iat[12, 1] = "Investimenti fissi lordi"
    frame.iloc[12, 2:4] = [1.0, 1.0]
    frame.iat[13, 1] = "Stock di capitale fisso"
    frame.iloc[13, 2:4] = [2.0, 2.0]
    frame.iat[14, 1] = "Ore lavorate (migliaia)"
    frame.iloc[14, 2:4] = [3.0, 3.0]
    frame.iat[15, 1] = "(a) nota"
    return frame


def _istat_import_frame() -> pd.DataFrame:
    frame = _blank_frame(10, 10)
    frame.iat[1, 1] = "Anno"
    frame.iat[2, 1] = 2020
    frame.iat[4, 0] = "BRANCHE (NACE)"
    frame.iat[5, 1] = "PRODOTTI (CPA)"
    frame.iat[4, 2] = "Agricoltura"
    frame.iat[5, 2] = "V01"
    frame.iat[4, 3] = "Manifatture"
    frame.iat[5, 3] = "V02"
    frame.iat[4, 4] = "Totale Impieghi intermedi (1)"
    frame.iat[5, 4] = "V"
    frame.iat[4, 5] = "Spesa per consumi finali delle famiglie"
    frame.iat[4, 6] = "Esportazioni"
    frame.iat[4, 7] = "Totale impieghi finali (2)"
    frame.iat[4, 8] = "Totale impieghi (1) + (2)"

    frame.iat[6, 0] = "R01"
    frame.iat[6, 1] = "Prodotto A"
    frame.iloc[6, 2:9] = [1.0, 0.0, 1.0, 2.0, 3.0, 5.0, 6.0]
    frame.iat[7, 0] = "R02"
    frame.iat[7, 1] = "Prodotto B"
    frame.iloc[7, 2:9] = [0.0, 2.0, 2.0, 4.0, 5.0, 9.0, 11.0]
    frame.iat[8, 0] = "R"
    frame.iat[8, 1] = "Consumi intermedi ai prezzi base"
    frame.iat[9, 1] = "(a) nota"
    return frame


def _write_xlsx(path: Path, sheet_name: str, frame: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=sheet_name, header=False, index=False)


def _minimal_istat_release_zip() -> bytes:
    iot = io.BytesIO()
    sut_supply = io.BytesIO()
    sut_use = io.BytesIO()
    sut_import = io.BytesIO()
    with pd.ExcelWriter(iot, engine="openpyxl") as writer:
        _istat_iot_frame().to_excel(writer, sheet_name="STOTPP_2020", header=False, index=False)
    with pd.ExcelWriter(sut_supply, engine="openpyxl") as writer:
        _istat_supply_frame().to_excel(writer, sheet_name="sup20", header=False, index=False)
    with pd.ExcelWriter(sut_use, engine="openpyxl") as writer:
        _istat_use_frame().to_excel(writer, sheet_name="uspb20", header=False, index=False)
    with pd.ExcelWriter(sut_import, engine="openpyxl") as writer:
        _istat_import_frame().to_excel(writer, sheet_name="imprt20", header=False, index=False)

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Tavole_I_O/SIMM_TOT_63PxP.xlsx", iot.getvalue())
        zf.writestr("Tavole_I_O/SUPPLY_63B.xlsx", sut_supply.getvalue())
        zf.writestr("Tavole_I_O/USEPB_63B.xlsx", sut_use.getvalue())
        zf.writestr("Tavole_I_O/IMPORT_63B.xlsx", sut_import.getvalue())
    return archive.getvalue()


def test_build_istat_iot_from_frame_returns_canonical_blocks():
    matrices, indeces, units, layout = build_istat_iot_from_frame(
        _istat_iot_frame(),
        year=2020,
        mode="product",
    )
    base = matrices["baseline"]

    assert layout.dataset_name == "ISTAT IOT 2020 product"
    assert set(base) == {"Z", "Y", "V", "E", "EY"}
    assert base["Z"].shape == (2, 2)
    assert base["Y"].shape == (2, 2)
    assert base["V"].shape == (3, 2)
    assert float(base["Z"].iloc[0, 0]) == 10.0
    assert float(base["Y"].iloc[0, 0]) == 2.0
    assert float(base["Y"].iloc[0, 1]) == 3.0
    assert "Spesa per consumi finali" not in indeces["n"]["main"]
    assert units["Sector"].iloc[0, 0] == "Milioni di euro"


def test_build_istat_sut_from_frames_returns_split_native_blocks():
    matrices, indeces, units, layout = build_istat_sut_from_frames(
        _istat_supply_frame(),
        _istat_use_frame(),
        _istat_import_frame(),
        year=2020,
        level="63",
        valuation="basic",
    )
    base = matrices["baseline"]

    assert layout.dataset_name == "ISTAT SUT 2020 63 current basic"
    assert set(base) == {"S", "U", "Ya", "Yc", "Va", "Vc", "VY", "Ea", "Ec", "EY"}
    assert base["S"].shape == (2, 2)
    assert base["U"].shape == (2, 2)
    assert base["Yc"].shape == (2, 2)
    assert float(base["S"].iloc[0, 0]) == 10.0
    assert float(base["U"].iloc[0, 0]) == 3.0
    assert float(base["Yc"].iloc[0, 0]) == 5.0
    assert float(base["Va"].loc["Valore aggiunto ai prezzi base"].iloc[0]) == 4.0
    assert float(base["Vc"].loc["Importazioni cif"].iloc[0]) == 6.0
    assert "Spesa per consumi finali" not in indeces["n"]["main"]
    assert units["Activity"].iloc[0, 0] == "Milioni di euro"


def test_istat_separate_imports_pipeline(tmp_path):
    """Raw workbooks -> coefficients -> aggregation -> accounting/file round trips."""
    supply, use, imports = _istat_supply_frame(), _istat_use_frame(), _istat_import_frame()
    # Make published rows balance exactly, with nonzero imported intermediate
    # and final uses and a final-demand product-tax adjustment.
    supply.iloc[6, 2:4] = [5.0, 4.0]
    supply.iloc[7, 2:4] = [5.0, 5.0]
    use.iloc[10, 2:4] = [4.5, 3.3]
    use.iat[9, 5] = 0.25
    for filename, sheet, frame in (
        ("SUPPLY_63B.xlsx", "sup20", supply),
        ("USEPB_63B.xlsx", "uspb20", use),
        ("IMPORT_63B.xlsx", "imprt20", imports),
    ):
        _write_xlsx(tmp_path / filename, sheet, frame)
    db = mario.parse_istat(str(tmp_path), year=2020, table="SUT", import_representation="separate")
    from mario.parsers.api import build_database_from_state
    state = mario.parse_istat(str(tmp_path), year=2020, table="SUT",
                             import_representation="separate", model="ModelState")
    rebuilt = build_database_from_state(state)
    assert rebuilt.configuration == db.configuration
    pd.testing.assert_frame_equal(rebuilt.query("IMP_a"), db.query("IMP_a"))
    assert db.configuration.imports_by == "commodity"
    assert db.configuration.import_representation == "separate"
    assert "Importazioni cif" not in db.get_index("Factor of production")
    np.testing.assert_allclose(db.query("U") + db.query("IMP_a").to_numpy(), use.iloc[6:8, 2:4].astype(float))
    np.testing.assert_allclose(db.query("Yc") + db.query("IMP_Y").to_numpy(), use.iloc[6:8, 5:7].astype(float))
    np.testing.assert_allclose(db.query("IMP_a"), [[1, 0], [0, 2]])
    np.testing.assert_allclose(db.query("IMP_Y"), [[2, 3], [4, 5]])
    assert db.query("VY").loc["Tasse meno contributi ai prodotti"].iloc[0] == 0.25
    np.testing.assert_allclose(db.query("imp_a").to_numpy() * db.query("Xa").to_numpy().T, db.query("IMP_a"))
    np.testing.assert_allclose(
        db.query("U").sum().to_numpy() + db.query("Va").sum().to_numpy() + db.query("IMP_a").sum().to_numpy(),
        db.query("Xa").to_numpy().ravel(),
    )
    np.testing.assert_allclose(db.query("S").sum().to_numpy(), db.query("Xc").to_numpy().ravel())
    db.reset_to_coefficients("baseline")
    db.reset_to_flows("baseline")
    combined = db.to_import_representation("factor-accounts", inplace=False)
    restored = combined.to_import_representation("separate", inplace=False)
    for name in ("IMP_a", "IMP_Y", "U", "Yc", "VY"):
        np.testing.assert_allclose(restored.query(name), db.query(name))
    mappings = {
        level: pd.DataFrame({"Aggregation": ["All", "All"]}, index=db.get_index(level))
        for level in ("Activity", "Commodity")
    }
    db.aggregate(io=mappings, levels=["Activity", "Commodity"], calc_all=False)
    assert db.query("IMP_a").shape == (1, 1)
    assert db.query("IMP_a").iloc[0, 0] == pytest.approx(3.0)
    np.testing.assert_allclose(db.query("IMP_Y"), [[6, 8]])
    output = tmp_path / "roundtrip.xlsx"
    db.to_excel(str(output), flows=True, coefficients=False)
    loaded = mario.parse_from_excel(str(output), table="SUT", mode="flows", data_sheet="flows")
    assert loaded.configuration.import_representation == "separate"
    for name in ("S", "U", "Yc", "Va", "VY", "IMP_a", "IMP_Y", "Xa", "Xc"):
        np.testing.assert_allclose(loaded.query(name), db.query(name))


def test_istat_sut_excludes_overlapping_value_added_subtotals():
    use = _istat_use_frame()
    # Include all published decomposition levels in a reduced official layout.
    use.iloc[10:16, 1] = [
        "Redditi da lavoro dipendente", "Altre imposte nette sulla produzione",
        "Ammortamenti", "Risultato netto di gestione", "Risultato lordo di gestione",
        "Valore aggiunto ai prezzi base",
    ]
    use.iloc[10:16, 2:4] = [[2, 3], [1, 1], [1, 2], [4, 5], [5, 7], [8, 11]]
    matrices, indexes, _, _ = build_istat_sut_from_frames(
        _istat_supply_frame(), use, _istat_import_frame(), year=2020,
    )
    assert "Risultato lordo di gestione" not in indexes["f"]["main"]
    assert "Valore aggiunto ai prezzi base" not in indexes["f"]["main"]
    np.testing.assert_allclose(matrices["baseline"]["Va"].sum(), [8.5, 11.7])


def test_istat_import_final_demand_aligns_by_label_and_rejects_missing_categories():
    imports = _istat_import_frame()
    imports.iloc[:, [5, 6]] = imports.iloc[:, [6, 5]].to_numpy()
    matrices, _, _, _ = build_istat_sut_from_frames(
        _istat_supply_frame(), _istat_use_frame(), imports, year=2020,
        import_representation="separate",
    )
    np.testing.assert_allclose(matrices["baseline"]["IMP_Y"], [[2, 3], [4, 5]])
    imports.iat[4, 5] = "Unknown final demand"
    with pytest.raises(WrongFormat, match="final-demand"):
        build_istat_sut_from_frames(
            _istat_supply_frame(), _istat_use_frame(), imports, year=2020,
            import_representation="separate",
        )


@pytest.mark.parametrize("table,valuation,representation", [
    ("IOT", "basic", "separate"), ("SUT", "purchaser", "separate"),
    ("SUT", "basic", "invalid"),
])
def test_istat_rejects_unsupported_import_requests_before_io(table, valuation, representation):
    with pytest.raises(WrongInput):
        mario.parse_istat("missing", year=2022, table=table, valuation=valuation,
                          import_representation=representation)


def test_detect_istat_layouts_require_unambiguous_files(tmp_path):
    workbook_a = tmp_path / "SIMM_TOT_63PxP.xlsx"
    workbook_b = tmp_path / "SIMM_TOT_63PxP_v2.xlsx"
    _write_xlsx(workbook_a, "STOTPP_2020", _istat_iot_frame())
    _write_xlsx(workbook_b, "STOTPP_2020", _istat_iot_frame())

    with pytest.raises(WrongInput):
        detect_istat_iot_layout(tmp_path, year=2020, mode="product")


def test_public_parse_istat_builds_iot_database_from_local_workbook(tmp_path):
    workbook = tmp_path / "SIMM_TOT_63PxP.xlsx"
    _write_xlsx(workbook, "STOTPP_2020", _istat_iot_frame())

    database = mario.parse_istat(str(workbook), year=2020, table="IOT", calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.year == 2020
    assert database.meta.price == "Current prices"
    assert database.get_index(_MASTER_INDEX["r"]) == ["ITA"]


def test_public_parse_istat_builds_sut_database_from_local_directory(tmp_path):
    _write_xlsx(tmp_path / "SUPPLY_63B.xlsx", "sup20", _istat_supply_frame())
    _write_xlsx(tmp_path / "USEPB_63B.xlsx", "uspb20", _istat_use_frame())
    _write_xlsx(tmp_path / "IMPORT_63B.xlsx", "imprt20", _istat_import_frame())

    database = mario.parse_istat(str(tmp_path), year=2020, table="SUT", calc_all=False)

    assert database.table_type == "SUT"
    assert database.meta.year == 2020
    assert sorted(database["baseline"].keys()) == ["EY", "Ea", "Ec", "S", "U", "VY", "Va", "Vc", "Ya", "Yc"]
    assert database.Z.shape == (4, 4)


def test_parse_istat_supports_zip_input(tmp_path):
    archive = tmp_path / "istat_io.zip"
    archive.write_bytes(_minimal_istat_release_zip())

    database = mario.parse_istat(str(archive), year=2020, table="SUT", calc_all=False)

    assert database.table_type == "SUT"
    assert database.meta.year == 2020


def test_detect_istat_sut_requires_matching_triplet(tmp_path):
    _write_xlsx(tmp_path / "SUPPLY_63B.xlsx", "sup20", _istat_supply_frame())
    _write_xlsx(tmp_path / "USEPB_63B.xlsx", "uspb20", _istat_use_frame())

    with pytest.raises(WrongInput):
        detect_istat_sut_layout(tmp_path, year=2020, level="63", price="current", valuation="basic")


def test_public_parse_istat_can_download_release(monkeypatch, tmp_path):
    archive = _minimal_istat_release_zip()
    page_html = '<html><body><a href="/downloads/Tavole_I_O.zip">Tavole</a></body></html>'

    class FakeResponse:
        def __init__(self, *, text=None, content=None):
            self.text = text or ""
            self._content = content or b""
            self.status_code = 200
            self.headers = {}

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=1024 * 1024):
            for index in range(0, len(self._content), chunk_size):
                yield self._content[index : index + chunk_size]

        def close(self):
            return None

    def fake_get(url, **kwargs):
        if "tavole-di-dati" in url:
            return FakeResponse(text=page_html)
        if "Tavole_I_O.zip" in url:
            return FakeResponse(content=archive)
        raise AssertionError(url)

    monkeypatch.setattr("mario.download.requests.get", fake_get)

    database = mario.parse_istat(
        str(tmp_path),
        year=2020,
        table="IOT",
        download=True,
        calc_all=False,
    )

    assert database.table_type == "IOT"
    assert database.meta.year == 2020
