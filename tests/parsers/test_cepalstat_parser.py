from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from mario.log_exc.exceptions import WrongInput
from mario.parsers.entrypoints import parse_cepalstat


def _write_zip_with_workbooks(target: Path, workbooks: dict[str, dict[str, pd.DataFrame]]) -> Path:
    """Write one zip archive containing one or more Excel workbooks."""
    with ZipFile(target, "w") as archive:
        for workbook_name, sheets in workbooks.items():
            tmp_path = target.parent / workbook_name
            with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
                for sheet_name, frame in sheets.items():
                    frame.to_excel(writer, sheet_name=sheet_name, header=False, index=False)
            archive.write(tmp_path, arcname=workbook_name)
            tmp_path.unlink()
    return target


def _cepalstat_sut_frames(*, npish_label: str = "Instituciones sin fines de lucro que sirven a los hogares") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create one compact Colombia-style integrated SUT workbook."""
    offer = pd.DataFrame("", index=range(20), columns=range(80), dtype=object)
    offer.iat[2, 0] = "Cuadro oferta"
    offer.iat[5, 0] = "Año 2020"
    offer.iat[9, 3] = "Márgenes de comercio"
    offer.iat[9, 4] = "Márgenes de transporte"
    offer.iat[9, 5] = "Impuestos y derechos a las importaciones"
    offer.iat[9, 6] = "IVA no deducible"
    offer.iat[9, 7] = "Impuestos a los productos (excepto impuestos a importaciones e IVA no deducible)"
    offer.iat[9, 8] = "Subvenciones a los productos"
    offer.iat[10, 10] = "A01"
    offer.iat[10, 11] = "A02"
    offer.iat[10, 72] = "Total"
    offer.iat[10, 77] = "Ajustes  CIF/FOB sobre importaciones"
    offer.iat[10, 78] = "Bienes"
    offer.iat[10, 79] = "Servicios"
    offer.iat[11, 10] = "Activity 1"
    offer.iat[11, 11] = "Activity 2"

    product_rows = {
        13: ("01", "Product 1", [10.0, 2.0], [1.0, 0.5, 0.2, 0.3, 0.4, -0.1, 0.0, 3.0, 1.0]),
        14: ("02", "Product 2", [4.0, 8.0], [0.5, 0.1, 0.0, 0.2, 0.3, 0.0, 0.2, 1.5, 0.5]),
    }
    for row, (code, label, supply_values, vc_values) in product_rows.items():
        offer.iat[row, 0] = code
        offer.iat[row, 1] = label
        offer.iat[row, 10] = supply_values[0]
        offer.iat[row, 11] = supply_values[1]
        for column, value in zip([3, 4, 5, 6, 7, 8, 77, 78, 79], vc_values):
            offer.iat[row, column] = value

    use = pd.DataFrame("", index=range(100), columns=range(138), dtype=object)
    use.iat[2, 0] = "Cuadro utilización"
    use.iat[5, 0] = "Año 2020"
    use.iat[10, 5] = "A01\nActivity 1"
    use.iat[10, 6] = "A02\nActivity 2"
    use.iat[10, 70] = "Impuestos excepto IVA"
    use.iat[10, 78] = "Hogares"
    use.iat[11, 78] = "A precios de comprador"
    use.iat[10, 86] = npish_label
    use.iat[11, 86] = "A precios de comprador"
    use.iat[10, 94] = "Gobierno"
    use.iat[11, 96] = "Total"
    use.iat[12, 96] = "A precios de comprador"
    use.iat[10, 105] = "Formación bruta de capital fijo"
    use.iat[11, 105] = "A precios de comprador"
    use.iat[10, 113] = "Variación de existencias"
    use.iat[11, 113] = "A precios de comprador"
    use.iat[10, 121] = "Adquisición menos disposición de objetos valiosos"
    use.iat[11, 121] = "A precios de comprador"
    use.iat[10, 131] = "Total"
    use.iat[11, 131] = "A precios de comprador"

    use_rows = {
        14: ("01", "Product 1", [1.0, 3.0], [5.0, 0.5, 1.0, 2.0, 0.2, 0.0, 4.0]),
        15: ("02", "Product 2", [2.0, 1.0], [6.0, 0.0, 1.5, 1.0, 0.1, 0.0, 3.0]),
    }
    for row, (code, label, use_values, fd_values) in use_rows.items():
        use.iat[row, 0] = code
        use.iat[row, 1] = label
        use.iat[row, 5] = use_values[0]
        use.iat[row, 6] = use_values[1]
        for column, value in zip([78, 86, 96, 105, 113, 121, 131], fd_values):
            use.iat[row, column] = value

    use.iat[85, 1] = "Remuneración de los asalariados"
    use.iat[85, 5] = 7.0
    use.iat[85, 6] = 8.0
    use.iat[89, 1] = "Otros impuestos sobre la producción"
    use.iat[89, 5] = 1.0
    use.iat[89, 6] = 0.5
    use.iat[90, 1] = "Otras subvenciones a la producción"
    use.iat[90, 5] = -0.2
    use.iat[90, 6] = -0.1
    use.iat[91, 1] = "Ingreso mixto"
    use.iat[91, 5] = 2.0
    use.iat[91, 6] = 1.0
    use.iat[92, 1] = "Excedente de explotación bruto"
    use.iat[92, 5] = 3.0
    use.iat[92, 6] = 4.0
    return offer, use


def _cepalstat_iot_frame(base_value: float) -> pd.DataFrame:
    """Create one compact direct-matrix IOT workbook."""
    frame = pd.DataFrame("", index=range(14), columns=range(13), dtype=object)
    frame.iat[0, 0] = "Matriz Insumo-Producto de prueba"
    frame.iat[0, 2] = "S01"
    frame.iat[0, 3] = "S02"
    frame.iat[0, 5] = "P31"
    frame.iat[0, 6] = "P31"
    frame.iat[0, 7] = "P31 y P32"
    frame.iat[0, 8] = "P.51"
    frame.iat[0, 9] = "P.52"
    frame.iat[0, 10] = "P.53"
    frame.iat[0, 11] = "P.6"
    frame.iat[1, 2] = "Sector 1"
    frame.iat[1, 3] = "Sector 2"
    frame.iat[1, 4] = "TOTAL DEMANDA INTERMEDIA"
    frame.iat[1, 5] = "GASTO EN CONSUMO FINAL DE LOS HOGARES"
    frame.iat[1, 6] = "GASTO EN CONSUMO FINAL DE LAS ISFLSH"
    frame.iat[1, 7] = "GASTO EN CONSUMO FINAL DEL GOBIERNO"
    frame.iat[1, 8] = "FORMACIÓN BRUTA DE CAPITAL FIJO"
    frame.iat[1, 9] = "VARIACIÓN DE EXISTENCIAS"
    frame.iat[1, 10] = "ADQUISICIONES NETAS DE OBJETOS VALIOSOS"
    frame.iat[1, 11] = "EXPORTACIONES"

    frame.iloc[2, :12] = ["S01", "Sector 1", base_value, 2.0, 0.0, 5.0, 0.5, 1.0, 2.0, 0.1, 0.0, 3.0]
    frame.iloc[3, :12] = ["S02", "Sector 2", 4.0, base_value, 0.0, 6.0, 0.0, 1.5, 1.0, 0.2, 0.0, 4.0]
    frame.iat[4, 1] = "TOTAL INSUMOS INTERMEDIOS (a precios básicos)"
    frame.iat[5, 1] = "Impuestos Netos sobre los productos"
    frame.iat[5, 2] = 1.0
    frame.iat[5, 3] = 2.0
    frame.iat[6, 1] = "TOTAL INSUMOS INTERMEDIOS (a precios de comprador)"
    frame.iat[7, 1] = "VALOR AGREGADO BRUTO TOTAL/PIB"
    frame.iat[8, 0] = "D.1"
    frame.iat[8, 1] = "Remuneración de los asalariados"
    frame.iat[8, 2] = 7.0
    frame.iat[8, 3] = 8.0
    frame.iat[9, 0] = "D.29"
    frame.iat[9, 1] = "Otros impuestos sobre la producción "
    frame.iat[9, 2] = 1.0
    frame.iat[9, 3] = 0.5
    frame.iat[10, 0] = "D.39"
    frame.iat[10, 1] = "Otras subvenciones a la producción (-)"
    frame.iat[10, 2] = -0.2
    frame.iat[10, 3] = -0.1
    frame.iat[11, 0] = "B.2b"
    frame.iat[11, 1] = "Excedente de explotación, bruto"
    frame.iat[11, 2] = 2.0
    frame.iat[11, 3] = 3.0
    frame.iat[12, 0] = "B.3b"
    frame.iat[12, 1] = "Ingreso mixto, bruto"
    frame.iat[12, 2] = 1.5
    frame.iat[12, 3] = 1.0
    frame.iat[13, 1] = "PRODUCCIÓN TOTAL"
    return frame


def _cepalstat_iot_cri_like_frame() -> pd.DataFrame:
    """Create one Costa-Rica-style direct IOT sheet with stacked headers."""
    frame = pd.DataFrame("", index=range(18), columns=range(13), dtype=object)
    frame.iat[8, 2] = "Demanda Intermedia"
    frame.iat[8, 4] = "Total de Demanda Intermedia"
    frame.iat[8, 5] = "Consumo Privado"
    frame.iat[8, 6] = "NPISH"
    frame.iat[8, 7] = "Gobierno"
    frame.iat[8, 8] = "Formación bruta de capital fijo"
    frame.iat[8, 9] = "Variación de existencias"
    frame.iat[8, 10] = "Objetos valiosos"
    frame.iat[8, 11] = "Exportaciones"
    frame.iat[9, 2] = "NP001"
    frame.iat[9, 3] = "NP002"
    frame.iat[10, 2] = "Product 1"
    frame.iat[10, 3] = "Product 2"
    frame.iloc[11, :12] = ["NP001", "Product 1", 10.0, 2.0, 12.0, 5.0, 0.5, 1.0, 2.0, 0.1, 0.0, 3.0]
    frame.iloc[12, :12] = ["NP002", "Product 2", 4.0, 8.0, 12.0, 6.0, 0.0, 1.5, 1.0, 0.2, 0.0, 4.0]
    frame.iat[14, 0] = "Valor Agregado Bruto Economía Total"
    frame.iat[14, 2] = 7.0
    frame.iat[14, 3] = 8.0
    return frame


def _cepalstat_iot_ven_like_frame() -> pd.DataFrame:
    """Create one Venezuela-style direct IOT sheet with sparse left identifiers."""
    frame = pd.DataFrame("", index=range(22), columns=range(15), dtype=object)
    frame.iat[6, 4] = "Consumo intermedio a precios básicos"
    frame.iat[6, 6] = "Total Demanda Intermedia (a precios básicos)"
    frame.iat[6, 7] = "Exportaciones"
    frame.iat[6, 8] = "Consumo Privado"
    frame.iat[6, 9] = "ISFLSH"
    frame.iat[6, 10] = "Gobierno"
    frame.iat[6, 11] = "Formación bruta de capital fijo"
    frame.iat[6, 12] = "Variación de existencias"
    frame.iat[6, 13] = "Objetos valiosos"
    frame.iat[7, 4] = "001"
    frame.iat[7, 5] = "017"
    frame.iat[8, 4] = "Product 1"
    frame.iat[8, 5] = "Product 2"
    frame.iloc[10, :14] = ["", "001", "", "Product 1", 10.0, 2.0, 12.0, 3.0, 5.0, 0.5, 1.0, 2.0, 0.1, 0.0]
    frame.iloc[11, :14] = ["", "017", "", "Product 2", 4.0, 8.0, 12.0, 4.0, 6.0, 0.0, 1.5, 1.0, 0.2, 0.0]
    frame.iat[13, 0] = "D.1"
    frame.iat[13, 3] = "Remuneración de los asalariados"
    frame.iat[13, 4] = 7.0
    frame.iat[13, 5] = 8.0
    frame.iat[14, 0] = "B.2b"
    frame.iat[14, 3] = "Excedente de explotación, bruto"
    frame.iat[14, 4] = 2.0
    frame.iat[14, 5] = 3.0
    return frame


def _arg_sut_workbook() -> dict[str, pd.DataFrame]:
    """Create one compact Argentina-style two-sheet SUT workbook."""
    offer = pd.DataFrame("", index=range(20), columns=range(12), dtype=object)
    offer.iat[3, 2] = "Activity 1"
    offer.iat[3, 3] = "Activity 2"
    offer.iat[4, 4] = "OPB"
    offer.iat[4, 5] = "IMPO"
    offer.iat[4, 6] = "Ajuste CIF/FOB"
    offer.iat[4, 7] = "DI"
    offer.iat[4, 8] = "IP"
    offer.iat[4, 9] = "Mg D"
    offer.iat[4, 10] = "IVA"
    offer.iat[4, 11] = "CSCD"
    offer.iloc[5, :12] = ["Product 1", "P1", 10.0, 2.0, 0.0, 3.0, 0.5, 0.2, 0.4, 0.1, 0.3, 0.0]
    offer.iloc[6, :12] = ["Product 2", "P2", 4.0, 8.0, 0.0, 1.5, 0.2, 0.1, 0.3, 0.0, 0.2, 0.1]

    use = pd.DataFrame("", index=range(24), columns=range(12), dtype=object)
    use.iat[4, 5] = "CH"
    use.iat[4, 6] = "CP"
    use.iat[4, 7] = "EX"
    use.iat[4, 8] = "Fbc Fijo"
    use.iat[4, 9] = "OV"
    use.iat[4, 10] = "Productos terminados"
    use.iat[4, 11] = "Trabajos en curso"
    use.iloc[5, :12] = ["Product 1", "P1", 1.0, 3.0, 0.0, 5.0, 1.0, 4.0, 2.0, 0.0, 0.2, 0.1]
    use.iloc[6, :12] = ["Product 2", "P2", 2.0, 1.0, 0.0, 6.0, 1.5, 3.0, 1.0, 0.0, 0.1, 0.0]
    use.iat[20, 0] = "Valor Agregado Bruto pb"
    use.iat[20, 2] = 7.0
    use.iat[20, 3] = 8.0
    return {"Mat_Of_pc_2020": offer, "Mat_Ut_pc_2020": use}


def _bra_sut_workbooks() -> dict[str, dict[str, pd.DataFrame]]:
    """Create one compact Brazil-style split SUT bundle."""
    producao = pd.DataFrame("", index=range(10), columns=range(5), dtype=object)
    producao.iat[3, 2] = "Activity 1"
    producao.iat[3, 3] = "Activity 2"
    producao.iloc[5, :5] = ["P1", "Product 1", 10.0, 2.0, 0.0]
    producao.iloc[6, :5] = ["P2", "Product 2", 4.0, 8.0, 0.0]

    oferta = pd.DataFrame("", index=range(10), columns=range(9), dtype=object)
    oferta.iloc[5, :9] = ["P1", "Product 1", 0.0, 1.0, 0.5, 0.2, 0.1, 0.3, -0.1]
    oferta.iloc[6, :9] = ["P2", "Product 2", 0.0, 0.5, 0.1, 0.0, 0.2, 0.3, 0.0]

    importacao = pd.DataFrame("", index=range(10), columns=range(4), dtype=object)
    importacao.iloc[5, :4] = ["P1", 0.2, 3.0, 1.0]
    importacao.iloc[6, :4] = ["P2", 0.1, 1.5, 0.5]

    ci = pd.DataFrame("", index=range(10), columns=range(5), dtype=object)
    ci.iloc[5, :5] = ["P1", "Product 1", 1.0, 3.0, 0.0]
    ci.iloc[6, :5] = ["P2", "Product 2", 2.0, 1.0, 0.0]

    demanda = pd.DataFrame("", index=range(10), columns=range(9), dtype=object)
    demanda.iloc[5, :9] = ["P1", "Product 1", 1.0, 0.5, 1.0, 0.2, 5.0, 2.0, 0.3]
    demanda.iloc[6, :9] = ["P2", "Product 2", 2.0, 0.5, 1.5, 0.1, 6.0, 1.0, 0.2]

    va = pd.DataFrame("", index=range(16), columns=range(5), dtype=object)
    va.iloc[6, 2:4] = [7.0, 8.0]
    va.iloc[12, 2:4] = [2.0, 3.0]
    va.iloc[15, 2:4] = [1.0, 0.5]

    return {
        "BRA_COU_2020_PRECIOSCORRIENTES_2x2_OFERTA.xlsx": {
            "oferta": oferta,
            "producao": producao,
            "importacao": importacao,
        },
        "BRA_COU_2020_PRECIOSCORRIENTES_2x2_DEMANDA.xlsx": {
            "CI": ci,
            "demanda": demanda,
            "VA": va,
        },
    }


def _chi_sut_workbook() -> dict[str, pd.DataFrame]:
    """Create one compact Chile-style multi-cuadro SUT workbook."""
    production = pd.DataFrame("", index=range(20), columns=range(4), dtype=object)
    production.iat[0, 0] = "Matriz de producción"
    production.iat[10, 2] = "A1"
    production.iat[10, 3] = "A2"
    production.iloc[13, :4] = ["", "P1", 10.0, 2.0]
    production.iloc[14, :4] = ["", "P2", 4.0, 8.0]

    intermediate = pd.DataFrame("", index=range(20), columns=range(4), dtype=object)
    intermediate.iloc[13, :4] = ["", "P1", 1.0, 3.0]
    intermediate.iloc[14, :4] = ["", "P2", 2.0, 1.0]

    final_use = pd.DataFrame("", index=range(20), columns=range(10), dtype=object)
    final_use.iloc[13, :10] = ["", "P1", "", "", 5.0, 0.5, 1.0, 2.0, 0.2, 4.0]
    final_use.iloc[14, :10] = ["", "P2", "", "", 6.0, 0.0, 1.5, 1.0, 0.1, 3.0]

    value_added = pd.DataFrame("", index=range(10), columns=range(4), dtype=object)
    value_added.iat[0, 0] = "Cuadrante de valor agregado"
    value_added.iat[3, 1] = "Remuneraciones"
    value_added.iat[3, 2] = 7.0
    value_added.iat[3, 3] = 8.0
    value_added.iat[4, 1] = "Excedente bruto de explotación"
    value_added.iat[4, 2] = 2.0
    value_added.iat[4, 3] = 3.0
    value_added.iat[5, 1] = "Impuestos netos"
    value_added.iat[5, 2] = 1.0
    value_added.iat[5, 3] = 0.5

    offer_total = pd.DataFrame("", index=range(20), columns=range(10), dtype=object)
    offer_total.iloc[14, :10] = ["", "P1", "", 3.0, "", 0.2, 0.1, "", 0.3, 0.4]
    offer_total.iloc[15, :10] = ["", "P2", "", 1.5, "", 0.1, 0.0, "", 0.2, 0.3]
    return {"1": production, "5": intermediate, "6": final_use, "23": value_added, "2": offer_total}


def _arg_iot_workbook() -> dict[str, pd.DataFrame]:
    """Create one compact Argentina-style symmetric IOT workbook."""
    frame = pd.DataFrame("", index=range(14), columns=range(12), dtype=object)
    frame.iat[5, 4] = "DEMANDA INTERMEDIA"
    frame.iat[5, 5] = "EXPORTACIONES"
    frame.iat[5, 6] = "CONSUMO FINAL"
    frame.iat[6, 6] = "GASTO DE LOS HOGARES"
    frame.iat[6, 7] = "GOBIERNO"
    frame.iat[5, 8] = "FORMACIÓN BRUTA DE CAPITAL"
    frame.iat[6, 8] = "FORMACIÓN BRUTA DE CAPITAL FIJO"
    frame.iat[6, 9] = "VARIACIÓN DE EXISTENCIAS"
    frame.iloc[8, :10] = ["S1", "Sector 1", 10.0, 2.0, 0.0, 4.0, 5.0, 1.0, 2.0, 0.1]
    frame.iloc[9, :10] = ["S2", "Sector 2", 3.0, 8.0, 0.0, 3.0, 6.0, 1.5, 1.0, 0.2]
    frame.iat[11, 0] = "D.1"
    frame.iat[11, 1] = "Remuneración de los asalariados"
    frame.iat[11, 2] = 7.0
    frame.iat[11, 3] = 8.0
    frame.iat[12, 1] = "Valor agregado bruto"
    frame.iat[12, 2] = 10.0
    frame.iat[12, 3] = 11.0
    return {"Cuadro 12": frame}


def _bra_iot_workbook() -> dict[str, dict[str, pd.DataFrame]]:
    """Create one compact Brazil-style demand-basic IOT workbook without explicit factor rows."""
    frame = pd.DataFrame("", index=range(10), columns=range(13), dtype=object)
    frame.iat[2, 6] = "Demanda final"
    frame.iat[3, 3] = "01"
    frame.iat[3, 4] = "02"
    frame.iat[3, 5] = "Total"
    frame.iat[3, 6] = "Exportação"
    frame.iat[3, 7] = "Consumo da administração pública"
    frame.iat[3, 8] = "Consumo das ISFLSF"
    frame.iat[3, 9] = "Consumo das famílias"
    frame.iat[3, 10] = "Formação bruta de capital fixo"
    frame.iat[3, 11] = "Variação de estoque"
    frame.iat[3, 12] = "Demanda final"
    frame.iloc[5, :13] = ["01", "Sector 1", 20.0, 10.0, 2.0, 0.0, 4.0, 1.0, 0.5, 5.0, 2.0, 0.5, 13.0]
    frame.iloc[6, :13] = ["02", "Sector 2", 15.0, 3.0, 6.0, 0.0, 3.0, 1.5, 0.2, 2.0, 1.0, 0.3, 8.0]
    return {"BRA_MIP_2020_2x2_DEMANDA_BASICO.xlsx": {"3": frame}}


def _chi_iot_workbook() -> dict[str, pd.DataFrame]:
    """Create one compact Chile-style matrix IOT workbook."""
    frame = pd.DataFrame("", index=range(36), columns=range(18), dtype=object)
    frame.iat[0, 0] = "Matriz de insumo-producto"
    frame.iat[7, 17] = "Exportaciones"
    frame.iat[7, 13] = "Formación bruta de capital fijo"
    frame.iat[7, 11] = "Consumo de gobierno"
    frame.iat[7, 9] = "Consumo  de IPSFL"
    frame.iat[7, 7] = "Consumo de hogares"
    frame.iat[8, 2] = "1"
    frame.iat[8, 3] = "2"
    frame.iat[8, 5] = "Total"
    frame.iloc[11, :18] = ["", "S1", 10.0, 2.0, "", 0.0, "", 5.0, "", 0.5, "", 1.0, "", 2.0, "", 0.2, "", 4.0]
    frame.iloc[12, :18] = ["", "S2", 3.0, 8.0, "", 0.0, "", 6.0, "", 0.0, "", 1.5, "", 1.0, "", 0.1, "", 3.0]
    frame.iat[26, 1] = "Valor agregado bruto"
    frame.iat[26, 2] = 10.0
    frame.iat[26, 3] = 11.0
    frame.iat[27, 1] = "Remuneraciones de asalariados"
    frame.iat[27, 2] = 7.0
    frame.iat[27, 3] = 8.0
    frame.iat[28, 1] = "Excedente bruto de explotación"
    frame.iat[28, 2] = 2.0
    frame.iat[28, 3] = 3.0
    return {"1": frame}


def test_parse_cepalstat_integrated_sut_bundle(tmp_path: Path):
    offer, use = _cepalstat_sut_frames()
    archive = _write_zip_with_workbooks(
        tmp_path / "COL_COU_2020.zip",
        {"COL_COU_2020.xlsx": {"Cuadro 1": offer, "Cuadro 2": use}},
    )

    database = parse_cepalstat(str(archive), table="SUT", calc_all=False)

    assert database.table_type == "SUT"
    assert database.meta.year == 2020
    assert database.meta.name == "CEPALSTAT SUT COL 2020"
    assert set(database["baseline"]) == {"S", "U", "Ya", "Yc", "Va", "Vc", "Ea", "Ec", "EY"}
    assert database.S.shape == (2, 2)
    assert database.U.shape == (2, 2)
    assert database.Yc.shape == (2, 7)
    assert database.Va.shape == (14, 2)
    assert database.Vc.shape == (14, 2)
    assert float(database.S.iloc[0, 0]) == 10.0
    assert float(database.U.iloc[1, 0]) == 2.0
    assert float(database.Va.iloc[0, 0]) == 7.0


def test_parse_cepalstat_integrated_sut_bundle_accepts_npish_alias(tmp_path: Path):
    offer, use = _cepalstat_sut_frames(npish_label="ISFLH1")
    archive = _write_zip_with_workbooks(
        tmp_path / "COL_COU_2020.zip",
        {"COL_COU_2020_corrientes.xlsx": {"Cuadro 37": offer, "Cuadro 38": use}},
    )

    database = parse_cepalstat(str(archive), table="SUT", year=2020, calc_all=False)

    assert database.table_type == "SUT"
    assert database.meta.year == 2020
    assert float(database.Yc.iloc[0, 1]) == 0.5


def test_parse_cepalstat_integrated_sut_bundle_reports_missing_year(tmp_path: Path):
    offer, use = _cepalstat_sut_frames()
    archive = _write_zip_with_workbooks(
        tmp_path / "COL_COU_2020.zip",
        {"COL_COU_2020.xlsx": {"Cuadro 1": offer, "Cuadro 2": use}},
    )

    with pytest.raises(WrongInput, match=r"does not contain year 2021.*Available years: \[2020\]"):
        parse_cepalstat(str(archive), table="SUT", year=2021, calc_all=False)


def test_parse_cepalstat_direct_iot_bundle_prefers_requested_mode(tmp_path: Path):
    pxp_frame = _cepalstat_iot_frame(10.0)
    axa_frame = _cepalstat_iot_frame(99.0)
    archive = _write_zip_with_workbooks(
        tmp_path / "DOM_MIP_2012.zip",
        {
            "DOM_MIP_2012_24x24_PxP.xlsx": {"MIP": pxp_frame},
            "DOM_MIP_2012_24x24_AxA.xlsx": {"MIP": axa_frame},
        },
    )

    database = parse_cepalstat(str(archive), table="IOT", iot_mode="pxp", calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.year == 2012
    assert database.meta.name == "CEPALSTAT IOT DOM 2012 PXP"
    assert set(database["baseline"]) == {"Z", "Y", "V", "E", "EY"}
    assert database.Z.shape == (2, 2)
    assert database.Y.shape == (2, 7)
    assert database.V.shape == (7, 2)
    assert float(database.Z.iloc[0, 0]) == 10.0
    assert float(database.Y.iloc[0, 0]) == 5.0


def test_parse_cepalstat_argentina_two_sheet_sut_uses_vab_fallback(tmp_path: Path):
    archive = _write_zip_with_workbooks(
        tmp_path / "ARG_COU_2020.zip",
        {"ARG_COU_2020.xlsx": _arg_sut_workbook()},
    )

    database = parse_cepalstat(str(archive), table="SUT", year=2020, calc_all=False)

    assert database.meta.name == "CEPALSTAT SUT ARG 2020"
    assert database.S.shape == (2, 2)
    assert database.Va.shape[0] == 8
    assert "Value added at basic prices" in database.get_index("Factor of production")


def test_parse_cepalstat_brazil_split_sut_bundle(tmp_path: Path):
    archive = _write_zip_with_workbooks(tmp_path / "BRA_COU_2020.zip", _bra_sut_workbooks())

    database = parse_cepalstat(str(archive), table="SUT", year=2020, calc_all=False)

    assert database.meta.name == "CEPALSTAT SUT BRA 2020"
    assert database.S.shape == (2, 2)
    assert float(database.Yc.iloc[0, 6]) == 1.5


def test_parse_cepalstat_chile_multicuadro_sut(tmp_path: Path):
    archive = _write_zip_with_workbooks(
        tmp_path / "CHI_COU_2020.zip",
        {"CHI_COU_2020.xlsx": _chi_sut_workbook()},
    )

    database = parse_cepalstat(str(archive), table="SUT", year=2020, calc_all=False)

    assert database.meta.name == "CEPALSTAT SUT CHI 2020"
    assert database.S.shape == (2, 2)
    assert float(database.Va.iloc[0, 0]) == 7.0


def test_parse_cepalstat_argentina_symmetric_iot(tmp_path: Path):
    archive = _write_zip_with_workbooks(
        tmp_path / "ARG_MIP_2020.zip",
        {"ARG_MIP_2020_SIMETRICA.xlsx": _arg_iot_workbook()},
    )

    database = parse_cepalstat(str(archive), table="IOT", calc_all=False)

    assert database.meta.name == "CEPALSTAT IOT ARG 2020 AUTO"
    assert database.Z.shape == (2, 2)
    assert "Compensation of employees" in database.get_index("Factor of production")


def test_parse_cepalstat_brazil_iot_builds_residual_value_added(tmp_path: Path):
    archive = _write_zip_with_workbooks(tmp_path / "BRA_MIP_2020.zip", _bra_iot_workbook())

    database = parse_cepalstat(str(archive), table="IOT", calc_all=False)

    assert database.meta.name == "CEPALSTAT IOT BRA 2020 AUTO"
    assert database.Z.shape == (2, 2)
    assert list(database.get_index("Factor of production")) == ["Value added at basic prices"]


def test_parse_cepalstat_chile_iot_workbook(tmp_path: Path):
    archive = _write_zip_with_workbooks(
        tmp_path / "CHI_MIP_2020.zip",
        {"CHI_MIP_2020.xlsx": _chi_iot_workbook()},
    )

    database = parse_cepalstat(str(archive), table="IOT", calc_all=False)

    assert database.meta.name == "CEPALSTAT IOT CHI 2020 AXA"
    assert database.Z.shape == (2, 2)
    assert database.V.shape == (3, 2)


def test_parse_cepalstat_direct_iot_handles_cri_like_stacked_headers(tmp_path: Path):
    archive = _write_zip_with_workbooks(
        tmp_path / "CRI_MIP_2017.zip",
        {"CRI_MIP_2017_PRECIOSCORRIENTES_184x184_PxP.xlsx": {"MIP 2017": _cepalstat_iot_cri_like_frame()}},
    )

    database = parse_cepalstat(str(archive), table="IOT", iot_mode="pxp", calc_all=False)

    assert database.meta.name == "CEPALSTAT IOT CRI 2017 PXP"
    assert database.Z.shape == (2, 2)
    assert list(database.get_index("Factor of production")) == ["Value added at basic prices"]


def test_parse_cepalstat_direct_iot_handles_ven_like_sparse_identifiers(tmp_path: Path):
    archive = _write_zip_with_workbooks(
        tmp_path / "VEN_MIP_1997.zip",
        {"VEN_MIP_1997_121x121_PxP.xlsx": {"MATRIZ U SIMETRICA (121x121)(px": _cepalstat_iot_ven_like_frame()}},
    )

    database = parse_cepalstat(str(archive), table="IOT", iot_mode="pxp", calc_all=False)

    assert database.meta.name == "CEPALSTAT IOT VEN 1997 PXP"
    assert database.Z.shape == (2, 2)
    assert "Compensation of employees" in database.get_index("Factor of production")
