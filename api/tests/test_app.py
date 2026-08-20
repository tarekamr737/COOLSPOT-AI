"""Smoke tests for the API scaffold."""

from fastapi import FastAPI

from api.app.main import app


def test_application_is_fastapi() -> None:
    assert isinstance(app, FastAPI)
