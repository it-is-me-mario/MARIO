"""Ghosh-side formulas kept separate for easy future revision."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mario.compute.helpers import (
    identity_like,
    inverse_vector,
    require_same_index,
    safe_inverse,
    validate_square,
)


def build_ghosh_b_from_X_Z(X: pd.DataFrame, Z: pd.DataFrame) -> pd.DataFrame:
    validate_square(Z)
    require_same_index(Z, X, lhs_name="Z", rhs_name="X")
    x_inv = inverse_vector(X)
    values = pd.DataFrame(
        np.diagflat(x_inv.to_numpy(dtype=float)) @ Z.to_numpy(dtype=float),
        index=Z.index,
        columns=Z.columns,
    )
    return values


def build_ghosh_g_from_b(b: pd.DataFrame) -> pd.DataFrame:
    validate_square(b)
    return safe_inverse(identity_like(b) - b)


def build_iot_b_from_X_Z(X: pd.DataFrame, Z: pd.DataFrame) -> pd.DataFrame:
    return build_ghosh_b_from_X_Z(X, Z)


def build_iot_g_from_b(b: pd.DataFrame) -> pd.DataFrame:
    return build_ghosh_g_from_b(b)


def build_sut_b_from_X_Z(X: pd.DataFrame, Z: pd.DataFrame) -> pd.DataFrame:
    return build_ghosh_b_from_X_Z(X, Z)


def build_sut_g_from_b(b: pd.DataFrame) -> pd.DataFrame:
    return build_ghosh_g_from_b(b)
