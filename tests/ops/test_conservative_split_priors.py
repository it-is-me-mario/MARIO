"""Prior conservation, information retention and unchanged signed accounts."""
from itertools import product
import numpy as np
import pandas as pd
import pytest
from mario.ops.split_priors import conservative_family_prior, prepare_intermediate_priors, KEYS
from mario.ops.split_model import normalize_options


def example(regions=('R',)):
    rows=[(o,d,s,t,q) for o,d in product(regions,repeat=2)
          for (s,t),q in zip(product(['Parent','Child'],repeat=2),[40.5,4.5,40.5,0.])]
    table=pd.DataFrame(rows,columns=KEYS+['values'])
    original=pd.DataFrame([(o,d,'Parent','Parent',45.) for o,d in product(regions,repeat=2)],columns=KEYS+['values'])
    quantities=pd.DataFrame({'production':[q for r in regions for q in [90.,10.]]},
        index=pd.MultiIndex.from_tuples([(r,'Sector',s) for r in regions for s in ['Parent','Child']]))
    return table,original,quantities,table.assign(values=0.)


def test_self_consumption_preserves_recipe_and_original_45_instead_of_duplicating_to_85_5():
    frame,baseline,x,zero=example();before=frame.copy()
    result,records=conservative_family_prior(frame,baseline,x,{'Child':'Parent'},zero)
    np.testing.assert_allclose(result['values'],[36.45,4.5,4.05,0.])
    assert result['values'].sum()==pytest.approx(45.)
    pd.testing.assert_frame_equal(frame,before)
    assert records[0]['prior_before_original_units']==85.5
    assert records[0]['child_columns_after_original_units']==4.5


def test_foreign_blocks_use_origin_shares_and_preserve_nonstandard_row_order():
    frame,baseline,x,zero=example(('A','B'))
    x.loc[('B','Sector','Parent'),'production']=75.
    x.loc[('B','Sector','Child'),'production']=25.
    frame=frame.sample(frac=1.,random_state=4).set_axis(np.arange(100,116))
    result,_=conservative_family_prior(frame,baseline,x,{'Child':'Parent'},zero)
    assert result.index.equals(frame.index)
    selected=(result.region_from_Name=='A')&(result.region_to_Name=='B')&(result.sector_from_Name=='Child')&(result.sector_to_Name=='Parent')
    assert result.loc[selected,'values'].iloc[0]==pytest.approx(4.05)
    np.testing.assert_allclose(result.groupby(KEYS[:2])['values'].sum(),45.)


def test_bridge_parent_identity_is_not_a_child_column():
    frame,baseline,x,zero=example()
    result,records=conservative_family_prior(frame,baseline,x,{'Child':'Parent','Parent':'Parent'},zero)
    np.testing.assert_allclose(result['values'],[36.45,4.5,4.05,0.])
    assert records[0]['child_columns_after_original_units']==4.5


def test_cross_family_blocks_are_conserved_and_stable_supplier_cells_untouched():
    frame=pd.DataFrame([['R','R',s,t,q] for (s,t),q in zip(product(['P','A'],['Q','B']),[12.,3.,12.,1.])]
        +[['R','R','Stable','Q',7.]],columns=KEYS+['values'])
    baseline=pd.DataFrame([['R','R','P','Q',20.]],columns=KEYS+['values'])
    x=pd.DataFrame({'production':[75.,25.,80.,20.]},index=pd.MultiIndex.from_tuples([('R','Sector',s) for s in ['P','A','Q','B']]))
    result,_=conservative_family_prior(frame,baseline,x,{'A':'P','B':'Q'},frame.assign(values=0.))
    np.testing.assert_allclose(result['values'],[12.,3.,4.,1.,7.])


def test_no_residual_column_support_rescales_admissible_child_references():
    frame,baseline,x,zero=example()
    zero.loc[zero.sector_to_Name=='Parent','values']=1.
    result,records=conservative_family_prior(frame,baseline,x,{'Child':'Parent'},zero)
    np.testing.assert_allclose(result['values'],[0.,45.,0.,0.])
    assert records[0]['mode']=='rescale_child_recipes_no_residual_column_support'


