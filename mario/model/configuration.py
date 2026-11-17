"""Accounting configurations shared by the runtime and format diagrams."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from mario.log_exc.exceptions import WrongInput


IMPORT_REPRESENTATIONS = ("factor-accounts", "separate")
IMPORT_FLOW_BLOCKS = {
    "IOT": ("IMP", "IMP_Y"),
    "SUT": ("IMP_a", "IMP_c", "IMP_Y"),
}
IMPORT_COEFFICIENT_BLOCKS = {
    "IOT": ("imp", "IMP_Y"),
    "SUT": ("imp_a", "imp_c", "IMP_Y"),
}
REGIONAL_TOPOLOGY = {
    "isard": {"S": "diagonal", "U": "bilateral", "Yc": "bilateral"},
    "chenery-moses": {"S": "bilateral", "U": "diagonal", "Yc": "diagonal"},
}


@dataclass(frozen=True)
class ModelConfiguration:
    """Describe the accounting structure and assumptions of one scenario.

    Foreign origin descriptors do not add endogenous regions. Technology
    assumptions belong to the database; trade representations can be recorded
    separately for each scenario.
    """

    table_format: str
    regional_scope: str
    trade_representation: str
    import_representation: str
    imports_by: str | None
    trade_resolution: str
    tech_assumption: str | None
    sector_type: str | None

    def to_dict(self):
        """Return independent JSON-compatible configuration values."""
        return asdict(self)


def validate_import_representation(value):
    """Normalize a requested external-import representation."""
    if value not in IMPORT_REPRESENTATIONS:
        raise WrongInput(f"import_representation must be one of {IMPORT_REPRESENTATIONS}.")
    return value


def configuration_values(database):
    """Read persisted structural choices without invoking dynamic block access."""
    attributes = getattr(database, "__dict__", {})
    metadata = attributes.get("meta")
    if metadata is not None:
        values = dict(getattr(metadata, "model_configuration", {}) or {})
    else:
        metadata = attributes.get("metadata")
        values = dict(getattr(metadata, "extra", {}).get("model_configuration", {}) or {})
    if "import_origins" in values:
        values.setdefault("trade_resolution", values.pop("import_origins"))
    return values


def separate_imports(database):
    """Return whether external imports use their own native blocks."""
    return configuration_values(database).get("import_representation") == "separate"


def get_configuration(database, scenario="baseline"):
    """Build the effective configuration of an existing database scenario."""
    scenario = database._validate_scenario(scenario)
    values = configuration_values(database)
    regions = database.get_index("Region")
    regional_scope = "single-region" if len(regions) == 1 else "multi-region"
    trade = values.get("trade_representations", {}).get(scenario, "unspecified")
    if len(regions) == 1:
        trade = "external-trade"
    elif database.table_type == "IOT":
        trade = "bilateral"
    elif trade == "unspecified":
        trade = _sut_trade_representation(database, scenario)
    return ModelConfiguration(
        table_format=database.table_type,
        regional_scope=regional_scope,
        trade_representation=trade,
        import_representation=values.get("import_representation", "factor-accounts"),
        imports_by=values.get("imports_by"),
        trade_resolution=values.get("trade_resolution", "unspecified"),
        tech_assumption=getattr(database.meta, "tech_assumption", None),
        sector_type=getattr(database.meta, "sector_type", None),
    )


def _has_foreign_cells(frame):
    row_regions = frame.index.get_level_values(0)
    col_regions = frame.columns.get_level_values(0)
    for region in col_regions.unique():
        block = frame.iloc[row_regions != region, col_regions == region]
        if all(isinstance(dtype, pd.SparseDtype) for dtype in block.dtypes):
            if any(np.any(column.array.sp_values != 0) for _, column in block.items()):
                return True
        elif np.any(block.to_numpy() != 0):
            return True
    return False


def _sut_trade_representation(database, scenario):
    """Recognize structural regional patterns on available native flows."""
    frames = database.matrices[scenario]
    supply = frames.get("S", frames.get("s"))
    use = frames.get("U", frames.get("u"))
    demand = frames.get("Yc")
    if supply is None or use is None or demand is None:
        return "unspecified"
    foreign_supply = _has_foreign_cells(supply)
    foreign_uses = _has_foreign_cells(use) or _has_foreign_cells(demand)
    if foreign_supply and foreign_uses:
        return "mixed"
    if foreign_supply:
        return "chenery-moses"
    if foreign_uses:
        return "isard"
    return "domestic-only"


def update_configuration(database, **changes):
    """Persist structural choices in the database metadata."""
    values = configuration_values(database)
    values.update(changes)
    database.meta.model_configuration = values


def record_trade_representation(database, scenario, representation):
    """Record a trade transformation on its actual scenario."""
    values = configuration_values(database)
    representations = dict(values.get("trade_representations", {}))
    representations[scenario] = representation
    update_configuration(database, trade_representations=representations)


def import_blocks(database, mode="flows"):
    """Return the native import blocks required by the active representation."""
    if not separate_imports(database):
        return ()
    blocks = IMPORT_COEFFICIENT_BLOCKS if mode == "coefficients" else IMPORT_FLOW_BLOCKS
    return blocks[database.table_type]
