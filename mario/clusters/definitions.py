"""Validation and normalization of common and regional cluster members."""

from collections.abc import Mapping

from mario.log_exc.exceptions import WrongInput


def _items(values):
    return "{" + ", ".join(repr(value) for value in sorted(values, key=str)) + "}"


def _member_list(values):
    if isinstance(values, str):
        return [values]
    if isinstance(values, Mapping):
        raise WrongInput(
            "Cluster members must be a list of codes, not another mapping."
        )
    try:
        return list(values)
    except TypeError as error:
        raise WrongInput(
            "Cluster members must be a code or an iterable of codes."
        ) from error


def normalize_cluster_members(members, domain, *, level, name):
    """Validate member codes and preserve their regional association.

    On regional domains a plain list means its intersection with each region.
    Explicit regional definitions retain their keys; omitted regions select
    nothing. No input objects are modified.
    """

    def checked(values, allowed, region=None):
        values = _member_list(values)
        invalid = set(values).difference(allowed)
        if invalid:
            location = "" if region is None else f" in region {region!r}"
            raise WrongInput(
                f"{_items(invalid)} in cluster {name} for level {level}{location} "
                "is/are not a valid item/s."
            )
        return values

    if not isinstance(domain, Mapping):
        if isinstance(members, Mapping):
            raise WrongInput(
                f"Cluster {name} for level {level} requires a list: this set is not regional."
            )
        return checked(members, set(domain))

    if isinstance(members, Mapping):
        unknown = set(members).difference(domain)
        if unknown:
            raise WrongInput(
                f"Unknown regions {_items(unknown)} in cluster {name} for level {level}."
            )
        return {
            region: checked(values, set(domain[region]), region)
            for region, values in members.items()
        }

    union = {code for codes in domain.values() for code in codes}
    values = checked(members, union)
    allowed = {region: set(codes) for region, codes in domain.items()}
    return {
        region: [value for value in values if value in codes]
        for region, codes in allowed.items()
    }
