"""Shared isolation for tests that intentionally change session settings."""

import pytest

import mario


@pytest.fixture
def isolated_session_settings():
    previous = mario.download_settings()
    mario.reset_settings()
    try:
        yield
    finally:
        mario.upload_settings(previous)


@pytest.fixture
def bonsai_without_umfpack(isolated_session_settings, monkeypatch):
    """Exercise parsing without the optional native solver; no UMFPACK solves."""
    monkeypatch.setattr("mario.compute.linear_solvers.load_umfpack", lambda: None)
