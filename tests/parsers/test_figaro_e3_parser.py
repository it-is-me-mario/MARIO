from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pytest

import mario
from mario.log_exc.exceptions import WrongInput, WrongFormat
from mario.parsers.figaro_e3 import (FINAL_CODES, GHG_CODES, ENERGY_CODES,
                                    EMPLOYMENT_CODES, _economic, _extensions, _metadata)

pytestmark = pytest.mark.usefixtures('isolated_session_settings')


def bundle(root):
    root.mkdir(exist_ok=True)
    regions, activities, products = ['AA','BB'], ['I1','I2'], ['CPA_P1','CPA_P2','CPA_P3']
    with pd.ExcelWriter(root/'230312_D_FIGARO-env_Classifications.xlsx') as writer:
        for sheet,codes in [('Country resolution',regions+['W2']),('Industry resolution',activities),('Product resolution',products),('Additional rows and colums',['D1','OP_RES',*FINAL_CODES])]:
            pd.DataFrame({'code':codes,'description':['Label '+code for code in codes]}).to_excel(writer,sheet_name=sheet,index=False)
    raw=lambda codes:[r+'_'+c for r in regions for c in codes]
    ar,cr,nr=raw(activities),raw(products),raw(FINAL_CODES)
    fr=['W2_D1','W2_OP_RES']
    source={}
    def write(stem,rows,columns,values):
        frame=pd.DataFrame(values,index=rows,columns=columns)
        frame.index.name='rowId'
        frame.to_csv(root/f'matrix_{stem}_2015.csv')
        flat=frame.rename_axis(index='rowId',columns='colId').stack().rename('obsValue').reset_index()
        flat['unit']='million EURO'
        flat.to_csv(root/f'flatfile_{stem}_2015.csv',index=False)
        return frame
    source['supply']=write('FIGARO-e-ic-supply_millionEUR',cr,ar,np.arange(24).reshape(6,4)+1.)
    source['use']=write('FIGARO-e-ic-use_millionEUR',cr+fr,ar+nr,np.arange(112).reshape(8,14)-3.)
    source['industry']=write('FIGARO-e-ic-io-D_ind-by-ind_millionEUR',ar+fr,ar+nr,np.arange(84).reshape(6,14)-5.)
    source['product']=write('FIGARO-e-ic-io-B_prod-by-prod_millionEUR',cr+fr,cr+nr,np.arange(128).reshape(8,16)-7.)
    # Source extension final-demand order differs from the economic matrices.
    ext_cols=ar+list(reversed(nr))
    for basis in ['mass','co2eq']:
        stem='FIGARO-e_AEM_Gg'+('_CO2e' if basis=='co2eq' else '')
        values=np.arange(56).reshape(4,14)+10.
        frame=pd.DataFrame(values,index=GHG_CODES,columns=ext_cols)
        frame.to_csv(root/f'matrix_{stem}_2015.csv',index_label='rowLabels')
        rows=[]
        for gas in GHG_CODES:
            for key,value in frame.loc[gas].items():
                region,code=key.split('_',1)
                rows.append(['Air emissions',gas,region,code,2015,'kt CO2e' if basis=='co2eq' or gas=='F-gases' else 'kt',value])
        pd.DataFrame(rows,columns=['category','codeIndicator','refArea','colPi','timePeriod','unit','obsValue']).to_csv(root/f'flatfile_{stem}_2015.csv',index=False)
        source[basis]=frame
    energy=[]
    for number,code in enumerate(ENERGY_CODES):
        values=np.arange(14)+100.*number
        pd.DataFrame([values],index=['Total'],columns=ext_cols).to_csv(root/f'matrix_FIGARO-e_ENE_{code}_TJ_2015.csv',index_label='rowLabels')
        for key,value in zip(ext_cols,values):
            region,item=key.split('_',1)
            energy.append(['Energy',code,region,'Total',item,2015,'TJ',value])
    pd.DataFrame(energy,columns=['category','codeIndicator','refArea','codeEproduct','colPi','timePeriod','unit','obsValue']).to_csv(root/'flatfile_FIGARO-e_ENE_TJ_2015.csv',index=False)
    employment=[]
    for number,method in enumerate(['EDU','OCC']):
        frame=pd.DataFrame(np.arange(24).reshape(4,6)+number*100.,index=ar,columns=EMPLOYMENT_CODES)
        frame.to_csv(root/f'matrix_FIGARO-e_employment_{method}_k_2015.csv',index_label='rowLabels')
        for key,row in frame.iterrows():
            region,code=key.split('_',1)
            for indicator,value in row.items():
                employment.append(['Employment',' '+method,region,code,indicator,2015,'k',value])
    pd.DataFrame(employment,columns=['category','codeEstimMethod','refArea','colPi','codeIndicator','timePeriod','unit','obsValue']).to_csv(root/'flatfile_FIGARO-e_employment_2015.csv',index=False)
    source.update(ar=ar,cr=cr,nr=nr)
    return source


