"""Resolve a SUT production market and its valuation for IAM shocks."""

import copy
import re

from mario.log_exc.exceptions import WrongInput
from mario.model.electricity_mix import resolve_electricity_commodity_aggregation
from mario.model.conventions import _MASTER_INDEX


def iam_market(database, commodity, electricity, pool):
    products = database.get_index(_MASTER_INDEX["c"], flat=True)
    if electricity and commodity is None and "Electricity (generation)" in products:
        commodity = "Electricity (generation)"
    if commodity in products:
        if electricity and (
            commodity.casefold().startswith("electricity by ")
            or commodity.casefold() == "electricity nec"
        ):
            raise WrongInput(
                "Choose a shared generation commodity or omit commodity and pass pool=True."
            )
        return commodity, [commodity]
    if not electricity:
        raise WrongInput(f"Expected an existing shared commodity, got {commodity!r}.")
    name, members = next(
        iter(resolve_electricity_commodity_aggregation(database).items())
    )
    if members == [name]:
        if commodity is None or commodity == name:
            return name, members
        raise WrongInput(
            f"The shared electricity commodity is {name!r}, not {commodity!r}."
        )
    if not pool:
        raise WrongInput(
            "Separate generation commodities found. Pass pool=True to combine them across all scenarios."
        )
    return commodity or "Electricity (generation)", members


def iam_market_basis(database, members, basis):
    units = database.units[_MASTER_INDEX["c"]]["unit"].reindex(members)
    if units.isna().any() or units.nunique() != 1:
        raise WrongInput(
            f"The generation or production market needs one common unit, found {units.unique().tolist()}."
        )
    unit = str(units.iloc[0]).strip()
    if re.fullmatch(r"(?:[kMGTPE]?Wh|[kMGTPE]?J)", unit):
        detected = "physical"
    elif re.fullmatch(
        r"(?:(?:mio|million|millions|mn|m|bn|billion)[. _-]*)?(?:EUR|EURO|USD|GBP|JPY|CNY|CHF|CAD|AUD|€|\$)",
        unit,
        re.I,
    ):
        detected = "value"
    else:
        detected = None
    if basis is None:
        if detected is None:
            raise WrongInput(
                f"Specify basis='physical' or 'value' for the market unit {unit!r}."
            )
        return detected
    if basis not in ("physical", "value") or (detected and basis != detected):
        raise WrongInput(f"Incompatible basis {basis!r} for market unit {unit!r}.")
    return basis


def apply_iam_market_shares(
    database, base, target, market, members, shares, electricity
):
    """Pool if requested and publish a new scenario after the complete mix succeeds."""
    # Pooling changes all scenarios. Otherwise only the new scenario needs
    # private matrices. Publish the result after recipe filling succeeds.
    pooling = members != [market]
    if pooling:
        staged = database.copy()
        staged._apply_commodity_aggregation({market: members})
    else:
        staged = copy.copy(database)
        staged.matrices = database.matrices.copy()
        staged.meta = copy.deepcopy(database.meta)
    staged.clone_scenario(base, target)
    supply = staged.query(
        "S" if staged.has_matrix("S", target) else "s", scenarios=target
    )
    market_columns = supply.columns.get_level_values(-1) == market
    for region, weights in shares.items():
        labels = staged.get_index(_MASTER_INDEX["a"], region=region)
        if electricity:
            wanted = {item.casefold() for item in weights}
            native = {}
            for label in labels:
                key = str(label).casefold()
                if key in native and key in wanted:
                    raise WrongInput(
                        f"Ambiguous generation activity {label!r} in {region!r}."
                    )
                native[key] = label
            weights = {
                native.get(label.casefold(), label): weight
                for label, weight in weights.items()
            }
            shares[region] = weights
        missing = set(weights).difference(labels)
        if missing:
            raise WrongInput(
                f"Missing production activities in {region!r}: {sorted(missing)}."
            )
        bundle = supply.loc[(region, _MASTER_INDEX["a"], list(weights)), market_columns]
        if not (bundle.to_numpy().sum() > 0):
            raise WrongInput(
                f"No production of {market!r} by the selected activities in {region!r}."
            )
    staged.update_supply_mix(
        shares, level=_MASTER_INDEX["a"], commodities=market, scenario=target
    )
    if pooling:
        database._indeces, database.units, database.matrices = (
            staged._indeces,
            staged.units,
            staged.matrices,
        )
    else:
        database.matrices[target] = staged.matrices[target]
    database.meta = staged.meta
