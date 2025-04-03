#%%
import mario

db_iot = mario.parse_exiobase(
    path='/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase 3.8.2/IOT/IOT_2022_ixi.zip',
    table="IOT",
    unit="Monetary",
    version='3.8.2',
)
#%%
db_iot.aggregate("aggregate_IOT.xlsx")
#%%
db_iot.clone_scenario("baseline","Test - 2022")

db_iot.to_flat_csv(
    path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/Product development - Documents/MARIO/Test_export_IOT',
    flows = True,
    coefficients = True,
    scenario_split={
        "separator": " - ",
        "Scenario":0,
        "Year":1,
        "rename_baseline": "Baseline - 2022",
        },
    export=False,
)

# %%
import mario

db_sut = mario.parse_from_txt(
    path='/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase Hybrid 3.3.18 with VA/flows',
    table="SUT",
    mode="flows",
)
#%%
db_sut.aggregate("aggregate_SUT.xlsx")

#%%
# db_sut.clone_scenario("baseline","Test - 2022")

db_sut.to_flat_csv(
    path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/Product development - Documents/MARIO/Test_export_SUT',
    flows = True,
    coefficients = True,
    scenario_split={
        "separator": " - ",
        "Scenario":0,
        "Year":1,
        "rename_baseline": "Baseline - 2022",
        },
    export=False,
)


# %%
