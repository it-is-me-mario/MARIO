import warnings
warnings.filterwarnings("ignore",category=DeprecationWarning)

from mario.ops.add_sector_specs import (
    ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_SHEET,
    ADVANCED_ADD_SECTOR_MASTER_SHEET,
    ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS,
    ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_SHEET,
    ADVANCED_ADD_SECTOR_UNCERTAINTIES_SHEET,
)
from mario.ops.add_sector_workbook import (
    derive_advanced_add_sector_sets,
    group_advanced_inventories_by_target,
    read_advanced_add_sector_workbook,
)
from mario.ops.sectoradd import get_corresponding_keys,matrix_concat,fill_matrix
from mario.model.conventions import _MASTER_INDEX
from mario.model.builders import MatrixBuilder
from mario.ops.workbook_specs import ADD_SECTOR_SHEETS
import pandas.testing as pdt
import pandas as pd
import pytest
from mario import load_test
from mario.model.conventions import _ENUM,_MASTER_INDEX

@pytest.fixture()
def CoreDataIOT():
    return load_test("IOT")


@pytest.fixture()
def CoreDataSUT():
    return load_test("SUT")

def test_get_corresponding_keys():

    # case 1, Sector
    item = _MASTER_INDEX["s"]

    keys,counter_item = get_corresponding_keys(item)

    assert counter_item == _MASTER_INDEX["s"]
    assert set(keys) == set([key for key in ADD_SECTOR_SHEETS.keys() if key not in ["of"]])

    # case 2, Activity
    item = _MASTER_INDEX["a"]

    keys,counter_item = get_corresponding_keys(item)

    assert counter_item == _MASTER_INDEX["c"]
    assert set(keys) == set([key for key in ADD_SECTOR_SHEETS.keys() if key not in ["sf","it"]])

    # case 3, Commodity
    item = _MASTER_INDEX["c"]

    keys,counter_item = get_corresponding_keys(item)

    assert counter_item == _MASTER_INDEX["a"]
    assert set(keys) == set([key for key in ADD_SECTOR_SHEETS.keys() if key not in ["sf","if"]])


def test_matrix_concat():

    # Test should be global for SUT and IOT

    set_1 = MatrixBuilder(
        "IOT",
        {
            _MASTER_INDEX.s : ["sector 1"],
            _MASTER_INDEX.k : ["CO2"],
            _MASTER_INDEX.n : ["FD"],
            _MASTER_INDEX.f : ["VA"],
            _MASTER_INDEX.r : ["reg 1","reg 2"]
        }
    )

    set_2 = MatrixBuilder(
        "IOT",
        {
            _MASTER_INDEX.s : ["sector 2"],
            _MASTER_INDEX.k : ["CO2"],
            _MASTER_INDEX.n : ["FD"],
            _MASTER_INDEX.f : ["VA"],
            _MASTER_INDEX.r : ["reg 1","reg 2"]
        }
    )

    data = dict(
        Y = set_1.Y,
        z = set_1.Z,
        e = set_1.E,
        v = set_1.V,
        EY = set_1.EY,
    )

    empty_matrices = dict(
        Y = set_2.Y,
        z = set_2.Z,
        e = set_2.E,
        v = set_2.V,
        EY = set_2.EY,
    )

    matrix_concat(data,empty_matrices)

    Y_index = pd.MultiIndex.from_product(
        [["reg 1","reg 2"],[_MASTER_INDEX["s"]],["sector 1","sector 2"]]
    ).sort_values()

    pdt.assert_index_equal(Y_index,data["Y"].index)
    pdt.assert_index_equal(Y_index,data["z"].index)
    pdt.assert_index_equal(Y_index,data["z"].columns)
    pdt.assert_index_equal(Y_index,data["v"].columns)
    pdt.assert_index_equal(Y_index,data["e"].columns)

