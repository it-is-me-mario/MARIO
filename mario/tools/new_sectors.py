#Code to enhance tables with new sectors, either splitting an existing "parent" sector or adding a new one

import pandas as pd
from copy import deepcopy
from mario.tools.constants import _ADD_SECTORS_OUTPUT_SHEET_COLUMNS, _MASTER_INDEX as MI
from mario.tools.constants import _ADD_SECTORS_OUTPUT_SHEET_COLUMNS as OSC
from mario.tools.constants import (
    _ENUM,
    _ADD_SECTORS_UNCERTAINTY_PARAMETERS,
    _ADD_SECTORS_MASTER_SHEET_COLUMNS,
)
from mario.tools.iomath import (
    calc_Z, calc_E, calc_V, calc_X_from_w, calc_w, calc_z
    )
# from mario.tools.add_sectors import #what to import

# from mario.log_exc.exceptions import (
#     #new exceptions here
# )

import warnings

def _sector_to_parent_map(
        self,
        table: str = 'IOT'):
    """
    Create a mapping dictionary from new sectors to their parent sectors based on the master sheet."""
    return dict(zip(
        self.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[table]['s']],
        self.add_sectors_master[_ADD_SECTORS_MASTER_SHEET_COLUMNS[table]['ps']]
    ))

#coefficients to flows
def _new_flow_columns(
        self,
        X: pd.DataFrame,
        scenario: str = 'baseline'
    ):
    """
    Args:
        self: AttrData object
        X: DataFrame with original total outputs per sector and region (not updated with new sectors yet)
        scenario (str, optional): The scenario to add the inventories to. Defaults to 'baseline'.
    
    Create new X and new columns in flow matrices (Z, E, V) for the new sectors being added by splitting existing ones.
    """

    scenario_split = f"split_{scenario}"
    new_sectors_list=list(self.inventories.keys())
    sector_to_parent_map=_sector_to_parent_map(self)
    regions=self.get_index('Region')

    Output_new_sectors =self.split_info['Total outputs']
    #No negatives allowed in X (check 1)
    negatives = Output_new_sectors['Quantity'] < 0
    if negatives.any().any():
        raise ValueError(f"Negative values found in input X: should be avoided by data pre-processing. {Output_new_sectors.loc[negatives[negatives['production']==True].index]}")
    
    #Check that new sectors' X is smaller than corresponding parent sector's X
    #If condition respected, fill X with total outputs for new sectors from input sheet "Total outputs", and modify parents
    for s in new_sectors_list:
        if s not in Output_new_sectors[OSC['s']].unique():
            raise ValueError(f"Total output for sector {s} not found in the template sheets.")
        else:
            parent_sector=sector_to_parent_map[s]
        for r in Output_new_sectors[Output_new_sectors[OSC['s']] == s][OSC['r']]:
            # If X provided by region cluster
            if r in self.regions_clusters:
                warnings.warn(f"Using region-cluster output for sector {s} in region cluster {r}.")
                # If sector s has a parent
                if pd.isna(parent_sector) == False:
                    cluster_output = X.loc[(self.regions_clusters[r],'Sector',parent_sector)]
                    #<-subtract from parent
                # If sector s doesn't have a parent
                else:
                    cluster_output = self.matrices[scenario][_ENUM['X']].loc[(self.regions_clusters[r],'Sector',s)]
                if isinstance(cluster_output,pd.Series):
                    cluster_output = cluster_output.to_frame()
            else:
                X.loc[r, 'Sector', s] = Output_new_sectors[(Output_new_sectors[OSC['s']] == s) & (Output_new_sectors[OSC['r']] == r)][OSC['qt']].values[0]
                if pd.isna(parent_sector) == False:
                    if X.loc[r, 'Sector', s]['production'] > X.loc[r, 'Sector', parent_sector]['production']:
                        print(f"Total output for new sector {s} in region {r} is {X.loc[r, 'Sector', s]['production']} exceeds that of parent sector {parent_sector} {X.loc[r, 'Sector', parent_sector]['production']}-> Parent=0 and {s}=parent.")
                        X.loc[r, 'Sector', s] = X.loc[r, 'Sector', parent_sector] #INCONSISTENCIES HANDLING, may be changed
                        X.loc[r, 'Sector', parent_sector] = 0 #INCONSISTENCIES HANDLING, may be changed
                        
    #Copy z,e,v,EY,VY from the output of the add_sectors function
    self.matrices[scenario_split] = deepcopy(self.matrices[scenario])
    
    # Compute Z, V and E from coefficients and new X
    self.matrices[scenario_split][_ENUM.Z] = calc_Z(self.matrices[scenario][_ENUM.z],X)
    self.matrices[scenario_split][_ENUM.E] = calc_E(self.matrices[scenario][_ENUM.e],X)
    self.matrices[scenario_split][_ENUM.V] = calc_V(self.matrices[scenario][_ENUM.v],X)
    for s in new_sectors_list:
        parent_sector=sector_to_parent_map[s]
        for r in regions:
            #Subtract from parent sector the new flows
            self.matrices[scenario_split][_ENUM.Z][r, 'Sector', parent_sector] -= self.matrices[scenario_split][_ENUM.Z][r, 'Sector', s]
            self.matrices[scenario_split][_ENUM.E][r, 'Sector', parent_sector] -= self.matrices[scenario_split][_ENUM.E][r, 'Sector', s]
            self.matrices[scenario_split][_ENUM.V][r, 'Sector', parent_sector] -= self.matrices[scenario_split][_ENUM.V][r, 'Sector', s]
            #Not done before because the coefficients depend on original X
            if X.loc[r, 'Sector', s]['production'] < X.loc[r, 'Sector', parent_sector]['production']:    
                X.loc[r, 'Sector', parent_sector] -= X.loc[r, 'Sector', s]
    self.matrices[scenario_split][_ENUM.X] = X

    #No negatives allowed in X (check 2)
    negatives = self.matrices[scenario_split][_ENUM.X] < 0
    if negatives.any().any():
        raise ValueError(f"Negative values found in X: should be avoided by data pre-processing. {X.loc[negatives[negatives['production']==True].index]}")
    
    #No negatives allowed in Z
    negatives = self.matrices[scenario_split][_ENUM.Z] < 0
    
    if negatives.any().any():
        warnings.warn(f"Negative values found in matrix Z: changed to 0.")
        
        # Create parent sector index mapping
        parent_index = [
            (idx[0], idx[1], sector_to_parent_map.get(idx[2], idx[2]))
            for idx in negatives.index
        ]
        
        negatives_parent = deepcopy(negatives)
        negatives_parent.index = pd.MultiIndex.from_tuples(parent_index, names=negatives.index.names)
        
        # Set to zero
        self.matrices[scenario_split][_ENUM.Z][negatives] = 0

        # Set low confidence in uncertainty matrix
        self.uncertainty_matrix[negatives] = self.uncertainty_values['forced zero']
        for original_idx, parent_idx in zip(negatives.index, parent_index):
            if negatives.loc[original_idx].any():
                    # Trova le colonne dove c'è True
                    cols_to_update = negatives.loc[original_idx][negatives.loc[original_idx]].index
                    self.uncertainty_matrix.loc[parent_idx, cols_to_update] = self.uncertainty_values['forced zero']

    return self

