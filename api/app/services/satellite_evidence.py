"""Normalize the single governed satellite probe into compact surface context."""

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    SatelliteRequest,
    SatelliteResult,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SATELLITE_PROBE_PATH = (
    ROOT / "data" / "processed" / "fortyguard_satellite_probe.json"
)
DEFAULT_SATELLITE_EVIDENCE_PATH = (
    ROOT / "data" / "processed" / "pacoima_satellite_evidence.json"
)


class SatelliteProbeReport(BaseModel):
    """Secret-free result and credit provenance for the sole satellite probe."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    measured_at: datetime
    endpoint: Literal["satellite"] = "satellite"
    request_hash: str = Field(pattern=SHA256_PATTERN)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    candidate_id: str
    site_id: str
    site_name: str
    tile_id: str
    request: SatelliteRequest
    status: Literal["Completed", "Failed"]
    result: SatelliteResult | None = None
    usage_before: int = Field(ge=0)
    usage_after: int = Field(ge=0)
    observed_credit_delta: int = Field(ge=0)
    total_allocation: int = Field(default=2_000_000, ge=500_001, le=2_000_000)
    hard_reserve: int = Field(default=500_000, ge=500_000)
    remaining_after: int = Field(ge=500_000)
    source_url: Literal["https://api.fortyguard.com/v1/satellite"] = (
        "https://api.fortyguard.com/v1/satellite"
    )
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if (self.status == "Completed") != (self.result is not None):
            raise ValueError("only a completed satellite probe may include a result")
        if self.observed_credit_delta != self.usage_after - self.usage_before:
            raise ValueError("observed delta does not match usage counters")
        if self.remaining_after != self.total_allocation - self.usage_after:
            raise ValueError("remaining credits do not match allocation minus usage")
        return self


class SurfaceClassCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    road_route_percent: float = Field(ge=0, le=100)
    sidewalk_pavement_percent: float = Field(ge=0, le=100)
    combined_surface_class_percent: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_sum(self) -> Self:
        if not math.isclose(
            self.combined_surface_class_percent,
            self.road_route_percent + self.sidewalk_pavement_percent,
            abs_tol=1e-9,
        ):
            raise ValueError("combined surface coverage must equal its two source classes")
        return self


class SatelliteSurfaceEvidence(BaseModel):
    """Image-free exact-site overhead context; never a field-feasibility finding."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    candidate_id: str
    site_id: str
    tile_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    image_year: int = Field(ge=2019, le=2200)
    image_width_px: int = Field(gt=0)
    image_height_px: int = Field(gt=0)
    segments: dict[str, float]
    surface_class_coverage: SurfaceClassCoverage
    request_hash: str = Field(pattern=SHA256_PATTERN)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    observed_credit_delta: int = Field(ge=0)
    source_url: Literal["https://docs-api.fortyguard.com/docs/satellite-view-segmentation"] = (
        "https://docs-api.fortyguard.com/docs/satellite-view-segmentation"
    )
    assessment: Literal["source_complete"] = "source_complete"
    limitation: str = Field(min_length=120)

    @field_validator("segments")
    @classmethod
    def validate_segments(cls, value: dict[str, float]) -> dict[str, float]:
        if not value or any(not 0 <= percentage <= 100 for percentage in value.values()):
            raise ValueError("satellite segments must be percentages in [0,100]")
        if not {"road, route", "sidewalk, pavement"} <= set(value):
            raise ValueError("satellite evidence lacks required surface classes")
        if not math.isclose(math.fsum(value.values()), 100, abs_tol=0.05):
            raise ValueError("satellite segment percentages must total approximately 100")
        return value


class SatelliteEvidenceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    source_probe_path: Literal["data/processed/fortyguard_satellite_probe.json"]
    source_probe_sha256: str = Field(pattern=SHA256_PATTERN)
    site_count: Literal[1] = 1
    sites: tuple[SatelliteSurfaceEvidence, ...] = Field(min_length=1, max_length=1)


def build_satellite_evidence(
    probe_path: Path = DEFAULT_SATELLITE_PROBE_PATH,
) -> SatelliteEvidenceArtifact:
    report = SatelliteProbeReport.model_validate_json(probe_path.read_text(encoding="utf-8"))
    if report.status != "Completed" or report.result is None:
        raise ValueError("satellite evidence requires a completed probe")
    result = report.result
    segments = {
        key: float(value)
        for key, value in result.segmentation.segments.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    road = segments.get("road, route")
    sidewalk = segments.get("sidewalk, pavement")
    if road is None or sidewalk is None:
        raise ValueError("satellite result lacks required surface class values")
    evidence = SatelliteSurfaceEvidence(
        candidate_id=report.candidate_id,
        site_id=report.site_id,
        tile_id=report.tile_id,
        latitude=result.coordinates.latitude,
        longitude=result.coordinates.longitude,
        image_year=result.image_year,
        image_width_px=result.segmentation.image_dimensions.width,
        image_height_px=result.segmentation.image_dimensions.height,
        segments=segments,
        surface_class_coverage=SurfaceClassCoverage(
            road_route_percent=road,
            sidewalk_pavement_percent=sidewalk,
            combined_surface_class_percent=road + sidewalk,
        ),
        request_hash=report.request_hash,
        activity_id=report.activity_id,
        observed_credit_delta=report.observed_credit_delta,
        limitation=(
            "Dated overhead class coverage is surface-screening context for this exact finalist "
            "only. It does not establish ownership, current pavement condition, treatment area, "
            "traction, glare, drainage, pedestrian radiant exposure, product compatibility, "
            "permits, or construction feasibility."
        ),
    )
    return SatelliteEvidenceArtifact(
        source_probe_path="data/processed/fortyguard_satellite_probe.json",
        source_probe_sha256=hashlib.sha256(probe_path.read_bytes()).hexdigest(),
        sites=(evidence,),
    )


def canonical_satellite_evidence_bytes(document: SatelliteEvidenceArtifact) -> bytes:
    return (
        json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()


def load_satellite_evidence(
    path: Path = DEFAULT_SATELLITE_EVIDENCE_PATH,
) -> SatelliteEvidenceArtifact:
    return SatelliteEvidenceArtifact.model_validate_json(path.read_text(encoding="utf-8"))
