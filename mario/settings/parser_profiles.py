"""Session compute presets selected by public parser entry points.

Keys are parser function names without the ``parse_`` prefix. Parsers absent
from the registry leave the active settings unchanged. Profiles override only
the listed compute options and never modify the saved user profile.
``linear_solver_fallback`` applies only if the preferred optional solver cannot
be imported; mathematical or factorization failures never trigger a fallback.
"""

from functools import wraps
import logging

from mario.log_exc.logger import log_time
from mario.settings.settings import download_settings, upload_settings
from mario.log_exc.exceptions import WrongFormat
from mario.database_profiles.compute import PARSER_COMPUTE_PROFILES


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
        fallback = overrides.pop("linear_solver_fallback", None)
        if fallback not in (None, "scipy"):
            raise WrongFormat(
                "A parser's linear_solver_fallback must be 'scipy' or None."
            )
        previous = download_settings()
        configured = {**previous, "compute": {**previous["compute"], **overrides}}
        if configured["compute"]["linear_solver"] == "umfpack":
            from mario.compute.linear_solvers import load_umfpack

            try:
                load_umfpack()
            except ImportError:
                if fallback is None:
                    raise
                overrides["linear_solver"] = fallback
                configured["compute"]["linear_solver"] = fallback
                log_time(
                    logger,
                    f"{profile_name.upper()}: optional UMFPACK unavailable; using SciPy.",
                    "info",
                )
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
