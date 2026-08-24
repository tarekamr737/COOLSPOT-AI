"""Deterministically extract compact features from cached FortyGuard street views."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self, cast

from pydantic import Field, model_validator

from api.app.fortyguard_models import (
    ActivityLifecycle,
    ResultCoordinates,
    StreetViewFrame,
    StreetViewResult,
    StrictModel,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STREETVIEW_CONFIG_PATH = ROOT / "config" / "streetview_evidence.json"
DEFAULT_STREETVIEW_LEGACY_PATH = ROOT / "data" / "processed" / "pacoima_streetview.json"
DEFAULT_STREETVIEW_SITE_DIR = ROOT / "data" / "processed" / "pacoima_streetview_sites"


class StreetContextConfidenceWeights(StrictModel):
    """Versioned weights for independently observable confidence components."""

    usable_views: float = Field(ge=0, le=1)
    imagery_availability: float = Field(ge=0, le=1)
    imagery_age: float = Field(ge=0, le=1)
    segmentation_completeness: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if not math.isclose(sum(self.model_dump().values()), 1.0):
            raise ValueError("Street View confidence weights must sum to 1")
        return self


class ShadeEvidenceWeights(StrictModel):
    """Weights for visual context used to screen shade-structure opportunity."""

    open_sky_context: float = Field(ge=0, le=1)
    low_tree_context: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if not math.isclose(sum(self.model_dump().values()), 1.0):
            raise ValueError("shade evidence weights must sum to 1")
        return self


class StreetViewEvidenceConfig(StrictModel):
    """Versioned deterministic Street View evidence settings."""

    version: Literal["1.0"]
    target_view_count: int = Field(ge=1, le=2)
    fresh_age_days: int = Field(ge=0)
    stale_age_days: int = Field(gt=0)
    stale_age_score: float = Field(ge=0, le=1)
    confidence_weights: StreetContextConfidenceWeights
    shade_evidence_weights: ShadeEvidenceWeights
    shade_screening_limitation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_age_thresholds(self) -> Self:
        if self.stale_age_days <= self.fresh_age_days:
            raise ValueError("stale_age_days must be greater than fresh_age_days")
        return self


def load_streetview_evidence_config(
    path: Path = DEFAULT_STREETVIEW_CONFIG_PATH,
) -> StreetViewEvidenceConfig:
    """Load the versioned confidence settings."""

    return StreetViewEvidenceConfig.model_validate_json(path.read_text(encoding="utf-8"))


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


class StreetContextConfidenceComponents(StrictModel):
    """Auditable component scores used by street context confidence."""

    usable_views: float = Field(ge=0, le=1)
    imagery_availability: float = Field(ge=0, le=1)
    imagery_age: float = Field(ge=0, le=1)
    segmentation_completeness: float = Field(ge=0, le=1)


class StreetContextConfidence(StrictModel):
    """Deterministic evidence completeness score, not outcome certainty."""

    score: float = Field(ge=0, le=1)
    usable_view_count: int = Field(ge=0, le=2)
    oldest_image_age_days: int = Field(ge=0)
    components: StreetContextConfidenceComponents


class ShadeInterventionEvidence(StrictModel):
    """Visual intervention-screening evidence, never a direct shade measurement."""

    score: float = Field(ge=0, le=1)
    open_sky_context: float | None = Field(default=None, ge=0, le=1)
    low_tree_context: float | None = Field(default=None, ge=0, le=1)
    street_context_confidence: float = Field(ge=0, le=1)
    limitation: str = Field(min_length=1)


class ExtractedStreetViewFrame(StrictModel):
    """Compact frame evidence with image payloads intentionally removed."""

    direction: StreetViewDirection
    image_date: date
    original_image_available: bool
    segmented_image_available: bool
    segments: tuple[ExtractedSegment, ...]
    metrics: StreetViewSegmentationMetrics


class ExtractedStreetViewFeatures(StrictModel):
    """Validated raw features for one exact cached site."""

    site_id: str = Field(min_length=1)
    coordinates: ResultCoordinates
    frames: tuple[ExtractedStreetViewFrame, ...] = Field(min_length=1, max_length=2)
    aggregate: AggregatedStreetViewMetrics
    street_context_confidence: StreetContextConfidence
    shade_intervention_evidence: ShadeInterventionEvidence


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


def _parse_retrieved_date(value: object) -> date:
    if not isinstance(value, str):
        raise ValueError("cached Street View response is missing retrieved_at")
    try:
        retrieved_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("cached Street View retrieved_at is invalid") from exc
    if retrieved_at.tzinfo is None:
        raise ValueError("cached Street View retrieved_at must include a timezone")
    return retrieved_at.date()


def _age_component(age_days: int, config: StreetViewEvidenceConfig) -> float:
    if age_days <= config.fresh_age_days:
        return 1.0
    if age_days >= config.stale_age_days:
        return config.stale_age_score
    elapsed = age_days - config.fresh_age_days
    interval = config.stale_age_days - config.fresh_age_days
    return 1 - (elapsed / interval) * (1 - config.stale_age_score)


def _confidence(
    frames: tuple[ExtractedStreetViewFrame, ...],
    retrieved_date: date,
    config: StreetViewEvidenceConfig,
) -> StreetContextConfidence:
    usable = tuple(frame for frame in frames if frame.segments)
    image_ages = tuple((retrieved_date - frame.image_date).days for frame in usable)
    if any(age < 0 for age in image_ages):
        raise ValueError("Street View image_date cannot be after retrieved_at")
    usable_score = min(len(usable) / config.target_view_count, 1.0)
    imagery_slots = 2 * len(usable)
    imagery_score = (
        sum(
            frame.original_image_available + frame.segmented_image_available
            for frame in usable
        )
        / imagery_slots
        if imagery_slots
        else 0.0
    )
    age_score = (
        math.fsum(_age_component(age, config) for age in image_ages) / len(image_ages)
        if image_ages
        else 0.0
    )
    requested_values = tuple(
        value
        for frame in usable
        for value in frame.metrics.model_dump().values()
    )
    completeness_score = (
        sum(value is not None for value in requested_values) / len(requested_values)
        if requested_values
        else 0.0
    )
    components = StreetContextConfidenceComponents(
        usable_views=usable_score,
        imagery_availability=imagery_score,
        imagery_age=age_score,
        segmentation_completeness=completeness_score,
    )
    weights = config.confidence_weights
    score = (
        components.usable_views * weights.usable_views
        + components.imagery_availability * weights.imagery_availability
        + components.imagery_age * weights.imagery_age
        + components.segmentation_completeness * weights.segmentation_completeness
    )
    return StreetContextConfidence(
        score=round(score, 6),
        usable_view_count=len(usable),
        oldest_image_age_days=max(image_ages, default=0),
        components=components,
    )


def _shade_evidence(
    aggregate: AggregatedStreetViewMetrics,
    confidence: StreetContextConfidence,
    config: StreetViewEvidenceConfig,
) -> ShadeInterventionEvidence:
    sky = aggregate.metrics.sky_pct
    tree = aggregate.metrics.tree_pct
    open_sky = sky / 100 if sky is not None else None
    low_tree = 1 - tree / 100 if tree is not None else None
    weighted = (
        (open_sky, config.shade_evidence_weights.open_sky_context),
        (low_tree, config.shade_evidence_weights.low_tree_context),
    )
    available_weight = math.fsum(weight for value, weight in weighted if value is not None)
    context_score = (
        math.fsum(value * weight for value, weight in weighted if value is not None)
        / available_weight
        if available_weight
        else 0.0
    )
    return ShadeInterventionEvidence(
        score=round(context_score * confidence.score, 6),
        open_sky_context=open_sky,
        low_tree_context=low_tree,
        street_context_confidence=confidence.score,
        limitation=config.shade_screening_limitation,
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
        original_image_available=bool(frame.original_image.strip()),
        segmented_image_available=bool(frame.segmented_image.strip()),
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
    *,
    config: StreetViewEvidenceConfig | None = None,
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
    retrieved_date = _parse_retrieved_date(payload.get("retrieved_at"))
    active_config = config or load_streetview_evidence_config()
    frames = [_extract_frame(StreetViewDirection.FRONT, result.front)]
    if result.back is not None:
        frames.append(_extract_frame(StreetViewDirection.BACK, result.back))
    normalized_frames = tuple(frames)
    aggregate = _aggregate_frames(normalized_frames)
    confidence = _confidence(normalized_frames, retrieved_date, active_config)
    return ExtractedStreetViewFeatures(
        site_id=site_id,
        coordinates=result.coordinates,
        frames=normalized_frames,
        aggregate=aggregate,
        street_context_confidence=confidence,
        shade_intervention_evidence=_shade_evidence(
            aggregate,
            confidence,
            active_config,
        ),
    )


def load_cached_street_view_features(
    site_dir: Path = DEFAULT_STREETVIEW_SITE_DIR,
    legacy_path: Path = DEFAULT_STREETVIEW_LEGACY_PATH,
    *,
    config: StreetViewEvidenceConfig | None = None,
) -> tuple[ExtractedStreetViewFeatures, ...]:
    """Parse every committed site cache once and return canonical site order."""

    paths = ([legacy_path] if legacy_path.exists() else []) + sorted(site_dir.glob("*.json"))
    by_site: dict[str, ExtractedStreetViewFeatures] = {}
    for path in paths:
        raw_payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_payload, dict):
            raise ValueError(f"cached Street View document must be an object: {path}")
        features = extract_street_view_features(
            cast(dict[str, object], raw_payload),
            config=config,
        )
        if features.site_id in by_site:
            raise ValueError(f"duplicate cached Street View site_id: {features.site_id}")
        by_site[features.site_id] = features
    return tuple(by_site[site_id] for site_id in sorted(by_site))
