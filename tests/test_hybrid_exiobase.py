import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

import sys
import os
import pytest
import requests
import pandas as pd
from pandas import testing as pdt

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_PATH = f"{MAIN_PATH}/tests/mocks/temp_files"

from mario import hybrid_sut_exiobase
from mario.log_exc.exceptions import WrongInput
from mario.tools.constants import _MASTER_INDEX
from mario.tools.parsers_id import hybrid_sut_exiobase_parser_id

exiobase_files = {
    "MR_HUSE_2011_v3_3_18.csv":"https://zenodo.org/record/7244919/files/MR_HUSE_2011_v3_3_18.csv?download=1",
    "MR_HSUTs_2011_v3_3_18_FD.csv":"https://zenodo.org/record/7244919/files/MR_HSUTs_2011_v3_3_18_FD.csv?download=1",
    "MR_HSUP_2011_v3_3_18.csv":"https://zenodo.org/record/7244919/files/MR_HSUP_2011_v3_3_18.csv?download=1",
    "MR_HSUTs_2011_v3_3_18_extensions.xlsx":"https://zenodo.org/record/7244919/files/MR_HSUTs_2011_v3_3_18_extensions.xlsx?download=1",
    "metadata.xlsx": "https://zenodo.org/record/7244919/files/Classifications_v_3_3_18.xlsx?download=1",
}


def download_exiobase_files(exiobase_files):

    if not os.path.exists(FILES_PATH):
        os.mkdir(FILES_PATH)

    for file,url in exiobase_files.items():
        path = f"{FILES_PATH}/{file}"

        if not os.path.exists(path):
            response = requests.get(url)
            open(path, "wb").write(response.content)


def test_parse_wrong_extension():
    download_exiobase_files(exiobase_files)

    with pytest.raises(WrongInput) as msg:
        world = hybrid_sut_exiobase('dummy',["dummy"])

    assert "Following items are not valid for extensions" in str(msg.value)

def test_parse_main_data():

    # no extension to parse
    db = hybrid_sut_exiobase(FILES_PATH)

    #checking regions
    region_info = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name="Country",index_col=0).index.tolist()
    # Taiwan is not in the sut version
    region_info.remove("TW")
    assert sorted(db.get_index(_MASTER_INDEX["r"])) == sorted(region_info)

    # checking activities
    activity_info = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name="Activities",index_col=1).index.unique(0).tolist()
    assert sorted(db.get_index(_MASTER_INDEX["a"])) == sorted(activity_info)    

    # checking commodities
    commodity_info = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name="Products_HSUTs",index_col=1)
    commodities = commodity_info.index.unique(0).tolist()
    assert sorted(db.get_index(_MASTER_INDEX["c"])) == sorted(commodities)    

    # checking final demand
    final_demand_info = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name="Final_demand",index_col=1).index.unique(0).tolist()
    assert sorted(db.get_index(_MASTER_INDEX["n"])) == sorted(final_demand_info)  

    # testing hybrid identifier
    assert db.is_hybrid

    # checking units
    assert sorted([*db.units]) == sorted([_MASTER_INDEX[i] for i in "ackf"])

    # activity units is all None
    pdt.assert_frame_equal(
        db.units[_MASTER_INDEX["a"]],pd.DataFrame(
            index = db.get_index(_MASTER_INDEX["a"],),columns=['unit']
        ).fillna("None")
    )

    # factor of production unit is None
    pdt.assert_frame_equal(
        db.units[_MASTER_INDEX["f"]],pd.DataFrame(
            index = db.get_index(_MASTER_INDEX["f"],),columns=['unit']
        ).fillna("None")
    )


    # commodity production -> read from metadata
    uniqe_index_len = len(commodity_info.index.unique(0))
    commodity_units = commodity_info.unit.iloc[0:uniqe_index_len].to_frame()
    commodity_units.index.name = None
    pdt.assert_frame_equal(
        db.units[_MASTER_INDEX["c"]], commodity_units
    )

def test_read_extensions():

    # reading all extensions (if read all extensions works, single ones should also work)
    db = hybrid_sut_exiobase(
        FILES_PATH,
        extensions = "all"
    )


    extension_info = {
        "Resources":["resource"],
        "Land":["Land"],
        "Emissions":["Emiss","Emis_unreg_w",],
        "waste":["waste_sup","waste_use","pack_sup_waste","pack_use_waste","mach_sup_waste","mach_use_waste","stock_addition","Unreg_w"],
        "Crop_residues":["crop_res"],
    }

    metadata = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name=[*extension_info],index_col=0)


    
    for category,types in extension_info.items():
        resource_info = metadata[category]
        idx = pd.Index([])
        units = []
        
        if "Compartment" in resource_info.columns:

            for extension in types:
                idx = idx.append(
                    pd.Index(
                        resource_info.index + " (" + resource_info.Compartment.values + f" - {extension})",
                    )
                )

                try:
                    units.extend(resource_info["Unit "].values.tolist())
                except KeyError:
                    units.extend(resource_info["Unit"].values.tolist())

        else:

            for extension in types:
                idx = idx.append(
                    pd.Index(resource_info.index + f" ({extension})",
                    ) 
                )

                try:
                    units.extend(resource_info["Unit "].values.tolist())
                except KeyError:
                    units.extend(resource_info["Unit"].values.tolist())


        # checking existence in in pd.DataFrames for E and EY
        for matrix in [db.E,db.EY,db.units[_MASTER_INDEX['k']]]:
            assert all(idx.isin(matrix.index))

        # checking if units are correct
        assert db.units[_MASTER_INDEX['k']].loc[idx,"unit"].values.tolist() == units  

