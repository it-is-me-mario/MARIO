#%%
import mario

db = mario.parse_from_txt(
    path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/ENTICE - Documents/WPs, Tasks & Deliverables/WP2 - Data/T2.2 & T2.3 - GTAP disaggregation/Database/GTAP 2023/2023_start',
    mode = "flows",
    table = "IOT"
)

#%%
db.read_add_sectors_excel(
    path = '/Users/lorenzorinaldi/Library/CloudStorage/OneDrive-SharedLibraries-eNextGen/ENTICE - Documents/WPs, Tasks & Deliverables/WP2 - Data/T2.2 & T2.3 - GTAP disaggregation/Data collection/Inventory cleaning',
    read_inventories = True
)