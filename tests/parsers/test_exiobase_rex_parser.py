from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
from scipy.io import savemat

import mario
from mario.log_exc.exceptions import WrongFormat, WrongInput
from mario.parsers.exiobase_rex import REX3_GHG_LABELS, detect_rex3_layout, parse_rex3_iot


@pytest.fixture(autouse=True)
def isolated_compute(isolated_session_settings):
    """Parser presets must not leak into other test modules."""


def _write_cellstr(path: Path, dataset_name: str, values: np.ndarray) -> None:
    values = np.asarray(values, dtype=object)
    with h5py.File(path, "w") as handle:
        refs_group = handle.create_group("#refs#")
        references = np.empty(values.shape, dtype=h5py.ref_dtype)
        for number, (index, value) in enumerate(np.ndenumerate(values)):
            encoded = np.array(
                [[ord(character)] for character in str(value)], dtype=np.uint16
            )
            dataset = refs_group.create_dataset(f"value_{number}", data=encoded)
            references[index] = dataset.ref
        handle.create_dataset(dataset_name, data=references, dtype=h5py.ref_dtype)


def _write_v73_numeric(path: Path, dataset_name: str, values: np.ndarray) -> None:
    with h5py.File(path, "w") as handle:
        handle.create_dataset(dataset_name, data=np.asarray(values, dtype=float).T)


def _write_rex3_bundle(root: Path, *, year: int = 1995) -> dict[str, np.ndarray]:
    year_dir = root / f"REX3_{year}"
    labels_dir = root / "REX3_Labels"
    ghg_dir = root / "GHG_data_REX3"
    ghg_labels_dir = ghg_dir / "Labels"
    for directory in (year_dir, labels_dir, ghg_labels_dir):
        directory.mkdir(parents=True)

    countries = ["Alpha", "Beta"]
    sectors = ["Sector one", "Sector two"]
    transaction_labels = np.vstack(
        [np.repeat(countries, len(sectors)), np.tile(sectors, len(countries))]
    )
    _write_cellstr(
        labels_dir / "Labels_Countries_REX3.mat",
        "Labels_Countries_REX3",
        np.asarray([countries], dtype=object),
    )
    _write_cellstr(
        labels_dir / "Labels_Sectors_REX3.mat",
        "Labels_Sectors_REX3",
        np.asarray([[*sectors, "Households"]], dtype=object),
    )
    _write_cellstr(
        labels_dir / "Labels_T_REX3.mat",
        "Labels_T_REX3",
        transaction_labels,
    )
    q_labels = np.asarray(
        [
            [
                "Climate change impacts [kg CO2-eq]",
                "Material footprint [kt]",
                "Value added [Mio Euro]",
            ]
        ],
        dtype=object,
    )
    _write_cellstr(labels_dir / "Labels_Q_REX3.mat", "Labels_Q_REX3", q_labels)

    T = np.array(
        [
            [1.0, 2.0, 30.0, 40.0],
            [5.0, 6.0, 70.0, 80.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ]
    )
    Y = np.array(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
            [4.0, 40.0],
        ]
    )
    Q = np.array(
        [
            [100.0, 200.0, 300.0, 400.0],
            [10.0, 20.0, 30.0, 40.0],
            [50.0, 60.0, 70.0, 80.0],
        ]
    )
    QY = np.array(
        [
            [7.0, 8.0],
            [9.0, 10.0],
            [0.0, 0.0],
        ]
    )
    for name, values in (("T_REX3", T), ("Y_REX3", Y), ("Q_REX3", Q), ("Q_Y_REX3", QY)):
        _write_v73_numeric(year_dir / f"{name}.mat", name, values)

    combinations = np.empty((len(transaction_labels[0]), 2), dtype=object)
    combinations[:, 0] = transaction_labels[0]
    combinations[:, 1] = transaction_labels[1]
    savemat(
        ghg_labels_dir / "Labels_Countrysector_combinations.mat",
        {"Labels_Countrysector_combinations": combinations},
    )
    savemat(ghg_labels_dir / "Labels_years.mat", {"Labels_years": np.array([[year]])})

    d_cc = np.stack(
        [np.full(len(transaction_labels[0]), factor / 10.0) for factor in range(1, 7)]
    )[:, :, np.newaxis]
    lulucf = np.array([[101.0], [102.0], [103.0], [104.0]])
    qy_lulucf = np.array([[201.0], [202.0]])
    savemat(ghg_dir / "d_CC_REX3_timeline.mat", {"d_CC_REX3_timeline": d_cc})
    savemat(
        ghg_dir / "Q_LULUCF_REX3_timeline.mat",
        {"Q_LULUCF_REX3_timeline": lulucf},
    )
    savemat(
        ghg_dir / "Q_Y_LULUCF_REX3_timeline.mat",
        {"Q_Y_LULUCF_REX3_timeline": qy_lulucf},
    )
    return {"T": T, "Y": Y, "Q": Q, "QY": QY, "d_cc": d_cc, "lulucf": lulucf}


