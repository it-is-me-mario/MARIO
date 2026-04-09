# -*- coding: utf-8 -*-
"""
module contains support functions for parsing GTAP database from GDX files
"""
import pandas as pd

from mario.log_exc.exceptions import FilteringError

def missing(df: pd.DataFrame,
            variant: str,
            indeces: dict,
            ) -> pd.DataFrame:
    #to optimize, takes too long
    """
    Starting from dataframes that include only non-zero values, this function fills in the missing combinations

    :param df: original DataFrame
    :param variant: string that specifies the possible treatment:
        - "dom"
        - "general"
        - "tax"
        - "ptax"
        - "single_region"
        - "single_region_va"
        - "emi_dom"
        - "emi_imp"
        - "emi_proc"
        - "ene_dom"
        - "ene_imp"
  
    :param indeces: Dictionary of indices


    Returns a DataFrame with missing values handled according to the selected mode.
    """
    # Extract useful lists
    r = indeces['r']['main']
    s = indeces['s']['main']
    n = indeces['n']['main']

    if variant == 'dom':
        # Set the index of your DataFrame to the columns you want to check for combinations.
        df_indexed = df.set_index(['COMM', 'agt', 'REG'])
        # Create a complete MultiIndex with all possible combinations.
        all_combinations = pd.MultiIndex.from_product([s, s + n, r], names=['COMM', 'agt', 'REG'])

        # Reindex the DataFrame: add rows for any combination in 'all_combinations' that is not in 'df_indexed'.
        df_full = df_indexed.reindex(all_combinations, fill_value=0)

        # 4. Reset the index to turn the index columns back into regular columns.
        df_full = df_full.reset_index()

        # Domestic only, so SRC=DST
        df_full['DST'] = df_full['REG']
        df_full.rename(columns={'REG': 'SRC'}, inplace=True)
        
        # Check dimensions
        expected_rows = len(s)*len(s+n)*len(r)
        assert len(df_full) == expected_rows, f"[Variant Z] Expected {expected_rows} rows, got {len(df_full)}."
        
        return df_full


    elif variant == 'general':
        c = s 
        a = s + n
        df_indexed = df.set_index(['COMM', 'agt', 'SRC', 'DST'])
        all_combinations = pd.MultiIndex.from_product([c, a, r, r], names=['COMM', 'agt', 'SRC', 'DST'])
        df_full = df_indexed.reindex(all_combinations, fill_value=0).reset_index()
        
        expected_rows = len(c)*len(a)*(len(r)**2)
        assert len(df_full) == expected_rows, f"[Variant items] Expected {expected_rows} rows, got {len(df_full)}."
        return df_full
    
    elif variant == 'tax':
        c = s
        df_indexed = df.set_index(['COMM', 'SRC', 'DST'])
        all_combinations = pd.MultiIndex.from_product([c, r, r], names=['COMM', 'SRC', 'DST'])
        df_full = df_indexed.reindex(all_combinations, fill_value=0).reset_index()

        expected_rows = len(c)*len(r)*len(r)
        assert len(df_full) == expected_rows, \
            f"[Variant tax] Expected {expected_rows} rows, got {len(df_full)}."
        return df_full
    
    elif variant == 'ptax':
        c = s  
        df.drop(columns=['acts'], inplace=True)
        df_indexed = df.set_index(['COMM', 'REG'])
        all_combinations = pd.MultiIndex.from_product([c, r], names=['COMM', 'REG'])
        df_full = df_indexed.reindex(all_combinations, fill_value=0).reset_index()

        expected_rows = len(c)*len(r)
        assert len(df_full) == expected_rows, \
            f"[Variant tax] Expected {expected_rows} rows, got {len(df_full)}."
        return df_full
    
    elif variant == 'single_region':
        c = s 
        a = s + n
        df_indexed = df.set_index(['COMM', 'agt', 'DST'])
        all_combinations = pd.MultiIndex.from_product([c, a, r], names=['COMM', 'agt', 'DST'])
        df_full = df_indexed.reindex(all_combinations, fill_value=0).reset_index()
        
        expected_rows = len(c)*len(a)*len(r)

        assert len(df_full) == expected_rows,f"[items_1reg] Expected {expected_rows} rows, got {len(df_full)}."
        return df_full
    
    elif variant == 'single_region_va':
        #when the commodities are the categories of value added
        endw = df['ENDW'].unique().tolist()
        df_indexed = df.set_index(['ENDW', 'acts', 'DST'])
        all_combinations = pd.MultiIndex.from_product([endw, s, r], names=['ENDW', 'acts', 'DST'])
        df_full = df_indexed.reindex(all_combinations, fill_value=0).reset_index()

        expected_rows = len(endw)*len(s)*len(r)
        
        assert len(df_full) == expected_rows,f"[items_1reg] Expected {expected_rows} rows, got {len(df_full)}."
        return df_full

    # Block for satellite accounts
    elif variant in ['emi_dom', 'emi_imp', 'emi_proc', 'ene_dom', 'ene_imp']:
        # This block handles all looped variants as the logic is similar
        if variant.startswith('emi'):
            group_col = 'em'
            key_cols_map = {
                'emi_dom': ['inputs', 'agt', 'SRC', 'DST'],
                'emi_imp': ['inputs', 'agt', 'SRC', 'DST'],
                'emi_proc': ['comm', 'acts', 'REG']
            }
        else: # energy
            group_col = 'ERG'
            key_cols_map = {
                'ene_dom': ['ERG', 'agt', 'SRC', 'DST'],
                'ene_imp': ['ERG', 'agt', 'SRC', 'DST']
            }
        df_full_list = []
        for group_val, df_group in df.groupby(group_col):
            key_cols = key_cols_map[variant]
            df_indexed = df_group.set_index(key_cols)
            if variant == 'emi_dom':
                c = df_group['inputs'].unique().tolist()
                a = s + n
                multi_index = pd.MultiIndex.from_product([c, a, r, r], names=['inputs', 'agt', 'SRC', 'DST'])
                # Filter for domestic cases where SRC == DST
                multi_index = multi_index[multi_index.get_level_values('SRC') == multi_index.get_level_values('DST')]
            elif variant == 'emi_imp':
                c = df_group['inputs'].unique().tolist()
                a = s + n
                multi_index = pd.MultiIndex.from_product([c, a, r, r], names=['inputs', 'agt', 'SRC', 'DST'])
            elif variant == 'emi_proc':
                c = df_group['comm'].unique().tolist()
                a = s + n
                multi_index = pd.MultiIndex.from_product([c, a, r], names=['comm', 'acts', 'REG'])
            elif variant == 'ene_dom':
                c = df_group['ERG'].unique().tolist()
                a = s + n
                multi_index = pd.MultiIndex.from_product([c, a, r, r], names=['ERG', 'agt', 'SRC', 'DST'])
                # Filter for domestic cases where SRC == DST
                multi_index = multi_index[multi_index.get_level_values('SRC') == multi_index.get_level_values('DST')]
            elif variant == 'ene_imp':
                c = df_group['ERG'].unique().tolist()
                a = s + n
                multi_index = pd.MultiIndex.from_product([c, a, r, r], names=['ERG', 'agt', 'SRC', 'DST'])
            
            # Reindex and append
            #Change category to string to avoid problems with fill_value
            for col in df_indexed.columns:
                if df_indexed[col].dtype.name == 'category':
                    df_indexed[col] = df_indexed[col].astype(str)  # or .astype('object')

            df_reindexed = df_indexed.reindex(multi_index, fill_value=0).reset_index()
            # The group_col might be empty after reindexing
            df_reindexed[group_col] = group_val

            df_full_list.append(df_reindexed)
        df_full = pd.concat(df_full_list, ignore_index=True)
        return df_full
    
    else:
        raise ValueError(f"Unrecognized variant '{variant}'.")

