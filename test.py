#%%
import mario
from mario.tools.constants import _MASTER_INDEX as MI
from mario.tools.constants import _ENUM
from mario.tools.constants import SUT, IOT, _INDEX_NAMES
import pandas as pd
import os 

iot_path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase 3.8.2/IOT/IOT_2022_ixi.zip'

db_iot = mario.parse_exiobase(
    path = iot_path,
    table = 'IOT',
    unit = 'Monetary',
    version = "3.8.2",
)

#%%
_SQL_COLUMNS = {
    'cases': {
        _ENUM.Z: {
            0: [f"{MI['r']}_from",f"{_INDEX_NAMES['3levels'][1]}_from",f"{_INDEX_NAMES['3levels'][2]}_from"],
            1: [f"{MI['r']}_to",f"{_INDEX_NAMES['3levels'][1]}_to",f"{_INDEX_NAMES['3levels'][2]}_to"],
        },
        _ENUM.Y: {
            0: [f"{MI['r']}_from",f"{_INDEX_NAMES['3levels'][1]}_from",f"{_INDEX_NAMES['3levels'][2]}_from"],
            1: [f"{MI['r']}_to",f"{_INDEX_NAMES['3levels'][1]}_to",f"{_INDEX_NAMES['3levels'][2]}_to"],
        },
        _ENUM.V: {
            0: [_INDEX_NAMES['1level'][0]],
            1: [f"{MI['r']}_to",f"{_INDEX_NAMES['3levels'][1]}_to",f"{_INDEX_NAMES['3levels'][2]}_to"],
        },
        _ENUM.EY: {
            0: [_INDEX_NAMES['1level'][0]],
            1: [f"{MI['r']}_to",f"{_INDEX_NAMES['3levels'][1]}_to",f"{_INDEX_NAMES['3levels'][2]}_to"],
        },
    },
    'correspondances': {
        _ENUM.z: _ENUM.Z,
        _ENUM.E: _ENUM.V,
        _ENUM.v: _ENUM.V,
        _ENUM.e: _ENUM.V,
        _ENUM.f: _ENUM.V,
        _ENUM.F: _ENUM.V,
    }
}

_matrices_list = {
    'flows': ['Z','Y','V','E','EY','F'],
    'coefficients': ['z','v','e','f','p','w'],
}


# %%
def to_flat_csv(
        self, 
        path: str,
        matrices: list = 'all',
        flows:bool = True,
        coefficients: bool = False,
        scenario_split: str = None,
        export:bool = True,
):
    
    self.flat_matrices = {}
    if matrices == 'all':
        matrices = []
        if flows:
            matrices = _matrices_list['flows']
        if coefficients: 
            if len(matrices) != 0:
                matrices = matrices.append([i for i in _matrices_list['coefficients']])
            else:
                matrices = _matrices_list['coefficients']

        self.calc_all(matrices)
        matrices = sorted(list(set(matrices)))

    for matrix in matrices:
        print(f"Matrix: {matrix}")
        df_all_scenarios = pd.DataFrame()

        for scenario in self.scenarios:
            print(f"   Scenario: {scenario}")

            df = self.query(matrices=[matrix],scenarios=[scenario])        

            if matrix in _SQL_COLUMNS['cases']:
                info = _SQL_COLUMNS['cases'][matrix]
            elif matrix not in _SQL_COLUMNS['correspondances']:
                raise ValueError(f"Matrix {matrix} cannot be exported to SQL")
            else:                
                info = _SQL_COLUMNS['cases'][_SQL_COLUMNS['correspondances'][matrix]]
            
            df.index.names = info[0]
            df.columns.names = info[1]
        
            for level in df.columns.names:
                df = df.stack()
            if isinstance(df,pd.Series):
                df = df.to_frame()
            df.columns = ['Value']
            
            if scenario_split == None:
                scenario_split = {"separator": " - ", "Scenario":0}

            scenarios_columns = []
            for k,v in scenario_split.items():
                if k != "separator":
                    try:
                        df[k] = scenario.split(scenario_split["separator"])[v]
                        scenarios_columns += [k]
                    except:
                        pass
                
            df.reset_index(inplace=True)                
            df.set_index(scenarios_columns,inplace=True)
            df.reset_index(inplace=True)
            df = df.query("Value!=0")

            df_all_scenarios = pd.concat([df_all_scenarios,df],axis=0)

        if export:
            df.to_csv(os.path.join(path,f"{matrix}.csv"),index=False)
            print(f"Exported")
        else:
            self.flat_matrices[matrix]
            print(f"Stored")
    
# %%
db_iot.to_flat_csv(
    path = '/Users/lorenzorinaldi/Documents/GitHub/Test_MARIO_tocsv',
    matrices = ['Y','E','F']
)


# %%