def test_fill_matrix(CoreDataIOT):
    
    # Empty matrix
    

    empty_df = MatrixBuilder(
        "IOT",
        {
            _MASTER_INDEX.s : CoreDataIOT.get_index(_MASTER_INDEX.s) + ["new_sector"],
            _MASTER_INDEX.k : CoreDataIOT.get_index(_MASTER_INDEX.k),
            _MASTER_INDEX.n : CoreDataIOT.get_index(_MASTER_INDEX.n),
            _MASTER_INDEX.f : CoreDataIOT.get_index(_MASTER_INDEX.f),
            _MASTER_INDEX.r : CoreDataIOT.get_index(_MASTER_INDEX.r),
        }
    )

    user_df = getattr(CoreDataIOT,_ENUM.Z)
    output = fill_matrix(empty_df.Z,user_df)
    output.index.names = user_df.index.names
    output.columns.names = user_df.columns.names

    pdt.assert_frame_equal(
        user_df.sort_index(axis=0).sort_index(axis=1),
        output.drop(
            labels=["new_sector"],axis=0,level=-1
            ).drop(
                labels=["new_sector"],axis=1,level=-1
                ).sort_index(axis=0).sort_index(axis=1),
                
    )


def test_get_add_sectors_excel_supports_advanced_iot_workbook(tmp_path, CoreDataIOT):
    regions = CoreDataIOT.get_index(_MASTER_INDEX["r"])[:2]
    new_sectors = ["New sector A", "New sector B"]
    path = tmp_path / "advanced_add_sector_iot.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=new_sectors,
        regions=regions,
        path=path,
        redefine_uncertainties=True,
    )

    workbook = pd.read_excel(path, sheet_name=None)
    item_sheet = ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_SHEET["IOT"]

    assert ADVANCED_ADD_SECTOR_MASTER_SHEET in workbook
    assert ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_SHEET in workbook
    assert ADVANCED_ADD_SECTOR_UNCERTAINTIES_SHEET in workbook
    assert item_sheet in workbook
    assert "DB units" in workbook

    master = workbook[ADVANCED_ADD_SECTOR_MASTER_SHEET]
    assert master.columns.tolist() == list(
        ADVANCED_ADD_SECTOR_MASTER_SHEET_COLUMNS["IOT"].values()
    )
    assert master[_MASTER_INDEX["s"]].tolist() == [
        "New sector A",
        "New sector B",
        "New sector A",
        "New sector B",
    ]
    assert sorted(master["Inventory sheet"].tolist()) == [
        "INV_001",
        "INV_002",
        "INV_003",
        "INV_004",
    ]
    for sheet_name in master["Inventory sheet"].tolist():
        assert sheet_name in workbook


def test_get_add_sectors_excel_can_write_empty_workbook(tmp_path, CoreDataIOT):
    path = tmp_path / "empty_add_sector_iot.xlsx"

    CoreDataIOT.get_add_sectors_excel(path=path)

    workbook = pd.read_excel(path, sheet_name=None)
    assert ADVANCED_ADD_SECTOR_MASTER_SHEET in workbook
    assert workbook[ADVANCED_ADD_SECTOR_MASTER_SHEET].empty


def test_get_add_sectors_excel_accepts_positional_path(tmp_path, CoreDataIOT):
    path = tmp_path / "positional_add_sector_iot.xlsx"

    CoreDataIOT.get_add_sectors_excel(path)

    workbook = pd.read_excel(path, sheet_name=None)
    assert ADVANCED_ADD_SECTOR_MASTER_SHEET in workbook


def test_get_add_sectors_excel_uses_all_regions_when_only_items_are_given(tmp_path, CoreDataIOT):
    path = tmp_path / "prefilled_all_regions_iot.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["New sector"],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET)
    assert sorted(master[_MASTER_INDEX["r"]].tolist()) == sorted(CoreDataIOT.get_index(_MASTER_INDEX["r"]))


