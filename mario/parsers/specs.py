"""Parsing and import specifications."""

from __future__ import annotations

from mario.model.conventions import (
    COEFFICIENTS,
    FLOWS,
    HYBRID,
    IOT,
    MONETARY,
    SUT,
    _MASTER_INDEX,
)


INPUT_OPTIONS = {
    "table": [SUT, IOT],
    "mode": [FLOWS, COEFFICIENTS],
    "unit": [MONETARY, HYBRID],
}


GTAP_VARIANTS = ("power",)
GTAP_LAYOUTS = ("MRIO",)
GTAP_INPUT_FORMATS = ("auto", "csv", "gdx")
GTAP_MONETARY_UNIT = "M USD"
GTAP_POWER_MRIO_SOURCE = "GTAP Power MRIO local bundle"
GTAP_POWER_MRIO_CSV_FILES = {
    "SRCxDST": "GSDFSRCxDST.csv",
    "V - Tax": "GSDFXTAX.csv",
    "V": "GSDF.csv",
    "E+EY - Emissions": "GSDFEMI.csv",
    "E+EY - Energy": "GSDFNRG.csv",
}
GTAP_POWER_MRIO_GDX_FILES = {
    "SRCxDST": "GSDFSRCxDST.gdx",
    "V": "GSDF.gdx",
    "V-Tax": "GSDFXTAX.gdx",
    "Emissions": "GSDFEMI.gdx",
    "Energy": "GSDFNRG.gdx",
}


FIGARO_SUPPLY_URL = (
    "https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/"
    "library/651e74b4-ff35-445b-9427-5b3ed9ec5ca9?p=1&n=10&sort=name_ASC"
)
FIGARO_USE_URL = (
    "https://circabc.europa.eu/ui/group/cec66924-a924-4f91-a0ef-600a0531e3ba/"
    "library/093bfbed-142f-47c8-a151-d9fd3f95a507?p=1&n=10&sort=name_ASC"
)
FIGARO_SOURCE = (
    "FIGARO database via CIRCABC "
    f"(supply: {FIGARO_SUPPLY_URL}; use: {FIGARO_USE_URL})"
)
FIGARO_FACTOR_UNIT = "nominal million euros"
FIGARO_SATELLITE_UNIT = "None"
FIGARO_EXTENSION_PLACEHOLDER = "-"
FIGARO_IOT_MODES = ("auto", "product", "industry")


ADB_SOURCE_URL = "https://kidb.adb.org/globalization/current"
ADB_SOURCE = f"Asian Development Bank MRIO Excel workbooks via {ADB_SOURCE_URL}"
ADB_MONETARY_UNIT = "millions of US$"
ADB_SATELLITE_UNIT = "None"
ADB_SATELLITE_PLACEHOLDER = "-"
ADB_FINAL_DEMAND_CODES = ("F1", "F2", "F3", "F4", "F5")
ADB_FINAL_DEMAND_LABELS = {
    "F1": "Households",
    "F2": "NPISH",
    "F3": "Government",
    "F4": "Gross fixed capital formation",
    "F5": "Changes in inventories and valuables",
}
ADB_FACTOR_ROWS = ("r99", "r61", "r62", "r63", "r64", "trs")
ADB_FACTOR_LABELS = {
    "r99": "Taxes less subsidies on products",
    "r61": "CIF / FOB adjustments",
    "r62": "Direct purchases abroad by residents",
    "r63": "Purchases on the domestic territory by non-residents",
    "r64": "Value added at basic prices",
    "trs": "International Transport Margins",
}


