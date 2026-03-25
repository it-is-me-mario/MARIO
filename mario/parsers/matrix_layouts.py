"""Shared helpers for parser-side matrix layout semantics."""

from __future__ import annotations

import pandas as pd

from mario.compute import block_spec
from mario.log_exc.exceptions import WrongInput


CANONICAL_LAYOUT_SETS = (
    "Region",
    "Sector",
    "Activity",
    "Commodity",
    "Consumption category",
    "Factor of production",
    "Satellite account",
)


def _normalize_one_matrix_layout(value) -> tuple[str, ...]:
    """Normalize one user-facing matrix-layout declaration."""
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.lower() == "standard":
            return ()
        values = (stripped,)
    elif isinstance(value, (tuple, list)):
        values = tuple(str(item).strip() for item in value if str(item).strip())
    else:
        raise WrongInput(
            "Each matrix layout should be None, a string like 'Region', or a tuple/list like ('Region', 'Sector')."
        )

    invalid = [item for item in values if item not in CANONICAL_LAYOUT_SETS]
    if invalid:
        raise WrongInput(
            f"Unsupported set names in matrix layout: {invalid}. Valid set names are: {sorted(CANONICAL_LAYOUT_SETS)}"
        )

    duplicates = [item for item in values if values.count(item) > 1]
    if duplicates:
        raise WrongInput(
            f"Duplicate set names are not allowed in matrix layouts: {sorted(set(duplicates))}"
        )

    return values


def normalize_matrix_layouts(matrix_layouts: dict[str, object] | None) -> dict[str, tuple[str, ...]]:
    """Normalize per-matrix layout declarations to tuples of canonical set names."""
    if matrix_layouts is None:
        return {}
    if not isinstance(matrix_layouts, dict):
        raise WrongInput(
            "matrix_layouts should be a dictionary like {'E': 'Region'} or {'E': ('Region', 'Sector')}."
        )

    normalized = {str(key): _normalize_one_matrix_layout(value) for key, value in matrix_layouts.items()}
    valid_names = {"Z", "z", "Y", "V", "v", "VY", "E", "e", "EY"}
    invalid = sorted(set(normalized).difference(valid_names))
    if invalid:
        raise WrongInput(
            f"Unsupported matrix names in matrix_layouts: {invalid}. Valid matrix names are: {sorted(valid_names)}"
        )
    return normalized


def infer_item_sets_from_units(units_frame: pd.DataFrame) -> dict[object, str]:
    """Build a unique item -> set mapping from the parser units table."""
    if not isinstance(units_frame.index, pd.MultiIndex) or units_frame.index.nlevels != 2:
        raise WrongInput("Units should expose a two-level index of (set, item).")

    mapping: dict[object, str] = {}
    for set_name, item in units_frame.index.tolist():
        if item in mapping and mapping[item] != set_name:
            raise WrongInput(
                f"Units should classify items univocally, but {item!r} appears in both {mapping[item]!r} and {set_name!r}."
            )
        mapping[item] = set_name
    return mapping


