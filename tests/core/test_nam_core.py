"""Native NAM accounting tests; no external workbook or FIGARO codes required."""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from mario.compute.catalog import available_matrix_names, get_matrix_spec
from mario.compute.planner import build_plan
from mario.compute.resolver import ResolutionError
from mario.internal import ModelState, ModelStateMetadata
from mario.internal.nam import NAMSchema
from mario.log_exc.exceptions import DataMissing, WrongInput
from mario.model.assumptions import resolve_tech_assumption
from mario.model.enums import BlockRole, TableKind
from mario.model.labels import get_table_schema_labels
from mario.model.nam import NAM_BLOCKS, NAM_SETS
from mario.parsers.matrix_layouts import normalize_matrix_layouts


def schema(members=None, mode="use_imports", **kwargs):
    return NAMSchema(members or {"IT": {
        "commodity": ["Goods", "Services"], "activity": ["Industry", "Services"],
        "tax": ["Product taxes", "Production taxes"],
        "income_resident": ["Households"], "income_nonresident": ["ROW"],
        "capital_resident": ["Households"], "capital_nonresident": ["ROW"],
        "financial_instrument": ["Loans"], "external_trade": ["ROW"],
    }}, representation=mode, currency="EUR", scale=1e6, period=2023, **kwargs)


def state_for(contract):
    return ModelState(ModelStateMetadata("NAM"), nam_schema=contract)


def metadata(presence="observed", **kwargs):
    return {"presence": presence, "valuation": "source_defined", **kwargs}


def complete_zeros(state):
    for name in state.nam_schema.required_flows():
        state.set_block(name, None, metadata=metadata("declared_zero"))


def dense(frame):
    return frame.sparse.to_dense() if all(isinstance(t, pd.SparseDtype) for t in frame.dtypes) else frame


def test_database_summary_reports_sets_without_resolving_missing_flows():
    from mario.api.nam import NAMDatabase

    state = state_for(schema())
    state.create_scenario("policy", parent="baseline")
    db = NAMDatabase(state, name="Example NAM")
    summary = repr(db)
    assert summary == str(db)
    assert summary.startswith("name = Example NAM\ntable = NAM\nscenarios = ['baseline', 'policy']\n")
    for line in ("Region = 1", "Commodity = 2", "Activity = 2", "Taxes = 2",
                 "Institutional sector - Resident income = 1",
                 "Institutional sector - Resident capital = 1", "Non-financial asset = 0"):
        assert f"{line}\n" in summary
    assert not state.list_matrices()


def test_database_summary_uses_regional_counts_instead_of_pooled_labels():
    from mario.api.nam import NAMDatabase

    db = NAMDatabase(state_for(schema(members={
        "IT": {"commodity": ["Goods", "Services"], "activity": ["Industry"],
               "income_resident": ["Households"]},
        "FR": {"commodity": ["Products", "Other"], "activity": ["Manufacturing", "Trade"]},
    })))
    summary = repr(db)
    assert summary == str(db)
    assert "Region = 2\n" in summary
    assert "Commodity = from 2 to 2 per region\n" in summary
    assert "Activity = from 1 to 2 per region\n" in summary
    assert "Institutional sector - Resident income = from 0 to 1 per region\n" in summary


def test_schema_and_explicit_roles_do_not_require_figaro_codes():
    contract = schema()
    state = state_for(contract)
    assert state.table_kind is TableKind.NAM
    assert "Institutional sector - Nonresident income" in get_table_schema_labels("NAM").dimension_labels
    assert len(state.get_index("income_resident")) == 1
    assert state.get_index("income_resident")[0][-1] == "Households"
    assert state.get_index("capital_resident")[0][-1] == "Households"
    assert state.get_index("income_resident") != state.get_index("capital_resident")
    assert get_matrix_spec("NAM", "B9_d").role is BlockRole.RESULT
    assert get_matrix_spec("NAM", "T").role is BlockRole.VIEW
    assert get_matrix_spec("NAM", "MU").role is BlockRole.FLOW
    assert set(available_matrix_names("NAM")) == set(NAM_BLOCKS)
    assert {"X", "Xa", "Xc", "Xsi_d", "u", "cf_d", "t"} <= set(available_matrix_names("NAM"))
    assert not {"w", "z"} & set(available_matrix_names("NAM"))
    with pytest.raises(KeyError):
        state.compute("w")
    assert resolve_tech_assumption(table="NAM", tech_assumption=None) == (None, None)
    with pytest.raises(WrongInput, match="only supported for SUT"):
        resolve_tech_assumption(table="NAM", tech_assumption="IT")
    with pytest.raises(ValueError, match="explicit NAMSchema"):
        ModelState(ModelStateMetadata("NAM"))


