"""Technology-assumption helpers for SUT databases."""

from __future__ import annotations

from mario.log_exc.exceptions import WrongInput
from mario.model.enums import TableKind

INDUSTRY_BASED_TECH = "industry-based"
PRODUCT_BASED_TECH = "product-based"

_TECH_ALIASES = {
    INDUSTRY_BASED_TECH: INDUSTRY_BASED_TECH,
    PRODUCT_BASED_TECH: PRODUCT_BASED_TECH,
    "IT": INDUSTRY_BASED_TECH,
    "PT": PRODUCT_BASED_TECH,
}


def normalize_tech_assumption(value: str | None) -> str | None:
    """Normalize one user-facing technology-assumption token."""
    if value is None:
        return None

    token = str(value).strip()
    if token == "":
        return None

    normalized = _TECH_ALIASES.get(token)
    if normalized is None:
        normalized = _TECH_ALIASES.get(token.upper())
    if normalized is None:
        raise WrongInput(
            "tech_assumption should be one of "
            "['industry-based', 'product-based', 'IT', 'PT']."
        )
    return normalized


def resolve_tech_assumption(
    *,
    table: TableKind | str,
    tech_assumption: str | None,
    activity_count: int | None = None,
    commodity_count: int | None = None,
) -> tuple[str | None, str | None]:
    """Resolve the effective technology assumption for one database shape."""
    table_kind = TableKind.coerce(table)
    requested = normalize_tech_assumption(tech_assumption)

    if table_kind == TableKind.IOT:
        if requested is not None:
            raise WrongInput("tech_assumption is only supported for SUT databases.")
        return None, None

    resolved = requested or INDUSTRY_BASED_TECH
    if (
        resolved == PRODUCT_BASED_TECH
        and activity_count is not None
        and commodity_count is not None
        and activity_count != commodity_count
    ):
        note = (
            "Requested product-based technology assumption for a non-square SUT "
            f"(activities={activity_count}, commodities={commodity_count}); "
            "falling back to industry-based."
        )
        return INDUSTRY_BASED_TECH, note

    return resolved, None
