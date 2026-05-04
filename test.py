#%%
import mario

#%%
folder= '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/ENTICE - Documents/WPs, Tasks & Deliverables/WP2 - Data/T2.2 & T2.3 - GTAP disaggregation/Disaggregation/MARIO implementation examples'

path_db=f"{folder}/3r 5s example/MRIOT 3r s4_5.xlsx"

path_inventory=f"{folder}/3r 5s example/inventory_3r_5s.xlsx"
path_cvxlab=f"{folder}/3r 5s example"

#%% ---------Parsing of original MRIO database
original_db=mario.parse_from_excel(path=path_db,table='IOT',mode='flows')

# %% Getting the template for adding new sectors
original_db.read_add_sectors_excel(path_inventory,read_inventories=True)

#%% Actually add and split
add_sector_db=original_db.add_sectors(
        inplace=False,
        split=True,
        cvxlab_path=path_cvxlab,
        input_data_files_type='xlsx',
        parent_names={'s2': 's2a'},
        solver = 'MOSEK',
        # solver_parameters= {
        #     'MSK_IPAR_INTPNT_MAX_ITERATIONS': 12000,
        #     # # primal feasibility tolerance (default ~1e-8)
        #     "MSK_DPAR_INTPNT_CO_TOL_PFEAS": 1e-2,
        #     # # dual feasibility tolerance (default ~1e-8)
        #     "MSK_DPAR_INTPNT_CO_TOL_DFEAS": 1e-2,
        #     # # relative optimality gap tolerance (default ~1e-8)
        #     "MSK_DPAR_INTPNT_CO_TOL_REL_GAP": 1e-2,
        #     # Automatic scaling - often solves stagnation with log
        #     "MSK_IPAR_INTPNT_SCALING": 1,
        #     }
    )

# %%