@pytest.mark.parametrize("mode", ["use_imports", "supply_imports"])
def test_T_uses_selected_import_representation_and_never_adds_B9(mode):
    state = state_for(schema(mode=mode))
    complete_zeros(state)
    active = "MU" if mode == "use_imports" else "MS"
    inactive = "MS" if mode == "use_imports" else "MU"
    imports = dense(state.get_block(active))
    imports.iloc[0, 0] = 7
    state.set_block(active, imports, metadata=metadata())
    alternative = dense(state.nam_schema.zero_block(inactive))
    alternative.iloc[0, 0] = 7
    with pytest.raises(ValueError, match="alternative import representation"):
        state.set_block(inactive, alternative, metadata=metadata())
    record = state.set_block(inactive, alternative, metadata=metadata("derived"))
    assert record.role is BlockRole.VIEW
    assets = dense(state.get_block("AF_d"))
    liabilities = dense(state.get_block("LF_d"))
    assets.iloc[0, 0] = -3
    liabilities.iloc[0, 0] = -5
    state.set_block("AF_d", assets, metadata=metadata())
    state.set_block("LF_d", liabilities, metadata=metadata())
    b9 = state.compute("B9_d")
    assert b9.iloc[0, 0] == 2
    record = state._resolve_block_record("B9_d")
    assert record.role is BlockRole.RESULT
    assert record.metadata["dependencies"] == ("AF_d", "LF_d")
    with pytest.raises(ValueError, match="native payment"):
        state.set_block("B9_d", b9, metadata=metadata())
    view = dense(state.compute("T"))
    assert view.to_numpy().sum() == -1  # 7 - 3 - 5, neither alternate import nor B9
    assert view.loc[imports.index[0], imports.columns[0]] == 7
    assert tuple(view.index.names) == ("Region", "Set", "Item")
    assert view.index.equals(view.columns)
    assert state._resolve_block_record("T").role is BlockRole.VIEW
    assert build_plan("T", state) == []


def test_unavailable_data_cannot_be_filled_with_implicit_zeros():
    state = state_for(schema())
    complete_zeros(state)
    state.set_block("TA", None, metadata={"presence": "unavailable"})
    assert not state.has_matrix("TA")
    assert "TA" not in state.list_matrices()
    assert state.validate()["nam"]["baseline"]["unavailable"] == ("TA",)
    with pytest.raises(DataMissing, match="TA"):
        state.compute("T")
    with pytest.raises(DataMissing, match="TA"):
        state.get_block("TA")
    state.set_block("TA", None, metadata=metadata("declared_zero"))
    state.compute("T")
    assert not state.validate()["nam"]["baseline"]["balance_certified"]
    # An unavailable child record masks a valid inherited parent block.
    state.create_scenario("policy")
    state.set_block("AF_d", None, "policy", {"presence": "unavailable"})
    assert not state.has_matrix("AF_d", "policy")
    with pytest.raises(ResolutionError, match="AF_d"):
        state.compute("B9_d", "policy")


def test_full_tax_axes_are_required_in_both_TA_and_TC():
    state = state_for(schema())
    for name in ("TA", "TC"):
        value = dense(state.nam_schema.zero_block(name))
        assert len(value.index) == 2
        with pytest.raises(ValueError, match="full declared tax domain"):
            state.set_block(name, value.iloc[:1], metadata=metadata())
        state.set_block(name, value, metadata=metadata())


