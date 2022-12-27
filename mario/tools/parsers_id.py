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
    header =  [0,1,2,3],
    index_col = [0,1]
)

_extension_type_2 = dict(
    file_name="MR_HSUTs_2011_v3_3_18_extensions.xlsx",
    header =  [0,1,2,3],
    index_col = [0,1,2]
)



hybrid_sut_exiobase_parser_id = {

    "matrices": {
        "S" : {
            "file_name": "MR_HSUP_2011_v3_3_18.csv",
            "index_col": [0,1,2,3,4],
            "header": [0,1,2,3],
        },
        "U" : {
            "file_name": "MR_HUSE_2011_v3_3_18.csv",
            "index_col": [0,1,2,3,4],
            "header": [0,1,2,3],
        },

        "Y": {
            "file_name": "MR_HSUTs_2011_v3_3_18_FD.csv",
            "index_col": [0,1,2,3,4],
            "header": [0,1,2,3],
        },

    },

    "resource": {
        "activity":{**_extension_type_1,**dict(sheet_name="resource_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="resource_FD")},
    },

    "Land": {
        "activity":{**_extension_type_1,**dict(sheet_name="Land_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="Land_FD")},
        }, 

    "Emiss": {
        "activity":{**_extension_type_2,**dict(sheet_name="Emiss_act")},
        "final_demand":{**_extension_type_2,**dict(sheet_name="Emiss_FD")},
        }, 

    "Emis_unreg_w": {
        "activity":{**_extension_type_2,**dict(sheet_name="Emis_unreg_w_act")},
        "final_demand":{**_extension_type_2,**dict(sheet_name="Emis_unreg_w_FD")},
        },

    "waste_sup": {
        "activity":{**_extension_type_1,**dict(sheet_name="waste_sup_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="waste_sup_FD")},
        },

    "waste_use": {
        "activity":{**_extension_type_1,**dict(sheet_name="waste_use_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="waste_use_FD")},
        },

    "pack_sup_waste": {
        "activity":{**_extension_type_1,**dict(sheet_name="pack_sup_waste_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="pack_sup_waste_fd")},
        },

    "pack_use_waste": {
        "activity":{**_extension_type_1,**dict(sheet_name="pack_use_waste_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="pack_use_waste_fd")},
        },

    "mach_sup_waste": {
        "activity":{**_extension_type_1,**dict(sheet_name="mach_use_waste_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="mach_use_waste_fd")},
        },

    "mach_use_waste": {
        "activity":{**_extension_type_1,**dict(sheet_name="mach_use_waste_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="mach_use_waste_fd")},
        },

    "stock_addition": {
        "activity":{**_extension_type_1,**dict(sheet_name="stock_addition_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="stock_addition_fd")},
        },

    "crop_res": {
        "activity":{**_extension_type_1,**dict(sheet_name="crop_res_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="crop_res_FD")},
        },
    
    "Unreg_w":{
        "activity":{**_extension_type_1,**dict(sheet_name="Unreg_w_act")},
        "final_demand":{**_extension_type_1,**dict(sheet_name="Unreg_w_FD")},       
    },
    }






