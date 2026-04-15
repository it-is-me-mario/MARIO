#%%
import mario

db = mario.load_test(
    "SUT", 
    tech_assumption='IT',
    )

#%%
db

#%%
db.change_assumption("product-based")

# %%