EXIOBASE_HYBRID_3318_ZENODO_URL = "https://doi.org/10.5281/zenodo.7244919"
EXIOBASE_HYBRID_3318_RECORD_ID = "7244919"
EXIOBASE_HYBRID_3318_SOURCE = (
    "EXIOBASE HYBRID v3.3.18 via Zenodo "
    f"({EXIOBASE_HYBRID_3318_ZENODO_URL})"
)
EXIOBASE_MONETARY_ZENODO_RECORDS = {
    "3.10.1": {
        "record_id": "18937492",
        "doi": "https://doi.org/10.5281/zenodo.18937492",
        "tables": ("IOT",),
    },
    "3.9.6": {
        "record_id": "15689391",
        "doi": "https://doi.org/10.5281/zenodo.15689391",
        "tables": ("IOT",),
    },
    "3.9.5": {
        "record_id": "14869924",
        "doi": "https://doi.org/10.5281/zenodo.14869924",
        "tables": ("IOT",),
    },
    "3.9.4": {
        "record_id": "14614930",
        "doi": "https://doi.org/10.5281/zenodo.14614930",
        "tables": ("IOT",),
    },
    "3.8.2": {
        "record_id": "5589597",
        "doi": "https://doi.org/10.5281/zenodo.5589597",
        "tables": ("IOT", "SUT"),
    },
}


EMERGING_V1_CONCEPT_DOI = "https://doi.org/10.5281/zenodo.14258421"
EMERGING_V1_ZENODO_URL = "https://doi.org/10.5281/zenodo.14258422"
EMERGING_V1_RECORD_ID = "14258422"
EMERGING_ZENODO_URL = "https://doi.org/10.5281/zenodo.14258422"
EMERGING_SOURCE = (
    "EMERGING V2.5 MATLAB bundle via Zenodo "
    f"({EMERGING_ZENODO_URL})"
)
EMERGING_PAPER_CITATION = (
    "Huo, J., Chen, P., Hubacek, K., Zheng, H., Meng, J., & Guan, D. (2022). "
    "Full-scale, near real-time multi-regional input-output table for the global "
    "emerging economies (EMERGING). Journal of Industrial Ecology, 26, 1218–1232. "
    "https://doi.org/10.1111/jiec.13264"
)
EMERGING_MONETARY_UNIT = "current million US$"
EMERGING_SATELLITE_UNIT = "Mt CO2eq"
EMERGING_SATELLITE_PLACEHOLDER = "-"
EMERGING_FACTOR_LABEL = "Value added at basic prices"
EMERGING_CO2_LABELS = (
    "Coal",
    "Natural gas",
    "Oil products",
    "Crude, NGL, Ref Feeds.",
    "Other",
    "Oil shale & oil sands",
    "Peat & Peat products",
)


OECD_ICIO_SOURCE_URL = "https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html"
OECD_ICIO_SOURCE = (
    "OECD Inter-Country Input-Output tables page "
    f"(2025 edition): {OECD_ICIO_SOURCE_URL}"
)
OECD_ICIO_FINAL_DEMAND_CODES = ("HFCE", "NPISH", "GGFC", "GFCF", "INVNT", "DPABR", "DIRP")
OECD_ICIO_FACTOR_ROWS = ("TLS", "VA")
OECD_ICIO_FACTOR_UNIT = "nominal million USD"
OECD_ICIO_SATELLITE_UNIT = "None"
OECD_ICIO_SATELLITE_PLACEHOLDER = "-"

GLORIA_SOURCE = "GLORIA MRIO release local files"
GLORIA_MONETARY_UNIT = "current 000 US$"
GLORIA_SATELLITE_UNIT = "None"
GLORIA_SATELLITE_PLACEHOLDER = "-"
GLORIA_VALUATION_MARKUPS = {
    1: "Basic prices",
    2: "Trade margins",
    3: "Transport margins",
    4: "Taxes on products",
    5: "Subsidies on products",
}


