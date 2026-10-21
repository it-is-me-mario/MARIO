"""Developer-only authoring tool for the CHECKED-IN CVXLab workbooks.

Run explicitly after changing this specification, then review the workbooks.
MARIO never calls this tool while preparing or solving a model.
"""
from copy import copy
import json
from pathlib import Path
import re
import shutil

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'Split_sectors'
OPERATORS = (BASE / 'user_defined_operators.py').read_text()
IMPORTS = '''\n# Shared named operators; formulation is declared in model_settings*.xlsx.\nfrom mario.ops.cvxlab_models.split_operators import (\n+    active_kl, signed_kl, quadratic, weighted_active_kl, weighted_signed_kl,\n+    weighted_quadratic, weighted_signed_values, positive_va_kl, free_va_kl,\n+    positive_va_entropy, free_va_entropy, model_masked_values, refinement_entropy, legacy_entropy,\n+)\n+'''.replace('\n+', '\n')


def append_variable(book, source, name, **changes):
    sheet = book['structure_variables']
    headers = [c.value for c in sheet[1]]
    row = next([c.value for c in row] for row in sheet.iter_rows(min_row=2)
               if row[headers.index('variables_info')].value == source)
    changes = dict(variables_info=name, table_key=name) | changes
    for key, value in changes.items():
        row[headers.index(key)] = value
    sheet.append(row)


def add_constraint(book, expression, description):
    book['problem'].append([None, None, expression, description])


def add_staging(book, *, refinement):
    for name in ('Positive_Y_mask', 'Negative_Y_mask'):
        append_variable(book, 'Zero_Y_mask', name, blank_fill=0)
    add_constraint(book, 'model_masked_values(Y_pn_to,Positive_Y_mask) >= 0', 'Preceding positive Y cells')
    add_constraint(book, 'model_masked_values(Y_pn_to,Negative_Y_mask) <= 0', 'Preceding negative Y cells')
    if refinement:
        for name in ('Z_refine', 'Refine_selector'):
            append_variable(book, 'Zero_supply_mask', name, region_to='dim: cols', blank_fill=0)
        append_variable(book, 'Z_supply_to', 'Z_supply_refined', table_key='Z_supply', region_to='dim: cols')


def objective(book, value):
    for row in book['problem'].iter_rows(min_row=2):
        if row[1].value:
            row[1].value = value


def base_workbook():
    book = load_workbook(BASE / 'model_settings.xlsx')
    for sheet in book:
        for row in range(sheet.max_row, 1, -1):
            if all(cell.value is None for cell in sheet[row]):
                sheet.delete_rows(row)
    return book


def compact(book, accounting):
    """Write a separate static workbook; retain trade bands for every delta."""
    for row in book['problem'].iter_rows(min_row=2):
        cell = row[2]
        value = cell.value or ''
        zero = re.fullmatch(r'\s*0\s*==\s*mult\((Zero_\w+),\s*(\w+)\)\s*', value)
        if zero:
            cell.value = f'model_masked_values({zero[2]},{zero[1]}) == 0'
        elif accounting == 'inherit':
            if value.startswith('Zold_') and '<=' in value and value.endswith('*(1+eps)'):
                left, right = value.split('<=', 1)
                cell.value = left + ' == ' + right[:-len('*(1+eps)')]
            elif value.startswith('Zold_') and '>=' in value and value.endswith('*(1-eps)'):
                cell.value = None
            for name in ('Yold', 'Vold'):
                if value.startswith(f'{name}-absval({name})*eps<='):
                    cell.value = name + ' == ' + value.split('<=', 1)[1]
                elif value.startswith(f'{name}+absval({name})*eps>='):
                    cell.value = None


def model_name(complete, flow, va):
    if not complete:
        return 'Split_sectors_MRIO_partial_entropy_V_' + va
    if (flow, va) == ('kl', 'signed_kl'):
        return 'Split_sectors_MRIO_KL'
    if (flow, va) == ('quadratic', 'quadratic'):
        return 'Split_sectors_MRIO_quadratic'
    return 'Split_sectors_MRIO_' + flow + '_V_' + va