def test_balanced_national_chain_keeps_same_named_income_and_capital_nodes_distinct():
    contract = schema({"IT": {
        "commodity": ["Goods"], "activity": ["Industry"], "factor": ["Labour"],
        "income_resident": ["Households"], "capital_resident": ["Households"],
        "consumption": ["Household consumption"], "nonfinancial_asset": ["Machinery"],
    }})
    state = state_for(contract)
    complete_zeros(state)
    payments = {"S": 100, "U": 40, "Va_f": 60, "RI_d": 60,
                "CF_d": 50, "RS_dd": 10, "Yc_c": 50, "Yc_inv": 10, "IK_d": 10}
    for name, amount in payments.items():
        value = dense(state.get_block(name))
        value.iloc[0, 0] = amount
        state.set_block(name, value, metadata=metadata())
    view = dense(state.compute("T"))
    assert (view.sum(axis=0) == view.sum(axis=1)).all()
    income = ("IT", NAM_SETS["income_resident"]["label"], "Households")
    capital = ("IT", NAM_SETS["capital_resident"]["label"], "Households")
    assert view.loc[capital, income] == 10
    assert view.loc[income, capital] == 0
    assert view.loc[income].sum() == 60
    assert view.loc[capital].sum() == 10
    # No financial observations: a balanced nonfinancial chain is not B9 data.
    with pytest.raises(ResolutionError, match="AF_d"):
        state.compute("B9_d")


def test_nonuniform_memberships_preserve_reporting_economies_and_reject_cross_entries():
    contract = schema({
        "IT": {"commodity": ["Goods", "Services"], "activity": ["Industry"]},
        "FR": {"commodity": ["Services"], "activity": ["Services"]},
    })
    assert len(contract.accounts()) == 5  # no Cartesian expansion to six nodes
    state = state_for(contract)
    complete_zeros(state)
    use = dense(state.get_block("U"))
    use.iloc[0, 0] = 3
    use.iloc[2, 1] = 5
    state.set_block("U", use, metadata=metadata())
    view = dense(state.compute("T"))
    assert view.loc[("IT", "Commodity", "Goods"), ("IT", "Activity", "Industry")] == 3
    assert view.loc[("FR", "Commodity", "Services"), ("FR", "Activity", "Services")] == 5
    use.iloc[0, 1] = 1
    with pytest.raises(ValueError, match="mix reference economies"):
        state.set_block("U", use, metadata=metadata())
    assert dense(state.get_block("U")).iloc[0, 1] == 0


def test_rich_layout_preserves_origin_and_product_but_projects_only_to_account():
    layout = {"MU": {
        "rows": ("reference_region", "origin_region", "imported_commodity", "external_trade"),
        "columns": ("reference_region", "activity"),
    }}
    contract = schema({"IT": {"commodity": ["Goods"], "activity": ["Industry"], "external_trade": ["Foreign"]}},
                      matrix_layouts=layout, descriptors={"origin_region": ["DE", "FR"], "imported_commodity": ["Goods", "Services"]})
    spec = contract.block_spec("MU")
    assert spec.row_axes[0].base == spec.row_axes[1].base == "region"
    assert spec.row_axes[0].id != spec.row_axes[1].id
    state = state_for(contract)
    for name in contract.required_flows():
        if name != "MU":
            state.set_block(name, None, metadata=metadata("declared_zero"))
    rows = pd.MultiIndex.from_tuples([
        ("IT", "DE", "Goods", NAM_SETS["external_trade"]["label"], "Foreign"),
        ("IT", "FR", "Services", NAM_SETS["external_trade"]["label"], "Foreign"),
    ], names=("Region", "origin_region", "imported_commodity", "Set", "Item"))
    columns = contract.accounts("activity")
    native = pd.DataFrame([2., 5.], index=rows, columns=columns)
    state.set_block("MU", native, metadata=metadata())
    view = dense(state.compute("T"))
    assert view.loc[("IT", NAM_SETS["external_trade"]["label"], "Foreign"), columns[0]] == 7
    pdt.assert_frame_equal(state.get_block("MU"), native)
    restored = NAMSchema(**json.loads(json.dumps(contract.to_dict())))
    assert restored.to_dict() == contract.to_dict()
    assert copy.deepcopy(contract) is contract
    with pytest.raises(ValueError, match="explicit axes"):
        state.set_block("MU", None, metadata=metadata("declared_zero"))