@pytest.mark.parametrize('fmt',['matrix','flatfile','auto'])
def test_sut_formats_preserve_native_blocks_and_final_accounts(tmp_path,fmt):
    source=bundle(tmp_path)
    db=mario.parse_figaro_e3(tmp_path,input_format=fmt,employment='both',chunksize=9)
    blocks=db.matrices['baseline']
    np.testing.assert_array_equal(blocks['S'],source['supply'].to_numpy().T)
    np.testing.assert_array_equal(blocks['U'],source['use'].iloc[:6,:4])
    np.testing.assert_array_equal(blocks['Yc'],source['use'].iloc[:6,4:])
    np.testing.assert_array_equal(blocks['Va'],source['use'].iloc[6:,:4])
    np.testing.assert_array_equal(blocks['VY'],source['use'].iloc[6:,4:])
    ghg=[f'GHG | {g} | AR5 GWP100 CO2eq' for g in GHG_CODES]
    np.testing.assert_array_equal(blocks['Ea'].loc[ghg],source['co2eq'].loc[:,source['ar']])
    np.testing.assert_array_equal(blocks['EY'].loc[ghg],source['co2eq'].loc[:,source['nr']])
    assert len(db.get_index('Satellite account'))==22
    assert not np.array_equal(blocks['Ea'].loc['Employment | EDU | EMPLS_M'],blocks['Ea'].loc['Employment | OCC | EMPLS_M'])
    assert not blocks['Ec'].to_numpy().any()
    assert db.database_profile['id']=='figaro_e3'
    assert not db.database_profile['concordances']['supported']
    db.calc_ghg(label='GHG native basis',ipcc_report='AR4')
    np.testing.assert_allclose(db.matrices['baseline']['Ea'].loc['GHG native basis'],blocks['Ea'].loc[ghg].sum())
    np.testing.assert_allclose(db.matrices['baseline']['EY'].loc['GHG native basis'],blocks['EY'].loc[ghg].sum())


@pytest.mark.parametrize('mode',['industry','product'])
@pytest.mark.parametrize('fmt',['matrix','flatfile'])
def test_iot_native_flows_and_explicit_product_extension_allocation(tmp_path,mode,fmt):
    source=bundle(tmp_path)
    options={'extension_allocation':'industry_technology'} if mode=='product' else {}
    db=mario.parse_figaro_e3(tmp_path,table='IOT',iot_mode=mode,input_format=fmt,extensions='emissions',**options)
    n=4 if mode=='industry' else 6
    blocks=db.matrices['baseline']
    np.testing.assert_array_equal(blocks['Z'],source[mode].iloc[:n,:n])
    np.testing.assert_array_equal(blocks['Y'],source[mode].iloc[:n,n:])
    np.testing.assert_array_equal(blocks['V'],source[mode].iloc[n:,:n])
    source_e=source['co2eq'].loc[:,source['ar']].to_numpy()
    expected=source_e if mode=='industry' else (source_e/source['supply'].sum(axis=0).to_numpy())@source['supply'].to_numpy().T
    np.testing.assert_allclose(blocks['E'],expected)
    np.testing.assert_allclose(blocks['E'].sum(axis=1),source_e.sum(axis=1))
    assert db.meta.sector_type==('Activity' if mode=='industry' else 'Commodity')


def test_generic_dispatch_and_mass_units(tmp_path):
    bundle(tmp_path)
    db=mario.parse_figaro(tmp_path,variant='E3',table='IOT',emissions='mass',extensions='emissions')
    assert db.meta.year==2015
    assert db.units['Satellite account'].loc['GHG | CO2 | native','unit']=='kt'
    assert db.units['Satellite account'].loc['GHG | F-gases | native','unit']=='kt CO2-eq'
    assert db.database_profile['ghg']['selected_profile'] is None


def test_browser_copies_are_collapsed_only_when_identical(tmp_path):
    bundle(tmp_path)
    path=tmp_path/'matrix_FIGARO-e-ic-use_millionEUR_2015.csv'
    copy=path.with_name(path.stem+' copy.csv')
    shutil.copy2(path,copy)
    mario.parse_figaro_e3(tmp_path,extensions=False)
    copy.write_text(copy.read_text().replace('-3.0','-9.0'))
    with pytest.raises(WrongInput,match='Conflicting'):
        mario.parse_figaro_e3(tmp_path,extensions=False)