def gdx_to_matrix(df: pd.DataFrame,
                var: str,
                variant_missing: str,
                indeces: dict,
                pivot_index: list = None,
                pivot_columns: list = None,
                ) -> tuple:
    """

    1) Filters DataFrame through column 'VAR' == var to obtain one specific matrix.
    2) Executes function missing() with appropriate variant.
    3) Separates in Z and Y and has 2 pivoted matrices as output.

    Returns: A tuple (pivot_1, pivot_2)
    """

    # 1) Filters according to var
    try:
        df_filtered = df.data[var].records
    except KeyError:
                raise FilteringError(f"Error in filtering dataframe for {var}")
    

    # 2) Apply missing with desired variant
    df_filled = missing(df_filtered, variant_missing, indeces)
    
    df_Z = df_filled[df_filled['agt'].isin(indeces['s']['main'])]
    df_Y = df_filled[df_filled['agt'].isin(indeces['n']['main'])]

    # 3) Pivoting
    # Pivot sectorxsector section
    pivot_Z = df_Z.pivot_table(
        index=pivot_index, 
        columns=pivot_columns, 
        values='value', 
        aggfunc='sum'
    ).fillna(0)

    # Pivot sectorxfinal demand section
    pivot_Y = df_Y.pivot_table(
        index=pivot_index, 
        columns=pivot_columns, 
        values='value', 
        aggfunc='sum'
    ).fillna(0)

    return pivot_Z, pivot_Y