ISTAT_IO_RELEASE_TAG_URL = "https://www.istat.it/tag/sistema-input-output/"
ISTAT_IO_RELEASE_PAGES = {
    "2020-2022": "https://www.istat.it/tavole-di-dati/il-sistema-di-tavole-input-output-anni-2020-2022/",
    "2015-2020": "https://www.istat.it/tavole-di-dati/il-sistema-di-tavole-input-output-anni-2015-2020/",
}
ISTAT_IO_SOURCE = (
    "ISTAT sistema di tavole input-output via official release pages "
    f"({ISTAT_IO_RELEASE_TAG_URL})"
)
ISTAT_MONETARY_UNIT = "Milioni di euro"
ISTAT_SATELLITE_UNIT = "None"
ISTAT_SATELLITE_PLACEHOLDER = "-"
ISTAT_IOT_MODES = ("product", "industry")
ISTAT_SUT_LEVELS = ("63", "20")
ISTAT_SUT_PRICES = ("current", "pyp")
ISTAT_SUT_VALUATIONS = ("basic", "purchaser")
ISTAT_IOT_FINAL_DEMAND_EXCLUDE = (
    "Spesa per consumi finali",
    "Variazione delle scorte e oggetti di valore",
    "Investimenti lordi",
)
ISTAT_SUT_FINAL_DEMAND_EXCLUDE = ISTAT_IOT_FINAL_DEMAND_EXCLUDE
ISTAT_FINAL_DEMAND_TOTAL_PREFIX = "Totale impieghi"
ISTAT_IOT_FACTOR_EXCLUDE = (
    "Consumi intermedi ai prezzi base",
    "Totale consumi intermedi/Impieghi finali ai prezzi di acquisto",
    "Produzione ai prezzi base",
    "Totale risorse ai prezzi base",
)
ISTAT_SUT_FACTOR_EXCLUDE = (
    "Consumi intermedi ai prezzi base",
    "Totale consumi intermedi/Impieghi finali ai prezzi di acquisto",
    "Produzione ai prezzi base",
    "Investimenti fissi lordi",
    "Stock di capitale fisso",
    "Ore lavorate (migliaia)",
)
ISTAT_IMPORT_FACTOR_LABEL = "Importazioni cif"


STATCAN_WDS_BASE_URL = "https://www150.statcan.gc.ca/t1/wds/rest"
STATCAN_WDS_USER_GUIDE_URL = "https://www.statcan.gc.ca/en/developers/wds/user-guide"
STATCAN_SDMX_USER_GUIDE_URL = "https://www.statcan.gc.ca/en/developers/sdmx/user-guide"
STATCAN_SOURCE = (
    "Statistics Canada WDS full-table API "
    f"({STATCAN_WDS_USER_GUIDE_URL}; SDMX guide: {STATCAN_SDMX_USER_GUIDE_URL})"
)
STATCAN_SATELLITE_PLACEHOLDER = "-"
STATCAN_SATELLITE_UNIT = "None"
STATCAN_VALUATIONS = {
    "basic": "Basic price",
    "purchaser": "Purchaser price",
}
STATCAN_ACTIVITY_CODE_PREFIXES = ("BS", "NP", "GS")
STATCAN_FINAL_DEMAND_CODE_PREFIXES = ("PEC", "CEN", "CEG", "CO", "ME", "IP", "INV", "INTEX", "INTRX")
STATCAN_IMPORT_CODE_PREFIXES = ("INTIM", "IPTIM")
STATCAN_TABLES = {
    "SUT": {
        "summary": {
            "pid": "36100438",
            "title": "Supply and use tables, summary level, provincial and territorial",
            "catalogue_url": "https://www150.statcan.gc.ca/n1/en/catalogue/36100438",
        },
        "detail": {
            "pid": "36100478",
            "title": "Supply and use tables, detail level, provincial and territorial",
            "catalogue_url": "https://www150.statcan.gc.ca/n1/en/catalogue/36100478",
        },
        "link1997": {
            "pid": "36100479",
            "title": "Supply and use tables, link-1997 level",
            "catalogue_url": "https://www150.statcan.gc.ca/n1/en/catalogue/36100479",
        },
    },
    "IOT": {
        "summary": {
            "pid": "36100084",
            "title": "Symmetric input-output tables, summary level",
            "catalogue_url": "https://www150.statcan.gc.ca/n1/en/catalogue/36100084",
        },
        "detail": {
            "pid": "36100001",
            "title": "Symmetric input-output tables, detail level",
            "catalogue_url": "https://www150.statcan.gc.ca/n1/en/catalogue/36100001",
        },
    },
}

