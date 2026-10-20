"""Session compute presets selected by public parser entry points.

Keys are parser function names without the ``parse_`` prefix. Parsers absent
from the registry leave the active settings unchanged. Profiles override only
the listed compute options and never modify the saved user profile.
"""

from functools import wraps
import logging

from mario.log_exc.logger import log_time
from mario.settings.settings import download_settings, upload_settings


PARSER_COMPUTE_PROFILES: dict[str, dict] = {
    "bonsai": {
        "compute_method": "solve",
        "linear_solver": "umfpack",
        "linear_strategy": "direct",
        "singular_policy": "partial",
    },
}

logger = logging.getLogger(__name__)


def with_parser_compute_profile(parser):
    """Look up a parser's preset at each call and retain it only on success.

    The wrapped function keeps its public signature and metadata. Missing or
    empty profiles are a no-op. Dependency and settings validation precede any
    input reads; import errors and interruptions restore previous settings.
    """
    profile_name = parser.__name__.removeprefix("parse_")

    @wraps(parser)
    def configured_parser(*args, **kwargs):
        profile = PARSER_COMPUTE_PROFILES.get(profile_name)
        if not profile:
            return parser(*args, **kwargs)

        overrides = dict(profile)
        previous = download_settings()
        configured = {**previous, "compute": {**previous["compute"], **overrides}}
        if configured["compute"]["linear_solver"] == "umfpack":
            from mario.compute.linear_solvers import load_umfpack

            load_umfpack()
        upload_settings(configured)
        try:
            result = parser(*args, **kwargs)
        except BaseException:
            upload_settings(previous)
            raise
        selected = ", ".join(f"{key}={value}" for key, value in overrides.items())
        log_time(
            logger,
            f"{profile_name.upper()} compute settings: {selected} (current Python session).",
            "info",
        )
        return result

    return configured_parser
