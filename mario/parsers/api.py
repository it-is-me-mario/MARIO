"""Developer-facing helpers for writing new MARIO parsers.

This module is the intended landing zone for parser authors. The goal is to
keep parser authoring simple:

* parse raw files into canonical MARIO blocks, indexes and units;
* call one builder to obtain a ``ModelState`` or ``Database``;
* optionally register the parser in the internal registry.

Parser authors should not need to interact directly with low-level helper
modules unless they are changing parser infrastructure itself.
"""

from __future__ import annotations

import copy

from mario.api import Database
from mario.internal import ModelState
from mario.log_exc.exceptions import WrongInput
from mario.model.enums import TableKind
from mario.parsers.helpers import build_state_from_parser_output
from mario.parsers.specs import INPUT_OPTIONS

_MODELS = {"Database": Database}


def validate_parse_request(
    *,
    table: str | None = None,
    mode: str | None = None,
    unit: str | None = None,
    model: str = "Database",
) -> None:
    """Validate common parser arguments against MARIO's accepted values."""
    errors: list[str] = []

    if table is not None and table not in INPUT_OPTIONS["table"]:
        errors.append(f"Table should be in {INPUT_OPTIONS['table']}")

    if mode is not None and mode not in INPUT_OPTIONS["mode"]:
        errors.append(f"Mode should be in {INPUT_OPTIONS['mode']}")

    if unit is not None and unit not in INPUT_OPTIONS["unit"]:
        errors.append(f"Unit should be in {INPUT_OPTIONS['unit']}")

    if model not in _MODELS:
        errors.append(f"Available models are {[*_MODELS]}")

    if errors:
        raise WrongInput(errors)


def build_parser_state(
    *,
    table: TableKind | str,
    matrices: dict[str, object],
    indexes: dict[str, dict[str, object]] | None,
    units: dict[str, object] | None,
    parser_name: str,
    mode: str | None = None,
    name: str | None = None,
    source: str | None = None,
    year: int | None = None,
    price: str | None = None,
    source_path: str | None = None,
    repository=None,
) -> ModelState:
    """Build a canonical internal parser state from normalized parser output."""
    return build_state_from_parser_output(
        table=table,
        matrices=matrices,
        indexes=indexes,
        units=units,
        parser_name=parser_name,
        mode=mode,
        name=name,
        source=source,
        year=year,
        price=price,
        source_path=source_path,
        repository=repository,
    )


def state_to_database_payload(
    state: ModelState,
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]], dict[str, object]]:
    """Convert a parser ``ModelState`` into the payload accepted by ``Database``."""
    baseline_blocks: dict[str, object] = {}
    for block_name in state.list_blocks("baseline", include_inherited=False):
        value = state.get_block(block_name)
        baseline_blocks[block_name] = value.copy(deep=True) if hasattr(value, "copy") else value

    matrices = {"baseline": baseline_blocks}
    indexes = {
        code: {level_name: list(values) for level_name, values in levels.items()}
        for code, levels in state.indexes.items()
    }
    units = {
        label: value.copy(deep=True) if hasattr(value, "copy") else copy.deepcopy(value)
        for label, value in state.units.items()
    }
    return matrices, indexes, units


def build_database_from_state(
    state: ModelState,
    *,
    model: str = "Database",
    calc_all: bool = False,
    name: str | None = None,
    source: str | None = None,
    year: int | None = None,
    price: str | None = None,
    **kwargs,
):
    """Build a public ``Database`` directly from a parser ``ModelState``."""
    validate_parse_request(model=model)
    matrices, indexes, units = state_to_database_payload(state)
    metadata = state.metadata

    return _MODELS[model](
        name=name if name is not None else metadata.name,
        table=TableKind.coerce(metadata.table_kind).value,
        source=source if source is not None else metadata.source,
        year=year if year is not None else metadata.year,
        price=price if price is not None else metadata.price,
        init_by_parsers={"matrices": matrices, "_indeces": indexes, "units": units},
        calc_all=calc_all,
        notes=list(metadata.history),
        **kwargs,
    )


def build_database_from_parser_output(
    *,
    table: TableKind | str,
    matrices: dict[str, object],
    indexes: dict[str, dict[str, object]] | None,
    units: dict[str, object] | None,
    parser_name: str,
    mode: str | None = None,
    name: str | None = None,
    source: str | None = None,
    year: int | None = None,
    price: str | None = None,
    source_path: str | None = None,
    repository=None,
    model: str = "Database",
    calc_all: bool = False,
    **kwargs,
):
    """Build a public ``Database`` directly from normalized parser output.

    This is the simplest builder for new parsers. A parser author only needs to
    provide canonical MARIO blocks, indexes and units.
    """
    state = build_parser_state(
        table=table,
        matrices=matrices,
        indexes=indexes,
        units=units,
        parser_name=parser_name,
        mode=mode,
        name=name,
        source=source,
        year=year,
        price=price,
        source_path=source_path,
        repository=repository,
    )
    return build_database_from_state(
        state,
        model=model,
        calc_all=calc_all,
        name=name,
        source=source,
        year=year,
        price=price,
        **kwargs,
    )
