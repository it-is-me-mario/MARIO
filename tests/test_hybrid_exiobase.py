
import sys
import os
import pytest
import requests
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_PATH = f"{MAIN_PATH}/tests/mocks/temp_files"

from mario import hybrid_sut_exiobase
from mario.log_exc.exceptions import WrongInput

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
    # region_info = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name="Country",index_col=0).index.tolist()
    # assert sorted(db.get_index("Region")) == sorted(region_info)

    # checking activities
    activity_info = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name="Activities",index_col=1).index.unique(0).tolist()
    assert sorted(db.get_index("Activity")) == sorted(activity_info)    

    # checking commodities
    commodity_info = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name="Products_HSUTs",index_col=1)
    commodities = commodity_info.index.unique(0).tolist()
    assert sorted(db.get_index("Commodity")) == sorted(commodities)    

    # checking final demand
    final_demand_info = pd.read_excel(f"{FILES_PATH}/metadata.xlsx",sheet_name="Final_demand",index_col=1).index.unique(0).tolist()
    assert sorted(db.get_index("Consumption category")) == sorted(final_demand_info   )  


# %%
