import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'doc/scripts'))
from build_country_scope import native_profile_without_readings, upsert_unmapped_guide


def test_parsed_e3_scope_keeps_native_sets_without_indicators():
    data=ROOT/'doc/source/_static/data'
    catalogue=json.loads((data/'database_profiles.json').read_text())
    profiles=[p for p in catalogue['profiles'] if p['guide']=='figaro-e3']
    assert len(profiles)==3
    for p in profiles:
        detail=json.loads((data.parent.parent/p['detail']).read_text())
        row=native_profile_without_readings(p,detail,catalogue['guides'])
        assert row['mapping'] is None and row['mapping_ids']==[] and row['reading_ids']==[]
        assert row['status']=='parsed'
        assert row['sets']=={k:v for k,v in detail['sets'].items() if k!='Region'}
        assert p['geography']['individual_countries']==45
        assert p['geography']['aggregate_count']==1 and p['geography']['unresolved_count']==0


def test_catalogue_separates_standard_and_e3_guides_and_recipes():
    data=json.loads((ROOT/'doc/database_catalogue.recipes.json').read_text())
    guides={g['id']:g for g in data['guides']}
    assert guides['figaro']['doc'].endswith('/walkthrough_figaro')
    assert guides['figaro-e3']['doc'].endswith('/e3')
    recipes=[r for r in data['recipes'] if r['guide']=='figaro-e3']
    assert len(recipes)==3 and all(r['runnable'] for r in recipes)
    assert len({r['id'] for r in data['recipes']})==len(data['recipes'])


def test_native_only_refresh_preserves_other_maps_and_refuses_reviewed_links(tmp_path):
    data=tmp_path/'source/_static/data'
    (data/'economy').mkdir(parents=True)
    profile={'id':'new','guide':'figaro-e3','source':'FIGARO','release':'E3','year':2015,
             'table':'SUT','status':'parsed','counts':{'Region':2},'geography':{'regions':[]},
             'detail':'_static/data/new.json','workbook':'_static/data/new.xlsx'}
    (data/'database_profiles.json').write_text(json.dumps({'guides':[{'id':'figaro-e3','doc':'e3'}],'profiles':[profile]}))
    (data/'new.json').write_text(json.dumps({'sets':{'Region':['AA','BB'],'Activity':['I1']}}))
    original={'profiles':[{'id':'old','mapping':'reviewed'}],'classifications':{'keep':1},'mappings':{'keep':2}}
    output=data/'economy/country-scope.json'
    output.write_text(json.dumps(original))
    result=upsert_unmapped_guide(data,'figaro-e3')
    assert result['profiles'][0]==original['profiles'][0]
    assert result['classifications']==original['classifications'] and result['mappings']==original['mappings']
    result['profiles'][-1]['mapping']='new-review'
    output.write_text(json.dumps(result))
    before=output.read_bytes()
    with pytest.raises(ValueError,match='reviewed'):
        upsert_unmapped_guide(data,'figaro-e3')
    assert output.read_bytes()==before
