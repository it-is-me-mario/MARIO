# -*- coding: utf-8 -*-
"""
a test for mario.Database
"""

from mario.tools.parsersclass import parse_from_excel
import os


path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
    )
)


def load_test(table):
    """Loads an example of mario.Database

    Parameters
    -----------
    table: str
        type of the table. 'IOT' or 'SUT'

    Returns
    -------
    mario.Database
    """

    return parse_from_excel(
        path=f"{path}\\{table}.xlsx", table=table, name=f"{table} test"
    )
