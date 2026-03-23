# -*- coding: utf-8 -*-
"""Custom exception types used across MARIO."""


class Rewrite(Exception):
    """Raised when an operation would overwrite existing data or objects."""

    pass


class WrongFormat(Exception):
    """Raised when a file or dataframe has the wrong format."""

    pass


class WrongInput(ValueError):
    """Raised when a user-facing argument value is invalid."""

    pass


class WrongExcelFormat(Exception):
    """Raised when an Excel workbook does not match the expected MARIO format."""

    pass


class WrongOperativeSet(Exception):
    """Raised when an operation is incompatible with the current database."""

    pass


class LackOfInput(Exception):
    """Raised when required inputs are missing."""

    pass


class WrongData(Exception):
    """Raised when data objects have an unexpected type or structure."""

    pass


class NotImplementable(Exception):
    """Raised when a requested operation is not implemented or not feasible."""

    pass


class DataMissing(Exception):
    """Raised when required data blocks or matrices are missing."""

    pass