WIOD_2016_RELEASE_URL = "https://www.rug.nl/ggdc/valuechain/wiod/wiod-2016-release?lang=en"
WIOD_IOT_FILE_URL = "https://dataverse.nl/api/access/datafile/199104"
WIOD_SUT_FILE_URL = "https://dataverse.nl/api/access/datafile/199100"
WIOD_SOURCE = (
    "WIOD 2016 Release Excel workbook via GGDC/University of Groningen "
    f"({WIOD_2016_RELEASE_URL})"
)
WIOD_MONETARY_UNIT = "millions of US$"
WIOD_SATELLITE_UNIT = "None"
WIOD_SATELLITE_PLACEHOLDER = "-"
WIOD_FINAL_DEMAND_CODES = ("CONS_h", "CONS_np", "CONS_g", "GFCF", "INVEN")
WIOD_SUT_FINAL_DEMAND_CODES = ("CONS_h", "CONS_np", "CONS_g", "GFCF", "INVEN", "EXP")
WIOD_SUT_USE_TOTAL_COLUMNS = ("INTC", "CONS", "GCF", "FU_bas", "USE_bas", "ReEXP", "IntTTM")
WIOD_SUT_SUPPLY_TOTAL_COLUMNS = ("DSUP_bas", "IMP", "SUP_bas", "ExpTTM", "ReEXP", "IntTTM")
WIOD_FACTOR_ROWS = (
    "TXSP",
    "EXP_adj",
    "PURR",
    "PURNR",
    "VA",
    "IntTTM",
)
WIOD_FACTOR_LABELS = {
    "TXSP": "taxes less subsidies on products",
    "EXP_adj": "Cif/ fob adjustments on exports",
    "PURR": "Direct purchases abroad by residents",
    "PURNR": "Purchases on the domestic territory by non-residents ",
    "VA": "Value added at basic prices",
    "IntTTM": "International Transport Margins",
}
WIOD_SUT_FINAL_DEMAND_LABELS = {
    "CONS_h": "Households",
    "CONS_np": "NPISH",
    "CONS_g": "Government",
    "GFCF": "Gross fixed capital formation",
    "INVEN": "Changes in inventories and valuables",
    "EXP": "Exports",
}


EUROSTAT_SDMX_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
EUROSTAT_SUT_DATAFLOWS = {
    "supply": "NAIO_10_CP15",
    "use": "NAIO_10_CP16",
}
EUROSTAT_IOT_DATAFLOWS = {
    "product": "NAIO_10_CP1700",
    "industry": "NAIO_10_CP1750",
}
EUROSTAT_SUT_UNITS = ("MIO_EUR", "MIO_NAC")
EUROSTAT_IOT_MODES = ("product", "industry")
EUROSTAT_SOURCE = (
    "Eurostat SDMX API @ https://ec.europa.eu/eurostat/web/"
    "user-guides/data-browser/api-data-access/api-introduction"
)
EUROSTAT_SATELLITE_PLACEHOLDER = "-"

EUROSTAT_SUT_ACTIVITY_CODES = [
    "A01",
    "A02",
    "A03",
    "B",
    "C10-12",
    "C13-15",
    "C16",
    "C17",
    "C18",
    "C19",
    "C20",
    "C21",
    "C22",
    "C23",
    "C24",
    "C25",
    "C26",
    "C27",
    "C28",
    "C29",
    "C30",
    "C31_32",
    "C33",
    "D",
    "E36",
    "E37-39",
    "F",
    "G45",
    "G46",
    "G47",
    "H49",
    "H50",
    "H51",
    "H52",
    "H53",
    "I",
    "J58",
    "J59_60",
    "J61",
    "J62_63",
    "K64",
    "K65",
    "K66",
    "L68A",
    "L68B",
    "M69_70",
    "M71",
    "M72",
    "M73",
    "M74_75",
    "N77",
    "N78",
    "N79",
    "N80-82",
    "O",
    "P",
    "Q86",
    "Q87_88",
    "R90-92",
    "R93",
    "S94",
    "S95",
    "S96",
    "T",
    "U",
]