def gdx_to_matrix_rowname(df: pd.DataFrame,
                var: str,
                variant_missing: str,
                indeces: dict,
                row_name_setting: str,
                row_name_categ: str,
                row_name_reg: str = "",
                pivot_index: list = None,
                pivot_columns: list = None,
                split_agt: bool = False,
                ) -> pd.DataFrame or tuple:
    """

    Construction of matrices from files with specific row names.

    1) Filters DataFrame through column 'VAR' == var to obtain one specific matrix.
    2) Drops the 'VAR' column
    3) Executes function missing() with appropriate variant.
    4a) If 'split_agt' is True, separates in 2 matrices for intermediate and final
    4b) If 'split_agt' is False, unique pivot on pivot_index e pivot_columns.
    
    Returns:
    - A DataFrame if split_agt = False
    - A tuple (pivot_1, pivot_2) if split_agt = False
    """

    # 1) Filters according to var
    try:
        df_filtered = df.data[var].records
    except KeyError:
                raise FilteringError(f"Error in filtering dataframe for {var}")

    # 2) Apply missing with desired variant
    df_filled = missing(df_filtered, variant_missing, indeces)

    # 3) Change row name
    if row_name_setting=='only_region':
        df_filled['row_name']=row_name_categ+'_'+df_filled[row_name_reg]
    elif row_name_setting=='only_categ':
        df_filled['row_name']=row_name_categ+'_REG'
    elif row_name_setting=='reg_comm':
        df_filled['row_name']=row_name_categ+'_'+df_filled[row_name_reg]+'_'+df_filled['COMM']
        df_filled.drop(columns='SRC',inplace=True)
        df_filled.drop(columns='COMM',inplace=True)
    elif row_name_setting=='only_endw':
        df_filled['row_name']=row_name_categ+'_REG_'+df_filled['ENDW']
    elif row_name_setting=='only_comm':
        df_filled['row_name']=row_name_categ+'_REG_'+df_filled['COMM']


    # 4) If need to split
    if split_agt:
        df_Z = df_filled[df_filled['agt'].isin(indeces['s']['main'])]
        df_Y = df_filled[df_filled['agt'].isin(indeces['n']['main'])]

        # Pivot part that has sectors as columns (intermediate)
        pivot_Z = df_Z.pivot_table(
            index=pivot_index, 
            columns=pivot_columns, 
            values='value', 
            aggfunc='sum'
        ).fillna(0)

        # Pivot part that has final demand as columns (final)
        pivot_Y = df_Y.pivot_table(
            index=pivot_index, 
            columns=pivot_columns, 
            values='value', 
            aggfunc='sum'
        ).fillna(0)

        return pivot_Z, pivot_Y

    else:
        # Unique pivot
        matrix = df_filled.pivot_table(
            index=pivot_index, 
            columns=pivot_columns, 
            values='value', 
            aggfunc='sum'
        ).fillna(0)

        return matrix
    