@pytest.mark.parametrize('unit_scale',[1.,1e-6,1e6])
def test_multiple_siblings_keep_fine_child_links_and_conserve_joint_block(unit_scale):
    members=['P','A','B']
    raw=np.array([[34.,3.,8.],[27.,0.,1.],[27.,0.,0.]])*unit_scale
    frame=pd.DataFrame([['R','R',s,t,raw[i,j]] for i,s in enumerate(members)
                        for j,t in enumerate(members)],columns=KEYS+['values'])
    original=pd.DataFrame([['R','R','P','P',45.*unit_scale]],columns=KEYS+['values'])
    x=pd.DataFrame({'production':np.array([60.,10.,30.])*unit_scale},
                   index=pd.MultiIndex.from_tuples([('R','Sector',s) for s in members]))
    result,_=conservative_family_prior(frame,original,x,{'A':'P','B':'P'},frame.assign(values=0.))
    expected=np.array([[19.8,3.,8.],[3.3,0.,1.],[9.9,0.,0.]])*unit_scale
    np.testing.assert_allclose(result['values'].to_numpy().reshape(3,3),expected)
    assert result['values'].sum()==pytest.approx(45.*unit_scale)


def test_conflicting_support_is_diagnostic_without_a_monetary_rejection_gate():
    frame,baseline,x,zero=example();zero['values']=1.
    result,records=conservative_family_prior(frame,baseline,x,{'Child':'Parent'},zero)
    assert result['values'].eq(0.).all()
    assert baseline['values'].iloc[0]==45.
    assert records[0]['conservation_error_original_units']==-45.


def test_zero_output_family_keeps_available_budget_in_parent():
    frame,baseline,x,zero=example();x['production']=0.;frame['values']=0.
    zero.loc[(zero.sector_from_Name=='Child')|(zero.sector_to_Name=='Child'),'values']=1.
    result,_=conservative_family_prior(frame,baseline,x,{'Child':'Parent'},zero)
    np.testing.assert_allclose(result['values'],[45.,0.,0.,0.])


def test_legacy_comparison_and_signed_accounts_targets_masks_preserved(tmp_path):
    frame,baseline,x,zero=example()
    inputs={'Z_use0':frame.copy(),'Z0':frame.copy(),'Zero_use_mask':zero,
            'Y0':pd.DataFrame({'values':[-4.,2.]}),'V0':pd.DataFrame({'values':[-8.,7.]}),
            'X':x.copy(),'Trade':pd.DataFrame({'values':[3.]})}
    originals={k:v.copy(deep=True) for k,v in inputs.items()}
    prepare_intermediate_priors(inputs,baseline,x,{'Child':'Parent'},'legacy',tmp_path)
    for key in inputs:pd.testing.assert_frame_equal(inputs[key],originals[key])
    prepare_intermediate_priors(inputs,baseline,x,{'Child':'Parent'},'conservative',tmp_path)
    for key in set(inputs)-{'Z_use0','Z0'}:pd.testing.assert_frame_equal(inputs[key],originals[key])


def test_partial_legacy_reference_does_not_rescale_a_compatible_child_recipe():
    frame,baseline,x,zero=example()
    partial=frame.copy();partial.loc[partial.sector_to_Name=='Parent','values']=0.
    inputs={'Z0':partial,'Z_use0':frame,'Zero_use_mask':zero}
    report=prepare_intermediate_priors(inputs,baseline,x,{'Child':'Parent','Parent':'Parent'},'conservative')
    np.testing.assert_allclose(inputs['Z0']['values'],[36.45,4.5,4.05,0.])
    assert report['child_recipe_rescaling_groups']==0
    # Partial-entropy models can obtain the same complete reference from the
    # prepared split flow, without requiring a Z_use0 parameter in their template.
    inputs={'Z0':partial,'Zero_use_mask':zero}
    prepare_intermediate_priors(inputs,baseline,x,{'Child':'Parent'},'conservative',complete_reference=frame)
    np.testing.assert_allclose(inputs['Z0']['values'],[36.45,4.5,4.05,0.])


def test_named_models_default_to_conservative_with_explicit_legacy_control():
    assert normalize_options({'model':'Split_sectors_MRIO_quadratic'})['intermediate_prior_policy']=='conservative'
    assert normalize_options({'intermediate_prior_policy':'legacy'})['intermediate_prior_policy']=='legacy'
    with pytest.raises(Exception,match='intermediate_prior_policy'):
        normalize_options({'intermediate_prior_policy':'unknown'})
