"""Classification of IAM-to-MRIO shocks and their implemented operators."""

from functools import cache
from importlib import resources

import pandas as pd
import yaml

from mario.log_exc.exceptions import NotImplementable, WrongInput
from mario.ops.iam_shocks import apply_iam_production_mix


_OPERATORS = {"activity_market_shares": {"SUT": apply_iam_production_mix}}


@cache
def _definitions():
    resource = resources.files("mario.settings").joinpath("iam_shocks.yaml")
    with resource.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def list_iam_shocks(family=None, *, implemented_only=False):
    """Return the shock taxonomy indexed by the identifiers used by shock_from_iam.

    Optionally select a family (production_structure, input_structure or
    final_demand), or show only implemented operators. Each row describes the
    IAM input, SUT and IOT targets, physical and monetary rules, and the
    concordances or other inputs required. Variable examples are illustrative.

    supported_tables lists the table types executable through shock_from_iam.
    A specified shock has an economic definition and no executable operator.
    """
    records = []
    for name, definition in _definitions().items():
        tables = tuple(_OPERATORS.get(definition["operator"], {}))
        records.append(
            {
                "shock": name,
                **definition,
                "status": "implemented" if tables else "specified",
                "supported_tables": tables,
                "example_variables": tuple(definition["example_variables"]),
            }
        )
    result = pd.DataFrame.from_records(records).set_index("shock")
    if family is not None:
        families = result["family"].unique()
        if family not in families:
            raise WrongInput(
                f"Unknown IAM shock family {family!r}. Available: {', '.join(families)}."
            )
        result = result.loc[result["family"] == family]
    if implemented_only:
        result = result.loc[result["status"] == "implemented"]
    return result


def resolve_iam_shock(shock, table):
    """Resolve an executable taxonomy entry before downloading or editing data."""
    definitions = _definitions()
    if not isinstance(shock, str) or shock not in definitions:
        raise WrongInput(
            f"Unknown IAM shock {shock!r}. See mario.list_iam_shocks() for the identifiers."
        )
    entry = definitions[shock]
    handlers = _OPERATORS.get(entry["operator"])
    if not handlers:
        raise NotImplementable(
            f"{shock!r} is specified in the {entry['family']} family and has no implemented "
            f"operator. Required inputs: {entry['requires']}"
        )
    if table not in handlers:
        raise WrongInput(
            f"IAM shock {shock!r} is implemented for {', '.join(handlers)}. Got {table!r}."
        )
    return entry, handlers[table]