def test_parse_rex3_reconstructs_ghg_for_complete_mrio(tmp_path):
    source = _write_rex3_bundle(tmp_path)

    matrices, indexes, units, layout = parse_rex3_iot(tmp_path, year=1995)

    blocks = matrices["baseline"]
    assert not any(isinstance(dtype, pd.SparseDtype) for dtype in blocks["Z"].dtypes)
    np.testing.assert_allclose(blocks["Z"], source["T"])
    np.testing.assert_allclose(blocks["Y"], source["Y"])
    np.testing.assert_allclose(blocks["V"], source["Q"][[2], :])

    full_output = source["T"].sum(axis=1) + source["Y"].sum(axis=1)
    for position, label in enumerate(REX3_GHG_LABELS[:5]):
        np.testing.assert_allclose(
            blocks["E"].loc[label].to_numpy(dtype=float),
            source["d_cc"][position, :, 0] * full_output,
        )
    np.testing.assert_allclose(
        blocks["E"].loc[REX3_GHG_LABELS[-1]].to_numpy(dtype=float),
        source["lulucf"][:, 0],
    )
    assert blocks["EY"].loc[REX3_GHG_LABELS[0]].sum() == 0
    np.testing.assert_allclose(
        blocks["EY"].loc[REX3_GHG_LABELS[-1]],
        [201.0, 202.0],
    )
    assert indexes["r"]["main"] == ["Alpha", "Beta"]
    assert len(indexes["k"]["main"]) == 8
    assert units["Satellite account"].loc[REX3_GHG_LABELS[0], "unit"] == "kg CO2-eq"
    assert layout.year == 1995


def test_public_rex3_entrypoints_build_database(tmp_path):
    _write_rex3_bundle(tmp_path)

    direct = mario.parse_exiobase_rex(
        str(tmp_path),
        year=1995,
        calc_all=False,
    )
    dispatched = mario.parse_exiobase(
        table="IOT",
        unit="Monetary",
        path=str(tmp_path),
        year=1995,
        variant="REX3",
        calc_all=False,
    )

    assert direct.meta.name == "EXIOBASE REX3 1995"
    assert dispatched.meta.name == direct.meta.name
    assert direct.get_index("Region") == ["Alpha", "Beta"]
    assert REX3_GHG_LABELS[-1] in direct.get_index("Satellite account")


def test_public_rex3_parser_rejects_region_slicing(tmp_path):
    _write_rex3_bundle(tmp_path)

    with pytest.raises(WrongInput, match="complete 189-region MRIO"):
        mario.parse_exiobase_rex(
            str(tmp_path),
            year=1995,
            regions=["Alpha"],
            calc_all=False,
        )


def versioned_bundle(root, year=2022):
    economic = root / 'Version REX3 database'
    ghg = root / 'Version GHG extension (+LULUCF)'
    source = _write_rex3_bundle(economic, year=year)
    ghg.mkdir()
    (economic / 'GHG_data_REX3').rename(ghg / 'GHG_data_REX3')
    return economic, ghg, source


@pytest.mark.parametrize('entry', ['root', 'economic', 'year', 'explicit'])
def test_2022_in_separate_zenodo_version_directories(tmp_path, entry):
    economic, ghg, source = versioned_bundle(tmp_path)
    paths = {'root': tmp_path, 'economic': economic,
             'year': economic / 'REX3_2022', 'explicit': economic / 'REX3_2022'}
    kwargs = {'labels_path': economic, 'ghg_path': ghg} if entry == 'explicit' else {}
    db = mario.parse_exiobase(path=paths[entry], table='IOT', unit='Monetary',
                             variant='REX3', year=2022, calc_all=False, **kwargs)
    np.testing.assert_array_equal(db.query('Z'), source['T'])
    np.testing.assert_array_equal(db.query('Y'), source['Y'])
    assert db.meta.year == 2022
    profile = db.database_profile
    assert profile['id'] == 'rex3'
    assert profile['ghg']['selected_profile'] == 'rex3'
    assert profile['compute']['parser_presets']['exiobase_rex']['compute_method'] == 'solve'
    assert not profile['concordances']['supported']