def test_missing_conflicting_and_unallocatable_inputs_raise(tmp_path):
    bundle(tmp_path)
    with pytest.raises(WrongInput,match='industry-based'):
        mario.parse_figaro_e3(tmp_path,table='IOT',iot_mode='product')
    path=tmp_path/'matrix_FIGARO-e-ic-supply_millionEUR_2015.csv'
    supply=pd.read_csv(path,index_col=0)
    supply.iloc[:,0]=0
    supply.to_csv(path)
    with pytest.raises(WrongInput,match='zero-output'):
        mario.parse_figaro_e3(tmp_path,table='IOT',iot_mode='product',extension_allocation='industry_technology')
    use=tmp_path/'matrix_FIGARO-e-ic-use_millionEUR_2015.csv'
    frame=pd.read_csv(use,index_col=0).iloc[:-1]
    frame.to_csv(use)
    with pytest.raises(WrongFormat,match='Missing'):
        mario.parse_figaro_e3(tmp_path,extensions=False)


def test_flat_duplicate_observations_are_rejected(tmp_path):
    bundle(tmp_path)
    path=tmp_path/'flatfile_FIGARO-e-ic-use_millionEUR_2015.csv'
    frame=pd.read_csv(path)
    pd.concat([frame,frame.iloc[[0]]]).to_csv(path,index=False)
    with pytest.raises(WrongFormat,match='Duplicate'):
        mario.parse_figaro_e3(tmp_path,input_format='flatfile',extensions=False,chunksize=13)


def test_truncated_domestic_supply_is_not_filled_with_zeros(tmp_path):
    bundle(tmp_path)
    path=tmp_path/'flatfile_FIGARO-e-ic-supply_millionEUR_2015.csv'
    pd.read_csv(path).iloc[1:].to_csv(path,index=False)
    with pytest.raises(WrongFormat,match='domestic supply'):
        mario.parse_figaro_e3(tmp_path,input_format='flatfile',extensions=False)


def test_extension_unit_and_final_demand_labels_are_validated(tmp_path):
    bundle(tmp_path)
    path=tmp_path/'flatfile_FIGARO-e_AEM_Gg_2015.csv'
    frame=pd.read_csv(path)
    frame.loc[0,'unit']='kg'
    frame.to_csv(path,index=False)
    with pytest.raises(WrongFormat,match='units'):
        mario.parse_figaro_e3(tmp_path,input_format='flatfile',emissions='mass')
    path=tmp_path/'matrix_FIGARO-e_AEM_Gg_CO2e_2015.csv'
    frame=pd.read_csv(path,index_col=0)
    frame.columns=frame.columns.str.replace('AA_P3_S13','AA_UNEXPECTED')
    frame.to_csv(path)
    with pytest.raises(WrongFormat,match='axes'):
        mario.parse_figaro_e3(tmp_path)


def test_model_state_and_true_extension_selector(tmp_path):
    bundle(tmp_path)
    state=mario.parse_figaro_e3(tmp_path,model='ModelState',extensions=True)
    assert state.metadata.table_kind.value=='SUT'


@pytest.mark.parametrize('companion',[False,True],ids=['web-guide','notebook'])
def test_published_workflows_execute(tmp_path,companion):
    import json
    from tests.docs.test_workflow_examples import python_blocks
    bundle(tmp_path)
    page=Path(__file__).resolve().parents[2]/'doc/source/notebooks/parsers/figaro/e3'
    blocks=([''.join(c['source']) for c in json.loads(page.with_suffix('.ipynb').read_text())['cells'] if c['cell_type']=='code']
            if companion else python_blocks(page.with_suffix('.rst')))
    scope={}
    for block in blocks:
        exec(block.replace('/path/to/FIGARO E3',str(tmp_path)),scope)
    assert scope['db'].meta.year==2015
    assert 'GHG source AR5 GWP100' in scope['db'].get_index('Satellite account')


@pytest.mark.parametrize('option',[{'year':2022},{'input_format':'zip'},{'employment':'total'},{'emissions':'total'},{'chunksize':0},{'extensions':'typo'}])
def test_invalid_options_raise(tmp_path,option):
    bundle(tmp_path)
    with pytest.raises(WrongInput):
        mario.parse_figaro_e3(tmp_path,**option)
