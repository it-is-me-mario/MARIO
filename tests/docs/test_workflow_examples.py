"""Run published accounting and scenario recipes on small economic examples."""
import ast
import json
from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd
import pytest

import mario

ROOT = Path(__file__).resolve().parents[2] / 'doc/source/user_guide'


def python_blocks(path):
    lines = path.read_text().splitlines()
    blocks = []
    for start, line in enumerate(lines):
        if not line.strip().startswith('.. code-block:: python'):
            continue
        first = start + 1
        while first < len(lines) and not lines[first].strip():
            first += 1
        indent = len(lines[first]) - len(lines[first].lstrip())
        end = first
        while end < len(lines) and (not lines[end].strip()
                                   or len(lines[end]) - len(lines[end].lstrip()) >= indent):
            end += 1
        blocks.append(dedent('\n'.join(lines[first:end])))
    return blocks


def nam_notebook_cell(relative, ident):
    notebook = json.loads((ROOT.parent / relative).read_text())
    return ''.join(next(c for c in notebook['cells'] if c['id'] == ident)['source'])


@pytest.fixture
def nam_example(tmp_path):
    """Portable public workbook input with one income account paying three blocks."""
    from mario.internal.nam import NAMSchema

    members = {'IT': {'commodity': ['Goods'], 'activity': ['Industry'], 'factor': ['Labour'],
                      'income_resident': ['Households'], 'consumption': ['Household consumption'],
                      'distribution': ['Income taxes'], 'capital_resident': ['Households']}}
    units = {'currency': 'EUR', 'scale': 1_000_000, 'period': 2023}
    schema = NAMSchema(members, representation='use_imports', **units)
    source = tmp_path / 'nam_fixture.xlsx'
    mario.write_parse_template(source, table='NAM', sets=members, units=units,
                               block_states={n: 'declared_zero' for n in schema.required_flows()})
    nam = mario.parse_from_excel(source, table='NAM', mode='flows')
    for name, value in [('CF_d', 70.), ('TP_d', 20.), ('RS_dd', 10.)]:
        frame = nam.get_block(name)
        frame.iloc[0, 0] = value
        nam.set_block(name, frame)
    return nam


@pytest.mark.parametrize('companion', [False, True], ids=['web-guide', 'notebook'])
def test_nam_totals_recipe_uses_account_expenditure_across_blocks(nam_example, companion):
    if companion:
        code = nam_notebook_cell('notebooks/parsers/figaro/walkthrough_figaro.ipynb',
                                 'nam-account-coefficients')
    else:
        code = next(b for b in python_blocks(ROOT / 'inspection/compute_matrices.rst')
                    if 'totals = nam.resolve_many' in b)
    scope = {'nam': nam_example}
    exec(code, scope)
    assert nam_example.Xsi_d.iloc[0, 0] == pytest.approx(100.)
    assert scope['coefficients']['cf_d'].iloc[0, 0] == pytest.approx(.7)


@pytest.mark.parametrize('companion', [False, True], ids=['web-guide', 'notebook'])
def test_nam_scenario_recipe_keeps_baseline_and_recalculates_full_denominator(nam_example, companion):
    if companion:
        code = nam_notebook_cell('notebooks/parsers/figaro/walkthrough_figaro.ipynb',
                                 'nam-scenario-edit')
    else:
        code = next(b for b in python_blocks(ROOT.parent / 'get_started/scenarios.rst')
                    if 'nam.clone_scenario' in b)
    exec(code, {'nam': nam_example})
    assert nam_example.get_block('CF_d').iloc[0, 0] == pytest.approx(70.)
    assert nam_example.resolve('Xsi_d', scenario='alternative').iloc[0, 0] == pytest.approx(100.7)
    assert nam_example.resolve('cf_d', scenario='alternative').iloc[0, 0] == pytest.approx(70.7 / 100.7)


@pytest.mark.parametrize('companion', [False, True], ids=['web-guide', 'notebook'])
def test_nam_export_recipe_retains_scenarios_and_recomputes_coefficients(nam_example, tmp_path, monkeypatch, companion):
    monkeypatch.chdir(tmp_path)
    nam_example.clone_scenario('baseline', 'alternative')
    if companion:
        code = nam_notebook_cell('notebooks/parsers/figaro/walkthrough_figaro.ipynb', 'dc24b514')
    else:
        code = next(b for b in python_blocks(ROOT / 'inspection/export_and_roundtrip.rst')
                    if 'nam.to_excel' in b)
    scope = {'nam': nam_example, 'mario': mario}
    exec(code, scope)
    restored = scope['restored']
    assert restored.scenarios == ['baseline', 'alternative']
    assert restored.units == nam_example.units
    pd.testing.assert_frame_equal(restored.get_block('CF_d'), nam_example.get_block('CF_d'))
    assert restored.resolve('cf_d').iloc[0, 0] == pytest.approx(.7)


@pytest.mark.parametrize('companion', [False, True], ids=['web-guide', 'notebook'])
def test_nam_template_recipe_preserves_unknown_inputs(tmp_path, monkeypatch, companion):
    monkeypatch.chdir(tmp_path)
    if companion:
        code = nam_notebook_cell('user_guide/parsers/provide_your_database.ipynb', 'nam-workflow')
    else:
        code = next(b for b in python_blocks(ROOT / 'parsers/provide_your_database.rst')
                    if '"custom_nam.xlsx"' in b)
    scope = {'mario': mario}
    exec(code, scope)
    nam = scope['nam']
    assert nam.get_index('Region') == ['IT']
    assert nam.get_index('c') == ['Goods', 'Services']
    assert nam.list_matrices() == ()
    assert 'U' in nam.available_matrices()
    assert not nam.has_matrix('U')


