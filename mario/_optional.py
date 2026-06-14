"""Helpers for optional third-party dependencies."""

from __future__ import annotations


def require_pyarrow(*, feature: str, error_type: type[Exception] = ImportError) -> None:
    """Ensure a NumPy 2 compatible ``pyarrow`` build is importable."""
    try:
        import pyarrow  # noqa: F401
    except Exception as exc:
        raise error_type(
            f"{feature} requires the dependency 'pyarrow>=17'. "
            "It is installed with MARIO by default; reinstall MARIO with dependencies "
            "or run `pip install 'pyarrow>=17'`. If `pyarrow` is already installed, "
            "upgrade it to a build compatible with NumPy 2."
        ) from exc
