#%%
import mario

#%%
db = mario.parse_GTAP('/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/ENTICE - Documents/Database/GTAP11Power')

# %%
db

#%%
db.to_txt('/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/ENTICE - Documents/Database/MARIO')

# %%
import mario

db = mario.parse_from_txt(
    path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/ENTICE - Documents/Database/MARIO/flows',
    mode = 'flows',
    table = 'IOT',
)

# %%
