import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

import pytest
import os
import sys
import yaml
from copy import deepcopy
from mario.log_exc.exceptions import WrongFormat


from mario.model.conventions import _ENUM
from mario.settings.settings import Compute, Index, IndexAliases, reset_settings
from mario.settings.settings import (
    download_settings,
    upload_settings,
    set_compute_method,
    set_linear_solver,
    set_linear_strategy,
)

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

MAIN_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK_PATH = f"{MAIN_PATH}/tests/mocks"

def test_download_settings():
    
    file_path = f"{MOCK_PATH}/settings.yaml"
    output = download_settings(None)

    assert not os.path.exists(file_path)
    assert isinstance(output,dict)

    output = download_settings(MOCK_PATH)
    assert os.path.exists(file_path)

    os.remove(file_path)

def test_upload_setting():

    # take the exisiting setting
    original = download_settings(None)

    # make some changes
    new = original.copy()
    new["index"]["r"] = "country"

    upload_settings(new)

    uploaded = download_settings(None)

    assert uploaded["index"]["r"] == "Region"
    assert "country" in uploaded["index_aliases"]["r"]

    reset_settings()

    # save the new settings to a file
    with open(f"{MOCK_PATH}/settings.yaml", 'w') as yaml_file:
        yaml.dump(new, yaml_file, default_flow_style=False)

    # reupload
    upload_settings(f"{MOCK_PATH}/settings.yaml")

    # check if it is correct
    uploaded = download_settings(None)

    assert uploaded["index"]["r"] == "Region"
    assert "country" in uploaded["index_aliases"]["r"]

    os.remove(f"{MOCK_PATH}/settings.yaml")

    # reset to orignal settings
    reset_settings()

    # catching errors 
    with pytest.raises(WrongFormat) as msg:
        upload_settings("test")
    assert 'only yaml file is acceptable' in str(msg.value)

    # catching errors 
    with pytest.raises(WrongFormat) as msg:
        upload_settings([])
    assert 'Only dict or a yaml file directory can be passed' in str(msg.value)

    

def test_Setting():

    original = download_settings(None)

    new = deepcopy(original)
    del new["index"]["r"]

    upload_settings(new)

    idx = Index()

    for k,v in original["index"].items():
        assert idx[k] == v

    new = deepcopy(original)
    new["index"]["r"] = "COUNTRY"
    upload_settings(new)

    idx = Index()
    aliases = IndexAliases()

    assert idx.r == "Region"
    assert "country" in aliases.r

    reset_settings()

    idx = Index()
    assert idx.r == idx["r"]


def test_compute_settings_helpers():
    original = download_settings(None)

    set_compute_method("solve")
    set_linear_solver("scipy")
    set_linear_strategy("iterative")

    compute = Compute()
    assert compute.compute_method == "solve"
    assert compute.linear_solver == "scipy"
    assert compute.linear_strategy == "iterative"

    reset_settings()
    restored = download_settings(None)
    assert restored["compute"] == original["compute"]