def test_read_advanced_add_sector_workbook_roundtrip_parses_metadata(tmp_path, CoreDataIOT):
    regions = CoreDataIOT.get_index(_MASTER_INDEX["r"])[:2]
    path = tmp_path / "advanced_add_sector_iot.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["New sector A", "New sector B"],
        regions=regions,
        path=path,
        redefine_uncertainties=True,
    )

    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        pd.DataFrame({"GLOBAL": regions, "EU": [regions[0], ""]}).to_excel(
            writer,
            sheet_name=ADVANCED_ADD_SECTOR_REGIONS_CLUSTERS_SHEET,
            index=False,
        )
        pd.DataFrame({"Cluster1": [CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]]}).to_excel(
            writer,
            sheet_name=ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_SHEET["IOT"],
            index=False,
        )
        pd.DataFrame(
            {
                "Inventory data categories": ["certain", "no info"],
                "New uncertainty values": [0.88, 0.22],
            }
        ).to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_UNCERTAINTIES_SHEET, index=False)
        pd.DataFrame(
            [
                {
                    "Quantity": 1,
                    "Unit": CoreDataIOT.units[_MASTER_INDEX["s"]].iloc[0, 0],
                    "Input": "demo input",
                    "Item type": _MASTER_INDEX["s"],
                    "DB Item": CoreDataIOT.get_index(_MASTER_INDEX["s"])[0],
                    "DB Region": regions[0],
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "note",
                }
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    workbook = read_advanced_add_sector_workbook(path, table="IOT")
    derived = derive_advanced_add_sector_sets(
        workbook,
        existing_sectors=CoreDataIOT.get_index(_MASTER_INDEX["s"]),
    )
    grouped = group_advanced_inventories_by_target(workbook)

    assert workbook.regions_clusters["GLOBAL"] == regions
    assert workbook.regions_clusters["EU"] == regions[:1]
    assert workbook.item_clusters["Cluster1"] == [CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]]
    assert workbook.uncertainty_values["certain"] == 0.88
    assert workbook.inventories_by_sheet["INV_001"].iloc[0]["DB Item"] == CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]
    assert derived["new_sectors"] == ["New sector A", "New sector B"]
    assert derived["to_split_sectors"] == []
    assert list(grouped) == ["New sector A", "New sector B"]
    assert "INV_001" in grouped["New sector A"]


def test_get_add_sectors_excel_supports_advanced_sut_workbook(tmp_path, CoreDataSUT):
    region = CoreDataSUT.get_index(_MASTER_INDEX["r"])[0]
    path = tmp_path / "advanced_add_sector_sut.xlsx"

    CoreDataSUT.get_add_sectors_excel(
        items=["New activity"],
        regions=[region],
        path=path,
        item=_MASTER_INDEX["a"],
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET)
    assert master[_MASTER_INDEX["a"]].tolist() == ["New activity"]
    assert master[_MASTER_INDEX["c"]].fillna("").tolist() == [""]


def test_get_add_sectors_excel_sut_defaults_to_activity_and_commodity(tmp_path, CoreDataSUT):
    region = CoreDataSUT.get_index(_MASTER_INDEX["r"])[0]
    path = tmp_path / "advanced_add_sector_sut_default.xlsx"

    CoreDataSUT.get_add_sectors_excel(
        items=["New item"],
        regions=[region],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET)
    assert master[_MASTER_INDEX["a"]].tolist() == ["New item"]
    assert master[_MASTER_INDEX["c"]].tolist() == ["New item"]


def test_database_can_attach_advanced_add_sector_workbook_state(tmp_path, CoreDataIOT):
    regions = CoreDataIOT.get_index(_MASTER_INDEX["r"])[:2]
    path = tmp_path / "advanced_add_sector_iot.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["New sector A", "New sector B"],
        regions=regions,
        path=path,
        redefine_uncertainties=True,
    )

    CoreDataIOT.read_add_sectors_excel(path)

    assert hasattr(CoreDataIOT, "add_sectors_workbook")
    assert CoreDataIOT.regions_clusters["GLOBAL"] == CoreDataIOT.get_index(_MASTER_INDEX["r"])
    assert CoreDataIOT.new_sectors == ["New sector A", "New sector B"]
    assert not hasattr(CoreDataIOT, "inventories")


