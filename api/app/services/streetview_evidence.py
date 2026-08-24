"""Deterministically extract compact features from cached FortyGuard street views."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from enum import StrEnum

from pydantic import Field

from api.app.fortyguard_models import (
    ActivityLifecycle,
    ResultCoordinates,
    StreetViewFrame,
    StreetViewResult,
    StrictModel,
)


class StreetViewDirection(StrEnum):
    """Supported camera directions in a normalized Street View result."""

    FRONT = "front"
    BACK = "back"


class ExtractedSegment(StrictModel):
    """One validated raw segmentation percentage from a Street View frame."""

    label: str = Field(min_length=1)
    percentage: float = Field(ge=0, le=100)


class ExtractedStreetViewFrame(StrictModel):
    """Compact frame evidence with image payloads intentionally removed."""

    direction: StreetViewDirection
    image_date: date
    segments: tuple[ExtractedSegment, ...]


class ExtractedStreetViewFeatures(StrictModel):
    """Validated raw features for one exact cached site."""

    site_id: str = Field(min_length=1)
    coordinates: ResultCoordinates
    frames: tuple[ExtractedStreetViewFrame, ...] = Field(min_length=1, max_length=2)


def _extract_frame(
    direction: StreetViewDirection,
    frame: StreetViewFrame,
) -> ExtractedStreetViewFrame:
    normalized: dict[str, float] = {}
    for raw_label, raw_percentage in frame.segments.items():
        label = raw_label.strip().lower().replace(" ", "_")
        if not label:
            raise ValueError("Street View segment labels must not be empty")
        if label in normalized:
            raise ValueError(f"duplicate normalized Street View segment label: {label}")
        if isinstance(raw_percentage, bool) or not isinstance(raw_percentage, (int, float)):
            raise ValueError(f"Street View segment {label} must be numeric")
        percentage = float(raw_percentage)
        if not math.isfinite(percentage) or not 0 <= percentage <= 100:
            raise ValueError(f"Street View segment {label} must be between 0 and 100")
        normalized[label] = percentage

    return ExtractedStreetViewFrame(
        direction=direction,
        image_date=frame.image_date,
        segments=tuple(
            ExtractedSegment(label=label, percentage=percentage)
            for label, percentage in sorted(normalized.items())
        ),
    )


def extract_street_view_features(
    payload: Mapping[str, object],
) -> ExtractedStreetViewFeatures:
    """Extract deterministic, image-free features from a completed cached response."""

    if payload.get("status") != ActivityLifecycle.COMPLETED.value:
        raise ValueError("cached Street View response is not completed")
    site_id = payload.get("site_id")
    if not isinstance(site_id, str) or not site_id.strip():
        raise ValueError("cached Street View response is missing site_id")
    raw_result = payload.get("result")
    if not isinstance(raw_result, Mapping):
        raise ValueError("completed cached Street View response is missing result")

    result = StreetViewResult.model_validate(raw_result)
    frames = [_extract_frame(StreetViewDirection.FRONT, result.front)]
    if result.back is not None:
        frames.append(_extract_frame(StreetViewDirection.BACK, result.back))
    return ExtractedStreetViewFeatures(
        site_id=site_id,
        coordinates=result.coordinates,
        frames=tuple(frames),
    )
