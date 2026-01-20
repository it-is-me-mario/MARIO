#%%
from importlib import resources
import os
import stat

from matplotlib.table import table
import cvxlab as cl
import shutil
import pandas as pd
from itertools import product

from mario.tools.constants import (
    _ADD_SECTORS_MASTER_SHEET_COLUMNS
)
#%%
def _optimize_in_cvxlab(
        instance,
        main_dir_path,
        model_dir,
        default_model,
        model_settings_from,
        solver,
        scenario=None,
        input_data_files_type: str = 'xlsx'
    ):

    # check if destination folder exists and create it
    dest_dir = os.path.join(main_dir_path, model_dir)
    if os.path.exists(dest_dir):
        response = input(f"Directory '{dest_dir}' already exists. Erase content and overwrite? (y/n): ")
        if response.lower() not in ['yes', 'y']:
            raise FileExistsError(f"Directory '{dest_dir}' already exists, code interrupted by user.")
        
        # Robust deletion: handles read-only files which commonly cause rmtree to fail on Windows
        def handle_remove_readonly(func, path, exc):
            os.chmod(path, stat.S_IWRITE)
            func(path)
            
        shutil.rmtree(dest_dir, onerror=handle_remove_readonly)
    
    os.makedirs(dest_dir, exist_ok=True)

    
    # default for attributes
    import_custom_constants=False
    import_custom_operators=False
    # copy default files into desired directory
    if default_model is not None:
        package_root = resources.files("mario.tools.cvxlab")
        source_dir = package_root / default_model
        if source_dir.exists():
            dest_dir = os.path.join(main_dir_path, model_dir)
            shutil.copy2(source_dir / "model_settings.xlsx", dest_dir)
            shutil.copy2(source_dir / "mapping.xlsx", dest_dir)
            #User defined constants and operators may not be defined
            if (source_dir / "user_defined_constants.py").exists():
                import_custom_constants=True
                shutil.copy2(source_dir / "user_defined_constants.py", dest_dir)
            if (source_dir / "user_defined_operators.py").exists():
                import_custom_operators=True
                shutil.copy2(source_dir / "user_defined_operators.py", dest_dir)
        else:
            raise FileNotFoundError(
                f"Model '{default_model}' not among default options."
            )
    

    # reading mapping file
    mapping = pd.read_excel(os.path.join(main_dir_path, model_dir, "mapping.xlsx"), sheet_name=None, index_col=0)

    # get matrices in flat format 
    instance.to_flat_txt(
        path = "",
        matrices=mapping['matrices']['mario'].to_list(),
        export=False,
        ) 

    # replace columns header of each matrix with cvxlab expected ones
    for matrix in instance.matrices_flat:
        instance.matrices_flat[matrix].rename(
            columns=mapping['sets']['cvxlab'].to_dict(), 
            inplace=True
            )

    if input_data_files_type=='xlsx':
        multiple_input_files=False
    elif input_data_files_type=='csv':
        multiple_input_files=True
    else:
        raise ValueError("input_data_files_type can be either 'xlsx' or 'csv'")
    
    # initialize cvxlab model and create sets file in destination folder
    model = cl.Model(
        model_dir_name = model_dir,
        main_dir_path = main_dir_path,
        log_level = 'info',
        model_settings_from = model_settings_from,
        use_existing_data = False,
        detailed_validation = True,
        import_custom_constants=import_custom_constants,
        import_custom_operators=import_custom_operators,
        input_data_files_type=input_data_files_type,
        multiple_input_files=multiple_input_files,
        )

    # filling sets file
    sets_file = cl.Defaults.ConfigFiles.SETS_FILE
    sets = pd.read_excel(os.path.join(main_dir_path, model_dir, sets_file), sheet_name=None, index_col=None)

    for set_name in mapping['sets']['cvxlab']:
        try: # replace try-except with check on whether set is not "copy_from"
            mario_set = mapping['sets'].query("cvxlab == @set_name")['mario'].values[0]
            column_header = sets['_set_'+set_name.upper()].columns.tolist()
            
            if mario_set == 'Scenario':
                set_list = instance.scenarios
            else:
                set_list = instance.get_index(mario_set)

            sets['_set_'+set_name.upper()] = pd.concat(
                [sets['_set_'+set_name.upper()], 
                pd.DataFrame(set_list, columns=[column_header[0]]),
                ],
                axis=0,
                ignore_index=True
                )
        except:
            pass      

    if default_model=="Split_sectors":
        if scenario is None:
            raise ValueError("scenario must be provided when splitting sectors using cvxlab")
        _inputs_to_cvxlab_split_sectors(instance, sets, scenario, model, main_dir_path, model_dir, mapping,input_data_files_type=input_data_files_type)
    else:

        with pd.ExcelWriter(os.path.join(main_dir_path, model_dir, sets_file), engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            for sheet_name in sets:
                sets[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False) 

        # load model's sets and settings
        model.load_model_coordinates()

        # initialize database
        model.initialize_blank_data_structure() 

        # fill input data
        input_data = pd.read_excel(os.path.join(main_dir_path, model_dir, "input_data\\input_data.xlsx"), sheet_name=None)
        matrix_map = dict(zip( mapping['matrices'].index.to_list(),  mapping['matrices']["cvxlab"]))
        set_map = dict(zip(mapping['sets'].index.to_list(), mapping['sets']["cvxlab"]))    

        for mario_matrix_name, mario_df in instance.matrices_flat.items():

            cvxlab_sheet = matrix_map[mario_matrix_name]
            cvxlab_df = input_data[cvxlab_sheet]
            mario_renamed = mario_df.rename(columns=set_map)
            mario_renamed = mario_renamed.rename(columns={"Value":"values"})
            mario_renamed.columns = [c+"_Name" for c in mario_renamed.columns if c != "values"] + ["values"]

            join_cols = [c for c in mario_renamed.columns if c in cvxlab_df.columns if c != "values"]
            
            # Perform the merge
            merged = cvxlab_df.merge(
                mario_renamed[join_cols + ['values']],
                on=join_cols,
                how="left"
            )

            merged = merged.drop(columns=["values_x"]).rename(columns={"values_y": "values"})

            input_data[cvxlab_sheet] = merged
        
        with pd.ExcelWriter(os.path.join(main_dir_path, model_dir, "input_data\\input_data.xlsx"), engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            for sheet_name in input_data:
                input_data[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)

    # load data from excel to database 
    model.load_exogenous_data_to_sqlite_database(force_overwrite=True)

    model.initialize_problems()

    model.run_model(
        verbose=True,
        solver=solver,
        integrated_problems=False,
    )

    if model.core.problem.problem_status[''] != 'optimal':
        raise ValueError("Cvxlab optimization problem did not solve optimally, check cvxlab log for details.")

    model.load_results_to_database(force_overwrite=True)

    print("Results loaded to database")

    return



def _inputs_to_cvxlab_split_sectors(
        instance,
        sets,
        scenario,
        model,
        main_dir_path,
        model_dir,
        mapping,
        input_data_files_type: str = 'xlsx'
    ):
    
    #Sectors filters
    map_new_parent=dict(zip(
        instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['s']],
        instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['ps']]
    ))
    for value in set(map_new_parent.values()):
        map_new_parent[str(value)] = value

    new_sectors=list(set(instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['s']]))
    parent_sectors=list(set(instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['ps']]))                        
    
    #parent_sectors=list(set(parent_sectors))
    sectors_p_n=new_sectors+parent_sectors
    stable_sectors=[s for s in instance.get_index('Sector') if s not in new_sectors and s not in parent_sectors]

    #Assign filters for new, parent, stable sectors
    sets['_set_SECTOR_FROM']['sector_from_category']=sets['_set_SECTOR_FROM']['sector_from_Name'].apply(
        lambda x: 'new' if x in new_sectors 
        else 'parent' if x in parent_sectors 
        else 'stable' if x in stable_sectors 
        else None
    )
    sets['_set_SECTOR_TO']['sector_to_category']=sets['_set_SECTOR_TO']['sector_to_Name'].apply(
        lambda x: 'new' if x in new_sectors 
        else 'parent' if x in parent_sectors 
        else 'stable' if x in stable_sectors 
        else None
    )
    
    #Export sets excel
    with pd.ExcelWriter(os.path.join(main_dir_path, model_dir, 'sets.xlsx'), engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        for sheet_name in sets:
            sets[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False) 

    # load model's sets and settings
    model.load_model_coordinates()

    # initialize database
    model.initialize_blank_data_structure() 

    #new: get X,Y,Z,V
    #old: get Y,Z
    
    #->modify to csv input data
    if input_data_files_type=='xlsx':
        input_data = pd.read_excel(os.path.join(main_dir_path, model_dir, "input_data\\input_data.xlsx"), sheet_name=None)
    elif input_data_files_type=='csv':
        input_data = {}
    matrix_map = dict(zip( mapping['matrices'].index.to_list(),  mapping['matrices']["cvxlab"]))
    matrix_map_old = dict(zip( mapping['matrices_old'].index.to_list(),  mapping['matrices_old']["cvxlab"]))
    set_map = dict(zip(mapping['sets'].index.to_list(), mapping['sets']["cvxlab"]))    

    #New matrices
    for mario_matrix_name, mario_df in instance.matrices_flat.items():
        cvxlab_table = matrix_map[mario_matrix_name]
        if input_data_files_type=='xlsx':
            cvxlab_df = input_data[cvxlab_table]
        elif input_data_files_type=='csv':
            cvxlab_df = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\{cvxlab_table}.csv")
        mario_df=mario_df[mario_df['scenarios']==f"split_{scenario}"]
        mario_renamed = mario_df.rename(columns=set_map)
        mario_renamed = mario_renamed.rename(columns={"Value":"values"})
        mario_renamed.columns = [c+"_Name" for c in mario_renamed.columns if c != "values"] + ["values"]

        join_cols = [c for c in mario_renamed.columns if c in cvxlab_df.columns if c != "values"]
        
        # Perform the merge
        merged = cvxlab_df.merge(
            mario_renamed[join_cols + ['values']],
            on=join_cols,
            how="left"
        )

        merged = merged.drop(columns=["values_x"]).rename(columns={"values_y": "values"})

        input_data[cvxlab_table] = merged
    
    #Old matrices Zold and Yold
    old_matrices_config = {
            'Z': ('Zold', ['region_from_Name', 'region_to_Name', 'sector_from_Name', 'sector_to_Name']),
            'Y': ('Yold', ['region_from_Name', 'sector_from_Name', 'region_to_Name', 'cons_categ_Name'])
        }

    for mario_name, (target_name, join_cols) in old_matrices_config.items():
        # Filter and rename Mario data
        mario_df = instance.matrices_flat[mario_name]
        mario_df = mario_df[mario_df['scenarios'] == 'original'].rename(columns=set_map)
        mario_df = mario_df.rename(columns={"Value": "values"})
        mario_df.columns = [c + "_Name" if c != "values" else c for c in mario_df.columns]

        # Load base data
        if input_data_files_type == 'xlsx':
            base_df = input_data[target_name]
        elif input_data_files_type == 'csv':
            csv_path = os.path.join(main_dir_path, model_dir, "input_data", f"{target_name}.csv")
            base_df = pd.read_csv(csv_path)
        else:
            raise ValueError("input_data_files_type must be 'xlsx' or 'csv'")

        # Merge and cleanup
        merged = base_df.merge(mario_df[join_cols + ['values']], on=join_cols, how="left")
        input_data[target_name] = merged.drop(columns=["values_x"]).rename(columns={"values_y": "values"})

    #Create dataframe for I_sp_spn
    if input_data_files_type=='xlsx':
        input_data['I_sp_spn']['values'] = (
            input_data['I_sp_spn']['sector_from_Name'].map(map_new_parent) == input_data['I_sp_spn']['sector_to_Name']
            ).astype(int)
    elif input_data_files_type=='csv':
        I_sp_spn = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\I_sp_spn.csv")
        I_sp_spn['values'] = (
            I_sp_spn['sector_from_Name'].map(map_new_parent) == I_sp_spn['sector_to_Name']
            ).astype(int)
        input_data['I_sp_spn'] = I_sp_spn
    
    #Create Trade variable
    Trade_db=instance.split_info['Trades']
    Trade_db=Trade_db.rename(columns={"Quantity":"values"})
    Trade_db = Trade_db.rename(columns=mapping['sets']['cvxlab'].to_dict())
    Trade_db.columns = [col + "_Name" if col != "values" else col for col in Trade_db.columns]
    if input_data_files_type=='xlsx':
        Trade = input_data['Trade']
    elif input_data_files_type=='csv':
        Trade = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\Trade.csv")
    join_cols = ['region_from_Name','region_to_Name','sector_from_Name']
    Trade=Trade.merge(Trade_db[join_cols+['values']], on=join_cols, how='left')
    Trade['values_y']=Trade['values_y'].fillna(0)
    input_data['Trade'] = Trade.drop(columns=["values_x"]).rename(columns={"values_y": "values"})
    
    if input_data_files_type=='xlsx':
        with pd.ExcelWriter(os.path.join(main_dir_path, model_dir, "input_data\\input_data.xlsx"), engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            for sheet_name in input_data:
                input_data[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)
    elif input_data_files_type=='csv':
        for file_name, df in input_data.items():
            df.to_csv(f'{main_dir_path}\\{model_dir}\\input_data\\{file_name}.csv', index=False)

    return 

def _check_cvxlab_parameters(
        cvxlab_path,
        input_data_files_type,
):
    if not os.path.exists(cvxlab_path):
        raise FileNotFoundError(f"Directory where to insert cvxlab files '{cvxlab_path}' does not exist.")
    if input_data_files_type not in ['xlsx','csv']:
        raise ValueError("input_data_files_type can be either 'xlsx' or 'csv'")


    