def build():
    registry = {}
    staged = ROOT / 'Split_sectors_staged'
    staged.mkdir(exist_ok=True)
    for filename in ('mapping.xlsx', 'user_defined_constants.py'):
        shutil.copy2(BASE / filename, staged / filename)
    (staged / 'user_defined_operators.py').write_text(OPERATORS + IMPORTS)
    book = base_workbook()
    add_staging(book, refinement=True)
    old = next(row[1].value for row in book['problem'].iter_rows(min_row=2) if row[1].value)
    objective(book, old[:-1] + '+refinement_entropy(Z_supply_refined,Z_refine,Refine_selector))')
    book.save(staged / 'model_settings.xlsx')
    book.close()
    for complete, flow in ((False, 'kl'), (True, 'kl'), (True, 'quadratic')):
        for va in ('legacy', 'signed_kl', 'quadratic'):
            name = model_name(complete, flow, va)
            folder = ROOT / name
            folder.mkdir(exist_ok=True)
            registry[name] = dict(complete_intermediate_priors=complete, flow_loss=flow, value_added_loss=va)
            for filename in ('mapping.xlsx', 'user_defined_constants.py'):
                shutil.copy2(BASE / filename, folder / filename)
            (folder / 'user_defined_operators.py').write_text(
                '# Numerical operators only; the workbook declares the formulation.\n'
                'from mario.ops.cvxlab_models.Split_sectors.user_defined_operators import absval, block_diag\n'
                + IMPORTS)
            for accounting in ('strict', 'inherit'):
                book = base_workbook()
                sheet = book['structure_variables']
                sheet.cell(1, 17, 'model_control')
                book['structure_sets'].append(['model_control', 'Numerical weights and support floor', None, None,
                                               'parameter: [y_weight,supply_weight,reference_floor,entropy_floor]'])
                for control, parameter in [('Weight_Y', 'y_weight'), ('Weight_supply', 'supply_weight'), ('Reference_floor', 'reference_floor'), ('Entropy_floor', 'entropy_floor')]:
                    row = [None] * 17
                    row[:6] = ['Model_controls', 'Numerical model control', 'exogenous', None, 'model_control', control]
                    row[16] = f'dim: rows, filters: {{parameter: {parameter}}}'
                    sheet.append(row)
                for mask in ('V_nonnegative_mask', 'V_signed_mask'):
                    append_variable(book, 'Zero_V_mask', mask, blank_fill=0)
                for src, namevar, changes in [
                    ('Y_pn_to', 'Y_all', dict(table_key='Y', region_to='dim: cols')),
                    ('Y_pn_to', 'Y0', dict(type='exogenous', nonneg=None, region_to='dim: cols')),
                    ('Zero_Y_mask', 'Zero_Y_all', dict(table_key='Zero_Y_mask', region_to='dim: cols')),
                    ('Z_supply_to', 'Z_supply_all', dict(table_key='Z_supply', region_to='dim: cols')),
                    ('Z_supply_to', 'Z_supply0', dict(type='exogenous', nonneg=None, region_to='dim: cols')),
                    ('Zero_supply_mask', 'Zero_supply_all', dict(table_key='Zero_supply_mask', region_to='dim: cols')),
                ]:
                    append_variable(book, src, namevar, **changes)
                if complete:
                    append_variable(book, 'Z_use_to', 'Z_use_all', table_key='Z_use', region_to='dim: cols')
                    append_variable(book, 'Z_use_to', 'Z_use0', type='exogenous', nonneg=None, region_to='dim: cols')
                    append_variable(book, 'Zero_use_mask', 'Zero_use_all', table_key='Zero_use_mask', region_to='dim: cols')
                add_staging(book, refinement=not complete)
                if accounting == 'inherit':
                    append_variable(book, 'X_intra', 'RowResidual', type='exogenous', nonneg=None)
                    append_variable(book, 'XT_intra', 'ColumnResidual', type='exogenous', nonneg=None)
                    for row in book['problem'].iter_rows(min_row=2):
                        value = row[2].value or ''
                        if value.startswith('X_intra'):
                            row[2].value = 'Z_supply_from@I_r_st+Z_use_pn_pn_from@I_r_pn+Y_pn_from@I_r_c == X_intra+RowResidual' if '<=' in value else None
                        elif value.startswith('XT_intra'):
                            row[2].value = 'I_row_rs@Z_use_to+I_row_v@V_intra == XT_intra+ColumnResidual' if '<=' in value else None
                add_constraint(book, 'model_masked_values(V,V_nonnegative_mask) >= 0', 'Capital/Labor and other nonnegative factors')
                support = 'Reference_floor' if flow == 'quadratic' else 'Entropy_floor'
                terms = [f'{"quadratic" if flow == "quadratic" else "active_kl"}(Z_use_all,Z_use0,Zero_use_all,{support})'] if complete else ['sum(legacy_entropy(Z_use_n,Z0_all_n,Entropy_floor))', 'sum(legacy_entropy(Z_use_st_p,Z0_st_p,Entropy_floor))']
                if va == 'quadratic':
                    terms.append('quadratic(V,V0,Zero_V_mask,Reference_floor)')
                else:
                    for auxiliary in ('V_signed_positive', 'V_signed_negative'):
                        append_variable(book, 'V', auxiliary, nonneg=True)
                        add_constraint(book, f'{auxiliary} >= 0', 'Nonnegative component of signed TTM/Tax')
                        add_constraint(book, f'model_masked_values({auxiliary},V_nonnegative_mask) == 0', 'Signed components only on TTM/Tax')
                        add_constraint(book, f'model_masked_values({auxiliary},Zero_V_mask) == 0', 'Preserve structural zero factors')
                    add_constraint(book, 'model_masked_values(V-V_signed_positive+V_signed_negative,V_signed_mask) == 0', 'TTM/Tax = positive component minus negative component')
                    loss = 'entropy' if va == 'legacy' else 'kl'
                    terms += [f'positive_va_{loss}(V,V0,Zero_V_mask,V_nonnegative_mask,Entropy_floor)',
                              f'free_va_{loss}(V_signed_positive,V_signed_negative,V0,Zero_V_mask,V_signed_mask,Entropy_floor)']
                yloss = 'quadratic' if flow == 'quadratic' else 'signed_kl'
                zloss = 'quadratic' if flow == 'quadratic' else 'active_kl'
                terms += [f'weighted_{yloss}(Y_all,Y0,Zero_Y_all,Weight_Y,{support})',
                          f'weighted_{zloss}(Z_supply_all,Z_supply0,Zero_supply_all,Weight_supply,{support})']
                if not complete:
                    terms.append('refinement_entropy(Z_supply_refined,Z_refine,Refine_selector,Entropy_floor)')
                if flow == 'quadratic':
                    add_constraint(book, 'weighted_signed_values(Y_all,Y0,Zero_Y_all,Weight_Y) >= 0', 'Y prior sign only when its loss is enabled')
                objective(book, 'Minimize(' + '+'.join(terms) + ')')
                suffix = '' if accounting == 'inherit' else '_strict'
                book.save(folder / f'model_settings{suffix}.xlsx')
                compact(book, accounting)
                book.save(folder / f'model_settings{suffix}_compact.xlsx')
                book.close()
    (ROOT / 'split_models.json').write_text(json.dumps(registry, indent=2) + '\n')


if __name__ == '__main__':
    build()
