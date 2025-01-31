
import mario
import pymrio
from pathlib import Path

def parse_oecd(path,year):
    """Parses OECD data using pymrio parser function

    Parameters
    ----------
    path : str
        path to the folder the oecd data is stored
    year : int
        the year of the data to be parsed

    Returns
    -------
    mario.Database
    """

    oecd_storage = Path(path)
    data = pymrio.parse_oecd(path=oecd_storage, year=year)

    world = mario.parse_from_pymrio(
        data,
        value_added={"factor_inputs":["TLS","VA"]}, 
        satellite_account={},
    )

    return world


def parse_exiobase_3_9_4(path):


    sat_acc = {  
    'material': 'all',
    'water': 'all',
    'employment': 'all',
    'air_emissions': 'all',
    'energy': 'all',
    'land': 'all',
    'nutrients': 'all'
    } 


    value_added = {'factor_inputs': 'all'} 

    exio3 = pymrio.parse_exiobase3(path)

    return mario.parse_from_pymrio(exio3, satellite_account=sat_acc, value_added=value_added)


