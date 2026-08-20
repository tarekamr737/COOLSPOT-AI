"""Typed API response models."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Service readiness response."""

    status: Literal["ok"] = "ok"
