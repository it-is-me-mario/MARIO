# -*- coding: utf-8 -*-
"""
Created on Wed May 17 14:16:35 2023

@author: loren
"""

import mario

path = r"C:\Users\loren\Politecnico di Milano\DENG-SESAM - Documenti\DATASETS\EORA\Full Eora\2016"
indices = r"C:\Users\loren\Politecnico di Milano\DENG-SESAM - Documenti\DATASETS\EORA\Full Eora\indices.zip"

#%%
world = mario.parse_full_eora(path, indices)