def test_database_can_attach_inventories_via_read_add_sectors_excel(tmp_path, CoreDataIOT):
    regions = CoreDataIOT.get_index(_MASTER_INDEX["r"])[:2]
    path = tmp_path / "advanced_add_sector_iot_with_inventories.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["New sector A", "New sector B"],
        regions=regions,
        path=path,
    )

    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        pd.DataFrame(
            [
                {
                    "Quantity": 1,
                    "Unit": CoreDataIOT.units[_MASTER_INDEX["s"]].iloc[0, 0],
                    "Input": "demo input",
                    "Item type": _MASTER_INDEX["s"],
                    "DB Item": CoreDataIOT.get_index(_MASTER_INDEX["s"])[0],
                    "DB Region": regions[0],
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "note",
                }
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    ret = CoreDataIOT.read_add_sectors_excel(path, read_inventories=True)

    assert ret is None
    assert set(CoreDataIOT.inventories) == {"New sector A", "New sector B"}


def test_database_can_group_inventories_from_advanced_workbook(tmp_path, CoreDataIOT):
    regions = CoreDataIOT.get_index(_MASTER_INDEX["r"])[:2]
    path = tmp_path / "advanced_add_sector_iot.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["New sector A", "New sector B"],
        regions=regions,
        path=path,
    )

    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        pd.DataFrame(
            [
                {
                    "Quantity": 1,
                    "Unit": CoreDataIOT.units[_MASTER_INDEX["s"]].iloc[0, 0],
                    "Input": "demo input",
                    "Item type": _MASTER_INDEX["s"],
                    "DB Item": CoreDataIOT.get_index(_MASTER_INDEX["s"])[0],
                    "DB Region": regions[0],
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "note",
                }
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    inventories = CoreDataIOT.read_inventory_sheets(path)
    assert "New sector A" in inventories
    assert inventories["New sector A"]["INV_001"].iloc[0]["Input"] == "demo input"


def test_add_sectors_advanced_engine_adds_iot_sector_from_workbook(tmp_path, CoreDataIOT):
    region = CoreDataIOT.get_index(_MASTER_INDEX["r"])[0]
    existing_sector = CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]
    factor = CoreDataIOT.get_index(_MASTER_INDEX["f"])[0]
    satellite = CoreDataIOT.get_index(_MASTER_INDEX["k"])[0]
    unit = CoreDataIOT.units[_MASTER_INDEX["s"]].loc[existing_sector, "unit"]
    path = tmp_path / "advanced_iot.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["New sector"],
        regions=[region],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET)
    master = master.astype(object)
    master.loc[0, "Unit"] = unit
    master.loc[0, "Parent Sector"] = existing_sector
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False)
        pd.DataFrame(
            [
                {
                    "Quantity": 0.25,
                    "Unit": unit,
                    "Input": "input row",
                    "Item type": _MASTER_INDEX["s"],
                    "DB Item": existing_sector,
                    "DB Region": region,
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "",
                },
                {
                    "Quantity": 0.1,
                    "Unit": CoreDataIOT.units[_MASTER_INDEX["f"]].loc[factor, "unit"],
                    "Input": "factor row",
                    "Item type": _MASTER_INDEX["f"],
                    "DB Item": factor,
                    "DB Region": "",
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "",
                },
                {
                    "Quantity": 0.2,
                    "Unit": CoreDataIOT.units[_MASTER_INDEX["k"]].loc[satellite, "unit"],
                    "Input": "sat row",
                    "Item type": _MASTER_INDEX["k"],
                    "DB Item": satellite,
                    "DB Region": "",
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "",
                },
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    new = CoreDataIOT.add_sectors(io=path, inplace=False)

    assert "New sector" in new.get_index(_MASTER_INDEX["s"])
    assert new.units[_MASTER_INDEX["s"]].loc["New sector", "unit"] == unit
    assert new.z.loc[(region, _MASTER_INDEX["s"], existing_sector), (region, _MASTER_INDEX["s"], "New sector")] == pytest.approx(0.25)
    assert new.v.loc[factor, (region, _MASTER_INDEX["s"], "New sector")] == pytest.approx(0.1)
    assert new.e.loc[satellite, (region, _MASTER_INDEX["s"], "New sector")] == pytest.approx(0.2)
    assert hasattr(new, "uncertainty_matrix")
    assert new.uncertainty_matrix.loc[(region, _MASTER_INDEX["s"], existing_sector), (region, _MASTER_INDEX["s"], "New sector")] == 1


def test_add_sectors_advanced_engine_adds_sut_activity_and_commodity(tmp_path, CoreDataSUT):
    region = CoreDataSUT.get_index(_MASTER_INDEX["r"])[0]
    existing_activity = CoreDataSUT.get_index(_MASTER_INDEX["a"])[0]
    existing_commodity = CoreDataSUT.get_index(_MASTER_INDEX["c"])[0]
    unit = CoreDataSUT.units[_MASTER_INDEX["a"]].loc[existing_activity, "unit"]
    path = tmp_path / "advanced_sut.xlsx"

    CoreDataSUT.get_add_sectors_excel(
        items=["New activity"],
        regions=[region],
        path=path,
        item=_MASTER_INDEX["a"],
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET)
    master = master.astype(object)
    master.loc[0, "Commodity"] = "New commodity"
    master.loc[0, "Unit"] = unit
    master.loc[0, "Parent Activity"] = existing_activity
    master.loc[0, "Market share"] = 1.0
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False)
        pd.DataFrame(
            [
                {
                    "Quantity": 0.4,
                    "Unit": CoreDataSUT.units[_MASTER_INDEX["c"]].loc[existing_commodity, "unit"],
                    "Input": "commodity row",
                    "Item type": _MASTER_INDEX["c"],
                    "DB Item": existing_commodity,
                    "DB Region": region,
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "",
                }
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    new = CoreDataSUT.add_sectors(io=path, inplace=False)

    assert "New activity" in new.get_index(_MASTER_INDEX["a"])
    assert "New commodity" in new.get_index(_MASTER_INDEX["c"])
    assert new.units[_MASTER_INDEX["a"]].loc["New activity", "unit"] == unit
    assert new.units[_MASTER_INDEX["c"]].loc["New commodity", "unit"] == unit
    assert new.u.loc[(region, _MASTER_INDEX["c"], existing_commodity), (region, _MASTER_INDEX["a"], "New activity")] == pytest.approx(0.4)
    assert new.s.loc[(region, _MASTER_INDEX["a"], "New activity"), (region, _MASTER_INDEX["c"], "New commodity")] == pytest.approx(1.0)


def test_add_sectors_advanced_engine_honors_leave_empty_iot(tmp_path, CoreDataIOT):
    region = CoreDataIOT.get_index(_MASTER_INDEX["r"])[0]
    existing_sector = CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]
    unit = CoreDataIOT.units[_MASTER_INDEX["s"]].loc[existing_sector, "unit"]
    path = tmp_path / "advanced_iot_leave_empty.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["Empty sector"],
        regions=[region],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET).astype(object)
    master.loc[0, "Unit"] = unit
    master.loc[0, "Leave empty"] = True
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False)

    new = CoreDataIOT.add_sectors(io=path, inplace=False)
    new_col = (region, _MASTER_INDEX["s"], "Empty sector")
    new_row = (region, _MASTER_INDEX["s"], "Empty sector")

    assert new.z.loc[:, new_col].sum() == pytest.approx(0.0)
    assert new.z.loc[new_row, :].sum() == pytest.approx(0.0)