EUROSTAT_SUT_ACTIVITY_LABELS = dict(
    zip(
        EUROSTAT_SUT_ACTIVITY_CODES,
        [
            "Crop and animal production, hunting and related service activities",
            "Forestry and logging",
            "Fishing and aquaculture",
            "Mining and quarrying",
            "Manufacture of food products; beverages and tobacco products",
            "Manufacture of textiles, wearing apparel, leather and related products",
            "Manufacture of wood and of products of wood and cork, except furniture; manufacture of articles of straw and plaiting materials",
            "Manufacture of paper and paper products",
            "Printing and reproduction of recorded media",
            "Manufacture of coke and refined petroleum products",
            "Manufacture of chemicals and chemical products",
            "Manufacture of basic pharmaceutical products and pharmaceutical preparations",
            "Manufacture of rubber and plastic products",
            "Manufacture of other non-metallic mineral products",
            "Manufacture of basic metals",
            "Manufacture of fabricated metal products, except machinery and equipment",
            "Manufacture of computer, electronic and optical products",
            "Manufacture of electrical equipment",
            "Manufacture of machinery and equipment n.e.c.",
            "Manufacture of motor vehicles, trailers and semi-trailers",
            "Manufacture of other transport equipment",
            "Manufacture of furniture; other manufacturing",
            "Repair and installation of machinery and equipment",
            "Electricity, gas, steam and air conditioning supply",
            "Water collection, treatment and supply",
            "Sewerage, waste management, remediation activities",
            "Construction",
            "Wholesale and retail trade and repair of motor vehicles and motorcycles",
            "Wholesale trade, except of motor vehicles and motorcycles",
            "Retail trade, except of motor vehicles and motorcycles",
            "Land transport and transport via pipelines",
            "Water transport",
            "Air transport",
            "Warehousing and support activities for transportation",
            "Postal and courier activities",
            "Accommodation and food service activities",
            "Publishing activities",
            "Motion picture, video, television programme production; programming and broadcasting activities",
            "Telecommunications",
            "Computer programming, consultancy, and information service activities",
            "Financial service activities, except insurance and pension funding",
            "Insurance, reinsurance and pension funding, except compulsory social security",
            "Activities auxiliary to financial services and insurance activities",
            "Imputed rents of owner-occupied dwellings",
            "Real estate activities excluding imputed rents",
            "Legal and accounting activities; activities of head offices; management consultancy activities",
            "Architectural and engineering activities; technical testing and analysis",
            "Scientific research and development",
            "Advertising and market research",
            "Other professional, scientific and technical activities; veterinary activities",
            "Rental and leasing activities",
            "Employment activities",
            "Travel agency, tour operator reservation service and related activities",
            "Security and investigation, service and landscape, office administrative and support activities",
            "Public administration and defence; compulsory social security",
            "Education",
            "Human health activities",
            "Residential care activities and social work activities without accommodation",
            "Creative, arts and entertainment activities; libraries, archives, museums and other cultural activities; gambling and betting activities",
            "Sports activities and amusement and recreation activities",
            "Activities of membership organisations",
            "Repair of computers and personal and household goods",
            "Other personal service activities",
            "Activities of households as employers; undifferentiated goods- and services-producing activities of households for own use",
            "Activities of extraterritorial organisations and bodies",
        ],
    )
)

EUROSTAT_SUT_COMMODITY_CODES = [
    "CPA_A01",
    "CPA_A02",
    "CPA_A03",
    "CPA_B",
    "CPA_C10-12",
    "CPA_C13-15",
    "CPA_C16",
    "CPA_C17",
    "CPA_C18",
    "CPA_C19",
    "CPA_C20",
    "CPA_C21",
    "CPA_C22",
    "CPA_C23",
    "CPA_C24",
    "CPA_C25",
    "CPA_C26",
    "CPA_C27",
    "CPA_C28",
    "CPA_C29",
    "CPA_C30",
    "CPA_C31_32",
    "CPA_C33",
    "CPA_D",
    "CPA_E36",
    "CPA_E37-39",
    "CPA_F",
    "CPA_G45",
    "CPA_G46",
    "CPA_G47",
    "CPA_H49",
    "CPA_H50",
    "CPA_H51",
    "CPA_H52",
    "CPA_H53",
    "CPA_I",
    "CPA_J58",
    "CPA_J59_60",
    "CPA_J61",
    "CPA_J62_63",
    "CPA_K64",
    "CPA_K65",
    "CPA_K66",
    "CPA_L68A",
    "CPA_L68B",
    "CPA_M69_70",
    "CPA_M71",
    "CPA_M72",
    "CPA_M73",
    "CPA_M74_75",
    "CPA_N77",
    "CPA_N78",
    "CPA_N79",
    "CPA_N80-82",
    "CPA_O",
    "CPA_P",
    "CPA_Q86",
    "CPA_Q87_88",
    "CPA_R90-92",
    "CPA_R93",
    "CPA_S94",
    "CPA_S95",
    "CPA_S96",
    "CPA_T",
    "CPA_U",
]