def test_caches_and_scenario_inheritance_follow_native_flow_changes():
    state = state_for(schema({"IT": {"commodity": ["Goods"], "activity": ["Industry"]}}))
    complete_zeros(state)
    original = dense(state.compute("T"))
    state.create_scenario("policy")
    assert not state.has_matrix("T", "policy")
    use = dense(state.get_block("U"))
    use.iloc[0, 0] = 4
    state.set_block("U", use, "policy", metadata())
    assert dense(state.compute("T", "policy")).to_numpy().sum() == 4
    pdt.assert_frame_equal(dense(state.compute("T")), original)
    # Neither passed frames nor returned frames may mutate the authority.
    use.iloc[0, 0] = 9
    fetched = state.get_block("U", "policy")
    fetched.iloc[0, 0] = 12
    assert dense(state.get_block("U", "policy")).iloc[0, 0] == 4
    state.set_block("S", None, metadata={"presence": "unavailable"})
    assert not state.has_matrix("T", "policy")
    with pytest.raises(DataMissing, match="S"):
        state.compute("T", "policy")


@pytest.mark.parametrize("replacement", [np.nan, np.inf, -np.inf, "missing"])
def test_invalid_values_are_rejected_before_storage(replacement):
    state = state_for(schema())
    value = dense(state.nam_schema.zero_block("TA"))
    if isinstance(replacement, str):
        value = value.astype(object)
    value.iloc[0, 0] = replacement
    with pytest.raises(ValueError, match="numeric|nonfinite"):
        state.set_block("TA", value, metadata=metadata())
    assert not state.has_matrix("TA")


@pytest.mark.parametrize("extra", [{"currency": "USD"}, {"period": 2022}, {"scale": 1}])
def test_monetary_units_cannot_be_mixed(extra):
    state = state_for(schema())
    with pytest.raises(ValueError, match="incompatible"):
        state.set_block("TA", state.nam_schema.zero_block("TA"), metadata=metadata(**extra))


def test_named_layout_checks_preserve_legacy_semantics_and_reject_ambiguous_nam():
    assert normalize_matrix_layouts({"E": ("Region", "Sector")}, table="IOT") == {"E": ("Region", "Sector")}
    assert normalize_matrix_layouts({"V": "Commodity"}, table="SUT") == {"V": ("Commodity",)}
    with pytest.raises(WrongInput, match="explicitly declare"):
        normalize_matrix_layouts({"MU": "Region"}, table="NAM")
    with pytest.raises(WrongInput, match="reference_region"):
        normalize_matrix_layouts({"MU": {"rows": ["origin_region", "external_trade"],
                                               "columns": ["reference_region", "activity"]}}, table="NAM")


def test_runtime_structural_contract_matches_development_proposal():
    root = Path(__file__).resolve().parents[2]
    draft = json.loads((root / "doc/development/nam/catalogue.json").read_text())
    runtime = json.loads((root / "mario/model/nam_schema.json").read_text())
    for key in ("sets", "domains", "axis_roles", "representations"):
        assert runtime[key] == draft[key]
    for block in runtime["matrices"]:
        proposal = next(item for item in draft["matrices"] if item["name"] == block["name"])
        fields = ("name", "rows", "columns", "role", "presence")
        assert {key: block[key] for key in fields} == {key: proposal[key] for key in fields}


def test_single_set_axes_aliases_and_symmetric_account_membership():
    from mario.model.nam import NAM_DOMAINS, nam_set_id, validate_nam_contract

    for key, definition in NAM_SETS.items():
        for alias in (key, definition['label'], definition['short_name'].upper()):
            assert nam_set_id(alias) == key
    for name, block in NAM_BLOCKS.items():
        if name == 'T':
            assert block['rows'] == block['columns'] == 'all_accounts'
        elif block['role'] == 'flow':
            assert len(NAM_DOMAINS[block['rows']]['sets']) == 1
            assert len(NAM_DOMAINS[block['columns']]['sets']) == 1
    root = Path(__file__).resolve().parents[2]
    contract = json.loads((root / 'mario/model/nam_schema.json').read_text())
    contract['domains']['activity']['sets'].append('commodity')
    with pytest.raises(ValueError, match='exactly one'):
        validate_nam_contract(contract)
    contract = json.loads((root / 'mario/model/nam_schema.json').read_text())
    contract['sets']['external_trade']['short_name'] = 'o'
    with pytest.raises(ValueError, match='unambiguously'):
        validate_nam_contract(contract)


