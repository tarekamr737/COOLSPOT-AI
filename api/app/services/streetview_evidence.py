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


class StreetViewSegmentationMetrics(StrictModel):
    """Transparent per-view percentages copied from exact vendor categories."""

    tree_pct: float | None = Field(default=None, ge=0, le=100)
    grass_pct: float | None = Field(default=None, ge=0, le=100)
    sky_pct: float | None = Field(default=None, ge=0, le=100)
    road_pct: float | None = Field(default=None, ge=0, le=100)
    sidewalk_pct: float | None = Field(default=None, ge=0, le=100)
    building_pct: float | None = Field(default=None, ge=0, le=100)


class StreetViewMetricCoverage(StrictModel):
    """Number of observed views contributing to each aggregated percentage."""

    tree_pct: int = Field(ge=0, le=2)
    grass_pct: int = Field(ge=0, le=2)
    sky_pct: int = Field(ge=0, le=2)
    road_pct: int = Field(ge=0, le=2)
    sidewalk_pct: int = Field(ge=0, le=2)
    building_pct: int = Field(ge=0, le=2)


class AggregatedStreetViewMetrics(StrictModel):
    """Equal-weight mean of observed views, without interpreting shade."""

    view_count: int = Field(ge=1, le=2)
    metrics: StreetViewSegmentationMetrics
    contributing_views: StreetViewMetricCoverage


class ExtractedStreetViewFrame(StrictModel):
    """Compact frame evidence with image payloads intentionally removed."""

    direction: StreetViewDirection
    image_date: date
    segments: tuple[ExtractedSegment, ...]
    metrics: StreetViewSegmentationMetrics


class ExtractedStreetViewFeatures(StrictModel):
    """Validated raw features for one exact cached site."""

    site_id: str = Field(min_length=1)
    coordinates: ResultCoordinates
    frames: tuple[ExtractedStreetViewFrame, ...] = Field(min_length=1, max_length=2)
    aggregate: AggregatedStreetViewMetrics


def _mean_observed(values: tuple[float | None, ...]) -> float | None:
    observed = tuple(value for value in values if value is not None)
    return round(math.fsum(observed) / len(observed), 6) if observed else None


def _aggregate_frames(
    frames: tuple[ExtractedStreetViewFrame, ...],
) -> AggregatedStreetViewMetrics:
    tree = tuple(frame.metrics.tree_pct for frame in frames)
    grass = tuple(frame.metrics.grass_pct for frame in frames)
    sky = tuple(frame.metrics.sky_pct for frame in frames)
    road = tuple(frame.metrics.road_pct for frame in frames)
    sidewalk = tuple(frame.metrics.sidewalk_pct for frame in frames)
    building = tuple(frame.metrics.building_pct for frame in frames)
    return AggregatedStreetViewMetrics(
        view_count=len(frames),
        metrics=StreetViewSegmentationMetrics(
            tree_pct=_mean_observed(tree),
            grass_pct=_mean_observed(grass),
            sky_pct=_mean_observed(sky),
            road_pct=_mean_observed(road),
            sidewalk_pct=_mean_observed(sidewalk),
            building_pct=_mean_observed(building),
        ),
        contributing_views=StreetViewMetricCoverage(
            tree_pct=sum(value is not None for value in tree),
            grass_pct=sum(value is not None for value in grass),
            sky_pct=sum(value is not None for value in sky),
            road_pct=sum(value is not None for value in road),
            sidewalk_pct=sum(value is not None for value in sidewalk),
            building_pct=sum(value is not None for value in building),
        ),
    )


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
        metrics=StreetViewSegmentationMetrics(
            tree_pct=normalized.get("tree"),
            grass_pct=normalized.get("grass"),
            sky_pct=normalized.get("sky"),
            road_pct=normalized.get("road"),
            sidewalk_pct=normalized.get("sidewalk"),
            building_pct=normalized.get("building"),
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
    normalized_frames = tuple(frames)
    return ExtractedStreetViewFeatures(
        site_id=site_id,
        coordinates=result.coordinates,
        frames=normalized_frames,
        aggregate=_aggregate_frames(normalized_frames),
    )
