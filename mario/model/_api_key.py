"""Resolve the unified ``api_key`` data-source selector, with a global key store.

Both ``update_supply_mix('electricity')`` and ``update_trade_mix('electricity')``
accept a single ``api_key`` selector naming the live data provider:

* a mapping with the key, ``{"entsoe": "<key>"}`` / ``{"ember": "<key>"}``;
* just the provider name, ``"entsoe"`` (or ``{"entsoe": None}``), to use a key
  configured **globally** -- so a user sets their keys once and then only names
  the provider at the call site.

Global keys resolve in this precedence (first hit wins), so an inline key always
overrides and secrets never need to live in code:

1. the inline ``api_key`` mapping value (if given);
2. :func:`set_api_keys` set earlier this session (like ``set_log_verbosity``);
3. the ``<PROVIDER>_API_KEY`` environment variable (``ENTSOE_API_KEY`` etc.);
4. the git-ignored ``mario/settings/api_keys.yaml`` file (copy
   ``api_keys.example.yaml``; never commit real keys).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from importlib import resources
import os

import yaml

from mario.log_exc.exceptions import WrongInput

_API_KEYS_FILE = "api_keys.yaml"

# Session overrides set via set_api_keys(...); highest precedence after inline.
_SESSION_KEYS: dict[str, str] = {}


def set_api_keys(**providers: str | None) -> None:
    """Set global API keys for this session, e.g. ``set_api_keys(entsoe="...", ember="...")``.

    Persist for the session like ``set_log_verbosity``; a value of ``None``
    clears a provider. Inline ``api_key=`` at a call site still overrides these.
    """
    for provider, key in providers.items():
        name = str(provider).strip().lower()
        if key is None:
            _SESSION_KEYS.pop(name, None)
        else:
            _SESSION_KEYS[name] = str(key)


@lru_cache(maxsize=1)
def _file_keys() -> dict[str, str]:
    """Load the git-ignored api_keys.yaml (cached); empty if absent/blank."""
    try:
        path = resources.files("mario.settings").joinpath(_API_KEYS_FILE)
        if not path.is_file():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (FileNotFoundError, OSError):  # pragma: no cover
        return {}
    return {str(k).strip().lower(): str(v) for k, v in data.items() if v}


def get_api_key(provider: str) -> str | None:
    """Return the globally configured key for `provider` (session > env > file)."""
    name = str(provider).strip().lower()
    if name in _SESSION_KEYS:
        return _SESSION_KEYS[name]
    env = os.environ.get(f"{name.upper()}_API_KEY")
    if env:
        return env
    return _file_keys().get(name)


def resolve_api_key(api_key, valid_providers) -> tuple[str | None, str | None]:
    """Return ``(provider, key)`` from an ``api_key`` selector, or ``(None, None)``.

    ``api_key`` is a provider name (``"entsoe"``) or a one-entry mapping
    (``{"entsoe": "<key>"}``; a null/blank value falls back to the global store).
    ``valid_providers`` is the set the calling method supports. Raises
    :class:`WrongInput` for a bad shape, an unsupported provider, or no key found.
    """
    if api_key is None:
        return None, None
    if isinstance(api_key, str):
        provider, key = api_key, None
    elif isinstance(api_key, Mapping) and len(api_key) == 1:
        provider, key = next(iter(api_key.items()))
    else:
        raise WrongInput(
            "api_key must be a provider name (e.g. 'entsoe') or a one-entry mapping "
            f"(e.g. {{'{sorted(valid_providers)[0]}': '<key>'}})."
        )
    provider = str(provider).strip().lower()
    if provider not in valid_providers:
        raise WrongInput(
            f"api_key provider {provider!r} is not available here; expected one of "
            f"{sorted(valid_providers)}."
        )
    if not key:
        key = get_api_key(provider)
    if not key:
        raise WrongInput(
            f"No API key found for {provider!r}. Pass api_key={{'{provider}': '<key>'}}, "
            f"call mario.set_api_keys({provider}='<key>'), set the "
            f"{provider.upper()}_API_KEY env var, or add it to "
            f"mario/settings/{_API_KEYS_FILE}."
        )
    return provider, str(key)
