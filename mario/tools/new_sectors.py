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
    
    #fill X with total outputs for new sectors from input sheet "Total outputs", and modify parents
    Output_new_sectors =self.split_info['Total outputs']
    for s in new_sectors_list:
        if s not in Output_new_sectors[OSC['s']].unique():
            raise ValueError(f"Total output for sector {s} not found in the template sheets.")
        for r in Output_new_sectors[Output_new_sectors[OSC['s']] == s][OSC['r']]:
            # If X provided by region cluster
            parent_sector=sector_to_parent_map[s]
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
                #X in region cluster
                X.loc[r, 'Sector', s] = Output_new_sectors[(Output_new_sectors[OSC['s']] == s) & (Output_new_sectors[OSC['r']] == r)][OSC['qt']].values[0]
                if pd.isna(parent_sector) == False:
                    #Subtract from parent output
                    X.loc[r, 'Sector', parent_sector] -= X.loc[r, 'Sector', s]

    self.matrices[scenario_split] = {}
    for key, matrix in self.matrices[scenario].items():
        if key in [_ENUM.z, _ENUM.e, _ENUM.v, _ENUM.EY,_ENUM.VY]:
            self.matrices[scenario_split][key] = deepcopy(matrix)
        else:
            self.matrices[scenario_split][key] = pd.DataFrame(
                0, 
                index=matrix.index, 
                columns=matrix.columns
            )
            
    self.matrices[scenario_split][_ENUM.X] = X
    #No negatives allowed in X
    negatives = self.matrices[scenario_split][_ENUM.X] < 0
    if negatives.any().any():
        raise ValueError(f"Negative values found in X: should be avoided by data pre-processing.")
    
    # Compute Z, V and E from coefficients and new X
    self.matrices[scenario_split][_ENUM.Z] = calc_Z(self.matrices[scenario][_ENUM.z],X)
    self.matrices[scenario_split][_ENUM.E] = calc_E(self.matrices[scenario][_ENUM.e],X)
    self.matrices[scenario_split][_ENUM.V] = calc_V(self.matrices[scenario][_ENUM.v],X)
    for s in new_sectors_list:
        parent_sector=sector_to_parent_map[s]
        for r in self.get_index('Region'):
            #Subtract from parent sector the new flows
            self.matrices[scenario_split][_ENUM.Z][r, 'Sector', parent_sector] -= self.matrices[scenario_split][_ENUM.Z][r, 'Sector', s]
            self.matrices[scenario_split][_ENUM.E][r, 'Sector', parent_sector] -= self.matrices[scenario_split][_ENUM.E][r, 'Sector', s]
            self.matrices[scenario_split][_ENUM.V][r, 'Sector', parent_sector] -= self.matrices[scenario_split][_ENUM.V][r, 'Sector', s]
    
    # Check for negatives in Z and handle them (with consequence on uncertainty matrix)
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

#entropy minimization

#satellite accounts splitting

#save new database

