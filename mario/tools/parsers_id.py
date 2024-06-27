# -*- coding: utf-8 -*-
"""
module contains dictionaries guiding the file reader for structured databases
"""

from mario.tools.constants import _MASTER_INDEX


exiobase_mrsut = {
    "matrices": {
        "Y": {"file_name": "final_demand.csv", "index_col": [0, 1], "header": [0, 1]},
        "U": {"file_name": "use.csv", "index_col": [0, 1], "header": [0, 1]},
        "S": {"file_name": "supply.csv", "index_col": [0, 1], "header": [0, 1]},
        "V": {"file_name": "value_added.csv", "index_col": [0], "header": [0, 1]},
    }
}


exiobase_version_3 = {
    "3.8.2": {
        "matrices": {
            "Y": {"file_name": "Y.txt", "index_col": [0, 1], "header": [0, 1]},
            "Z": {"file_name": "Z.txt", "index_col": [0, 1], "header": [0, 1]},
            "F": {"file_name": r"satellite/F.txt", "index_col": [0], "header": [0, 1]},
            "EY": {
                "file_name": r"satellite/F_Y.txt",
                "index_col": [0],
                "header": [0, 1],
            },
        },
        "units": {
            _MASTER_INDEX["k"]: {
                "file_name": r"satellite/unit.txt",
                "index_col": [0],
                "header": [0],
            }
        },
    },
    "3.8.1": {
        "matrices": {
            "Y": {"file_name": "Y.txt", "index_col": [0, 1], "header": [0, 1]},
            "Z": {"file_name": "Z.txt", "index_col": [0, 1], "header": [0, 1]},
            "F": {"file_name": r"satellite/F.txt", "index_col": [0], "header": [0, 1]},
            "EY": {
                "file_name": r"satellite/F_hh.txt",
                "index_col": [0],
                "header": [0, 1],
            },
        },
        "units": {
            _MASTER_INDEX["k"]: {
                "file_name": r"satellite/unit.txt",
                "index_col": [0],
                "header": [0],
            }
        },
    },
}


txt_parser_id = {
    "flows": {
        "matrices": {
            "Y": {"file_name": "Y.txt", "index_col": [0, 1, 2], "header": [0, 1, 2]},
            "Z": {"file_name": "Z.txt", "index_col": [0, 1, 2], "header": [0, 1, 2]},
            "V": {"file_name": "V.txt", "index_col": [0], "header": [0, 1, 2]},
            "E": {"file_name": "E.txt", "index_col": [0], "header": [0, 1, 2]},
            "EY": {"file_name": "EY.txt", "index_col": [0], "header": [0, 1, 2]},
        },
        "units": {
            "all": {
                "file_name": "units.txt",
                "index_col": [0, 1],
                "header": [0],
            }
        },
    },
    "coefficients": {
        "matrices": {
            "Y": {"file_name": "Y.txt", "index_col": [0, 1, 2], "header": [0, 1, 2]},
            "z": {"file_name": "z.txt", "index_col": [0, 1, 2], "header": [0, 1, 2]},
            "v": {"file_name": "v.txt", "index_col": [0], "header": [0, 1, 2]},
            "e": {"file_name": "e.txt", "index_col": [0], "header": [0, 1, 2]},
            "EY": {"file_name": "EY.txt", "index_col": [0], "header": [0, 1, 2]},
        },
        "units": {
            "all": {
                "file_name": "units.txt",
                "index_col": [0, 1],
                "header": [0],
            }
        },
    },
}


eora = {
    _MASTER_INDEX["s"]: ["Industries"],
    _MASTER_INDEX["a"]: ["Industries"],
    _MASTER_INDEX["c"]: ["Commodities"],
    _MASTER_INDEX["f"]: ["Primary Inputs", "ImportsFrom"],
    _MASTER_INDEX["n"]: ["Final Demand", "ExportsTo"],
}

eora_parser_id = {
    "matrices": {
        "Z": {
            "file_name": "Eora26_{year}_{price}_T.txt",
            "index_col": None,
            "header": None,
        },
        "Y": {
            "file_name": "Eora26_{year}_{price}_FD.txt",
            "index_col": None,
            "header": None,
        },
        "V": {
            "file_name": "Eora26_{year}_{price}_VA.txt",
            "index_col": None,
            "header": None,
        },
        "E": {
            "file_name": "Eora26_{year}_{price}_Q.txt",
            "index_col": None,
            "header": None,
        },
        "EY": {
            "file_name": "Eora26_{year}_{price}_QY.txt",
            "index_col": None,
            "header": None,
        },
    },
    "labels": {
        "Z_i": {"file_name": "labels_T.txt", "index_col": [1, 2, 3], "header": None},
        "Y_c": {"file_name": "labels_FD.txt", "index_col": [1, 2, 3], "header": None},
        "V_i": {
            "file_name": "labels_VA.txt",
            "index_col": [
                1,
            ],
            "header": None,
        },
        "E_i": {
            "file_name": "labels_Q.txt",
            "index_col": [
                0,
                1,
            ],
            "header": None,
        },
    },
}