def iot_row_layout(matrix_name: str, matrix_layouts: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Return the configured extra row layout for one IOT matrix."""
    if matrix_name in {"EY"}:
        return matrix_layouts.get("EY", matrix_layouts.get("E", matrix_layouts.get("e", ())))
    if matrix_name in {"e"}:
        return matrix_layouts.get("e", matrix_layouts.get("E", ()))
    if matrix_name in {"E", "f", "F"}:
        return matrix_layouts.get("E", matrix_layouts.get("e", ()))
    if matrix_name in {"VY"}:
        return matrix_layouts.get("VY", matrix_layouts.get("V", matrix_layouts.get("v", ())))
    if matrix_name in {"v"}:
        return matrix_layouts.get("v", matrix_layouts.get("V", ()))
    if matrix_name in {"V", "m", "M"}:
        return matrix_layouts.get("V", matrix_layouts.get("v", ()))
    return ()


def iot_axis_names(matrix_name: str, side: str, matrix_layouts: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Return the semantic axis names expected for one IOT matrix side."""
    if side not in {"from", "to"}:
        raise WrongInput("side should be either 'from' or 'to'.")

    if side == "from":
        if matrix_name in {"Z", "z", "Y"}:
            return ("Region", "Sector")
        if matrix_name in {"V", "v", "M", "m", "VY"}:
            return iot_row_layout(matrix_name, matrix_layouts) + ("Factor of production",)
        if matrix_name in {"E", "e", "F", "f", "EY"}:
            return iot_row_layout(matrix_name, matrix_layouts) + ("Satellite account",)
    else:
        if matrix_name in {"Z", "z", "V", "v", "E", "e", "M", "m", "F", "f"}:
            return ("Region", "Sector")
        if matrix_name in {"Y", "EY", "VY"}:
            return ("Region", "Consumption category")

    raise WrongInput(f"No IOT axis definition is known for matrix {matrix_name!r} on side {side!r}.")


def coerce_axis_names(index, expected_names: tuple[str, ...]):
    """Return an index with the semantic names expected by the parser."""
    if len(expected_names) == 1:
        if isinstance(index, pd.MultiIndex):
            if index.nlevels != 1:
                raise WrongInput(
                    f"Expected a one-level axis named {expected_names}, got {index.nlevels} levels."
                )
            values = index.get_level_values(0)
            return pd.Index(values, name=expected_names[0])
        return pd.Index(index.tolist(), name=expected_names[0])

    if not isinstance(index, pd.MultiIndex):
        raise WrongInput(
            f"Expected a {len(expected_names)}-level axis named {expected_names}, got a single-level index."
        )
    if index.nlevels != len(expected_names):
        raise WrongInput(
            f"Expected a {len(expected_names)}-level axis named {expected_names}, got {index.nlevels} levels."
        )
    return pd.MultiIndex.from_tuples(index.tolist(), names=list(expected_names))


def _compact_axis_tokens(tokens: tuple[object, ...]) -> tuple[object, ...]:
    """Drop empty placeholders from one raw axis tuple."""
    return tuple(value for value in tokens if not pd.isna(value) and value != "None" and value != "")


def _build_axis_from_tuples(values: list[tuple[object, ...]], names: tuple[str, ...]):
    """Build a pandas axis from normalized tuple values and axis names."""
    if len(names) == 1:
        return pd.Index([value[0] for value in values], name=names[0])
    return pd.MultiIndex.from_tuples(values, names=list(names))


def _keep_legacy_terminal_level(matrix_name: str, side: str, expected_names: tuple[str, ...]) -> bool:
    """Return whether a legacy ``Level`` marker should remain public on one axis.

    For standard one-level extension/factor rows MARIO historically exposes a
    simple item index. We keep that behavior to avoid breaking older scripts.
    Once extra layout dimensions are present, preserving the raw ``Level/Item``
    pair becomes valuable and unambiguous, so those richer legacy axes remain
    public.
    """
    if side == "from" and len(expected_names) == 1 and matrix_name in {"V", "v", "VY", "m", "M", "E", "e", "EY", "F", "f"}:
        return False
    return True


def interpret_axis_tokens(
    tokens: tuple[object, ...],
    expected_names: tuple[str, ...],
    *,
    matrix_name: str | None = None,
    side: str | None = None,
) -> tuple[tuple[object, ...], tuple[str, ...], tuple[object, ...], tuple[str, ...]]:
    """Interpret one raw axis tuple as both semantic and public axis values."""
    compact = _compact_axis_tokens(tokens)

    if len(compact) == len(expected_names):
        return compact, expected_names, compact, expected_names

    if len(compact) == len(expected_names) + 1 and compact[-2] == expected_names[-1]:
        semantic = compact[:-2] + (compact[-1],)
        keep_terminal_level = _keep_legacy_terminal_level(
            matrix_name or "",
            side or "",
            expected_names,
        )
        if keep_terminal_level:
            public_names = expected_names[:-1] + ("Level", "Item")
            return semantic, expected_names, compact, public_names
        return semantic, expected_names, semantic, expected_names

    raise WrongInput(
        f"Unable to normalize axis values {compact} to expected semantic names {expected_names}."
    )


def normalize_axis_tokens(
    tokens: tuple[object, ...],
    expected_names: tuple[str, ...],
) -> tuple[object, ...]:
    """Normalize one raw axis tuple to the expected semantic names.

    Supported inputs are:

    - explicit layout: ``("r1", "s1")`` for ``("Region", "Sector")``
    - legacy layout with a ``Level`` marker before the terminal item:
      ``("r1", "Sector", "s1")`` for ``("Region", "Sector")``
    """
    return interpret_axis_tokens(tokens, expected_names)[0]


def normalize_axis_index(index, expected_names: tuple[str, ...]):
    """Normalize one pandas axis against the semantic names expected by a matrix layout."""
    if isinstance(index, pd.MultiIndex):
        raw_values = index.tolist()
    else:
        raw_values = [(value,) for value in index.tolist()]

    tuples = [normalize_axis_tokens(value, expected_names) for value in raw_values]
    if len(expected_names) == 1:
        return pd.Index([value[0] for value in tuples], name=expected_names[0])
    return pd.MultiIndex.from_tuples(tuples, names=list(expected_names))


def normalize_iot_final_demand_tokens(tokens: tuple[object, ...]) -> tuple[tuple[object, ...], tuple[str, ...]]:
    """Normalize one final-demand axis tuple.

    Supported forms are:

    - explicit no-region: ``("hh",)`` -> ``("Consumption category",)``
    - explicit with region: ``("r1", "hh")`` -> ``("Region", "Consumption category")``
    - legacy no-region: ``("Consumption category", "hh")`` -> ``("Consumption category",)``
    - legacy with region: ``("r1", "Consumption category", "hh")`` -> ``("Region", "Consumption category")``
    """
    compact = _compact_axis_tokens(tokens)

    if len(compact) == 1:
        return compact, ("Consumption category",)
    if len(compact) == 2:
        if compact[0] == "Consumption category":
            return (compact[1],), ("Consumption category",)
        return compact, ("Region", "Consumption category")
    if len(compact) == 3 and compact[-2] == "Consumption category":
        return (compact[0], compact[-1]), ("Region", "Consumption category")

    raise WrongInput(f"Unable to normalize final-demand axis values {compact}.")


def interpret_iot_final_demand_tokens(
    tokens: tuple[object, ...],
) -> tuple[tuple[object, ...], tuple[str, ...], tuple[object, ...], tuple[str, ...]]:
    """Interpret one final-demand axis as semantic and public values."""
    compact = _compact_axis_tokens(tokens)

    if len(compact) == 1:
        names = ("Consumption category",)
        return compact, names, compact, names

    if len(compact) == 2:
        if compact[0] == "Consumption category":
            return (compact[1],), ("Consumption category",), compact, ("Level", "Item")
        names = ("Region", "Consumption category")
        return compact, names, compact, names

    if len(compact) == 3 and compact[-2] == "Consumption category":
        return (
            (compact[0], compact[-1]),
            ("Region", "Consumption category"),
            compact,
            ("Region", "Level", "Item"),
        )

    raise WrongInput(f"Unable to normalize final-demand axis values {compact}.")


def interpret_iot_axis(index, matrix_name: str, side: str, matrix_layouts: dict[str, tuple[str, ...]]):
    """Interpret one IOT axis, preserving legacy public labels when present."""
    raw_values = index.tolist() if isinstance(index, pd.MultiIndex) else [(value,) for value in index.tolist()]

    semantic_values: list[tuple[object, ...]] = []
    public_values: list[tuple[object, ...]] = []
    semantic_names: tuple[str, ...] | None = None
    public_names: tuple[str, ...] | None = None

    if side == "to" and matrix_name in {"Y", "EY", "VY"}:
        for value in raw_values:
            current_semantic, current_semantic_names, current_public, current_public_names = (
                interpret_iot_final_demand_tokens(value)
            )
            if semantic_names is None:
                semantic_names = current_semantic_names
                public_names = current_public_names
            elif semantic_names != current_semantic_names or public_names != current_public_names:
                raise WrongInput(
                    "Mixed final-demand axis layouts are not allowed. "
                    f"Got semantic names {semantic_names} / {current_semantic_names} "
                    f"and public names {public_names} / {current_public_names}."
                )
            semantic_values.append(current_semantic)
            public_values.append(current_public)
    else:
        expected_names = iot_axis_names(matrix_name, side, matrix_layouts)
        for value in raw_values:
            current_semantic, current_semantic_names, current_public, current_public_names = interpret_axis_tokens(
                value,
                expected_names,
                matrix_name=matrix_name,
                side=side,
            )
            if semantic_names is None:
                semantic_names = current_semantic_names
                public_names = current_public_names
            semantic_values.append(current_semantic)
            public_values.append(current_public)

    assert semantic_names is not None
    assert public_names is not None
    return _build_axis_from_tuples(public_values, public_names), semantic_names, public_names


def normalize_iot_axis(index, matrix_name: str, side: str, matrix_layouts: dict[str, tuple[str, ...]]):
    """Normalize one IOT axis, allowing regionless final-demand columns."""
    if side == "to" and matrix_name in {"Y", "EY", "VY"}:
        raw_values = index.tolist() if isinstance(index, pd.MultiIndex) else [(value,) for value in index.tolist()]
        normalized_values: list[tuple[object, ...]] = []
        axis_names: tuple[str, ...] | None = None
        for value in raw_values:
            normalized, names = normalize_iot_final_demand_tokens(value)
            if axis_names is None:
                axis_names = names
            elif axis_names != names:
                raise WrongInput(
                    f"Mixed final-demand axis layouts are not allowed. Got both {axis_names} and {names}."
                )
            normalized_values.append(normalized)

        assert axis_names is not None
        if len(axis_names) == 1:
            return pd.Index([value[0] for value in normalized_values], name=axis_names[0]), axis_names
        return pd.MultiIndex.from_tuples(normalized_values, names=list(axis_names)), axis_names

    expected_names = iot_axis_names(matrix_name, side, matrix_layouts)
    return normalize_axis_index(index, expected_names), expected_names


def build_iot_indexes_from_units_and_y(units_frame: pd.DataFrame, matrices: dict[str, pd.DataFrame]) -> dict[str, dict[str, list[object]]]:
    """Build canonical IOT indexes from units and the parsed Y matrix."""
    item_sets = infer_item_sets_from_units(units_frame)

    def _dedupe(values):
        seen = []
        for value in values:
            if value not in seen:
                seen.append(value)
        return seen

    def _regions_from_axis(axis) -> list[object]:
        if isinstance(axis, pd.MultiIndex):
            return _dedupe(axis.get_level_values(0).tolist())
        return []

    regions = (
        _regions_from_axis(matrices["Z"].index)
        or _regions_from_axis(matrices["Z"].columns)
        or _regions_from_axis(matrices["Y"].index)
        or _regions_from_axis(matrices["Y"].columns)
    )
    final_use = _dedupe(
        [
            value
            for value in matrices["Y"].columns.get_level_values(-1).tolist()
            if value not in item_sets
        ]
    )

    sector_values = [item for item, set_name in item_sets.items() if set_name == "Sector"]
    factor_values = [item for item, set_name in item_sets.items() if set_name == "Factor of production"]
    satellite_values = [item for item, set_name in item_sets.items() if set_name == "Satellite account"]

    return {
        "r": {"main": regions},
        "n": {"main": final_use},
        "s": {"main": sector_values},
        "f": {"main": factor_values},
        "k": {"main": satellite_values},
    }


def iot_block_specs_for_matrix_layouts(
    matrix_layouts: dict[str, tuple[str, ...]],
    *,
    final_demand_axis_names: tuple[str, ...] = ("Region", "Consumption category"),
) -> list:
    """Return built-in block specs implied by custom IOT matrix layouts."""
    specs = []

    e_layout = matrix_layouts.get("E", ())
    ey_layout = matrix_layouts.get("EY", e_layout)
    if e_layout or ey_layout:
        specs.extend(
            [
                block_spec("E", row_axes=iot_axis_names("E", "from", matrix_layouts), col_axes=iot_axis_names("E", "to", matrix_layouts)),
                block_spec("EY", row_axes=iot_axis_names("EY", "from", matrix_layouts), col_axes=final_demand_axis_names),
                block_spec("e", row_axes=iot_axis_names("e", "from", matrix_layouts), col_axes=iot_axis_names("e", "to", matrix_layouts)),
                block_spec("f", row_axes=iot_axis_names("f", "from", matrix_layouts), col_axes=iot_axis_names("f", "to", matrix_layouts)),
                block_spec("F", row_axes=iot_axis_names("F", "from", matrix_layouts), col_axes=iot_axis_names("F", "to", matrix_layouts)),
            ]
        )

    v_layout = matrix_layouts.get("V", ())
    vy_layout = matrix_layouts.get("VY", v_layout)
    if v_layout or vy_layout:
        specs.extend(
            [
                block_spec("V", row_axes=iot_axis_names("V", "from", matrix_layouts), col_axes=iot_axis_names("V", "to", matrix_layouts)),
                block_spec("VY", row_axes=iot_axis_names("VY", "from", matrix_layouts), col_axes=final_demand_axis_names),
                block_spec("v", row_axes=iot_axis_names("v", "from", matrix_layouts), col_axes=iot_axis_names("v", "to", matrix_layouts)),
                block_spec("m", row_axes=iot_axis_names("m", "from", matrix_layouts), col_axes=iot_axis_names("m", "to", matrix_layouts)),
                block_spec("M", row_axes=iot_axis_names("M", "from", matrix_layouts), col_axes=iot_axis_names("M", "to", matrix_layouts)),
            ]
        )

    return specs


def iot_units_from_frame(units_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Convert one canonical two-level units frame into MARIO's unit dictionary."""
    units: dict[str, pd.DataFrame] = {}
    for level_name in ("Sector", "Factor of production", "Satellite account"):
        if level_name in units_frame.index.get_level_values(0):
            units[level_name] = units_frame.loc[[level_name]].droplevel(0).copy()
    return units
