#%%
import pandas as pd
import copy
from mario.tools.constants import _MASTER_INDEX
from mario.tools.constants import _ENUM

path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/FIGARO E3'

filenames = {
    'use': 'flatfile_FIGARO-e-ic-use_millionEUR_2015.csv',
    'supply': 'flatfile_FIGARO-e-ic-supply_millionEUR_2015.csv',
    'energy': 'flatfile_FIGARO-e_ENE_TJ_2015.csv',
    'employment': 'flatfile_FIGARO-e_employment_2015.csv',
    'emissions': 'flatfile_FIGARO-e_AEM_Gg_CO2e_2015.csv',
}


#%%
data = {}
for file in filenames:
    data[file] = pd.read_csv(f"{path}/{filenames[file]}")

# %% building sets
sets = {
    _MASTER_INDEX['a']: sorted(list(set(data['supply']['colPi']))),
    _MASTER_INDEX['c']: sorted(list(set(data['supply']['rowPi']))),
    _MASTER_INDEX['r']: sorted(list(set(data['supply']['refArea']))),
}
sets[_MASTER_INDEX['f']] = [i for i in sorted(list(set(data['use']['rowPi']))) if i not in sets[_MASTER_INDEX['c']]]
sets[_MASTER_INDEX['n']] = [i for i in sorted(list(set(data['use']['colPi']))) if i not in sets[_MASTER_INDEX['a']]]
 
# %% define units
units = {
    _MASTER_INDEX['a']: pd.DataFrame('million EURO',index=sets[_MASTER_INDEX['a']],columns=['unit']),
    _MASTER_INDEX['c']: pd.DataFrame('million EURO',index=sets[_MASTER_INDEX['c']],columns=['unit']),
    _MASTER_INDEX['f']: pd.DataFrame('million EURO',index=sets[_MASTER_INDEX['f']],columns=['unit']),
}

# %% unstack flat data - U matrix
U = data['use'][data['use']['rowPi'].isin(sets[_MASTER_INDEX['c']])]
U = U[U['colPi'].isin(sets[_MASTER_INDEX['a']])]

U.set_index(['refArea', 'rowPi', 'counterpartArea', 'colPi'],inplace=True)
U = U.drop(columns=[col for col in U.columns if col != 'obsValue'])
U = U.unstack(['counterpartArea', 'colPi'])

U.index = pd.MultiIndex.from_arrays([
    U.index.get_level_values('refArea'),
    [_MASTER_INDEX['c']]*U.shape[0],
    U.index.get_level_values('rowPi'),
], names=[_MASTER_INDEX['r'], 'Level','Item'])

U.columns = pd.MultiIndex.from_arrays([
    U.columns.get_level_values('counterpartArea'),
    [_MASTER_INDEX['a']]*U.shape[1],
    U.columns.get_level_values('colPi'),
], names=[_MASTER_INDEX['r'], 'Level','Item'])


#%% unstack flat data - Y matrix
Y = data['use'][data['use']['rowPi'].isin(sets[_MASTER_INDEX['c']])]
Y = Y[Y['colPi'].isin(sets[_MASTER_INDEX['n']])]

Y.set_index(['refArea', 'rowPi', 'counterpartArea', 'colPi'],inplace=True)
Y = Y.drop(columns=[col for col in Y.columns if col != 'obsValue'])
Y = Y.unstack(['counterpartArea', 'colPi'])

Y.index = U.index

Y.columns = pd.MultiIndex.from_arrays([
    Y.columns.get_level_values('counterpartArea'),
    [_MASTER_INDEX['n']]*Y.shape[1],
    Y.columns.get_level_values('colPi'),
], names=[_MASTER_INDEX['r'], 'Level','Item'])


#%% unstack flat data - V matrix
V = data['use'][data['use']['rowPi'].isin(sets[_MASTER_INDEX['f']])]
V = V[V['colPi'].isin(sets[_MASTER_INDEX['a']])]

V.set_index(['rowPi', 'counterpartArea', 'colPi'],inplace=True)
V = V.drop(columns=[col for col in V.columns if col != 'obsValue'])
V = V.unstack(['counterpartArea', 'colPi'])
V.index.names = ['Item']

V.columns = U.columns

#%% unstack flat data - E matrix
E_energy = data['energy'][data['energy']['colPi'].isin(sets[_MASTER_INDEX['a']])]
E_energy[_MASTER_INDEX['k']] = E_energy['codeIndicator'] + " - " + E_energy['codeEproduct']

E_employment = data['employment'][data['employment']['colPi'].isin(sets[_MASTER_INDEX['a']])]
E_employment[_MASTER_INDEX['k']] = E_employment['codeEstimMethod'] + " - " + E_employment['codeIndicator']

E_emissions = data['emissions'][data['emissions']['colPi'].isin(sets[_MASTER_INDEX['a']])]
E_emissions[_MASTER_INDEX['k']] = E_emissions['codeIndicator']

E = pd.concat([E_emissions,E_employment,E_energy],axis=0)
units[_MASTER_INDEX['k']] = E[[_MASTER_INDEX['k'],'unit']].drop_duplicates().set_index(_MASTER_INDEX['k'])

E.set_index([_MASTER_INDEX['k'], 'refArea', 'colPi'],inplace=True)
E = E.drop(columns=[col for col in E.columns if col != 'obsValue'])
E = E.unstack(['refArea', 'colPi'])
E.index.names = ['Item']
E.columns = U.columns

sets[_MASTER_INDEX['k']] = list(E.index)


# %% unstack flat data - S matrix
S = copy.deepcopy(data['supply'])

S.set_index(['refArea', 'rowPi', 'counterpartArea', 'colPi'],inplace=True)
S = S.drop(columns=[col for col in S.columns if col != 'obsValue'])
S = S.unstack(['counterpartArea', 'rowPi'])

S.index = pd.MultiIndex.from_arrays([
    S.index.get_level_values('refArea'),
    [_MASTER_INDEX['a']]*S.shape[0],
    S.index.get_level_values('colPi'),
], names=[_MASTER_INDEX['r'], 'Level','Item'])

S.columns = pd.MultiIndex.from_arrays([
    S.columns.get_level_values('counterpartArea'),
    [_MASTER_INDEX['c']]*S.shape[1],
    S.columns.get_level_values('rowPi'),
], names=[_MASTER_INDEX['r'], 'Level','Item'])

S.fillna(0,inplace=True)

# %%
Z = pd.concat([U,S],axis=1).fillna(0)
Y = pd.concat([Y,pd.DataFrame(0,index=S.index,columns=Y.columns)],axis=0)
V = pd.concat([pd.DataFrame(0,index=V.index,columns=S.columns),V],axis=1)
E = pd.concat([pd.DataFrame(0,index=E.index,columns=S.columns),E],axis=1)
EY = pd.DataFrame(0,index=E.index,columns=Y.columns)

matrices = {
    'baseline': {
        _ENUM['Z']: Z,
        _ENUM['Y']: Y,
        _ENUM['V']: V,
        _ENUM['E']: E,
        _ENUM['EY']: EY,
    }
}

# for key, df in matrices['baseline'].items():
#     df.sort_index(axis=0, level=list(range(df.index.nlevels)), inplace=True)
#     df.sort_index(axis=1, level=list(range(df.columns.nlevels)), inplace=True)
#     matrices['baseline'][key] = df

# %%



#%%
import mario
path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/FIGARO E3'

db = mario.parse_FIGARO_E3(path)

# %%
db
# %%