def consumer_example():
    sectors = pd.MultiIndex.from_tuples([('A', 'Sector', 'Product'), ('B', 'Sector', 'Product')])
    fd = pd.MultiIndex.from_tuples([(r, 'Consumption category', c)
                                   for r in ('A', 'B') for c in ('Households', 'Government')])
    # Both regions produce, but all products are consumed in B. Household
    # emissions are reported separately in each consumer region.
    z = pd.DataFrame(0., index=sectors, columns=sectors)
    y = pd.DataFrame([[0., 0., 6., 4.], [0., 0., 12., 8.]], index=sectors, columns=fd)
    ghg = 'GHG AR5 GWP-100'
    e = pd.DataFrame([[10., 40.]], index=[ghg], columns=sectors)
    ey = pd.DataFrame([[1., 0., 1., 1.]], index=[ghg], columns=fd)
    v = pd.DataFrame([[10., 20.]], index=['VA'], columns=sectors)
    units = {name: pd.DataFrame({'unit': unit}, index=items) for name, items, unit in [
        ('Sector', ['Product'], 'EUR'), ('Satellite account', [ghg], 'kg'),
        ('Factor of production', ['VA'], 'EUR')]}
    return mario.Database(Z=z, Y=y, E=e, V=v, EY=ey, units=units, table='IOT', calc_all=False), ghg


@pytest.mark.parametrize('companion', [False, True], ids=['web-guide', 'notebook'])
def test_ghg_example_attributes_imports_to_consumers_and_adds_direct_emissions_once(companion):
    db, ghg = consumer_example()
    if companion:
        nb = json.loads((ROOT / 'examples/compare_ghg.ipynb').read_text())
        source = next(''.join(c['source']) for c in nb['cells'] if 'def ghg_rearrangement(' in ''.join(c['source']))
        helper = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                      and n.name == 'ghg_rearrangement')
        scope = {'pd': pd, 'ghg_label': ghg}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), '<notebook helper>', 'exec'), scope)
        result = scope['ghg_rearrangement'](db, 'Example', '1', 'IOT', 2020)
        pba = result.xs('PBA', level='accounting', axis=1).iloc[:, 0]
        cba = result.xs('CBA', level='accounting', axis=1).iloc[:, 0]
    else:
        code = next(b for b in python_blocks(ROOT / 'examples/compare_ghg.rst') if 'direct_fd =' in b)
        scope = {'db': db, 'ghg': ghg}
        exec(code, scope)
        pba, cba = scope['pba'], scope['cba']
    np.testing.assert_allclose(pba.loc[['A', 'B']], [11., 42.])
    np.testing.assert_allclose(cba.loc[['A', 'B']], [1., 52.])
    assert pba.sum() == pytest.approx(cba.sum())


@pytest.mark.parametrize('companion', [False, True], ids=['web-guide', 'notebook'])
def test_electricity_recipe_keeps_generation_update_before_pooling(companion):
    db = mario.load_test('SUT')
    db.update_supply_mix({'Region 1': {'Manufacturing': .5, 'Services': .5}},
                         level='Activity', commodities='Goods', scenario='updated_mix', clone_from='baseline')
    if companion:
        nb = json.loads((ROOT / 'advanced/electricity_mix.ipynb').read_text())
        cells = [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']
        source = '\n'.join(c for c in cells if 'pool_trade(' in c or 'update_trade_mix(' in c)
        scenario = 'electricity_mix'
    else:
        source = next(b for b in python_blocks(ROOT / 'advanced/electricity_mix.rst') if 'pool_trade(' in b)
        scenario = 'trade_mix'
    # Substitute fixture labels and explicit sourcing data for the provider
    # preset; execute the published promotion/pooling/update sequence unchanged.
    source = source.replace('"electricity"', '"Goods"')
    source = source.replace('update_trade_mix(\n    "Goods",',
                            'update_trade_mix(\n    trade_shares,')
    source = source.replace('    year=2023,\n', '').replace('    api_key="entsoe",\n', '')
    scope = {'db': db, 'trade_shares': {'Region 1': {'Region 1': .4, 'Region 2': .6}}}
    exec(source, scope)
    pooled = scope['pooled_db']
    shares = pooled.get_block_as_pandas('s', scenario=scenario)
    goods = ('Region 1', 'Commodity', 'Goods')
    need = ('Region 1', 'Commodity', 'Goods - need')
    assert shares.loc[('Region 1', 'Activity', 'Manufacturing'), goods] == pytest.approx(.5)
    assert shares.loc[('Region 1', 'Activity', 'Services'), goods] == pytest.approx(.5)
    assert shares.loc[('Region 1', 'Activity', 'Goods - supply'), need] == pytest.approx(.4)
    assert shares.loc[('Region 2', 'Activity', 'Goods - supply'), need] == pytest.approx(.6)
    assert db.scenarios == ['baseline', 'updated_mix']