def test_other_items_remain_typed_and_imports_have_their_own_set():
    contract = schema({'IT': {'tr': ['Imports'], 'o': ['Allocation', 'Demand', 'Discrepancy']}},
                      item_metadata={'IT': {'o': {'Discrepancy': {'kind': 'statistical_adjustment'}}}})
    assert set(contract.accounts('other').get_level_values('Item')) == {'Allocation', 'Demand', 'Discrepancy'}
    assert contract.accounts('external_trade').get_level_values('Item').tolist() == ['Imports']
    assert contract.item_metadata['IT']['other']['Discrepancy']['kind'] == 'statistical_adjustment'
    with pytest.raises(TypeError):
        contract.item_metadata['IT']['other']['Discrepancy']['kind'] = 'imports'
    with pytest.raises(ValueError, match='Undeclared'):
        schema(item_metadata={'IT': {'o': {'Missing': {'kind': 'adjustment'}}}})


def test_resident_and_nonresident_financial_results_recompute_in_child_scenarios():
    state = state_for(schema())
    complete_zeros(state)
    state.compute('B9_d')
    state.compute('B9_f')
    state.create_scenario('policy')
    assets = dense(state.get_block('AF_f'))
    assets.iloc[0, 0] = 12
    state.set_block('AF_f', assets, 'policy', metadata())
    assert state.compute('B9_f', 'policy').iloc[0, 0] == 12
    assert state.compute('B9_d', 'policy').iloc[0, 0] == 0
    assert state.compute('B9_f').iloc[0, 0] == 0
    assets.iloc[0, 0] = -4
    state.set_block('AF_f', assets, metadata=metadata())
    assert not state.has_matrix('B9_f', 'policy')
    assert state.compute('B9_f', 'policy').iloc[0, 0] == 12
    assert state.compute('B9_f').iloc[0, 0] == -4


def test_account_totals_and_coefficients_use_the_complete_paying_account():
    state = state_for(schema({'IT': {'income_resident': ['Households'],
        'capital_resident': ['Households'], 'consumption': ['Consumption'], 'distribution': ['Taxes']}}))
    complete_zeros(state)
    for name, amount in {'CF_d': 70, 'TP_d': 20, 'RS_dd': 10}.items():
        value = dense(state.get_block(name)); value.iloc[0, 0] = amount
        state.set_block(name, value, metadata=metadata())
    assert state.compute('Xsi_d').iloc[0, 0] == 100
    assert dense(state.compute('cf_d')).iloc[0, 0] == pytest.approx(.7)
    assert dense(state.compute('tp_d')).iloc[0, 0] == pytest.approx(.2)
    assert dense(state.compute('rs_dd')).iloc[0, 0] == pytest.approx(.1)
    assert state.compute('Xsc_d').iloc[0, 0] == 0
    assert state._resolve_block_record('cf_d').role is BlockRole.COEFFICIENT
    record = state._resolve_block_record('cf_d').metadata
    assert record['denominator'] == 'Xsi_d'
    assert record['units'] == 'dimensionless'
    assert 'currency' not in record
    pdt.assert_frame_equal(dense(state.compute('t')).mul(state.compute('X').iloc[:, 0], axis=1),
                           dense(state.compute('T')), check_dtype=False)


def test_account_total_requires_only_the_full_outgoing_coverage_of_its_set():
    state = state_for(schema())
    complete_zeros(state)
    state.set_block('U', None, metadata={'presence': 'unavailable'})
    state.compute('Xsi_d')
    state.compute('rs_dd')
    with pytest.raises(DataMissing, match='U'):
        state.compute('Xa')
    with pytest.raises(DataMissing, match='U'):
        state.compute('T')


