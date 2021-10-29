# -*- coding: utf-8 -*-
"""
Created on Fri Nov 20 12:00:01 2020

@author: Amin
"""


class Rewrite(Exception):
    """
    raise the exception when there is the danger of overwriting exising data or
    objects
    """

    pass


class WrongFormat(Exception):
    """raise when dataframes/ files have wrong format"""

    pass


class WrongInput(ValueError):

    """
    this exception class will be used to raise a value error if there is a wrong
    value input from the user in the functions which is not acceptable for the code
    """

    pass


class WrongExcelFormat(Exception):

    """
    This exception class will be used to raise an exception when a given excel file
    by the user is not in appropriate format which is acceptable by the code.
    """

    pass


class WrongOperativeSet(Exception):

    """
    This exception class will be used to rise an exception, when the operation called by the
    user is not feasible accoroding to the features of the database:

        e.g. transforming SUT table to SUT!!
    """

    pass


class LackOfInput(Exception):

    """
    This exception class will be used in cases that the user is not giving enough inputs to
    a function.
    """

    pass


class WrongData(Exception):

    """
    This Exception class will be used when there are Wrong Attribute type input.
    """

    pass


class NotImplementable(Exception):

    """
    This can be raised if some operation is not possible to be implemented.
    """

    pass


class DataMissing(Exception):

    """
    This can be raised if a matrix which is called by user is missed
    """

    pass
