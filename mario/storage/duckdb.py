"""Optional DuckDB helpers for the future storage/query layer."""

from __future__ import annotations


def require_duckdb():
    """Import and return ``duckdb`` or raise a focused missing-dependency error."""
    try:
        import duckdb
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "duckdb is not installed; DuckDB-backed storage/query features are unavailable."
        ) from exc

    return duckdb