EUROSTAT_SUT_COMMODITY_LABELS = dict(
    zip(
        EUROSTAT_SUT_COMMODITY_CODES,
        [
            "Products of agriculture, hunting and related services",
            "Products of forestry, logging and related services",
            "Fish and other fishing products; aquaculture products; support services to fishing",
            "Mining and quarrying",
            "Food, beverages and tobacco products",
            "Textiles, wearing apparel, leather and related products",
            "Wood and of products of wood and cork, except furniture; articles of straw and plaiting materials",
            "Paper and paper products",
            "Printing and recording services",
            "Coke and refined petroleum products",
            "Chemicals and chemical products",
            "Basic pharmaceutical products and pharmaceutical preparations",
            "Rubber and plastic products",
            "Other non-metallic mineral products",
            "Basic metals",
            "Fabricated metal products, except machinery and equipment",
            "Computer, electronic and optical products",
            "Electrical equipment",
            "Machinery and equipment n.e.c.",
            "Motor vehicles, trailers and semi-trailers",
            "Other transport equipment",
            "Furniture and other manufactured goods",
            "Repair and installation services of machinery and equipment",
            "Electricity, gas, steam and air conditioning",
            "Natural water; water treatment and supply services",
            "Sewerage services; sewage sludge; waste collection, treatment and disposal services; materials recovery services; remediation services and other waste management services",
            "Constructions and construction works",
            "Wholesale and retail trade and repair services of motor vehicles and motorcycles",
            "Wholesale trade services, except of motor vehicles and motorcycles",
            "Retail trade services, except of motor vehicles and motorcycles",
            "Land transport services and transport services via pipelines",
            "Water transport services",
            "Air transport services",
            "Warehousing and support services for transportation",
            "Postal and courier services",
            "Accommodation and food services",
            "Publishing services",
            "Motion picture, video and television programme production services, sound recording and music publishing; programming and broadcasting services",
            "Telecommunications services",
            "Computer programming, consultancy and related services; Information services",
            "Financial services, except insurance and pension funding",
            "Insurance, reinsurance and pension funding services, except compulsory social security",
            "Services auxiliary to financial services and insurance services",
            "Imputed rents of owner-occupied dwellings",
            "Real estate services excluding imputed rents",
            "Legal and accounting services; services of head offices; management consultancy services",
            "Architectural and engineering services; technical testing and analysis services",
            "Scientific research and development services",
            "Advertising and market research services",
            "Other professional, scientific and technical services and veterinary services",
            "Rental and leasing services",
            "Employment services",
            "Travel agency, tour operator and other reservation services and related services",
            "Security and investigation services; services to buildings and landscape; office administrative, office support and other business support services",
            "Human health services",
            "Residential care services; social work services without accommodation",
            "Creative, arts, entertainment, library, archive, museum, other cultural services; gambling and betting services",
            "Sporting services and amusement and recreation services",
            "Services furnished by membership organisations",
            "Repair services of computers and personal and household goods",
            "Other personal services",
            "Services of households as employers; undifferentiated goods and services produced by households for own use",
            "Services provided by extraterritorial organisations and bodies",
            "Public administration and defence services; compulsory social security services",
            "Education services",
        ],
    )
)

EUROSTAT_SUT_FACTOR_ROWS = [
    ("D1", "Compensation of employees"),
    ("D11", "Wages and salaries"),
    ("D29X39", "Other taxes less other subsidies on production"),
    ("P51C", "Consumption of fixed capital"),
    ("B2A3N", "Operating surplus and mixed income, net"),
    ("P7", "Imports of goods and services"),
]

