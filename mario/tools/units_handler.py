# -*- coding: utf-8 -*-
"""
Created on Mon Apr 11 15:00:26 2022

@author: loren
"""

import copy
import logging
import pandas as pd
from mario.log_exc.logger import log_time
from mario.log_exc.exceptions import WrongInput

from mario.tools.constants import _MASTER_INDEX

logger = logging.getLogger(__name__)


def _unit_converter(
        instance, 
        io,
        items,
        inplace,
        verbose,
    ):
    
    """
    This function applies unit conversion factors to desired items
    """   

    Z = instance.Z
    Y = instance.Y
    E = instance.E
    EY = instance.EY        
    V = instance.V


    if items=='all':
        items = [*instance.units]
        
    if all(i in [*instance.units] for i in items) == False:
        raise WrongInput(f"Acceptable items are {[*instance.units]}")
            
    new_units = {}
    
    if isinstance(io,str):
        for i in items:
            new_units[i] = pd.read_excel(io, i, index_col=[0,1]).dropna()
    elif isinstance(io,dict):
        for i in items:
            new_units[i] = io[i]
    
    if verbose:
        print("\nUnit of measure conversion started. Please be aware the process could take require some time in accordance to the size of the database and the number of items to be converted")
    
    if instance.is_hybrid:

        if instance.table_type == "IOT":
            raise WrongInput(f"Unit conversion is not available for {instance.table} tables")
            
        if _MASTER_INDEX['a'] in new_units:
            df = copy.deepcopy(new_units[_MASTER_INDEX['a']])
            if df.shape[0] != 0:
                log_time(logger,
                         f"No unit is associated to activities in an hybrid table, since they may produce \
                             multiple commodities characterized by different units themselves. \
                             Any input in the {_MASTER_INDEX['a']} sheet of the given excel file will be ignored",
                         level="warn")
                    
        if _MASTER_INDEX['c'] in new_units:
            df = copy.deepcopy(new_units[_MASTER_INDEX['c']])
            if df.shape[0] != 0:
                df = df.loc[df["conversion factor"]!=1]
                if verbose:
                    print(f"\nConverting units for '{_MASTER_INDEX['c']}' items...")
                for commodity,values in df.iterrows():
                    if verbose:
                        print(f"   {commodity[0]}...", end="")
                    Z.loc[(slice(None),_MASTER_INDEX['c'],commodity[0]),:] *= values.values[1]
                    Z.loc[:,(slice(None),_MASTER_INDEX['c'],commodity[0])] *= values.values[1]
                    Y.loc[(slice(None),_MASTER_INDEX['c'],commodity[0]),:] *= values.values[1]
                    if verbose:
                        print(" DONE")
                if verbose:
                    print(f"   '{_MASTER_INDEX['c']}' items unit conversion completed")

    else:            
        if instance.table_type == "IOT":
            if _MASTER_INDEX['s'] in new_units:
                df = copy.deepcopy(new_units[_MASTER_INDEX['a']])                    
                if df.shape[0] == new_units[_MASTER_INDEX['s']].shape[0]:
                    if len(set(df["new unit"])) == 1:                            
                        df = df.loc[df["conversion factor"]!=1]
                        if verbose:
                            print(f"\nConverting units for '{_MASTER_INDEX['s']}' items...")
                        for sector,values in df.iterrows():
                            if verbose:
                                print(f"   {sector[0]}...", end="")
                            Z.loc[(slice(None),_MASTER_INDEX['a'],sector[0]),:] *= values.values[1]
                            Y.loc[(slice(None),_MASTER_INDEX['a'],sector[0]),:] *= values.values[1]
                            if verbose:
                                print(" DONE")
                        if verbose:
                            print(f"   '{_MASTER_INDEX['s']}' items unit conversion completed")
                    else:
                        raise WrongInput(f"Unit conversions for monetary tables are allowed only if all the '{_MASTER_INDEX['s']}' items\
                                         are converted to the same new monetary unit (i.e. from Million Euros to Billion Euros)")
                else:
                    raise WrongInput(f"Not all '{_MASTER_INDEX['s']}' items have been provided with a new unit. Please note\
                                     unit conversions for monetary tables are allowed only if all the '{_MASTER_INDEX['s']}' items\
                                     are converted to the same new monetary unit (i.e. from Million Euros to Billion Euros)")
                                     
        elif instance.table_type == "SUT":
            if _MASTER_INDEX['a'] in new_units and _MASTER_INDEX['c'] in new_units:
                df_a = copy.deepcopy(new_units[_MASTER_INDEX['a']])
                df_c = copy.deepcopy(new_units[_MASTER_INDEX['c']])
                if df_a.shape[0] == new_units[_MASTER_INDEX['a']].shape[0] and df_c.shape[0] == new_units[_MASTER_INDEX['c']].shape[0]:
                    if len(set(df_a["new unit"])) == 1 and len(set(df_c["new unit"])) == 1:
                        df_a = df_a.loc[df["conversion factor"]!=1]
                        df_c = df_c.loc[df["conversion factor"]!=1]
                        if verbose:
                            print(f"\nConverting units for '{_MASTER_INDEX['a']}' items...")
                        for activity,values in df_a.iterrows():
                            if verbose:
                                print(f"   {activity[0]}...", end="")
                            Z.loc[(slice(None),_MASTER_INDEX['a'],activity[0]),:] *= values.values[1]
                            Y.loc[(slice(None),_MASTER_INDEX['a'],activity[0]),:] *= values.values[1]
                            if verbose:
                                print(" DONE")
                        if verbose:
                            print(f"   '{_MASTER_INDEX['a']}' items unit conversion completed")
                            print(f"\nConverting units for {_MASTER_INDEX['c']}...")
                        for commodity,values in df_c.iterrows():
                            if verbose:
                                print(f"   {commodity[0]}...", end="")
                            Z.loc[(slice(None),_MASTER_INDEX['c'],commodity[0]),:] *= values.values[1]
                            Y.loc[(slice(None),_MASTER_INDEX['c'],commodity[0]),:] *= values.values[1]
                            if verbose:
                                print(" DONE")
                        if verbose:
                            print(f"   '{_MASTER_INDEX['c']}' items unit conversion completed")
                    else:
                        raise WrongInput(f"Unit conversions for monetary tables are allowed only if all the '{_MASTER_INDEX['a']}' and '{_MASTER_INDEX['c']}' items\
                                         are converted to the same new monetary unit (i.e. from Million Euros to Billion Euros)")
                else:
                    raise WrongInput(f"Not all '{_MASTER_INDEX['a']}' or '{_MASTER_INDEX['c']}' items have been provided with a new unit. Please note\
                                     unit conversions for monetary tables are allowed only if all the '{_MASTER_INDEX['c']}'  and '{_MASTER_INDEX['a']}' items\
                                     are converted to the same new monetary unit (i.e. from Million Euros to Billion Euros)")
        

    if _MASTER_INDEX['k'] in new_units:
        df = copy.deepcopy(new_units[_MASTER_INDEX['k']])
        if df.shape[0] != 0:
            df = df.loc[df["conversion factor"]!=1]
            if verbose:
                print(f"\nConverting units for '{_MASTER_INDEX['k']}' items...")
            for sat_account,values in df.iterrows():
                if verbose:
                    print(f"   {sat_account[0]}...", end="")
                E.loc[sat_account[0],:] *= values.values[1]
                EY.loc[sat_account[0],:]*= values.values[1]
                if verbose:
                    print(" DONE")
            if verbose:
                print(f"   '{_MASTER_INDEX['k']}' items unit conversion completed")
        
            
    if _MASTER_INDEX['f'] in new_units:
        df = copy.deepcopy(new_units[_MASTER_INDEX['f']])
        if df.shape[0] != 0:
            if len(set(df["new unit"])) == 1:
                df = df.loc[df["conversion factor"]!=1]
                if verbose:
                    print(f"\nConverting units for '{_MASTER_INDEX['f']}' items...")
                for factor,values in df.iterrows():
                    if verbose:
                        print(f"   {factor[0]}...", end="")
                    V.loc[factor[0],:] *= values.values[1]
                    if verbose:
                        print(" DONE")
                if verbose:
                    print(f"   '{_MASTER_INDEX['f']}' item units conversion completed")
            else:
                raise WrongInput(f"Monetary units conversions are allowed only if all the {_MASTER_INDEX['a']} and {_MASTER_INDEX['c']} \
                                 expressed in monetary units are converted to the same new monetary unit (i.e. from Million Euros to Billion Euros)")
    
    if verbose:
        print("\nCreating new matrices and units objects...", end='')
    instance.matrices = {
                     'baseline': {
                                  'Z':  Z,
                                  'Y':  Y,
                                  'E':  E,
                                  'EY': EY,
                                  'V':  V
                                 },
                     }
    
    units = {}
    for u in instance.units:
        units[u] = copy.deepcopy(instance.units[u])
        if u in new_units:
            if not new_units[u].empty:
                for i in range(units[u].shape[0]):
                    units[u].iloc[i,0] = new_units[u].iloc[i,0]
    instance.units = units
    
    if verbose:
        print(" PROCESS COMPLETE")
