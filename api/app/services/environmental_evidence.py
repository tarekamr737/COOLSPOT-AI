"""Versioned selection and normalized finalist environmental evidence."""

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from api.app.fortyguard_models import ACTIVITY_ID_PATTERN, SHA256_PATTERN

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENVIRONMENTAL_CONFIG_PATH = ROOT / "config" / "environmental_parameters.json"
DEFAULT_ENVIRONMENTAL_SITES_DIR = (
    ROOT / "data" / "processed" / "pacoima_environmental_sites"
)
DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH = (
    ROOT / "data" / "processed" / "pacoima_environmental_evidence.json"
)


class EnvironmentalMetricId(StrEnum):
    APPARENT_TEMPERATURE = "apparent_temperature"
    RELATIVE_HUMIDITY = "relative_humidity"
    CLEAR_SKY_GHI = "clear_sky_ghi"


class EnvironmentalMetricSource(StrEnum):
    PARAMETERS = "parameters"
    SOLAR_CLEAR_SKY = "solar_irradiance.clear_sky"


class EnvironmentalMetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: EnvironmentalMetricId
    source: EnvironmentalMetricSource
    vendor_key: str = Field(min_length=1)
    display_label: str = Field(min_length=3)
    unit_label: str = Field(min_length=1)
    planning_context: str = Field(min_length=30)
    limitation: str = Field(min_length=40)


class EnvironmentalEvidenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    metrics: tuple[EnvironmentalMetricDefinition, ...] = Field(
        min_length=1, max_length=3
    )
    selection_note: str = Field(min_length=80)

    @model_validator(mode="after")
    def require_unique_complete_selection(self) -> Self:
        metric_ids = tuple(metric.id for metric in self.metrics)
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("environmental metric IDs must be unique")
        if set(metric_ids) != set(EnvironmentalMetricId):
            raise ValueError("environmental evidence must use the three approved metrics")
        return self


def load_environmental_evidence_config(
    path: Path = DEFAULT_ENVIRONMENTAL_CONFIG_PATH,
) -> EnvironmentalEvidenceConfig:
    return EnvironmentalEvidenceConfig.model_validate_json(path.read_text(encoding="utf-8"))


class EnvironmentalSourceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(pattern=r"^data/processed/pacoima_environmental_sites/.+\.json$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class FinalistEnvironmentalEvidence(BaseModel):
    """Three raw vendor values normalized into stable application fields."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    finalist_rank: int = Field(ge=1, le=10)
    candidate_id: str
    site_id: str
    site_name: str
    tile_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observed_temperature_c: float
    apparent_temperature_c: float
    relative_humidity_percent: float = Field(ge=0, le=100)
    clear_sky_ghi_vendor_value: float = Field(ge=0)
    observed_at: datetime
    vendor_timezone: str = Field(min_length=1)
    vendor_timezone_offset_hours: float = Field(ge=-14, le=14)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    source_artifact: EnvironmentalSourceArtifact


class PacoimaEnvironmentalEvidenceArtifact(BaseModel):
    """Deterministic, concise environmental evidence for the top finalists."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    pilot: Literal["Pacoima, Los Angeles"] = "Pacoima, Los Angeles"
    generated_at: datetime
    environmental_config_sha256: str = Field(pattern=SHA256_PATTERN)
    finalist_count: Literal[10] = 10
    metrics: tuple[EnvironmentalMetricId, ...]
    sites: tuple[FinalistEnvironmentalEvidence, ...] = Field(min_length=10, max_length=10)
    limitations: tuple[str, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_sites_and_metrics(self) -> Self:
        if self.metrics != tuple(EnvironmentalMetricId):
            raise ValueError("normalized metrics must match the approved config order")
        ranks = tuple(site.finalist_rank for site in self.sites)
        if ranks != tuple(range(1, 11)):
            raise ValueError("environmental finalist ranks must be complete and ordered")
        site_ids = tuple(site.site_id for site in self.sites)
        if len(site_ids) != len(set(site_ids)):
            raise ValueError("normalized environmental site IDs must be unique")
        return self


def _number(value: JsonValue, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def _single_parameter(
    parameters: dict[str, tuple[JsonValue, ...]], key: str
) -> float:
    values = parameters.get(key)
    if values is None or len(values) != 1:
        raise ValueError(f"{key} must contain exactly one value")
    return _number(values[0], key)


def build_environmental_evidence(
    sites_dir: Path = DEFAULT_ENVIRONMENTAL_SITES_DIR,
    config_path: Path = DEFAULT_ENVIRONMENTAL_CONFIG_PATH,
) -> PacoimaEnvironmentalEvidenceArtifact:
    """Normalize the ten exact cached responses without scoring or imputation."""

    from scripts.cache_environmental_finalists import FinalistEnvironmentalArtifact

    config = load_environmental_evidence_config(config_path)
    paths = tuple(sorted(sites_dir.glob("*.json")))
    if len(paths) != 10:
        raise ValueError("exactly ten cached environmental finalist responses are required")
    normalized: list[FinalistEnvironmentalEvidence] = []
    for path in paths:
        source_bytes = path.read_bytes()
        source = FinalistEnvironmentalArtifact.model_validate_json(source_bytes)
        if len(source.result.locations) != 1 or len(source.result.metadata.timestamps) != 1:
            raise ValueError("environmental finalist response must contain one point and timestamp")
        location = source.result.locations[0]
        clear_sky = location.solar_irradiance.get("clear_sky")
        if not isinstance(clear_sky, dict):
            raise ValueError("environmental response has no clear_sky irradiance object")
        normalized.append(
            FinalistEnvironmentalEvidence(
                finalist_rank=source.finalist_rank,
                candidate_id=source.candidate_id,
                site_id=source.site_id,
                site_name=source.site_name,
                tile_id=source.tile_id,
                latitude=location.lat,
                longitude=location.lon,
                observed_temperature_c=location.temperature,
                apparent_temperature_c=_single_parameter(
                    location.parameters, "apparent_temperature_celsius"
                ),
                relative_humidity_percent=_single_parameter(
                    location.parameters, "relative_humidity_percent"
                ),
                clear_sky_ghi_vendor_value=_number(clear_sky.get("ghi"), "clear_sky.ghi"),
                observed_at=source.result.metadata.timestamps[0],
                vendor_timezone=source.result.metadata.timezone,
                vendor_timezone_offset_hours=(
                    source.result.metadata.timezone_offset_hours
                ),
                request_hash=source.request_hash,
                activity_id=source.activity_id,
                source_artifact=EnvironmentalSourceArtifact(
                    path=path.relative_to(ROOT).as_posix(),
                    sha256=hashlib.sha256(source_bytes).hexdigest(),
                ),
            )
        )
    ordered = tuple(sorted(normalized, key=lambda site: site.finalist_rank))
    return PacoimaEnvironmentalEvidenceArtifact(
        generated_at=max(site.observed_at for site in ordered),
        environmental_config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        metrics=tuple(metric.id for metric in config.metrics),
        sites=ordered,
        limitations=(
            "Values are point-level, single-hour FortyGuard model outputs for finalist screening.",
            "The fields are context only and are not a medical-risk score or guaranteed outcome.",
            "Clear-sky GHI retains the vendor value because the endpoint schema does not "
            "state a unit.",
            "Vendor-returned timestamps and timezone metadata are preserved without correction.",
        ),
    )


def canonical_environmental_evidence_bytes(
    artifact: PacoimaEnvironmentalEvidenceArtifact,
) -> bytes:
    return (
        json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()


def load_environmental_evidence(
    path: Path = DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH,
) -> PacoimaEnvironmentalEvidenceArtifact:
    return PacoimaEnvironmentalEvidenceArtifact.model_validate_json(
        path.read_text(encoding="utf-8")
    )
