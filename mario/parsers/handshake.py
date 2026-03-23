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
    from mario.parsers.entrypoints import parse_from_pymrio

    world = parse_from_pymrio(
        data,
        value_added={"factor_inputs":["TLS","VA"]}, 
        satellite_account={},
    )

    return world


def parse_exiobase_3_9_4(path):
    """Compatibility wrapper for the EXIOBASE 3.9.4 monetary IOT parser."""
    from mario.parsers.entrypoints import parse_exiobase_3

    return parse_exiobase_3(path=path, version="3.9.4")
