#Code to enhance tables with new sectors, either splitting an existing "parent" sector or adding a new one

import pandas as pd
from copy import deepcopy
from mario.tools.constants import _MASTER_INDEX as MI
from mario.tools.constants import _ENUM
# from mario.tools.add_sectors import #what to import

# from mario.log_exc.exceptions import (
#     #new exceptions here
# )

import warnings

#coefficients to flows
def _new_flow_columns(
        self
    ):
    """
    Create new columns in flow matrices (Z, E, V, X) for the new sectors being added by splitting existing ones.
    """
    
    #fill X with total outputs for new sectors from input sheet "Total outputs"
    Output_new_sectors =self.split_info['Total outputs']
    new_sectors_list=list(self.inventories.keys())
    for s in new_sectors_list:
        if s not in Output_new_sectors['Sector'].unique(): #<-- put indirect definition for sector
            raise ValueError(f"Total output for sector {s} not found in the template sheets.")
        for r in Output_new_sectors[Output_new_sectors['Sector'] == s]['Region']: #<-- put indirect definition for sector and region
            #<-modify for clusters
            self.matrices['baseline'][_ENUM.X].loc[r, 'Sector', s] = Output_new_sectors[(Output_new_sectors['Sector'] == s) & (Output_new_sectors['Region'] == r)]['Quantity'].values[0]
    
    # Compute Z, V and E from coefficients and new X
    for s in new_sectors_list:
        for r in self.get_index('Region'):
            X_s_r=float(self.matrices['baseline'][_ENUM.X].loc[r, 'Sector', s])
            self.matrices['baseline'][_ENUM.Z][r,'Sector',s] = self.matrices['baseline'][_ENUM.z][r,'Sector',s]*X_s_r
            self.matrices['baseline'][_ENUM.E][r,'Sector',s] = self.matrices['baseline'][_ENUM.e][r,'Sector',s]*X_s_r
            self.matrices['baseline'][_ENUM.V][r,'Sector',s] = self.matrices['baseline'][_ENUM.v][r,'Sector',s]*X_s_r
            

    return self
#hypothesis for rows

#entropy minimization

#satellite accounts splitting

#save new database

