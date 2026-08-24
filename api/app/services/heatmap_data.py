"""Typed access to the frozen real Pacoima FortyGuard heatmap artifact."""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    DateTimeRequest,
    HeatmapResult,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_HEATMAP_PATH = ROOT / "data" / "processed" / "pacoima_fortyguard_heatmaps.json"
DEFAULT_EXCEEDANCE_PATH = (
    ROOT / "data" / "processed" / "pacoima_fortyguard_exceedance.json"
)
DEFAULT_TIME_OF_MEASURE_PATH = (
    ROOT / "data" / "processed" / "pacoima_fortyguard_time_of_measure.json"
)


class CachedHeatmapLayer(BaseModel):
    """One validated real layer plus immutable request and credit provenance."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    analytic_type: Literal["tcm", "persistence", "exceedance", "time_of_measure"]
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    completed_at: datetime
    granularity_m: Literal[100]
    date_time: DateTimeRequest
    threshold_c: float
    direction: Literal["above", "below"]
    observed_credit_delta: int = Field(ge=0)
    threshold_rationale: str = Field(min_length=20)
    feature_count: int = Field(gt=0)
    result: HeatmapResult

    @model_validator(mode="after")
    def validate_feature_count(self) -> Self:
        if self.feature_count != len(self.result.map_data.features):
            raise ValueError("feature_count does not match the heatmap result")
        return self


class PacoimaHeatmapArtifact(BaseModel):
    """Offline-ready pair of real, spatially matching Pacoima heatmap layers."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    source: Literal["FortyGuard Heatmap API"] = "FortyGuard Heatmap API"
    source_url: Literal["https://api.fortyguard.com/v1/heatmap"] = (
        "https://api.fortyguard.com/v1/heatmap"
    )
    license_notes: str
    pilot: Literal["Pacoima, Los Angeles"] = "Pacoima, Los Angeles"
    aoi_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    generated_at: datetime
    layers: tuple[CachedHeatmapLayer, CachedHeatmapLayer]

    @model_validator(mode="after")
    def require_matching_tcm_and_persistence(self) -> Self:
        by_type = {layer.analytic_type: layer for layer in self.layers}
        if set(by_type) != {"tcm", "persistence"}:
            raise ValueError("artifact requires exactly one tcm and one persistence layer")
        tcm = by_type["tcm"]
        persistence = by_type["persistence"]
        if tcm.granularity_m != persistence.granularity_m:
            raise ValueError("heatmap granularities do not match")
        if tcm.date_time.start_date != persistence.date_time.start_date:
            raise ValueError("heatmap dates do not match")
        tcm_tiles = tuple(
            (feature.id, feature.geometry) for feature in tcm.result.map_data.features
        )
        persistence_tiles = tuple(
            (feature.id, feature.geometry)
            for feature in persistence.result.map_data.features
        )
        if tcm_tiles != persistence_tiles:
            raise ValueError("heatmap tile IDs/geometries do not align")
        return self


class PacoimaExceedanceArtifact(BaseModel):
    """One offline-ready real Pacoima exceedance layer with provenance."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    source: Literal["FortyGuard Heatmap API"] = "FortyGuard Heatmap API"
    source_url: Literal["https://api.fortyguard.com/v1/heatmap"] = (
        "https://api.fortyguard.com/v1/heatmap"
    )
    license_notes: str
    pilot: Literal["Pacoima, Los Angeles"] = "Pacoima, Los Angeles"
    aoi_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    generated_at: datetime
    layer: CachedHeatmapLayer

    @model_validator(mode="after")
    def require_exceedance(self) -> Self:
        if self.layer.analytic_type != "exceedance":
            raise ValueError("artifact requires an exceedance layer")
        return self


class PacoimaTimeOfMeasureArtifact(BaseModel):
    """One offline-ready real Pacoima peak-hour layer with provenance."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    source: Literal["FortyGuard Heatmap API"] = "FortyGuard Heatmap API"
    source_url: Literal["https://api.fortyguard.com/v1/heatmap"] = (
        "https://api.fortyguard.com/v1/heatmap"
    )
    license_notes: str
    pilot: Literal["Pacoima, Los Angeles"] = "Pacoima, Los Angeles"
    aoi_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    generated_at: datetime
    timezone: Literal["UTC"] = "UTC"
    layer: CachedHeatmapLayer

    @model_validator(mode="after")
    def require_valid_time_of_measure(self) -> Self:
        if self.layer.analytic_type != "time_of_measure":
            raise ValueError("artifact requires a time-of-measure layer")
        values = tuple(
            feature.properties.get("value")
            for feature in self.layer.result.map_data.features
        )
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not 0 <= value <= 23
            or not float(value).is_integer()
            for value in values
        ):
            raise ValueError("time-of-measure values must be integer UTC hours from 0 to 23")
        return self


def load_heatmap_artifact(path: Path = DEFAULT_HEATMAP_PATH) -> PacoimaHeatmapArtifact:
    return PacoimaHeatmapArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def load_exceedance_artifact(
    path: Path = DEFAULT_EXCEEDANCE_PATH,
) -> PacoimaExceedanceArtifact:
    return PacoimaExceedanceArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def load_time_of_measure_artifact(
    path: Path = DEFAULT_TIME_OF_MEASURE_PATH,
) -> PacoimaTimeOfMeasureArtifact:
    return PacoimaTimeOfMeasureArtifact.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def canonical_heatmap_bytes(artifact: PacoimaHeatmapArtifact) -> bytes:
    """Serialize refreshed evidence in the repository's deterministic JSON format."""

    return (
        json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()


def canonical_exceedance_bytes(artifact: PacoimaExceedanceArtifact) -> bytes:
    """Serialize the frozen exceedance layer deterministically."""

    return (
        json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()


def canonical_time_of_measure_bytes(artifact: PacoimaTimeOfMeasureArtifact) -> bytes:
    """Serialize the frozen peak-hour layer deterministically."""

    return (
        json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()
