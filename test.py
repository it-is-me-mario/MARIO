#%%
import mario

db = mario.parse_from_excel(
    path = "tests/fixtures/realdata/data/IOT_Vssr_Esr.xlsx",
    table = 'IOT',
    mode = 'flows',
    matrix_layouts={
        'E': ('Region', 'Sector'),
        'V': 'Region',
    }
)

# %%
db.aggregate("test.xlsx",ignore_nan=True)
# %%
