"""Numerical guardrails for browser indicators; no real MRIO inputs or network."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("economy_browser", ROOT / "doc/source/_static/reproduce/economy_browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


def example():
    columns = pd.MultiIndex.from_product([["IT"], ["Sector"], ["Goods", "Services"]], names=["Region", "Level", "Item"])
    fd = pd.MultiIndex.from_product([["IT"], ["Consumption category"], ["Households"]], names=columns.names)
    blocks = {
        "V": pd.DataFrame([[10, 20], [2, 4], [1, 2], [1000, 1000]], index=["Wages", "Surplus", "Product tax", "Imports"], columns=columns),
        "E": pd.DataFrame([[1000, 2000], [10, 20], [50, 100]], index=["CO2", "CH4", "HFC_CO2eq"], columns=columns),
        "EY": pd.DataFrame([[500], [5], [20]], index=["CO2", "CH4", "HFC_CO2eq"], columns=fd),
    }
    recipe = {"label": "Example", "year": 2024, "sectors": ["Goods", "Services"],
              "regions": [{"label": "IT", "name": "Italy", "iso3": "ITA", "kind": "country"}],
              "value_added_rows": ["Wages", "Surplus"], "product_tax_rows": ["Product tax"],
              "ghg_factors": {"CO2": .001, "CH4": .0298, "HFC_CO2eq": .001}, "currency_scale": 1e6, "currency": "EUR"}
    wb = {"countries": {"DEU": {"years": {"2024": {"local_currency_per_usd": .8}}},
                        "ITA": {"years": {"2024": {"population": 10, "gdp": 50e6, "gdp_per_capita": 5e6}}}}}
    return blocks, recipe, wb


def test_gdp_includes_final_use_taxes_but_not_imports():
    blocks, recipe, _ = example()
    result = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe, {"IT": 5})[0]
    assert result["value_added"] == [12e6, 24e6]
    assert result["net_product_taxes"] == 8e6
    assert result["gdp"] == 44e6
    # Missing tax bridge must not silently relabel GVA as GDP.
    result = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe)[0]
    assert "gdp" not in result


def test_ghg_characterisation_units_and_household_boundary():
    blocks, recipe, _ = example()
    result = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe, {"IT": 5})[0]
    assert result["ghg"] == pytest.approx([1.348, 2.696])
    assert result["household_ghg"] == pytest.approx(.669)
    recipe["ghg_factors"] = {}
    result = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe)[0]
    assert "ghg" not in result


def test_emissions_without_income_accounts_never_publishes_placeholder_zeros():
    blocks, recipe, _ = example()
    recipe.update(value_added_available=False, final_demand_emissions_loaded=False,
                  sectors=["All native production activities"])
    # Even a nonzero V or EY must not be read as evidence for this source.
    result = browser.aggregate(SimpleNamespace(get_block=lambda name: blocks["E"] if name == "E" else pytest.fail(name)), recipe)[0]
    assert result["gdp"] is None and result["value_added"] is None
    assert result["ghg"] == pytest.approx([4.044])
    assert "household_ghg" not in result


def test_fail_on_missing_gas_nonfinite_value_or_changed_classification():
    blocks, recipe, _ = example()
    with pytest.raises(KeyError):
        browser.characterise(blocks["E"], {"Unknown gas": 1})
    blocks["V"].iloc[0,0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe)
    blocks["V"].iloc[0,0] = 10
    recipe["sectors"] = ["Goods"]
    with pytest.raises(ValueError, match="classification changed"):
        browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe)


def test_export_currency_population_and_exact_year():
    blocks, recipe, wb = example()
    rows = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe, {"IT": 5})
    config = {"recipe": recipe, "metric": "gdp", "per_capita": True, "country": "IT"}
    result = list(browser.selected_rows(rows, config, wb))[0]
    assert result["value"] == 5.5e6
    assert result["world_bank"] == 5e6
    assert result["difference_percent"] == pytest.approx(10)
    recipe["year"] = 2023
    result = list(browser.selected_rows(rows, config, wb))[0]
    assert result["value"] is None and result["world_bank"] is None


def test_sector_subsets_and_empty_selection():
    blocks, recipe, wb = example()
    rows = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe)
    config = {"recipe": recipe, "metric": "value_added", "sectors": ["Goods"]}
    assert list(browser.selected_rows(rows, config, wb))[0]["value"] == 15e6
    config["metric"] = "gdp"
    with pytest.raises(ValueError, match="whole economy"):
        list(browser.selected_rows(rows, config, wb))
    config["sectors"] = []
    with pytest.raises(ValueError, match="at least one"):
        list(browser.selected_rows(rows, config, wb))


def test_oecd_final_demand_bridge_collapses_split_regions(tmp_path):
    path = tmp_path / "2022.csv"
    pd.DataFrame([[3, 4, 5, 99]], index=["TLS"], columns=["CN1_HFCE", "CN2_HFCE", "ITA_HFCE", "ITA_C10"]).to_csv(path)
    recipe = {"tax_bridge": "oecd_csv", "product_tax_rows": ["TLS"], "consumption_categories": ["HFCE"]}
    assert browser.final_demand_taxes(path, recipe) == {"CHN": 7, "ITA": 5}


def test_published_snapshots_have_finite_additive_indicators_and_no_private_paths():
    folder = ROOT / "doc/source/_static/data/economy"
    manifest = json.loads((folder / "manifest.json").read_text())
    for d in manifest["datasets"]:
        raw = (folder / f"{d['id']}.json").read_text()
        assert "/Users/" not in raw
        snapshot = json.loads(raw)
        recipe = snapshot["recipe"]
        assert len(recipe["sectors"]) == len(set(recipe["sectors"]))
        if "sector_groups" in recipe:
            group_sectors = [s for items in recipe["sector_groups"].values() for s in items]
            assert sorted(group_sectors) == sorted(recipe["sectors"])
        for region in snapshot["regions"]:
            if recipe.get("value_added_available") is False:
                assert region["value_added"] is None and region["gdp"] is None
            else:
                assert len(region["value_added"]) == len(recipe["sectors"])
                assert np.isfinite(region["value_added"]).all()
            if "ghg" in region:
                assert len(region["ghg"]) == len(recipe.get("ghg_sectors", recipe["sectors"]))
                assert np.isfinite(region["ghg"]).all()
            if recipe.get("tax_bridge"):
                assert region["gdp"] == pytest.approx(sum(region["value_added"]) + region["net_product_taxes"])
            elif recipe.get("gdp_proxy") == "native_value_added":
                assert recipe["source"] == "EMERGING"
                assert recipe["gdp_bridge_verified"] is False
                assert region["gdp"] == sum(region["value_added"])
                assert "net_product_taxes" not in region
            elif recipe.get("value_added_available") is not False:
                assert "gdp" not in region


def test_parser_result_must_match_year_and_units(monkeypatch):
    import sys
    blocks, recipe, _ = example()
    recipe.update(parser="parse_example", parser_options={}, table="IOT", expected_units={"Factor of production": {"Wages": "million EUR"}})
    database = SimpleNamespace(meta=SimpleNamespace(year=2023), table_type="IOT", units={"Factor of production": pd.DataFrame({"unit": ["million EUR"]}, index=["Wages"])})
    monkeypatch.setitem(sys.modules, "mario", SimpleNamespace(parse_example=lambda **kwargs: database))
    with pytest.raises(ValueError, match="Expected source year"):
        browser.load_database(recipe, "local")
    database.meta.year = 2024
    assert browser.load_database(recipe, "local") is database
    database.units["Factor of production"].loc["Wages", "unit"] = "USD"
    with pytest.raises(ValueError, match="Unexpected unit"):
        browser.load_database(recipe, "local")



def test_download_breakdown_sums_to_selected_total():
    blocks, recipe, wb = example()
    snapshot = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe)
    config = {"recipe": recipe, "metric": "ghg", "per_capita": True, "breakdown": True}
    rows = list(browser.selected_rows(snapshot, config, wb))
    assert len(rows) == 4
    assert rows[0]["scope"] == "Whole economy including direct final demand"
    assert all(r["scope"] == "Industry" for r in rows[1:-1])
    assert rows[-1]["scope"] == "Direct final demand"
    assert rows[0]["value"] == pytest.approx(sum(r["value"] for r in rows[1:]))


def test_supply_tax_bridge_preserves_signed_product_subsidies():
    blocks, recipe, _ = example()
    blocks['Va'] = blocks.pop('V').rename(index={'Product tax': 'Positive subsidy'})
    blocks['Vc'] = pd.DataFrame([[3, 4], [-1, -2]], index=['Product tax', 'Product subsidy'], columns=blocks['Va'].columns)
    recipe.update(value_added_block='Va', value_added_rows=['Wages','Surplus','Positive subsidy'],
                  value_added_factors={'Wages':1,'Surplus':1,'Positive subsidy':-1},
                  tax_bridge='sut_supply_product_taxes', product_tax_rows=['Product tax','Product subsidy'])
    result = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe, {'IT':999})[0]
    assert result['value_added'] == [11e6,22e6]
    assert result['net_product_taxes'] == 4e6
    assert result['gdp'] == 37e6  # Supply taxes cover the total; no second final-use tax.


def test_sut_commodity_emissions_do_not_use_the_activity_axis():
    blocks, recipe, _ = example()
    columns=pd.MultiIndex.from_product([['IT'],['Commodity'],['One','Two','Three']],names=['Region','Level','Item'])
    blocks['Ec']=pd.DataFrame([[1000,2000,3000],[10,20,30],[50,100,150]], index=blocks['E'].index, columns=columns)
    recipe.update(emissions_block='Ec',ghg_sectors=['One','Two','Three'])
    result=browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__),recipe)[0]
    assert len(result['value_added'])==2
    assert result['ghg']==pytest.approx([1.348,2.696,4.044])
    recipe['ghg_sectors']=['One','Two']
    with pytest.raises(ValueError,match='emissions classification changed'):
        browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__),recipe)


def test_restricted_sources_remain_out_of_the_public_indicator_manifest():
    folder=ROOT/'doc/source/_static/data/economy'
    manifest=json.loads((folder/'manifest.json').read_text())
    assert not {'EORA','GTAP'}.intersection(d['source'] for d in manifest['datasets'])
    assert not list(folder.glob('*LOCAL-ONLY*'))


def test_historical_euro_conversion_never_uses_german_mark_rates():
    recipe = {"currency": "EUR", "year": 1995}
    wb = {"countries": {"DEU": {"years": {"1995": {"local_currency_per_usd": 1.4331325}}}}}
    assert browser.usd_factor(recipe, wb) is None
    wb["currency_rates"] = {"EUR": {"years": {"1995": 1.308}}}
    assert browser.usd_factor(recipe, wb) == 1.308


def test_sut_tax_bridge_converts_matching_iot_millions_to_eur(tmp_path):
    folder = tmp_path / "IOT_2011_ixi" / "satellite"
    folder.mkdir(parents=True)
    columns = pd.MultiIndex.from_tuples([("IT", "Households"), ("IT", "Government")])
    pd.DataFrame([[2.5, 1.5]], index=["Tax"], columns=columns).to_csv(folder / "F_Y.txt", sep="\t")
    recipe = {"tax_bridge":"exiobase_matching_iot", "product_tax_rows":["Tax"], "parser_options":{"add_extensions":str(folder.parent)}}
    assert browser.final_demand_taxes(tmp_path / "SUT", recipe) == {"IT":4e6}
    recipe["parser_options"]["add_extensions"] = "/path/to/corresponding-IOT"
    with pytest.raises(ValueError, match="same-year"):
        browser.final_demand_taxes(tmp_path, recipe)


def test_complete_official_exiobase_scope_and_lazy_index():
    folder=ROOT/"doc/source/_static/data/economy"
    manifest=json.loads((folder/"manifest.json").read_text())
    expected={f"exiobase-{release}-{year}-{system}"
              for release, end in [("382",2022),("394",2022),("395",2022),("396",2022),
                                   ("3101",2024),("3102",2024),("3112",2024)]
              for year in range(1995,end+1) for system in ["ixi","pxp"]}
    expected.update(f"exiobase-382-{year}-sut" for year in range(1995,2023))
    expected.update(["exiobase-hybrid-3318-2011-iot","exiobase-hybrid-3318-2011-sut"])
    assert {d["id"] for d in manifest["datasets"] if d["source"]=="EXIOBASE"}==expected
    assert manifest["schema_version"]==2
    for d in manifest["datasets"]:
        snapshot=json.loads((folder/(d["id"]+".json")).read_text())
        template=manifest["templates"][d["template"]]
        assert template["recipe"]["parser_guide"]==snapshot["recipe"]["parser_guide"]
        assert template["recipe"]["source_url"]==snapshot["recipe"]["source_url"]
        assert template["recipe"]["ghg_factors"]==snapshot["recipe"]["ghg_factors"]
        assert all(set(r)=={"code","name","iso3","kind"} for r in template["regions"])
        for metric in ["value_added","gdp","ghg"]:
            assert d["availability"][metric]==((metric != "ghg" or snapshot["recipe"].get("ghg_usable") is not False) and all(r.get(metric) is not None for r in snapshot["regions"]))


def test_all_monetary_sut_income_matches_its_exact_iot():
    folder=ROOT/"doc/source/_static/data/economy"
    for year in range(1995,2023):
        sut=json.loads((folder/f"exiobase-382-{year}-sut.json").read_text())
        iot=json.loads((folder/f"exiobase-382-{year}-ixi.json").read_text())
        assert sut["recipe"]["currency_scale"]==1
        assert iot["recipe"]["currency_scale"]==1e6
        by_region={r["code"]:r for r in iot["regions"]}
        for r in sut["regions"]:
            other=by_region[r["code"]]
            index={s:i for i,s in enumerate(iot["recipe"]["sectors"])}
            for metric in ["value_added","ghg"]:
                assert r[metric]==pytest.approx([other[metric][index[s]] for s in sut["recipe"]["sectors"]],rel=1e-9,abs=1)
            assert r["gdp"]==pytest.approx(other["gdp"],rel=1e-9)


def test_new_native_nf3_and_historical_fx_are_explicit():
    folder=ROOT/"doc/source/_static/data/economy"
    for year in range(1995,2025):
        recipe=json.loads((folder/f"exiobase-3112-{year}-ixi.json").read_text())["recipe"]
        assert recipe["ghg_factors"]["NF3 - air"]==16.1
        assert recipe["expected_units"]["Satellite account"]["NF3 - air"]=="kg"
    wb=json.loads((folder/"world-bank.json").read_text())
    rates=wb["currency_rates"]["EUR"]["years"]
    assert all(str(year) in rates for year in range(1995,2025))
    assert rates["1995"]==1.308
    assert rates["1995"]!=1/wb["countries"]["DEU"]["years"]["1995"]["local_currency_per_usd"]


def test_source_activity_tax_bridge_adds_only_the_value_added_tax_row():
    blocks, recipe, _ = example()
    recipe["tax_bridge"] = "source_activity_taxes"
    tax_fd = browser.final_demand_taxes("unused", recipe)
    assert tax_fd == {"IT": 0.0}
    result = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe, tax_fd)[0]
    assert result["net_product_taxes"] == 3e6
    assert result["gdp"] == 39e6  # VA 36 + product-tax row 3; imports excluded, no final-use taxes.


def test_hybrid_readings_keep_partial_three_gas_ghg():
    folder = ROOT / "doc/source/_static/data/economy"
    for table, block in [("iot", None), ("sut", "Ea")]:
        snapshot = json.loads((folder / f"exiobase-hybrid-3318-2011-{table}.json").read_text())
        recipe = snapshot["recipe"]
        assert recipe["tax_bridge"] == "source_activity_taxes" and recipe["gdp_bridge_verified"]
        assert recipe.get("emissions_block") == block
        assert not any(gas in row for row in recipe["ghg_factors"] for gas in ("HFC", "PFC", "SF6"))
        assert {recipe["ghg_factors"][f"CH4 (air - {a})"] for a in ("Emiss", "Emis_unreg_w")} == {28}
        assert {recipe["ghg_factors"][f"N2O (air - {a})"] for a in ("Emiss", "Emis_unreg_w")} == {265}
        assert all(r["gdp"] is not None and len(r["ghg"]) == len(recipe["sectors"]) for r in snapshot["regions"])


def test_explicit_emerging_gdp_proxy_does_not_invent_a_tax_bridge():
    blocks, recipe, _ = example()
    recipe.update(source="EMERGING",gdp_proxy="native_value_added",gdp_bridge_verified=False)
    result=browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__),recipe)[0]
    assert result["gdp"]==sum(result["value_added"])==36e6
    assert "net_product_taxes" not in result
    recipe.pop("gdp_proxy")
    assert "gdp" not in browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__),recipe)[0]


def test_missing_final_demand_accounts_are_not_zero_observations():
    blocks, recipe, _=example()
    recipe["final_demand_emissions_loaded"]=False
    blocks.pop("EY")
    result=browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__),recipe)[0]
    assert result["ghg"]==pytest.approx([1.348,2.696])
    assert "household_ghg" not in result


def test_reviewed_public_ghg_methods_keep_characterised_rows_and_units():
    folder=ROOT/'doc/source/_static/data/economy'
    manifest=json.loads((folder/'manifest.json').read_text())
    for d in manifest['datasets']:
        s=json.loads((folder/(d['id']+'.json')).read_text());r=s['recipe']
        if not r['ghg_factors']:continue
        if r['source']=='GLORIA':
            assert 'AR5' in r['gwp_basis'] and 'other F-gases unverified' in r['gwp_basis']
            assert r['gwp_horizon']==100
            assert r['ghg_factors']=={"Emissions (EDGAR) | 'GHG_total_EDGAR_consistent'":1000}
            continue
        assert r['gwp_horizon']==100
        assert r['gwp_basis']
        units=r['expected_units']['Satellite account']
        for row,factor in r['ghg_factors'].items():
            assert row in units
            if r['source']=='EXIOBASE' and r['parser_options']['unit']=='Monetary':
                if row in ['HFC - air','PFC - air']:
                    assert units[row]=='kg CO2-eq' and factor==.001
                elif row.startswith('CO2'):assert units[row]=='kg' and factor==.001
                elif row.startswith('CH4'):assert units[row]=='kg' and factor==.028
                elif row.startswith('N2O'):assert units[row]=='kg' and factor==.265
                elif row.startswith('SF6'):assert units[row]=='kg' and factor==23.5
                elif row.startswith('NF3'):assert units[row]=='kg' and factor==16.1
                else:pytest.fail('Unreviewed gas factor '+row)
            elif r['source']=='ADB':
                assert row=='GHG | Total by substance' and factor==1000
                assert 'AR5' in r['gwp_basis']
            elif r['source']=='EMERGING':
                assert factor==1e6 and units[row]=='Mt CO2eq'
                assert r['ghg_proxy']=='fossil_co2_only'
                assert r['final_demand_emissions_loaded'] is False
                assert all('household_ghg' not in region for region in s['regions'])


def test_wiod_sut_uses_signed_final_demand_product_taxes_from_vy():
    blocks, recipe, wb = example()
    blocks['Va'] = blocks['V']
    fd = blocks['EY'].columns
    blocks['VY'] = pd.DataFrame([[-.5]], index=['Product tax'], columns=fd)
    recipe.update(value_added_block='Va', tax_bridge='wiod_sut_vy', ghg_factors={})
    result = browser.aggregate(SimpleNamespace(get_block=blocks.__getitem__), recipe)[0]
    assert result['net_product_taxes'] == 2.5e6
    assert result['gdp'] == 38.5e6
    recipe['price_basis'] = 'Previous year prices'
    row = list(browser.selected_rows([result], {'recipe':recipe, 'metric':'gdp'}, wb))[0]
    assert row['world_bank'] is None and row['difference_percent'] is None
    assert row['unit'] == 'previous-year US$'


@pytest.mark.parametrize("options", [{"table":"IOT","iot_mode":"product"}, {"table":"IOT","iot_mode":"industry"}, {"table":"SUT"}])
def test_figaro_source_bridge_preserves_signed_final_taxes_and_rejects_missing_cells(monkeypatch, tmp_path, options):
    from mario.parsers import figaro
    cache = tmp_path / 'figaro.csv'
    fd_codes, _ = figaro._label_map(figaro.load_figaro_metadata(), level='n')
    rows = [['W2', 'D21X31', 'IT', code, value] for code, value in zip(fd_codes, [2, -.5, 3, 4, 5])]
    rows += [['W2', 'D21X31', 'IT', 'CPA_A01', 100], ['W2', 'OP_RES', 'IT', fd_codes[0], 999]]
    frame = pd.DataFrame(rows, columns=['refArea','rowCode','counterpartArea','colCode','obsValue'])
    frame.to_csv(cache, index=False)
    monkeypatch.setattr(figaro, '_figaro_cache_file', lambda *a, **kw: cache)
    recipe = {'tax_bridge':'figaro_csv', 'year':2023, 'parser_options':options, 'regions':[{'label':'Italy'}]}
    assert browser.final_demand_taxes(tmp_path, recipe) == {'Italy':13.5}
    frame.iloc[1:].to_csv(cache, index=False)
    with pytest.raises(ValueError, match='Incomplete FIGARO'):
        browser.final_demand_taxes(tmp_path, recipe)
    pd.concat([frame, frame.iloc[:1]]).to_csv(cache, index=False)
    with pytest.raises(ValueError, match='Duplicate or missing FIGARO'):
        browser.final_demand_taxes(tmp_path, recipe)


def test_source_quality_exclusions_persist_and_python_exports_withhold_values():
    _, _, wb = example()
    for release, year, bad in [('3.10.1',2021,False),('3.10.1',2022,True),('3.10.1',2024,True),('3.10.2',2022,False),('3.10.2',2023,True),('3.11.2',2024,False)]:
        recipe={'source':'EXIOBASE','release':release,'year':year,'parser_options':{'unit':'Monetary'}}
        browser.annotate_source_quality(recipe)
        assert (recipe.get('ghg_usable') is False) == bad
    folder=ROOT/'doc/source/_static/data/economy'
    snapshot=json.loads((folder/'exiobase-3101-2022-ixi.json').read_text())
    exported=list(browser.selected_rows(snapshot['regions'],{'recipe':snapshot['recipe'],'metric':'ghg'},wb))
    assert all(r['value'] is None and 'withheld' in r['note'] for r in exported)
    assert all('ghg' in r for r in snapshot['regions'])  # Original source aggregates retained only for audit.


def test_gloria_signed_valuation_bridge_reconciles_expenditure_and_never_double_subtracts_subsidies():
    spec=importlib.util.spec_from_file_location("gloria_product_taxes",ROOT/"doc/scripts/gloria/product_taxes.py")
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    snapshot={'recipe':{'id':'example','year':2023,'sectors':['a','b'],'consumption_categories':['FD'],'currency':'USD','currency_scale':1},
              'regions':[{'code':'R1','value_added':[5,5]},{'code':'R2','value_added':[10,10]}],'provenance':{}}
    def row(block,values):
        return {'activity_row_column_totals':[0]*len(values),'commodity_row_column_totals':values,'member':{'name':block}}
    sums={'T4':row('T4',[2,0,0,0,3,0,0,0]),'T5':row('T5',[-.5,0,0,0,-1,0,0,0]),
          'Y4':row('Y4',[4,5]),'Y5':row('Y5',[-.5,-.5]),'Y1':row('Y1',[12,21.5]),'Y2':row('Y2',[0,0]),'Y3':row('Y3',[0,0])}
    bridge=g.build(snapshot,sums);assert bridge['net_product_taxes']==[5,6.5]
    assert bridge['validation']['income_minus_expenditure']==0
    g.apply(snapshot,bridge);assert [r['gdp'] for r in snapshot['regions']]==[15,26.5]
    assert snapshot['recipe']['gdp_bridge_verified']
    sums['Y5']=row('Y5',[.5,.5])
    with pytest.raises(ValueError,match='subsidy sign'):g.build(snapshot,sums)


def test_gloria_source_residual_requires_independent_source_sums_and_keeps_original_values():
    spec=importlib.util.spec_from_file_location('gloria_residual',ROOT/'doc/scripts/gloria/product_taxes.py')
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    snapshot={'recipe':{'id':'source-example','year':2023,'sectors':['a'],'consumption_categories':['FD'],'currency':'USD','currency_scale':1},
              'regions':[{'code':'R1','value_added':[10]}],'provenance':{'economic_members':[{'name':'V','crc32':'v-crc'}]}}
    sums={f'Y{i}':{'activity_row_column_totals':[0],'commodity_row_column_totals':[11 if i==1 else 0], 'member':{'name':f'Y{i}','crc32':f'y{i}-crc'}} for i in range(1,6)}
    for name in ['T4','T5']:sums[name]={'activity_row_column_totals':[0,0],'commodity_row_column_totals':[0,0],'member':{'name':name}}
    with pytest.raises(ValueError,match='World GDP income/expenditure'):g.build(snapshot,sums)
    audit={'V1':{'member':'V','crc32':'v-crc','native_activity':10,'native_commodity':0},
           **{f'Y{i}':{'member':f'Y{i}','crc32':f'y{i}-crc','native_activity':0,'native_commodity':11 if i==1 else 0} for i in range(1,6)}}
    bridge=g.build(snapshot,sums,audit);g.apply(snapshot,bridge)
    assert snapshot['regions'][0]['gdp']==10
    assert bridge['validation']['world_gdp_expenditure']==11
    assert bridge['validation']['income_minus_expenditure']==-1
    assert bridge['validation']['identity_status']=='independently_reproduced_source_residual'
    assert 'not balanced or adjusted' in snapshot['recipe']['gdp_note']
    audit['Y1']['crc32']='different'
    with pytest.raises(ValueError,match='source Y identity mismatch'):g.build(snapshot,sums,audit)


def test_gloria_tax_reader_uses_parser_layout_metadata_tuple_and_destination_regions(monkeypatch):
    import sys
    sys.path.insert(0,str(ROOT))
    from mario.parsers import gloria
    metadata=SimpleNamespace(region_codes=('IT','FR'),sector_names=('One',),final_demand_names=('Households',))
    calls=[]
    def detect(path,year,valuation):
        calls.append((year,valuation))
        return SimpleNamespace(T_path=valuation+'-T',Y_path=valuation+'-Y'),metadata
    def batches(resource,columns,dtype,batch_size):
        assert list(columns)==([0,2] if resource.endswith('T') else [0,1])
        selected={
            'taxes-T':[[1,2],[3,4]],'taxes-Y':[[5,6],[7,8]],
            'subsidies-T':[[-.2,-.3],[-.4,-.5]],'subsidies-Y':[[-.1,-.2],[-.3,-.4]]}[resource]
        values=np.zeros((4,2));values[[1,3]]=selected
        yield np.arange(4),values
    monkeypatch.setattr(gloria,'detect_gloria_layout',detect);monkeypatch.setattr(gloria,'_iter_csv_batches',batches)
    recipe={'year':2023,'tax_bridge':'gloria_valuations','regions':[{'label':'IT'},{'label':'FR'}]}
    result=browser.final_demand_taxes(Path('/local/gloria.zip'),recipe)
    assert result==pytest.approx({'IT':15,'FR':18.6})
    assert calls==[(2023,'taxes'),(2023,'subsidies')]