def test_zero_account_coefficients_distinguish_inactivity_from_signed_cancellation():
    state = state_for(schema())
    complete_zeros(state)
    assert dense(state.compute('af_d')).to_numpy().sum() == 0
    for name, amount in {'LF_d': -5, 'LF_f': 5}.items():
        value = dense(state.get_block(name)); value.iloc[0, 0] = amount
        state.set_block(name, value, metadata=metadata())
    assert state.compute('Xfi').iloc[0, 0] == 0
    with pytest.raises(ValueError, match='zero account total with nonzero signed payments'):
        state.compute('lf_d')
    value.iloc[0, 0] = 0
    state.set_block('LF_f', value, metadata=metadata())
    assert state.compute('Xfi').iloc[0, 0] == -5
    assert dense(state.compute('lf_d')).iloc[0, 0] == 1


def test_native_coefficient_keeps_import_descriptors_and_projects_only_its_denominator():
    layout = {'MU': {'rows': ('reference_region', 'origin_region', 'imported_commodity', 'external_trade'),
                     'columns': ('reference_region', 'activity')}}
    contract = schema({'IT': {'c': ['Goods'], 'a': ['Industry'], 'tr': ['Imports']}},
                      matrix_layouts=layout, descriptors={'origin_region': ['DE', 'FR'], 'imported_commodity': ['Goods']})
    state = state_for(contract)
    for name in contract.required_flows():
        if name != 'MU':state.set_block(name, None, metadata=metadata('declared_zero'))
    rows = pd.MultiIndex.from_tuples([('IT', origin, 'Goods', 'External trade account', 'Imports') for origin in ('DE', 'FR')],
                                    names=('Region', 'origin_region', 'imported_commodity', 'Set', 'Item'))
    imports = pd.DataFrame([2., 5.], index=rows, columns=contract.accounts('activity'))
    state.set_block('MU', imports, metadata=metadata())
    use = dense(state.get_block('U')); use.iloc[0, 0] = 3
    state.set_block('U', use, metadata=metadata())
    coefficient = dense(state.compute('mu'))
    assert coefficient.index.equals(imports.index)
    assert coefficient.columns.equals(imports.columns)
    np.testing.assert_allclose(coefficient.iloc[:, 0], [.2, .5])
    assert contract.layout('mu') == contract.layout('MU')
    assert [a.id for a in contract.block_spec('mu').row_axes] == ['reference_region', 'origin_region', 'imported_commodity', 'Set', 'Item']


def test_coefficients_and_total_caches_follow_scenarios_and_preserve_input_flows():
    state = state_for(schema())
    complete_zeros(state)
    for name, amount in {'U': 4, 'TA': 6}.items():
        value = dense(state.get_block(name)); value.iloc[0, 0] = amount
        state.set_block(name, value, metadata=metadata())
    original = state.get_block('U')
    assert dense(state.compute('u')).iloc[0, 0] == .4
    state.create_scenario('policy')
    taxes = dense(state.get_block('TA'));taxes.iloc[0, 0] = 16
    state.set_block('TA', taxes, 'policy', metadata())
    assert dense(state.compute('u', 'policy')).iloc[0, 0] == pytest.approx(.2)
    assert state.compute('Xa', 'policy').iloc[0, 0] == 20
    assert dense(state.compute('u')).iloc[0, 0] == .4
    pdt.assert_frame_equal(original, state.get_block('U'))
    assert state._resolve_block_record('Xa', 'policy').metadata['dependencies'] == state.nam_schema.dependencies('Xa')


@pytest.mark.parametrize('mode', ['use_imports', 'supply_imports'])
def test_account_totals_respect_exclusive_import_authority(mode):
    state = state_for(schema(mode=mode));complete_zeros(state)
    active, inactive = ('MU', 'MS') if mode == 'use_imports' else ('MS', 'MU')
    imports = dense(state.get_block(active));imports.iloc[0, 0] = 7
    state.set_block(active, imports, metadata=metadata())
    alternative = dense(state.nam_schema.zero_block(inactive));alternative.iloc[0, 0] = 999
    state.set_block(inactive, alternative, metadata=metadata('derived'))
    assert state.compute('X').production.sum() == 7
    assert dense(state.compute(active.lower())).iloc[0, 0] == 1
