import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

import pytest
import os
import sys
import yaml
import pandas as pd
from copy import deepcopy
from mario.log_exc.exceptions import WrongFormat
from tests._paths import MOCKS_ROOT


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

MOCK_PATH = str(MOCKS_ROOT)

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


def test_index_aliases_include_documented_terminology_defaults():
    aliases = IndexAliases()

    assert any(alias.casefold() == "consumption_category" for alias in aliases.n)
    assert any(alias.casefold() == "demand categories" for alias in aliases.n)
    assert any(alias.casefold() == "satellite_accounts" for alias in aliases.k)
    assert any(alias.casefold() == "factors of production" for alias in aliases.f)


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


def test_download_settings_returns_independent_copies():
    settings = download_settings(None)
    settings["compute"]["compute_method"] = "solve"

    fresh = download_settings(None)

    assert fresh["compute"]["compute_method"] != "solve"


def test_upload_settings_rejects_blocked_nomenclature_names():
    original = download_settings(None)

    try:
        duplicate_name = deepcopy(original)
        duplicate_name["nomenclature"]["z"] = "f"

        with pytest.raises(WrongFormat) as msg:
            upload_settings(duplicate_name)
        assert "blocked" in str(msg.value)

        reserved_split_name = deepcopy(original)
        reserved_split_name["nomenclature"]["z"] = "fa"

        with pytest.raises(WrongFormat) as msg:
            upload_settings(reserved_split_name)
        assert "reserved built-in matrix name" in str(msg.value)
    finally:
        reset_settings()


@pytest.mark.parametrize("table", ["IOT", "SUT"])
def test_aggregation_preserves_renamed_environmental_blocks_after_settings_upload(table):
    from mario import load_test

    original = download_settings(None)
    renamed = deepcopy(original)
    renamed["nomenclature"].update({"E": "R", "EY": "Ry", "F": "Re"})
    try:
        upload_settings(renamed)
        database = load_test(table)
        extension_total = database.R.to_numpy().sum()
        final_total = database.Ry.to_numpy().sum()
        levels = ["Sector"] if table == "IOT" else ["Activity", "Commodity"]
        mapping = {
            level: pd.DataFrame({"Aggregation": "All " + level}, index=database.get_index(level))
            for level in levels
        }
        if table == "SUT":
            from mario.ops.aggregation_engine import _extract_sut_split_from_unified

            extracted = _extract_sut_split_from_unified("Ea", "R", database.R)
            assert extracted.to_numpy().sum() == pytest.approx(database.Ea.to_numpy().sum())

        aggregated = database.aggregate(mapping, levels=levels, inplace=False)

        for level in levels:
            assert aggregated.get_index(level) == ["All " + level]
        assert aggregated.R.to_numpy().sum() == pytest.approx(extension_total)
        assert aggregated.Ry.to_numpy().sum() == pytest.approx(final_total)
        assert aggregated.get_block_spec("R").row_axes == aggregated.get_block_spec("E").row_axes
        assert "Ry" in aggregated["baseline"]
        assert "EY" not in aggregated["baseline"]
        if table == "IOT":
            assert "R" in aggregated["baseline"] and "E" not in aggregated["baseline"]
            assert aggregated.Re.to_numpy().sum() == pytest.approx(database.Re.to_numpy().sum())
    finally:
        upload_settings(original)


@pytest.mark.parametrize("table", ["IOT", "SUT"])
@pytest.mark.parametrize("single_region", [True, False])
@pytest.mark.parametrize("inplace", [True, False])
def test_region_extraction_then_aggregation_preserves_live_matrix_names(table, single_region, inplace):
    from mario import load_test

    original = download_settings(None)
    custom = deepcopy(original)
    custom["nomenclature"].update({"E": "R", "EY": "Ry", "F": "Re"})
    try:
        upload_settings(custom)
        database = load_test(table)
        region = database.regions[0]
        emissions = database.R.loc[:, database.R.columns.get_level_values(0) == region]
        final_emissions = database.Ry.loc[:, database.Ry.columns.get_level_values(0) == region]
        original_total = database.R.to_numpy().sum()

        if single_region:
            result = database.to_single_region(region, inplace=inplace)
        else:
            result = database.to_region_subset([region], inplace=inplace)
        subset = database if inplace else result

        assert subset.regions == [region]
        assert {"R", "Ry"} <= set(subset["baseline"])
        assert "E" not in subset["baseline"] and "EY" not in subset["baseline"]
        pd.testing.assert_frame_equal(subset.R, emissions)
        assert subset.Ry.to_numpy().sum() == pytest.approx(final_emissions.to_numpy().sum())
        levels = ["Sector"] if table == "IOT" else ["Activity", "Commodity"]
        mapping = {
            level: pd.DataFrame({"Aggregation": "All " + level}, index=subset.get_index(level))
            for level in levels
        }
        subset.aggregate(mapping, levels=levels)

        assert subset.R.to_numpy().sum() == pytest.approx(emissions.to_numpy().sum())
        assert subset.Ry.to_numpy().sum() == pytest.approx(final_emissions.to_numpy().sum())
        if table == "IOT":
            assert subset.Re.index.equals(subset.R.index)
        if not inplace:
            assert len(database.regions) > 1
            assert database.R.to_numpy().sum() == pytest.approx(original_total)
    finally:
        upload_settings(original)