def test_add_sectors_advanced_engine_supports_percentage_updates_iot(tmp_path, CoreDataIOT):
    region = CoreDataIOT.get_index(_MASTER_INDEX["r"])[0]
    parent_sector = CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]
    unit = CoreDataIOT.units[_MASTER_INDEX["s"]].loc[parent_sector, "unit"]
    parent_column = CoreDataIOT.z.loc[:, (region, _MASTER_INDEX["s"], parent_sector)]
    nonzero_rows = parent_column[parent_column != 0]
    target_row = nonzero_rows.index[0]
    untouched_row = nonzero_rows.index[1]
    path = tmp_path / "advanced_iot_percentage.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["Scaled sector"],
        regions=[region],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET).astype(object)
    master.loc[0, "Unit"] = unit
    master.loc[0, "Parent Sector"] = parent_sector
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False)
        pd.DataFrame(
            [
                {
                    "Quantity": 0.5,
                    "Unit": unit,
                    "Input": "scaled row",
                    "Item type": _MASTER_INDEX["s"],
                    "DB Item": target_row[2],
                    "DB Region": target_row[0],
                    "Change type": "Percentage",
                    "Source": "test",
                    "Notes": "",
                }
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    new = CoreDataIOT.add_sectors(io=path, inplace=False)
    new_col = (region, _MASTER_INDEX["s"], "Scaled sector")

    assert new.z.loc[target_row, new_col] == pytest.approx(parent_column.loc[target_row] * 1.5)
    assert new.z.loc[untouched_row, new_col] == pytest.approx(parent_column.loc[untouched_row])


def test_add_sectors_advanced_engine_supports_region_cluster_updates_iot(tmp_path, CoreDataIOT):
    target_region = CoreDataIOT.get_index(_MASTER_INDEX["r"])[0]
    parent_sector = CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]
    sector_candidates = CoreDataIOT.get_index(_MASTER_INDEX["s"])
    unit = CoreDataIOT.units[_MASTER_INDEX["s"]].loc[parent_sector, "unit"]
    chosen_sector = None
    for sector in sector_candidates:
        series = CoreDataIOT.Z.loc[
            (slice(None), _MASTER_INDEX["s"], sector),
            (target_region, _MASTER_INDEX["s"], parent_sector),
        ]
        if (series > 0).sum() >= 2:
            chosen_sector = sector
            break
    assert chosen_sector is not None
    path = tmp_path / "advanced_iot_cluster.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["Clustered sector"],
        regions=[target_region],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET).astype(object)
    master.loc[0, "Unit"] = unit
    master.loc[0, "Parent Sector"] = parent_sector
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False)
        pd.DataFrame(
            [
                {
                    "Quantity": 10.0,
                    "Unit": unit,
                    "Input": "cluster row",
                    "Item type": _MASTER_INDEX["s"],
                    "DB Item": chosen_sector,
                    "DB Region": "GLOBAL",
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "",
                }
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    new = CoreDataIOT.add_sectors(io=path, inplace=False)
    new_col = (target_region, _MASTER_INDEX["s"], "Clustered sector")
    allocated = new.z.loc[(slice(None), _MASTER_INDEX["s"], chosen_sector), new_col]
    assert allocated.sum() == pytest.approx(10.0)
    assert (allocated > 0).sum() >= 2


def test_add_sectors_advanced_engine_converts_satellite_units_iot(tmp_path, CoreDataIOT):
    region = CoreDataIOT.get_index(_MASTER_INDEX["r"])[0]
    parent_sector = CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]
    sector_unit = CoreDataIOT.units[_MASTER_INDEX["s"]].loc[parent_sector, "unit"]
    satellite = CoreDataIOT.units[_MASTER_INDEX["k"]].query("unit == 'TJ'").index[0]
    path = tmp_path / "advanced_iot_units.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["Converted sector"],
        regions=[region],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET).astype(object)
    master.loc[0, "Unit"] = sector_unit
    master.loc[0, "Parent Sector"] = parent_sector
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False)
        pd.DataFrame(
            [
                {
                    "Quantity": 1000.0,
                    "Unit": "GJ",
                    "Input": "converted energy",
                    "Item type": _MASTER_INDEX["k"],
                    "DB Item": satellite,
                    "DB Region": "",
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "",
                }
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    new = CoreDataIOT.add_sectors(io=path, inplace=False)
    new_col = (region, _MASTER_INDEX["s"], "Converted sector")

    assert new.e.loc[satellite, new_col] == pytest.approx(1.0)


def test_add_sectors_advanced_engine_supports_item_cluster_updates_iot(tmp_path, CoreDataIOT):
    region = CoreDataIOT.get_index(_MASTER_INDEX["r"])[0]
    parent_sector = CoreDataIOT.get_index(_MASTER_INDEX["s"])[0]
    sector_unit = CoreDataIOT.units[_MASTER_INDEX["s"]].loc[parent_sector, "unit"]
    positive_inputs = []
    for sector in CoreDataIOT.get_index(_MASTER_INDEX["s"]):
        total = CoreDataIOT.Z.loc[
            (region, _MASTER_INDEX["s"], sector),
            (region, slice(None), slice(None)),
        ].sum()
        if total > 0:
            positive_inputs.append(sector)
        if len(positive_inputs) == 2:
            break

    assert len(positive_inputs) == 2
    path = tmp_path / "advanced_iot_item_cluster.xlsx"

    CoreDataIOT.get_add_sectors_excel(
        items=["Cluster sector"],
        regions=[region],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET).astype(object)
    master.loc[0, "Unit"] = sector_unit
    master.loc[0, "Parent Sector"] = parent_sector
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False)
        pd.DataFrame({"Bundle": positive_inputs}).to_excel(
            writer,
            sheet_name=ADVANCED_ADD_SECTOR_ITEMS_CLUSTERS_SHEET["IOT"],
            index=False,
        )
        pd.DataFrame(
            [
                {
                    "Quantity": 10.0,
                    "Unit": sector_unit,
                    "Input": "clustered input",
                    "Item type": _MASTER_INDEX["s"],
                    "DB Item": "Bundle",
                    "DB Region": region,
                    "Change type": "Update",
                    "Source": "test",
                    "Notes": "",
                }
            ]
        ).to_excel(writer, sheet_name="INV_001", index=False)

    new = CoreDataIOT.add_sectors(io=path, inplace=False)
    new_col = (region, _MASTER_INDEX["s"], "Cluster sector")
    allocated = new.z.loc[(region, _MASTER_INDEX["s"], positive_inputs), new_col]

    assert allocated.sum() == pytest.approx(10.0)
    assert (allocated > 0).sum() == 2


def test_add_sectors_advanced_engine_supports_sut_final_demand_from_master(tmp_path, CoreDataSUT):
    region = CoreDataSUT.get_index(_MASTER_INDEX["r"])[0]
    new_item = "Demanded item"
    activity_unit = CoreDataSUT.units[_MASTER_INDEX["a"]].iloc[0, 0]
    final_demand = CoreDataSUT.get_index(_MASTER_INDEX["n"])[0]
    path = tmp_path / "advanced_sut_final_demand.xlsx"

    CoreDataSUT.get_add_sectors_excel(
        items=[new_item],
        regions=[region],
        path=path,
    )

    master = pd.read_excel(path, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET).astype(object)
    master.loc[0, "Unit"] = activity_unit
    master.loc[0, "Market share"] = 0.75
    master.loc[0, "Final consumption"] = 2.5
    master.loc[0, _MASTER_INDEX["n"]] = final_demand
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        master.to_excel(writer, sheet_name=ADVANCED_ADD_SECTOR_MASTER_SHEET, index=False)

    new = CoreDataSUT.add_sectors(io=path, inplace=False)
    new_supply_row = (region, _MASTER_INDEX["a"], new_item)
    new_use_row = (region, _MASTER_INDEX["c"], new_item)
    final_demand_col = (region, _MASTER_INDEX["n"], final_demand)

    assert new.s.loc[new_supply_row, new_use_row] == pytest.approx(0.75)
    assert new.Y.loc[new_use_row, final_demand_col] == pytest.approx(2.5)

    
