#%%
from importlib import resources
import os
import sqlite3
import stat

from matplotlib.table import table
import cvxlab as cl
import shutil
import pandas as pd

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
        input_data_files_type: str = 'xlsx',
        solver_parameters=None,
        parent_names=None,
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
        exclude_zeroes=False
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
        multiple_input_files=multiple_input_files,
        use_existing_data = False,
        detailed_validation = True,
        import_custom_constants=import_custom_constants,
        import_custom_operators=import_custom_operators,
        input_data_files_type=input_data_files_type
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
        #Remove rows with missing values, to avoid searching for non-existing cvxlab files
        mapping['matrices'] = mapping['matrices'].dropna(subset=['cvxlab'])
        matrix_map = dict(zip( mapping['matrices'].index.to_list(),  mapping['matrices']["cvxlab"]))
        set_map = dict(zip(mapping['sets'].index.to_list(), mapping['sets']["cvxlab"]))

        for mario_matrix_name, mario_df in instance.matrices_flat.items():
            if mario_matrix_name not in matrix_map:
                continue
            cvxlab_sheet = matrix_map[mario_matrix_name]
            cvxlab_df = input_data[cvxlab_sheet]
            mario_renamed = mario_df.rename(columns=set_map)
            mario_renamed = mario_renamed.rename(columns={"Value":"values"})
            mario_renamed.columns = [c+"_Name" for c in mario_renamed.columns if c != "values"] + ["values"]

            if default_model=="AuSteel" and mario_matrix_name=='ss': #fix by changing cvxlab problem formulation, not inverting to and from in ss
                mario_renamed=mario_renamed.rename(columns={'activity_from_Name': 'activity_to_Name','commodity_to_Name':'commodity_from_Name'}) 
                #Y_ex is not initialized here

            join_cols = [c for c in mario_renamed.columns if c in cvxlab_df.columns if c != "values"]
            
            # Perform the merge
            merged = cvxlab_df.merge(
                mario_renamed[join_cols + ['values']],
                on=join_cols,
                how="left"
            )

            merged = merged.drop(columns=["values_x"]).rename(columns={"values_y": "values"})

            input_data[cvxlab_sheet] = merged
        
        if default_model=='AuSteel':
            # ensure exogenous folder exists
            exo_path = os.path.join(main_dir_path, "exogenous data")
            os.makedirs(exo_path, exist_ok=True)

            # check for V_ex.xlsx and Y_ex.xlsx, create empty files if not exist and raise error to fill them, as they are necessary for the model to run and will be read by the model in the next steps, so better to create them with the right format if not provided by the user, to avoid searching for non-existing files in the next steps
            v_ex_path = os.path.join(exo_path, "V_ex.xlsx")
            y_ex_path = os.path.join(exo_path, "Y_ex.xlsx")
            if not os.path.exists(v_ex_path):
                v_cols = [c for c in input_data['V_ex'].columns if c != 'id']
                pd.DataFrame(columns=v_cols).to_excel(v_ex_path, index=False)

                if not os.path.exists(y_ex_path):
                    y_cols = [c for c in input_data['Y_ex'].columns if c != 'id']
                    pd.DataFrame(columns=y_cols).to_excel(y_ex_path, index=False)
                    raise ValueError(f"V_ex.xlsx and Y_ex.xlsx files not found in exogenous data folder, empty files with the right format have been created, fill them and run again.")
                else:
                    raise ValueError(f"V_ex.xlsx file not found in exogenous data folder, an empty file with the right format has been created, fill it and run again.")

            #changes to Vex
            V_ex=pd.read_excel(v_ex_path)
            join_cols = [c for c in V_ex.columns if c not in ["values"]]
            input_data['V_ex'] = input_data['V_ex'].merge(V_ex, on=join_cols, how='left', suffixes=('', '_new'))
            input_data['V_ex']['values'] = input_data['V_ex']['values_new'].fillna(input_data['V_ex']['values'])
            input_data['V_ex'] = input_data['V_ex'].drop(columns=['values_new'])
            
            #changes to Yex
            Y_ex=pd.read_excel(y_ex_path)
            join_cols = [c for c in Y_ex.columns if c not in ["values"]]
            input_data['Y_ex'] = input_data['Y_ex'].merge(Y_ex, on=join_cols, how='left', suffixes=('', '_new'))
            input_data['Y_ex']['values'] = input_data['Y_ex']['values_new'].fillna(input_data['Y_ex']['values'])
            input_data['Y_ex'] = input_data['Y_ex'].drop(columns=['values_new'])

        with pd.ExcelWriter(os.path.join(main_dir_path, model_dir, "input_data\\input_data.xlsx"), engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            for sheet_name in input_data:
                input_data[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)

    # load data from excel to database 
    model.load_exogenous_data_to_sqlite_database(force_overwrite=True)

    model.initialize_problems()

    if solver_parameters is not None:
        model.run_model(
            verbose=True,
            solver=solver,
            integrated_problems=False,
            mosek_params=solver_parameters,
        )
    else:
         model.run_model(
            verbose=True,
            solver=solver,
            integrated_problems=False)

    if model.core.problem.problem_status[''] != 'optimal':
        raise ValueError("Cvxlab optimization problem did not solve optimally, check cvxlab log for details.")

    model.load_results_to_database(force_overwrite=True)

    print("Results loaded to database")

    if default_model=="Split_sectors":
        map_new_parent=dict(zip(
        instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['s']],
        instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['ps']]
        ))
        for value in set(map_new_parent.values()):
            map_new_parent[str(value)] = value
        optimized_matrices=_cvxlab_results_parser_split_sectors(dest_dir,instance.matrices_flat,parent_names)

    else:
        optimized_matrices = _cvxlab_results_parser(dest_dir,mapping,default_model,instance.matrices_flat)
    
    return optimized_matrices


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
    
    sets['_set_SCALAR']['scalar_Name']=instance.split_info['Tolerances']['tol_Name']
    sets['_set_SCALAR']['scalar_tolerance']=instance.split_info['Tolerances']['tol_Name']

    #Export sets excel
    with pd.ExcelWriter(os.path.join(main_dir_path, model_dir, 'sets.xlsx'), engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        for sheet_name in sets:
            sets[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False) 

    # load model's sets and settings
    model.load_model_coordinates()

    # initialize database
    model.initialize_blank_data_structure() 

    #Get input data structure
    if input_data_files_type=='xlsx':
        input_data = pd.read_excel(os.path.join(main_dir_path, model_dir, "input_data\\input_data.xlsx"), sheet_name=None)
    elif input_data_files_type=='csv':
        input_data = {}
    #Remove rows with missing values, to avoid searching for non-existing cvxlab files
    mapping['matrices'] = mapping['matrices'].dropna(subset=['cvxlab'])
    matrix_map = dict(zip( mapping['matrices'].index.to_list(),  mapping['matrices']["cvxlab"]))
    matrix_map_old = dict(zip( mapping['matrices_old'].index.to_list(),  mapping['matrices_old']["cvxlab"]))
    set_map = dict(zip(mapping['sets'].index.to_list(), mapping['sets']["cvxlab"]))    

    #New matrices
    for mario_matrix_name, mario_df in instance.matrices_flat.items():
        if mario_matrix_name not in matrix_map.keys():
            continue
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
    
    #Old matrices Zold, Yold and Vold
    old_matrices_config = {
            'Z': ('Zold', ['region_from_Name', 'region_to_Name', 'sector_from_Name', 'sector_to_Name']),
            'Y': ('Yold', ['region_from_Name', 'sector_from_Name', 'region_to_Name', 'cons_categ_Name']),
            'V': ('Vold', ['factor_Name','region_to_Name', 'sector_to_Name'])
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

    #Create dataframe for I_p_pn
    if input_data_files_type=='xlsx':
        input_data['I_p_pn']['values'] = (
            input_data['I_p_pn']['sector_from_Name'].map(map_new_parent) == input_data['I_p_pn']['sector_to_Name']
            ).astype(int)
        input_data['tol']['values']=instance.split_info['Tolerances']['values']
    elif input_data_files_type=='csv':
        I_p_pn = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\I_p_pn.csv")
        I_p_pn['values'] = (
            I_p_pn['sector_from_Name'].map(map_new_parent) == I_p_pn['sector_to_Name']
            ).astype(int)
        input_data['I_p_pn'] = I_p_pn
        tol= pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\tol.csv")
        tol['values']=instance.split_info['Tolerances']['values']
        input_data['tol'] = tol
    
    #Create Trade variable
    Trade_db=instance.split_info['Trades']
    Trade_db=Trade_db.rename(columns={"Quantity":"values"})
    Trade_db = Trade_db.rename(columns=mapping['sets']['cvxlab'].to_dict())
    
    #Check trade data consistency with original table
    regions=sets['_set_REGION_FROM']['region_from_Name'].to_list()
    Trade_inconsistency=False
    for new_sector in new_sectors:
        parent_sector=map_new_parent[new_sector]
        for rf in regions:
            for rt in regions:
                if rf==rt:
                    continue
                trade_row = Trade_db.loc[(Trade_db['sector_from']==new_sector) & (Trade_db['region_from']==rf) & (Trade_db['region_to']==rt)]
                if trade_row.empty:
                    continue
                Zsum=instance.Z.loc[(rf, 'Sector',parent_sector), (rt, 'Sector',slice(None))].sum()
                Ysum=instance.Y.loc[(rf, 'Sector',parent_sector), (rt, 'Consumption category',slice(None))].sum()
                trade_value=trade_row['values'].values[0]  
                if trade_value>Zsum+Ysum:
                    Trade_inconsistency=True
                    print(f"Trade inconsistency: for {rf} to {rt} new sector trade {trade_value} is larger than parent Z and Y row sum: {Zsum+Ysum}")
    if Trade_inconsistency:
        raise ValueError(f"Trade inconsistencies found, fix before contininuing")

    Trade_db.columns = [col + "_Name" if col != "values" else col for col in Trade_db.columns]
    if input_data_files_type=='xlsx':
        Trade = input_data['Trade']
        Trade_selector = input_data['Trade_selector']
    elif input_data_files_type=='csv':
        Trade = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\Trade.csv")
        Trade_selector = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\Trade_selector.csv")
    join_cols = ['region_from_Name','region_to_Name','sector_from_Name']
    Trade=Trade.merge(Trade_db[join_cols+['values']], on=join_cols, how='left')
    Trade['values_y']=Trade['values_y'].fillna(0)
    #Set to 0 trades within the same region, as could cause inconsistencies
    same_region_mask = Trade['region_from_Name'] == Trade['region_to_Name']
    Trade.loc[same_region_mask, 'values_y'] = 0
    input_data['Trade'] = Trade.drop(columns=["values_x"]).rename(columns={"values_y": "values"})

    #Create trade selection matrix
    Trade_selector['values']=0
    for rf in instance.get_index('Region'):
        for rt in instance.get_index('Region'):
            for sf in new_sectors:
                if not Trade_db[(Trade_db['region_from_Name']==rf) & (Trade_db['region_to_Name']==rt) & (Trade_db['sector_from_Name']==sf)].empty:
                    Trade_selector.loc[
                        (Trade_selector['region_from_Name']==rf) & 
                        (Trade_selector['region_to_Name']==rt) & 
                        (Trade_selector['sector_from_Name']==sf),
                        'values'
                    ]=1
    input_data['Trade_selector'] = Trade_selector
    
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

def _cvxlab_results_parser(
        dest_dir,
        mapping,
        default_model,
        flat_matrices,
        parent_names=None,
):

    if default_model=='Split_sectors':  
        mario_matrices=_cvxlab_results_parser_split_sectors(dest_dir,flat_matrices,parent_names)

    else:
        # Reading mapping file
        matrices=list(mapping['result matrices'].index)

        result_matrices={}
        conn = sqlite3.connect(os.path.join(dest_dir, "database.db"))
        for matrix in matrices:
            result_matrices[matrix]=pd.read_sql_query(f"SELECT * FROM {matrix}" , conn)
        conn.close()

        if default_model=="AuSteel":
            #Create a fictitious column for Y which is aggregated
            result_matrices['Y']['cons_categ_Name']='Unique_cc'
            result_matrices['Y']['region_to_Name']='Unique_region'
        mario_matrices={}
        for matrix in matrices:
            mario_name = mapping['result matrices'].loc[matrix, 'mario']
            indeces = [s.strip(" '") for s in mapping['result matrices'].loc[matrix, 'indeces'].split(',')]
            unstack=[s.strip(" '") for s in mapping['result matrices'].loc[matrix, 'unstack'].split(',')]
            df=result_matrices[matrix].drop(columns=['id']).set_index(indeces)['values'].unstack(unstack)
            #To completely renovate, probably inserting new colums "row label" and "col label" in the mapping file
            df.index = pd.MultiIndex.from_tuples(
                [(idx[0], str(mapping['result matrices'].loc[matrix, 'row level']), idx[1]) for idx in df.index],
                names=['Region', 'Level', 'Item']
            )
            df.columns = pd.MultiIndex.from_tuples(
                [(col[0], str(mapping['result matrices'].loc[matrix, 'col level']), col[1]) for col in df.columns],
                names=['Region', 'Level', 'Item']
            )
            mario_matrices[mario_name]=df

    return mario_matrices

def _cvxlab_results_parser_split_sectors(
        dest_dir,
        flat_matrices,
        parent_names #map of new sector to parent sector names, to replace parent sector with new name that excludes the new sector
    ):

    #Read from sql database
    conn = sqlite3.connect(os.path.join(dest_dir, "database.db"))
    db_Z_supply = pd.read_sql_query("SELECT * FROM Z_supply" , conn).drop(columns=['id'])
    db_Z_use = pd.read_sql_query("SELECT * FROM Z_use" , conn).drop(columns=['id'])
    db_Y = pd.read_sql_query("SELECT * FROM Y" , conn).drop(columns=['id'])
    db_V=pd.read_sql_query("SELECT * FROM V" , conn).drop(columns=['id'])
    conn.close()

    #Obtain sets info
    sets=pd.read_excel(os.path.join(dest_dir, "sets.xlsx"), sheet_name=None)
    regions=sets['_set_REGION_FROM']['region_from_Name'].to_list()
    cons_categories=sets['_set_CONS_CATEG']['cons_categ_Name'].to_list()
    sectors_df=sets['_set_SECTOR_FROM']
    sectors_stable=[s for s in sectors_df[sectors_df['sector_from_category']=='stable']['sector_from_Name'].to_list()]
    sectors_parent=[s for s in sectors_df[sectors_df['sector_from_category']=='parent']['sector_from_Name'].to_list()]
    sectors_new=[s for s in sectors_df[sectors_df['sector_from_category']=='new']['sector_from_Name'].to_list()]

    #Compose the complete Znew, taking stable values from Zold
    if 'original' in flat_matrices['Z']['scenarios'].unique():
        scenario_to_extract='original'
    else:
        scenario_to_extract='baseline'
    flat_Zold=flat_matrices['Z'][flat_matrices['Z']['scenarios'] == scenario_to_extract].drop(columns='scenarios')
    flat_Zold=flat_Zold.rename(columns={'Value': 'values'})
    flat_Zold.columns = [f"{col}_Name" if col != "values" else col for col in flat_Zold.columns]
    Z=pd.concat([db_Z_supply,db_Z_use,flat_Zold[flat_Zold['sector_from_Name'].isin(sectors_stable) & flat_Zold['sector_to_Name'].isin(sectors_stable)]])
    Z=Z.set_index(['region_from_Name', 'sector_from_Name', 'region_to_Name', 'sector_to_Name'])['values'].unstack(['region_to_Name', 'sector_to_Name'])
    Z.index = pd.MultiIndex.from_tuples(
                [(idx[0], 'Sector', idx[1]) for idx in Z.index],
                names=['Region', 'Level', 'Item']
            )
    Z.columns = pd.MultiIndex.from_tuples(
                [(col[0], 'Sector', col[1]) for col in Z.columns],
                names=['Region', 'Level', 'Item']
            )
    # Reorder columns to match regions first, then sectors within each region
    sector_order = sectors_df['sector_from_Name'].to_list()
    Z = Z.reindex(
        columns=sorted(
            Z.columns,
            key=lambda x: (x[0], sector_order.index(x[2]) if x[2] in sector_order else float('inf'))
        )
    )
    
    #Compose the complete Ynew, taking stable values from Yold
    flat_Yold=flat_matrices['Y'][flat_matrices['Y']['scenarios'] == scenario_to_extract].drop(columns='scenarios')
    flat_Yold=flat_Yold.rename(columns={'Value': 'values'})
    flat_Yold.columns = [f"{col}_Name" if col != "values" else col for col in flat_Yold.columns]
    Y=pd.concat([db_Y,flat_Yold[flat_Yold['sector_from_Name'].isin(sectors_stable)]])
    Y=Y.set_index(['region_from_Name', 'sector_from_Name', 'region_to_Name', 'cons_categ_Name'])['values'].unstack(['region_to_Name', 'cons_categ_Name'])
    Y.index = pd.MultiIndex.from_tuples(
                [(idx[0], 'Sector', idx[1]) for idx in Y.index],
                names=['Region', 'Level', 'Item']
            )
    Y.columns = pd.MultiIndex.from_tuples(
                [(col[0], 'Consumption category', col[1]) for col in Y.columns],
                names=['Region', 'Level', 'Item']
            )
    # Reorder columns to match regions first, then sectors within each region
    Y = Y.reindex(
        columns=sorted(
            Y.columns,
            key=lambda x: (x[0], sector_order.index(x[2]) if x[2] in sector_order else float('inf'))
        )
    )
    
    #Compose the complete V
    flat_V=flat_matrices['V'][flat_matrices['V']['scenarios'] == scenario_to_extract].drop(columns='scenarios')
    flat_V=flat_V.rename(columns={'Value': 'values'})
    flat_V.columns = [f"{col}_Name" if col != "values" else col for col in flat_V.columns]
    V=pd.concat([db_V,flat_V[flat_V['sector_to_Name'].isin(sectors_stable)]])
    V=V.set_index(['factor_Name','region_to_Name', 'sector_to_Name'])['values'].unstack(['region_to_Name', 'sector_to_Name'])
    V.index.name="Item"
    V.columns = pd.MultiIndex.from_tuples(
                [(col[0], 'Sector', col[1]) for col in V.columns],
                names=['Region', 'Level', 'Item']
            )
    # Reorder columns to match regions first, then sectors within each region
    V = V.reindex(
        columns=sorted(
            V.columns, 
            key=lambda x: (x[0], sector_order.index(x[2]) if x[2] in sector_order else float('inf'))
        )
    )
    
    #Change parent sector name
    if parent_names:
        for matrix in [Z,Y,V]:
            matrix.columns = pd.MultiIndex.from_tuples(
                [(col[0], col[1], parent_names.get(col[2], col[2])) for col in matrix.columns],
                names=matrix.columns.names
            )
        for matrix in [Z,Y]:
            matrix.index = pd.MultiIndex.from_tuples(
                [(idx[0], idx[1], parent_names.get(idx[2], idx[2])) for idx in matrix.index],
                names=matrix.index.names
            )

    return {
        'Z': Z,
        'Y': Y,
        'V': V
        }


def _create_input_data_for_cvxlab(
        instance,
        main_dir_path,
        model_dir,
        default_model,
        model_settings_from,
        solver,
        scenario=None,
        input_data_files_type: str = 'xlsx',
    ):

    #Only for split problem, to implement in general?
    if default_model!="Split_sectors":
        raise ValueError("_create_input_data_for_cvxlab function currently only implemented for Split_sectors model, to be implemented in general if needed")
    else:
        # check if destination folder exists
        dest_dir = os.path.join(main_dir_path, model_dir)
        if not os.path.exists(dest_dir):
            raise FileNotFoundError(f"Declared directory of cvxlab files '{dest_dir}' does not exist.") 

        # reading mapping file
        mapping = pd.read_excel(os.path.join(main_dir_path, model_dir, "mapping.xlsx"), sheet_name=None, index_col=0)

        # get matrices in flat format 
        instance.to_flat_txt(
            path = "",
            matrices=mapping['matrices']['mario'].to_list(),
            export=False,
            exclude_zeroes=False
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
        
        # Reading sets file
        sets_file = cl.Defaults.ConfigFiles.SETS_FILE
        sets = pd.read_excel(os.path.join(main_dir_path, model_dir, sets_file), sheet_name=None, index_col=None)

        #Sectors filters
        map_new_parent=dict(zip(
            instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['s']],
            instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['ps']]
        ))
        for value in set(map_new_parent.values()):
            map_new_parent[str(value)] = value

        new_sectors=list(set(instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['s']]))
        parent_sectors=list(set(instance.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[instance.meta.table]['ps']]))                        
        
        #Get input data structure
        if input_data_files_type=='xlsx':
            input_data = pd.read_excel(os.path.join(main_dir_path, model_dir, "input_data\\input_data.xlsx"), sheet_name=None)
        elif input_data_files_type=='csv':
            input_data = {}
        matrix_map = dict(zip( mapping['matrices'].index.to_list(),  mapping['matrices']["cvxlab"]))
        set_map = dict(zip(mapping['sets'].index.to_list(), mapping['sets']["cvxlab"]))    

        # --- New matrices ---
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
        
        #Old matrices Zold, Yold, Vold
        old_matrices_config = {
                'Z': ('Zold', ['region_from_Name', 'region_to_Name', 'sector_from_Name', 'sector_to_Name']),
                'Y': ('Yold', ['region_from_Name', 'sector_from_Name', 'region_to_Name', 'cons_categ_Name']),
                'V': ('Vold', ['Factor_of_production_Name','region_to_Name','sector_to_Name'])
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
            input_data['tol']['values']=instance.split_info['Tolerances']['values']
        elif input_data_files_type=='csv':
            I_sp_spn = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\I_sp_spn.csv")
            I_sp_spn['values'] = (
                I_sp_spn['sector_from_Name'].map(map_new_parent) == I_sp_spn['sector_to_Name']
                ).astype(int)
            input_data['I_sp_spn'] = I_sp_spn
            tol= pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\tol.csv")
            tol['values']=instance.split_info['Tolerances']['values']
            input_data['tol'] = tol
        
        #Create Trade variable
        Trade_db=instance.split_info['Trades']
        Trade_db=Trade_db.rename(columns={"Quantity":"values"})
        Trade_db = Trade_db.rename(columns=mapping['sets']['cvxlab'].to_dict())

        #Check trade data consistency with original table
        regions=sets['_set_REGION_FROM']['region_from_Name'].to_list()
        for new_sector in new_sectors:
            parent_sector=map_new_parent[new_sector]
            Trade_inconsistencies=pd.DataFrame(columns=['Region_from','Region_to','Trade_value','Z_Y_sum'])
            for rf in regions:
                for rt in regions:
                    if rf==rt:
                        continue
                    trade_row = Trade_db.loc[(Trade_db['Region_from']==rf) & (Trade_db['Region_to']==rt)]
                    if trade_row.empty:
                        continue
                    Zsum=instance.Z.loc[(rf, 'Sector',parent_sector), (rt, 'Sector',slice(None))].sum()
                    Ysum=instance.Y.loc[(rf, 'Sector',parent_sector), (rt, 'Consumption category',slice(None))].sum()
                    trade_value=trade_row['Quantity'].values[0]  
                    if trade_value>Zsum+Ysum:
                        print(f"Trade inconsistency: for {rf} to {rt} new sector trade {trade_value} is larger than parent Z and Y row sum: {Zsum+Ysum}")
                        Trade_inconsistencies = pd.concat([Trade_inconsistencies, new_row], ignore_index=True)
                        new_row = pd.DataFrame([{'Region_from':rf,'Region_to':rt,'Trade_value':trade_value,'Z_Y_sum':Zsum+Ysum}])
            if not Trade_inconsistencies.empty:
                print(Trade_inconsistencies)
                raise ValueError(f"Trade inconsistencies found for new sector {new_sector}")


        Trade_db.columns = [col + "_Name" if col != "values" else col for col in Trade_db.columns]
        if input_data_files_type=='xlsx':
            Trade = input_data['Trade']
            Trade_selector = input_data['Trade_selector']
        elif input_data_files_type=='csv':
            Trade = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\Trade.csv")
            Trade_selector = pd.read_csv(f"{main_dir_path}\\{model_dir}\\input_data\\Trade_selector.csv")
        join_cols = ['region_from_Name','region_to_Name','sector_from_Name']
        Trade=Trade.merge(Trade_db[join_cols+['values']], on=join_cols, how='left')
        Trade['values_y']=Trade['values_y'].fillna(0)
        same_region_mask = Trade['region_from_Name'] == Trade['region_to_Name']
        Trade.loc[same_region_mask, 'values_y'] = 0
        input_data['Trade'] = Trade.drop(columns=["values_x"]).rename(columns={"values_y": "values"})

        #Create trade selection matrix
        Trade_selector['values']=0
        for rf in instance.get_index('Region'):
            for rt in instance.get_index('Region'):
                for sf in new_sectors:
                    if not Trade_db[(Trade_db['region_from_Name']==rf) & (Trade_db['region_to_Name']==rt) & (Trade_db['sector_from_Name']==sf)].empty:
                        Trade_selector.loc[
                            (Trade_selector['region_from_Name']==rf) & 
                            (Trade_selector['region_to_Name']==rt) & 
                            (Trade_selector['sector_from_Name']==sf),
                            'values'
                        ]=1
        input_data['Trade_selector'] = Trade_selector
        
        if input_data_files_type=='xlsx':
            with pd.ExcelWriter(os.path.join(main_dir_path, model_dir, "input_data\\input_data.xlsx"), engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                for sheet_name in input_data:
                    input_data[sheet_name].to_excel(writer, sheet_name=sheet_name, index=False)
        elif input_data_files_type=='csv':
            for file_name, df in input_data.items():
                df.to_csv(f'{main_dir_path}\\{model_dir}\\input_data\\{file_name}.csv', index=False)

    return

# def _split_sector_consistency_checK(
        
#     ):
#     #check that for each region, the trade of new commodity is smaller than X of commodity
    
#     return