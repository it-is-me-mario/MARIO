"""Hierarchy proposals preserve native totals, membership and unresolved items."""
from copy import deepcopy

import pandas as pd
import pytest

from mario import Database
from mario.log_exc.exceptions import WrongInput
from tests.api.test_concordances import sut


def test_many_linked_classes_collapse_only_to_a_unique_ancestor():
    db = sut(activities={'IT': ['Growing wheat', 'Fishing']})
    section = db.get_aggregation()['Activity']
    assert section['Aggregation'].tolist() == ['NACE Rev. 2.1:A'] * 2
    division = db.get_aggregation(level='2 digits')['Activity']
    assert division['Aggregation'].tolist() == ['NACE Rev. 2.1:01', 'Fishing']
    report = division.attrs['concordance']
    assert report['unresolved']['Fishing']['reason'] == 'multiple_groups'
    assert report['unresolved']['Fishing']['groups'] == ['01', '03']
    assert report['hierarchy_source']['id'] == 'S14'
    assert report['groups']['NACE Rev. 2.1:01']['name'].startswith('Crop and animal')
    with pytest.raises(WrongInput, match='Cannot assign 1 native items'):
        db.get_aggregation(level='division', unresolved='raise')


def test_unverified_items_remain_individual_and_the_report_is_independent():
    db = sut(activities={'IT': ['Growing wheat', 'Custom aggregate']})
    result = db.get_aggregation()['Activity']
    assert result.loc['Custom aggregate', 'Aggregation'] == 'Custom aggregate'
    assert result.attrs['concordance']['unresolved']['Custom aggregate']['reason'] == 'unverified'
    result.attrs['concordance']['hierarchy_source']['title'] = 'mutated'
    assert db.get_aggregation()['Activity'].attrs['concordance']['hierarchy_source']['title'] != 'mutated'


def test_regional_proposal_preserves_real_pairs_and_does_not_compute_or_mutate(monkeypatch):
    db = sut()
    history = deepcopy(db.meta._history)
    monkeypatch.setattr(db, 'calc_all', lambda *a, **k: pytest.fail('Metadata must not compute'))
    mapping = db.get_aggregation(level='division')['Activity']
    assert mapping.index.tolist() == [('IT', 'Growing wheat'), ('IT', 'Growing rice'), ('DE', 'Growing wheat')]
    assert mapping['Aggregation'].tolist() == ['NACE Rev. 2.1:01'] * 3
    assert db.meta._history == history
    assert db.get_index('Activity', region='DE') == ['Growing wheat']


def test_discovery_and_level_validation_require_an_official_hierarchy():
    db = sut('EXIOBASE monetary SUT')
    assert db.available_aggregations['Activity']['NACE Rev. 2.1'] == ['section', 'division', 'group', 'class']
    assert 'subcategory' in db.available_aggregations['Commodity']['CPA 2.2']
    assert 'HS 2007' not in db.available_aggregations['Commodity']
    with pytest.raises(WrongInput, match='Available levels: none'):
        db.get_aggregation(classification='NACE Rev. 2')
    with pytest.raises(WrongInput, match='No packaged aggregation level'):
        db.get_aggregation(level='subcategory')
    with pytest.raises(WrongInput, match='unresolved must'):
        db.get_aggregation(unresolved='split equally')


def test_retained_native_names_cannot_collide_with_generated_groups():
    db = sut(activities={'IT': ['Growing wheat', 'NACE Rev. 2.1:A']})
    with pytest.raises(WrongInput, match='collide'):
        db.get_aggregation()


def test_prepared_mapping_feeds_existing_aggregation_and_conserves_flows():
    labels = ['Wheat', 'Paddy rice', 'Unknown product']
    sectors = pd.MultiIndex.from_tuples([('IT', 'Sector', item) for item in labels])
    final = pd.MultiIndex.from_tuples([('IT', 'Consumption category', 'Households')])
    z = pd.DataFrame([[1., 2., 3.], [4., 5., 6.], [7., 8., 9.]], index=sectors, columns=sectors)
    y = pd.DataFrame([[10.], [20.], [30.]], index=sectors, columns=final)
    e = pd.DataFrame([[1., 2., 3.]], index=['CO2'], columns=sectors)
    v = pd.DataFrame([[10., 20., 30.]], index=['VA'], columns=sectors)
    ey = pd.DataFrame([[0.]], index=['CO2'], columns=final)
    units = {name: pd.DataFrame({'unit': unit}, index=items)
             for name, items, unit in [('Sector', labels, 'EUR'), ('Satellite account', ['CO2'], 'kg'), ('Factor of production', ['VA'], 'EUR')]}
    db = Database(Z=z, Y=y, E=e, V=v, EY=ey, units=units, table='IOT', source='EXIOBASE monetary IOT (pxp)', calc_all=False)
    mapping = db.get_aggregation(level='division')
    assert mapping['Sector']['Aggregation'].tolist() == ['CPA 2.2:01', 'CPA 2.2:01', 'Unknown product']
    aggregated = db.aggregate(mapping, levels=list(mapping), inplace=False)
    assert aggregated.get_index('Sector') == ['CPA 2.2:01', 'Unknown product']
    assert db.get_index('Sector') == labels
    for block in ['Z', 'Y', 'E', 'V']:
        assert aggregated.get_block_as_pandas(block).to_numpy().sum() == pytest.approx(db.get_block_as_pandas(block).to_numpy().sum())