def gdx_to_matrix_satellite(df: pd.DataFrame,
                var: str,
                variant_missing: str,
                indeces: dict,
                row_name_setting: str,
                row_name_categ: str,
                pivot_index: list = None,
                pivot_columns: list = None,
                split_agt: bool = False,
                ) -> pd.DataFrame or tuple:
    """

    Construction of matrices from satellite account files

    1) Filters DataFrame through column 'VAR' == var to obtain one specific matrix.
    2) Drops the 'VAR' column
    3) Executes function missing() with appropriate variant.
    4a) If 'split_agt' is True, separates in 2 matrices for intermediate and final
    4b) If 'split_agt' is False, unique pivot on pivot_index e pivot_columns.
    
    Returns:
    - A DataFrame if split_agt = False
    - A tuple (pivot_1, pivot_2) if split_agt = False
    """

    # 1) Filters according to var
    try:
        df_filtered = df.data[var].records
    except KeyError:
                raise FilteringError(f"Error in filtering dataframe for {var}")
    
    # 1b) If needed, select DOM/IMP
    filter_config = {
        'emi_dom': {'column': 'source', 'value': 'DOM'},
        'emi_imp': {'column': 'source', 'value': 'IMP'},
        'ene_dom': {'column': 'SOURCE', 'value': 'DOM'},
        'ene_imp': {'column': 'SOURCE', 'value': 'IMP'}
    }

    if row_name_setting in filter_config:
        config = filter_config[row_name_setting]
        df_filtered = df_filtered[df_filtered[config['column']] == config['value']]
        df_filtered.drop(columns=config['column'], inplace=True)
        
    # 2) Apply missing with desired variant
    df_filled = missing(df_filtered, variant_missing, indeces)

    # 3) Change row name
    if var=='Emi_COMB':
        if row_name_setting=='emi_dom':
            df_filled['row_name']=row_name_categ+'_'+df_filled['em']+'comb_dms_'+df_filled['inputs']
        elif row_name_setting=='emi_imp':
            df_filled['row_name']=row_name_categ+'_'+df_filled['em']+'comb_'+df_filled['SRC']+'_'+df_filled['inputs']
    else:
        if row_name_setting=='emi_dom':
            df_filled['row_name']=row_name_categ+'_'+df_filled['em']+'_dms_'+df_filled['inputs'] #careful: 'EM' element has different lengths
            df_filled.drop(columns='em',inplace=True)
            df_filled.drop(columns='SRC',inplace=True)
            df_filled.drop(columns='inputs',inplace=True)
        elif row_name_setting=='emi_imp':
            df_filled['row_name']=row_name_categ+'_'+df_filled['em']+'_'+df_filled['SRC']+'_'+df_filled['inputs']
            df_filled.drop(columns='em',inplace=True)
            df_filled.drop(columns='SRC',inplace=True)
            df_filled.drop(columns='inputs',inplace=True)
        elif row_name_setting=='emi_proc':
            df_filled['row_name']=row_name_categ+'_'+df_filled['em']+'_REG_'+df_filled['comm']
            df_filled.drop(columns='em',inplace=True)
            df_filled.drop(columns='comm',inplace=True)
        elif row_name_setting=='ene_dom':
            df_filled['row_name']=row_name_categ+'_dms_'+df_filled['ERG'] #domestic
            df_filled.drop(columns='SRC',inplace=True)
            df_filled.drop(columns='ERG',inplace=True)
        elif row_name_setting=='ene_imp':
            df_filled['row_name']=row_name_categ+'_'+df_filled['SRC']+'_'+df_filled['ERG']
            df_filled.drop(columns='SRC',inplace=True)
            df_filled.drop(columns='ERG',inplace=True)

    # 4) If need to split_agt
    if split_agt:
        if row_name_setting=='emi_proc':
            df_Z = df_filled[df_filled['acts'].isin(indeces['s']['main'])]
            df_Y = df_filled[df_filled['acts'].isin(indeces['n']['main'])]
        else:
            df_Z = df_filled[df_filled['agt'].isin(indeces['s']['main'])]
            df_Y = df_filled[df_filled['agt'].isin(indeces['n']['main'])]

        # Pivot part that has sectors as columns (intermediate)
        pivot_Z = df_Z.pivot_table(
            index=pivot_index, 
            columns=pivot_columns, 
            values='value', 
            aggfunc='sum'
        ).fillna(0)

        # Pivot part that has final demand as columns (final)
        pivot_Y = df_Y.pivot_table(
            index=pivot_index, 
            columns=pivot_columns, 
            values='value', 
            aggfunc='sum'
        ).fillna(0)

        return pivot_Z, pivot_Y

    else:
        # Unique pivot
        matrix = df_filled.pivot_table(
            index=pivot_index, 
            columns=pivot_columns, 
            values='value', 
            aggfunc='sum'
        ).fillna(0)

        return matrix
