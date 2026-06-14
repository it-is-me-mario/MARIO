"""Centralized ordering policy for unified SUT views."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from mario.model.labels import INDEX_LABELS

ACTIVITY = INDEX_LABELS["a"]
COMMODITY = INDEX_LABELS["c"]


def _require_multiindex(axis: pd.Index, label: str) -> pd.MultiIndex:
    """Require a canonical 3-level ``MultiIndex`` for SUT axes."""
    if not isinstance(axis, pd.MultiIndex) or axis.nlevels != 3:
        raise TypeError(f"{label} must be a 3-level pandas.MultiIndex.")

    return axis


def _slice_level(axis: pd.MultiIndex, level_value: str) -> pd.MultiIndex:
    """Return the subset of a unified SUT axis matching one middle-level label."""
    mask = axis.get_level_values(1) == level_value
    values = axis[mask]

    if len(values) == 0:
        raise ValueError(f"{level_value!r} labels are missing from unified SUT axis.")

    return values


def _take_axis(block: pd.DataFrame | pd.Series | None, axis_name: str) -> pd.MultiIndex | None:
    """Extract a ``MultiIndex`` axis from a block when present."""
    if block is None:
        return None

    axis = getattr(block, axis_name)
    if isinstance(axis, pd.MultiIndex):
        return axis

    return None


def _first_multiindex(*candidates: pd.MultiIndex | None) -> pd.MultiIndex | None:
    """Return the first non-null ``MultiIndex`` candidate."""
    for candidate in candidates:
        if candidate is not None:
            return candidate

    return None


@dataclass(frozen=True)
class SUTUnifiedOrderingPolicy:
    """Single source of truth for activity/commodity ordering in unified SUT blocks."""

    activity_index: pd.MultiIndex
    commodity_index: pd.MultiIndex
    final_demand_columns: pd.MultiIndex | None = None

    def __post_init__(self) -> None:
        """Validate that the stored indexes are canonical activity/commodity axes."""
        activity_index = _require_multiindex(self.activity_index, "activity_index")
        commodity_index = _require_multiindex(self.commodity_index, "commodity_index")

        if not (activity_index.get_level_values(1) == ACTIVITY).all():
            raise ValueError("activity_index must contain only Activity rows.")

        if not (commodity_index.get_level_values(1) == COMMODITY).all():
            raise ValueError("commodity_index must contain only Commodity rows.")

        if self.final_demand_columns is not None:
            _require_multiindex(self.final_demand_columns, "final_demand_columns")

    @property
    def unified_index(self) -> pd.MultiIndex:
        """Return the canonical unified activity+commodity index ordering."""
        return self.activity_index.append(self.commodity_index)

    @classmethod
    def from_blocks(
        cls,
        *,
        U: pd.DataFrame | None = None,
        S: pd.DataFrame | None = None,
        Z: pd.DataFrame | None = None,
        z: pd.DataFrame | None = None,
        w: pd.DataFrame | None = None,
        b: pd.DataFrame | None = None,
        g: pd.DataFrame | None = None,
        X: pd.DataFrame | None = None,
        Y: pd.DataFrame | None = None,
        V: pd.DataFrame | None = None,
        v: pd.DataFrame | None = None,
        E: pd.DataFrame | None = None,
        e: pd.DataFrame | None = None,
        u: pd.DataFrame | None = None,
        s: pd.DataFrame | None = None,
        bu: pd.DataFrame | None = None,
        bs: pd.DataFrame | None = None,
        gcc: pd.DataFrame | None = None,
        gca: pd.DataFrame | None = None,
        gac: pd.DataFrame | None = None,
        gaa: pd.DataFrame | None = None,
        Xa: pd.DataFrame | None = None,
        Xc: pd.DataFrame | None = None,
        Ya: pd.DataFrame | None = None,
        Yc: pd.DataFrame | None = None,
        Va: pd.DataFrame | None = None,
        Vc: pd.DataFrame | None = None,
        va: pd.DataFrame | None = None,
        vc: pd.DataFrame | None = None,
        Ea: pd.DataFrame | None = None,
        Ec: pd.DataFrame | None = None,
        ea: pd.DataFrame | None = None,
        ec: pd.DataFrame | None = None,
    ) -> "SUTUnifiedOrderingPolicy":
        """Infer canonical split and unified ordering from available SUT blocks."""
        unified_axis = _first_multiindex(
            _take_axis(Z, "index"),
            _take_axis(z, "index"),
            _take_axis(w, "index"),
            _take_axis(b, "index"),
            _take_axis(g, "index"),
            _take_axis(X, "index"),
            _take_axis(Y, "index"),
            _take_axis(V, "columns"),
            _take_axis(v, "columns"),
            _take_axis(E, "columns"),
            _take_axis(e, "columns"),
        )

        activity_index = _first_multiindex(
            _take_axis(S, "index"),
            _take_axis(U, "columns"),
            _take_axis(s, "index"),
            _take_axis(u, "columns"),
            _take_axis(bs, "index"),
            _take_axis(bu, "columns"),
            _take_axis(gaa, "index"),
            _take_axis(gac, "index"),
            _take_axis(gca, "columns"),
            _take_axis(Xa, "index"),
            _take_axis(Ya, "index"),
            _take_axis(Va, "columns"),
            _take_axis(va, "columns"),
            _take_axis(Ea, "columns"),
            _take_axis(ea, "columns"),
        )
        commodity_index = _first_multiindex(
            _take_axis(U, "index"),
            _take_axis(S, "columns"),
            _take_axis(u, "index"),
            _take_axis(s, "columns"),
            _take_axis(bu, "index"),
            _take_axis(bs, "columns"),
            _take_axis(gcc, "index"),
            _take_axis(gca, "index"),
            _take_axis(gac, "columns"),
            _take_axis(Xc, "index"),
            _take_axis(Yc, "index"),
            _take_axis(Vc, "columns"),
            _take_axis(vc, "columns"),
            _take_axis(Ec, "columns"),
            _take_axis(ec, "columns"),
        )

        if unified_axis is not None:
            unified_axis = _require_multiindex(unified_axis, "unified_axis")
            if activity_index is None:
                activity_index = _slice_level(unified_axis, ACTIVITY)
            if commodity_index is None:
                commodity_index = _slice_level(unified_axis, COMMODITY)

        if activity_index is None or commodity_index is None:
            raise ValueError(
                "Cannot build SUT ordering policy without enough activity and commodity indexes."
            )

        final_demand_columns = _first_multiindex(
            _take_axis(Y, "columns"),
            _take_axis(Ya, "columns"),
            _take_axis(Yc, "columns"),
        )

        return cls(
            activity_index=activity_index,
            commodity_index=commodity_index,
            final_demand_columns=final_demand_columns,
        )

    def activity_rows(self, block: pd.DataFrame) -> pd.DataFrame:
        """Return the activity-row slice of a unified SUT block."""
        return block.loc[self.activity_index, :]

    def commodity_rows(self, block: pd.DataFrame) -> pd.DataFrame:
        """Return the commodity-row slice of a unified SUT block."""
        return block.loc[self.commodity_index, :]

    def activity_columns(self, block: pd.DataFrame) -> pd.DataFrame:
        """Return the activity-column slice of a unified SUT block."""
        return block.loc[:, self.activity_index]

    def commodity_columns(self, block: pd.DataFrame) -> pd.DataFrame:
        """Return the commodity-column slice of a unified SUT block."""
        return block.loc[:, self.commodity_index]