EUROSTAT_SUT_FINAL_DEMAND = [
    {
        "label": "Final consumption expenditure",
        "preferred": "P3",
        "fallback": ("P3_S14", "P3_S13", "P3_S15"),
    },
    {
        "label": "Gross capital formation",
        "preferred": "P5",
        "fallback": ("P51G", "P52", "P53", "P5M"),
    },
    {
        "label": "Exports of goods and services",
        "preferred": "P6",
        "fallback": ("P6_B0", "P6_D0", "P6_U2", "P6_U3"),
    },
]


EXIO_FACTOR_ROWS = [
    "Taxes less subsidies on products purchased: Total",
    "Other net taxes on production",
    "Compensation of employees; wages, salaries, & employers' social contributions: Low-skilled",
    "Compensation of employees; wages, salaries, & employers' social contributions: Medium-skilled",
    "Compensation of employees; wages, salaries, & employers' social contributions: High-skilled",
    "Operating surplus: Consumption of fixed capital",
    "Operating surplus: Rents on land",
    "Operating surplus: Royalties on resources",
    "Operating surplus: Remaining net operating surplus",
]


EXIO_INDEX_LAYOUT = {
    _MASTER_INDEX["s"]: {
        "matrix": "Z",
        "item": "columns",
        "multi_index": True,
        "del_duplicate": True,
        "level": 1,
    },
    _MASTER_INDEX["r"]: {
        "matrix": "Z",
        "item": "index",
        "multi_index": True,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["k"]: {
        "matrix": "E",
        "item": "index",
        "multi_index": False,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["f"]: {
        "matrix": "V",
        "item": "index",
        "multi_index": False,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["n"]: {
        "matrix": "Y",
        "item": "columns",
        "multi_index": True,
        "del_duplicate": True,
        "level": 1,
    },
}


MRSUT_EXIO_INDEX_LAYOUT = {
    _MASTER_INDEX["s"]: {
        "matrix": "Y",
        "item": "index",
        "multi_index": True,
        "del_duplicate": True,
        "level": 1,
    },
    _MASTER_INDEX["r"]: {
        "matrix": "Z",
        "item": "index",
        "multi_index": True,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["k"]: {
        "matrix": "E",
        "item": "index",
        "multi_index": False,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["f"]: {
        "matrix": "V",
        "item": "index",
        "multi_index": False,
        "del_duplicate": True,
        "level": 0,
    },
    _MASTER_INDEX["n"]: {
        "matrix": "Y",
        "item": "columns",
        "multi_index": True,
        "del_duplicate": True,
        "level": 1,
    },
}


HMRSUT_EXTENSIONS = [
    "resource",
    "Land",
    "Emiss",
    "Emis_unreg_w",
    "Unreg_w",
    "waste_sup",
    "waste_use",
    "pack_sup_waste",
    "pack_use_waste",
    "mach_sup_waste",
    "mach_use_waste",
    "stock_addition",
    "crop_res",
]


HMIOT_EXTENSIONS = [
    "resource",
    "Land",
    "Emiss",
    "Emis_unreg_w",
    "waste_sup",
    "waste_use",
    "pack_sup_waste",
    "pack_use_waste",
    "mach_sup_waste",
    "mach_use_waste",
    "stock_addition",
    "crop_res",
]


PYMRIO_IMPORT_LAYOUTS = {
    "v": {"index": 1, "columns": 3, "add_c": [_MASTER_INDEX["s"]]},
    "e": {"index": 1, "columns": 3, "add_c": [_MASTER_INDEX["s"]]},
    "EY": {"index": 1, "columns": 3, "add_c": [_MASTER_INDEX["n"]]},
    "Y": {
        "index": 3,
        "columns": 3,
        "add_c": ["Consumption category"],
        "add_i": [_MASTER_INDEX["s"]],
    },
    "z": {
        "index": 3,
        "columns": 3,
        "add_c": [_MASTER_INDEX["s"]],
        "add_i": [_MASTER_INDEX["s"]],
    },
}
