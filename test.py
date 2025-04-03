#%% importing an IOT table
import mario

db_iot = mario.parse_exiobase(
    path='/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase 3.8.2/IOT/IOT_2022_ixi.zip',
    table="IOT",
    unit="Monetary",
    version='3.8.2',
)
#%% Aggregate it
db_iot.aggregate("aggregate_IOT.xlsx")
#%% Create a clone scenario just to export with multiple scenarios
db_iot.clone_scenario("baseline","Test - 2022")

#%% Export to flat csv
db_iot.to_flat_csv(
    path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/Product development - Documents/MARIO/Test_export_IOT',
    flows = True,
    coefficients = True,
    scenario_split={                            # scenario split allows to split name of mario scenarios into multiple columns of the exported database if desired
        "separator": " - ",                     # it needs a separator
        "Scenario":0,                           # each column name should be associated to an integer value, which is the position of the string in the list obtained by splitting the mario scenario name with the given separator
        "Year":1,
        "rename_baseline": "Baseline - 2022",   # in case it's desired, you can export the "baseline" mario scenario with a different name
        },
)

#%% Export to sql. The arguments are the same as to export in csv (the method used calls the previous one and adds the export to sql)
db_iot.to_sql(
    path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/Product development - Documents/MARIO/Test_export_IOT',
    flows = True,
    coefficients = True,
    scenario_split={
        "separator": " - ",
        "Scenario":0,
        "Year":1,
        "rename_baseline": "Baseline - 2022",
        },
)

# %% Importing a SUT database
import mario
db_sut = mario.parse_from_txt(
    path='/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-PolitecnicodiMilano/DENG-SESAM - Documenti/c-Research/a-Datasets/Exiobase Hybrid 3.3.18 with VA/flows',
    table="SUT",
    mode="flows",
)
#%% Aggregate it
db_sut.aggregate("aggregate_SUT.xlsx")

#%% Create a clone scenario just to export with multiple scenarios
db_sut.clone_scenario("baseline","Test - 2022")

#%% Export to flat csv
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

#%% Export to sql
db_iot.to_sql(
    path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/Product development - Documents/MARIO/Test_export_IOT',
    flows = True,
    coefficients = True,
    scenario_split={
        "separator": " - ",
        "Scenario":0,
        "Year":1,
        "rename_baseline": "Baseline - 2022",
        },
)