def test_detailed_ghg_sum_does_not_double_count_native_aggregate(tmp_path):
    _write_rex3_bundle(tmp_path, year=2022)
    db = mario.parse_exiobase_rex(tmp_path, year=2022)
    e, ey = db.query('E').copy(), db.query('EY').copy()
    db.calc_ghg(label='GHG detailed sources')
    np.testing.assert_allclose(db.query('E').loc['GHG detailed sources'], e.loc[list(REX3_GHG_LABELS)].sum())
    np.testing.assert_allclose(db.query('EY').loc['GHG detailed sources'], ey.loc[list(REX3_GHG_LABELS)].sum())
    db.calc_ghg(label='GHG unchanged basis', ipcc_report='AR4')
    np.testing.assert_allclose(db.query('E').loc['GHG unchanged basis'], db.query('E').loc['GHG detailed sources'])


def test_published_lulucf_survives_zero_output(tmp_path):
    source = _write_rex3_bundle(tmp_path)
    source['T'][0, :] = 0
    source['T'][:, 0] = 0
    source['Y'][0, :] = 0
    for name in ['T', 'Y']:
        _write_v73_numeric(tmp_path / 'REX3_1995' / f'{name}_REX3.mat', f'{name}_REX3', source[name])
    matrices, _, _, _ = parse_rex3_iot(tmp_path)
    e = matrices['baseline']['E']
    np.testing.assert_array_equal(e.loc[list(REX3_GHG_LABELS[:5])].iloc[:, 0], 0.)
    assert e.loc[REX3_GHG_LABELS[-1]].iloc[0] == 101.


@pytest.mark.parametrize('problem', ['missing', 'duplicate', 'misaligned', 'wrong_q_columns'])
def test_invalid_companions_and_dimensions_raise(tmp_path, problem):
    _write_rex3_bundle(tmp_path)
    if problem == 'missing':
        (tmp_path / 'GHG_data_REX3' / 'Labels' / 'Labels_years.mat').unlink()
    elif problem == 'duplicate':
        import shutil
        shutil.copytree(tmp_path / 'GHG_data_REX3', tmp_path / 'another_ghg')
    elif problem == 'misaligned':
        savemat(tmp_path / 'GHG_data_REX3' / 'Labels' / 'Labels_Countrysector_combinations.mat',
                {'Labels_Countrysector_combinations': np.array([['wrong', 'wrong']] * 4, dtype=object)})
    else:
        _write_v73_numeric(tmp_path / 'REX3_1995' / 'Q_REX3.mat', 'Q_REX3', np.zeros((3, 3)))
    with pytest.raises((WrongInput, WrongFormat)):
        parse_rex3_iot(tmp_path)


def test_multiple_years_need_selection_and_ghg_year_labels_are_used(tmp_path):
    import shutil
    _write_rex3_bundle(tmp_path, year=1995)
    shutil.copytree(tmp_path / 'REX3_1995', tmp_path / 'REX3_2022')
    with pytest.raises(WrongInput, match='More than one'):
        detect_rex3_layout(tmp_path)
    assert detect_rex3_layout(tmp_path, year=2022).year == 2022
    with pytest.raises(WrongFormat, match='Year 2022'):
        parse_rex3_iot(tmp_path, year=2022)


def test_explicit_year_supports_a_renamed_year_directory(tmp_path):
    _write_rex3_bundle(tmp_path, year=2022)
    target = tmp_path / 'annual_data'
    (tmp_path / 'REX3_2022').rename(target)
    assert parse_rex3_iot(target, year=2022)[-1].year == 2022


def test_local_zip_requires_extraction(tmp_path):
    archive = tmp_path / 'REX3_2022.zip'
    archive.touch()
    with pytest.raises(WrongInput, match='Extract'):
        detect_rex3_layout(archive, year=2022)


@pytest.mark.parametrize('companion', [False, True], ids=['web-guide', 'notebook'])
def test_published_2022_workflows_execute_without_network(tmp_path, monkeypatch, companion):
    import json
    from tests.docs.test_workflow_examples import python_blocks
    versioned_bundle(tmp_path)
    monkeypatch.setattr('mario.download.requests.get', lambda *a, **k: pytest.fail('Unexpected source download'))
    root = Path(__file__).resolve().parents[2]
    page = root / 'doc/source/notebooks/parsers/exiobase/rex3'
    if companion:
        notebook = json.loads(page.with_suffix('.ipynb').read_text())
        blocks = [''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code']
    else:
        blocks = [b for b in python_blocks(page.with_suffix('.rst')) if 'download_info' not in b]
    scope = {}
    for block in blocks:
        block = block.replace('Path("/path/to/REX3")', f'Path({str(tmp_path)!r})')
        exec(block, scope)
    db = scope['db']
    assert db.meta.year == 2022
    np.testing.assert_allclose(db.query('E').loc['GHG detailed sources'], db.query('E').loc[list(REX3_GHG_LABELS)].sum())