#hypothesis for rows
def _row_hypothesis(
        self,
        oldX: pd.DataFrame,
        scenario: str = 'baseline'
    ):
    """
    Define row hypotheses for new sectors being added by splitting existing ones.
    """
    scenario_split = f"split_{scenario}"
    new_sectors_list=list(self.inventories.keys())
    sector_to_parent_map=_sector_to_parent_map(self)
    all_sectors=list(self.matrices[scenario_split][_ENUM.X].index.get_level_values(2).unique())
    old_sectors = sorted(set(all_sectors) - set(new_sectors_list))

    for s in new_sectors_list:
        parent_sector=sector_to_parent_map[s]
        
        for r in self.get_index('Region'):
            if pd.isna(parent_sector) == False:
                #Z rows for new
                X_cut=self.matrices[scenario_split][_ENUM.X].loc[(slice(None),'Sector',old_sectors)].squeeze()
                z_row=self.matrices[scenario_split][_ENUM.z].loc[(r, 'Sector', parent_sector),(slice(None),'Sector',old_sectors)]
                X_cut.index=z_row.index
                new_Z_row=z_row*X_cut
                new_Z_row.name=(r, 'Sector', s)
                self.matrices[scenario_split][_ENUM.Z].loc[(r, 'Sector', s),(slice(None),'Sector',old_sectors)]=new_Z_row
                #Y rows for parent and new
                new_Y_row= self.matrices[scenario_split][_ENUM.Y].loc[(r, 'Sector', parent_sector),:]*self.matrices[scenario_split][_ENUM.X].loc[(r, 'Sector', s)].values[0]/oldX.loc[(r, 'Sector', parent_sector)].values[0]
                new_Y_row.name=(r, 'Sector', s)
                self.matrices[scenario_split][_ENUM.Y].loc[(r, 'Sector', s),:] = new_Y_row
                self.matrices[scenario_split][_ENUM.Y].loc[(r, 'Sector', parent_sector),:] = self.matrices[scenario_split][_ENUM.Y].loc[(r, 'Sector', parent_sector),:]*self.matrices[scenario_split][_ENUM.X].loc[(r, 'Sector', parent_sector)].values[0]/oldX.loc[(r, 'Sector', parent_sector)].values[0]
            #If no parent?
    
    return self

#Create files for cvxlab

#Cvxlab optimization

#analyze results

#satellite accounts splitting

#save new database

