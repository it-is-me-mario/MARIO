from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
from scipy.io import savemat

import mario
from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.parsers.emerging import detect_emerging_layout, parse_emerging_iot


def _write_ref_list(handle: h5py.File, group: h5py.Group, name: str, values: list[str]) -> None:
    """Write one MATLAB-like cellstr list as HDF5 object references."""
    refs_group = handle.require_group("#refs#")
    refs = np.empty((1, len(values)), dtype=h5py.ref_dtype)
    for idx, value in enumerate(values):
        data = np.array([[ord(char)] for char in value], dtype=np.uint16)
        dataset = refs_group.create_dataset(f"{name}_{idx}", data=data)
        refs[0, idx] = dataset.ref
    group.create_dataset(name, data=refs, dtype=h5py.ref_dtype)


def _write_emerging_bundle(root: Path, *, year: int = 2018) -> tuple[Path, Path, Path]:
    """Write one compact EMERGING-like local bundle."""
    root.mkdir(parents=True, exist_ok=True)
    main_path = root / f"EMERGING_V2_{year}.mat"
    co2_path = root / f"EMERGING_CO2_{year}_IEA.mat"
    labels_path = root / "EMERGING2.5_Sector&Country list.xlsx"

    with h5py.File(main_path, "w") as handle:
        group = handle.create_group(f"EMERGING_V2_{year}")
        z = np.array(
            [
                [1.0, 0.0, 2.0, 0.0],
                [0.0, 3.0, 0.0, 4.0],
                [5.0, 0.0, 6.0, 0.0],
                [0.0, 7.0, 0.0, 8.0],
            ]
        )
        f = np.array(
            [
                [10.0, 11.0, 12.0, 13.0],
                [20.0, 21.0, 22.0, 23.0],
                [30.0, 31.0, 32.0, 33.0],
                [40.0, 41.0, 42.0, 43.0],
                [50.0, 51.0, 52.0, 53.0],
                [60.0, 61.0, 62.0, 63.0],
            ]
        )
        va = np.array([[100.0, 101.0, 102.0, 103.0]])
        X = np.array([[111.0, 112.0, 113.0, 114.0]])

        group.create_dataset("z", data=z)
        group.create_dataset("f", data=f)
        group.create_dataset("va", data=va)
        group.create_dataset("X", data=X)
        _write_ref_list(handle, group, "country_list", ["AAA", "BBB"])
        _write_ref_list(handle, group, "sector_list", ["01 sector one", "02 sector two"])
        _write_ref_list(handle, group, "final_list", ["household", "government", "capital"])

    savemat(
        co2_path,
        {
            "CO2": np.array(
                [
                    [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
                    [11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0],
                    [21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0],
                    [31.0, 32.0, 33.0, 34.0, 35.0, 36.0, 37.0],
                ]
            )
        },
    )

    with pd.ExcelWriter(labels_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Code": [1, 2],
                "Sector": ["Sector One", "Sector Two"],
            }
        ).to_excel(writer, sheet_name="Sector", index=False)
        pd.DataFrame(
            {
                "Number": [1, 2],
                "Country": ["Alpha", "Beta"],
                "ISO3": ["AAA", "BBB"],
            }
        ).to_excel(writer, sheet_name="Country", index=False)

    return main_path, co2_path, labels_path


def test_parse_emerging_iot_reads_iot_blocks_and_co2(tmp_path):
    main_path, _, _ = _write_emerging_bundle(tmp_path)

    matrices, indeces, units, layout = parse_emerging_iot(main_path)
    base = matrices["baseline"]

    assert layout.year == 2018
    assert layout.co2_path is not None
    assert base["Z"].shape == (4, 4)
    assert base["Y"].shape == (4, 6)
    assert base["V"].shape == (1, 4)
    assert base["E"].shape == (7, 4)
    assert base["EY"].shape == (7, 6)
    assert indeces["r"]["main"] == ["AAA", "BBB"]
    assert indeces["s"]["main"] == ["Sector One", "Sector Two"]
    assert indeces["n"]["main"] == ["household", "government", "capital"]
    assert list(base["V"].index) == ["Value added at basic prices"]
    assert float(base["Y"].iloc[0, 0]) == 10.0
    assert float(base["E"].iloc[0, 0]) == 1.0
    assert units["Satellite account"].iloc[0, 0] == "Mt CO2eq"


def test_parse_emerging_iot_supports_region_subset_and_placeholder_satellites(tmp_path):
    main_path, _, _ = _write_emerging_bundle(tmp_path)

    matrices, indeces, units, _ = parse_emerging_iot(main_path, regions=["BBB"], load_co2=False)
    base = matrices["baseline"]

    assert base["Z"].shape == (2, 2)
    assert base["Y"].shape == (2, 3)
    assert base["V"].shape == (1, 2)
    assert base["E"].shape == (1, 2)
    assert indeces["r"]["main"] == ["BBB"]
    assert list(base["E"].index) == ["-"]
    assert units["Satellite account"].iloc[0, 0] == "None"


def test_detect_emerging_layout_requires_year_when_directory_contains_multiple_bundles(tmp_path):
    _write_emerging_bundle(tmp_path / "2018", year=2018)
    _write_emerging_bundle(tmp_path / "2019", year=2019)

    with pytest.raises(WrongInput):
        detect_emerging_layout(tmp_path)

    layout = detect_emerging_layout(tmp_path, year=2019)
    assert layout.year == 2019


def test_public_parse_emerging_returns_database_and_validates_table(tmp_path):
    main_path, _, _ = _write_emerging_bundle(tmp_path)

    database = mario.parse_emerging(str(main_path), calc_all=False)

    assert database.table_type == "IOT"
    assert database.meta.year == 2018
    assert database.meta.name == "EMERGING 2018"
    assert "zenodo" in database.meta.source.lower()
    assert "Huo, J." in database.meta.source
    assert database.Z.shape == (4, 4)
    assert database.Y.shape == (4, 6)
    assert database.V.shape == (1, 4)
    assert database.E.shape == (7, 4)
    assert "Zenodo" in mario.parse_emerging.__doc__

    with pytest.raises(NotImplementable):
        mario.parse_emerging(str(main_path), table="SUT", calc_all=False)