_extension_type_1 = dict(
    file_name="MR_HSUTs_2011_v3_3_18_extensions.xlsx",
    header=[0, 1, 2, 3],
    index_col=[0, 1],
)

_extension_type_2 = dict(
    file_name="MR_HSUTs_2011_v3_3_18_extensions.xlsx",
    header=[0, 1, 2, 3],
    index_col=[0, 1, 2],
)


hybrid_sut_exiobase_parser_id = {
    "matrices": {
        "S": {
            "file_name": "MR_HSUP_2011_v3_3_18.csv",
            "index_col": [0, 1, 2, 3, 4],
            "header": [0, 1, 2, 3],
        },
        "U": {
            "file_name": "MR_HUSE_2011_v3_3_18.csv",
            "index_col": [0, 1, 2, 3, 4],
            "header": [0, 1, 2, 3],
        },
        "Y": {
            "file_name": "MR_HSUTs_2011_v3_3_18_FD.csv",
            "index_col": [0, 1, 2, 3, 4],
            "header": [0, 1, 2, 3],
        },
    },
    "resource": {
        "activity": {**_extension_type_1, **dict(sheet_name="resource_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="resource_FD")},
    },
    "Land": {
        "activity": {**_extension_type_1, **dict(sheet_name="Land_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="Land_FD")},
    },
    "Emiss": {
        "activity": {**_extension_type_2, **dict(sheet_name="Emiss_act")},
        "final_demand": {**_extension_type_2, **dict(sheet_name="Emiss_FD")},
    },
    "Emis_unreg_w": {
        "activity": {**_extension_type_2, **dict(sheet_name="Emis_unreg_w_act")},
        "final_demand": {**_extension_type_2, **dict(sheet_name="Emis_unreg_w_FD")},
    },
    "waste_sup": {
        "activity": {**_extension_type_1, **dict(sheet_name="waste_sup_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="waste_sup_FD")},
    },
    "waste_use": {
        "activity": {**_extension_type_1, **dict(sheet_name="waste_use_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="waste_use_FD")},
    },
    "pack_sup_waste": {
        "activity": {**_extension_type_1, **dict(sheet_name="pack_sup_waste_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="pack_sup_waste_fd")},
    },
    "pack_use_waste": {
        "activity": {**_extension_type_1, **dict(sheet_name="pack_use_waste_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="pack_use_waste_fd")},
    },
    "mach_sup_waste": {
        "activity": {**_extension_type_1, **dict(sheet_name="mach_use_waste_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="mach_use_waste_fd")},
    },
    "mach_use_waste": {
        "activity": {**_extension_type_1, **dict(sheet_name="mach_use_waste_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="mach_use_waste_fd")},
    },
    "stock_addition": {
        "activity": {**_extension_type_1, **dict(sheet_name="stock_addition_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="stock_addition_fd")},
    },
    "crop_res": {
        "activity": {**_extension_type_1, **dict(sheet_name="crop_res_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="crop_res_FD")},
    },
    "Unreg_w": {
        "activity": {**_extension_type_1, **dict(sheet_name="Unreg_w_act")},
        "final_demand": {**_extension_type_1, **dict(sheet_name="Unreg_w_FD")},
    },
}

# letters follow the _MASTER_INDEX definitions
eurostat_id = {
    "a": [
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
    "c": [
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
    "n": [
        "Final consumption expenditure by households",
        "Final consumption expenditure by government",
        "Final consumption expenditure by non-profit organisations serving households (NPISH)",
        "Final consumption expediture",
        "Gross fixed capital formation",
        "Acquisitions less disposals of valuables",
        "Changes in inventories",
        "Changes in inventories and acquisition less disposals of valuables",
        "Gross Capital formation",
        "Exports to EU members states",
        "Exports to non-member of the EU",
        "Exports to members of the euro area",
        "Exports to non-members of the euro area",
        "Exports of goods and services",
    ],
    "f": [
        "Compensation of employees",
        "Wages and salaries",
        "Other taxes less other subsidies on production",
        "Consumption of fixed capital",
        "Operating surplus and mixed income, net",
    ],
    "c_import": [
        "Imports from EU member states",
        "Imports from non-members of the EU",
        "Imports from members of the euro area",
        "Imports from non-members of the euro area",
        "Imports of goods and services",
        "Total supply at basic prices",
        "Taxes less subsidies on products",
        "Trade and transport margins",
    ],
    "use": {"index_col": 0, "header": 11, "sheet_name": "Sheet 1"},
    "supply": {"index_col": 0, "header": 10, "sheet_name": "Sheet 1"},
    "meta_info": {"year": (7, 2, int), "country": (6, 2, str), "table": (0, 1, str)},
}
