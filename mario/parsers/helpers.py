"""Helpers that adapt parser outputs into the MARIO 2 Dataset model."""

from __future__ import annotations

from pathlib import Path
import logging

from mario.compute.ordering import SUTUnifiedOrderingPolicy
from mario.compute.views import (
    extract_Ea_from_E,
    extract_Ec_from_E,
    extract_S_from_Z,
    extract_U_from_Z,
    extract_Va_from_V,
    extract_Vc_from_V,
    extract_Xa_from_X,
    extract_Xc_from_X,
    extract_Ya_from_Y,
    extract_Yc_from_Y,
    extract_ea_from_e,
    extract_ec_from_e,
    extract_s_from_z,
    extract_u_from_z,
    extract_va_from_v,
    extract_vc_from_v,
)
from mario.log_exc.logger import log_time
from mario.model import Dataset, DatasetMetadata
from mario.model.enums import TableKind
from mario.storage.base import BlockRepository
from mario.storage.repository import InMemoryBlockRepository

logger = logging.getLogger(__name__)


def _copy_blocks(blocks: dict[str, object]) -> dict[str, object]:
    """Return defensive copies of parser-produced block values."""
    copied: dict[str, object] = {}
    for name, value in blocks.items():
        copied[name] = value.copy(deep=True) if hasattr(value, "copy") else value
    return copied


def copy_indexes(
    indexes: dict[str, dict[str, object]] | None,
) -> dict[str, dict[str, tuple[object, ...]]]:
    """Normalize parser index mappings into tuple-based containers."""
    normalized: dict[str, dict[str, tuple[object, ...]]] = {}
    if not indexes:
        return normalized

    for code, levels in indexes.items():
        normalized[code] = {}
        for level_name, values in levels.items():
            normalized[code][level_name] = tuple(values)

    return normalized


def copy_units(units: dict[str, object] | None) -> dict[str, object]:
    """Return defensive copies of parser-produced unit tables."""
    if not units:
        return {}

    copied: dict[str, object] = {}
    for label, value in units.items():
        copied[label] = value.copy(deep=True) if hasattr(value, "copy") else value
    return copied


def extract_baseline_blocks(matrices: dict[str, object]) -> dict[str, object]:
    """Extract the baseline block mapping from parser output payloads."""
    if "baseline" in matrices and isinstance(matrices["baseline"], dict):
        return _copy_blocks(matrices["baseline"])
    return _copy_blocks(matrices)


def promote_sut_blocks(blocks: dict[str, object]) -> dict[str, object]:
    """Convert unified SUT parser blocks into split-native canonical blocks."""
    log_time(logger, "Parser: promoting unified SUT blocks to split-native blocks.", "debug")
    ordering = SUTUnifiedOrderingPolicy.from_blocks(
        Z=blocks.get("Z"),
        z=blocks.get("z"),
        X=blocks.get("X"),
        Y=blocks.get("Y"),
        V=blocks.get("V"),
        E=blocks.get("E"),
    )

    promoted: dict[str, object] = {}

    if "Z" in blocks:
        promoted["U"] = extract_U_from_Z(blocks["Z"], ordering)
        promoted["S"] = extract_S_from_Z(blocks["Z"], ordering)

    if "z" in blocks:
        promoted["u"] = extract_u_from_z(blocks["z"], ordering)
        promoted["s"] = extract_s_from_z(blocks["z"], ordering)

    if "X" in blocks:
        promoted["Xa"] = extract_Xa_from_X(blocks["X"], ordering)
        promoted["Xc"] = extract_Xc_from_X(blocks["X"], ordering)

    if "Y" in blocks:
        promoted["Ya"] = extract_Ya_from_Y(blocks["Y"], ordering)
        promoted["Yc"] = extract_Yc_from_Y(blocks["Y"], ordering)

    if "V" in blocks:
        promoted["Va"] = extract_Va_from_V(blocks["V"], ordering)
        promoted["Vc"] = extract_Vc_from_V(blocks["V"], ordering)

    if "v" in blocks:
        promoted["va"] = extract_va_from_v(blocks["v"], ordering)
        promoted["vc"] = extract_vc_from_v(blocks["v"], ordering)

    if "E" in blocks:
        promoted["Ea"] = extract_Ea_from_E(blocks["E"], ordering)
        promoted["Ec"] = extract_Ec_from_E(blocks["E"], ordering)

    if "e" in blocks:
        promoted["ea"] = extract_ea_from_e(blocks["e"], ordering)
        promoted["ec"] = extract_ec_from_e(blocks["e"], ordering)

    if "EY" in blocks:
        promoted["EY"] = blocks["EY"].copy(deep=True) if hasattr(blocks["EY"], "copy") else blocks["EY"]

    return promoted


def build_dataset_from_parser_output(
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
    source_path: str | Path | None = None,
    repository: BlockRepository | None = None,
) -> Dataset:
    """Build a canonical ``Dataset`` from normalized parser output."""
    table_kind = TableKind.coerce(table)
    log_time(logger, f"Parser: building dataset payload for {table_kind.value}.", "debug")

    metadata = DatasetMetadata(
        table_kind=table_kind,
        name=name,
        source=source,
        year=year,
        price=price,
    )
    metadata.extra["parser"] = parser_name
    if mode is not None:
        metadata.extra["mode"] = mode
    if source_path is not None:
        metadata.extra["source_path"] = str(Path(source_path))
    metadata.add_history(f"Parsed with {parser_name}.")

    dataset = Dataset(
        metadata=metadata,
        repository=repository or InMemoryBlockRepository(),
        indexes=copy_indexes(indexes),
        units=copy_units(units),
    )

    parsed_blocks = extract_baseline_blocks(matrices)
    canonical_blocks = parsed_blocks if table_kind == TableKind.IOT else promote_sut_blocks(parsed_blocks)

    for block_name, value in canonical_blocks.items():
        dataset.set_block(block_name, value)

    log_time(
        logger,
        f"Parser: dataset payload ready with {len(canonical_blocks)} canonical blocks.",
        "info",
    )
    return dataset
