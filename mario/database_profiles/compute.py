"""Parser-selected session compute presets; unspecified parsers keep active settings.

These are preferred presets, not the current session configuration. Solver
availability and failure semantics remain in mario.settings.parser_profiles.
"""

PARSER_COMPUTE_PROFILES: dict[str, dict] = {
    "bonsai": {
        "compute_method": "solve",
        "linear_solver": "umfpack",
        "linear_solver_fallback": "scipy",
        "linear_strategy": "direct",
        "singular_policy": "partial",
    },
    "gloria": {
        "compute_method": "solve",
        "linear_solver": "umfpack",
        "linear_solver_fallback": "scipy",
        "linear_strategy": "direct",
        "singular_policy": "raise",
    },
    "emerging": {
        "compute_method": "solve",
        "linear_solver": "umfpack",
        "linear_solver_fallback": "scipy",
        "linear_strategy": "direct",
        "singular_policy": "raise",
    },
}
