#%%
import mario
import os

shared_folder = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/Gabriele Casella - Lorenzo_ROSSI/model'
raw_path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase Hybrid 3.3.18 with VA/flows'
aggr_path = 'Exiobase Hybrid 3.3.18 with VA/aggregated'
aggregation_excel = 'aggregations/raw_to_aggregated.xlsx'
mode = 'flows'

#%%
raw_db = mario.parse_from_txt(
    path = raw_path,
    mode=mode,
    table='SUT'
    )

#%%
raw_db.get_aggregation_excel(os.path.join(shared_folder,aggregation_excel))

#%%
aggregated_db = raw_db.aggregate(
    io = os.path.join(shared_folder,aggregation_excel),
    inplace=False, 
    ignore_nan=True
    )

#%%