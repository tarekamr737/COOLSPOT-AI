"""Typed API request and response models."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.app.services.boundary import BoundaryCollection, PolygonGeometry
from api.app.services.candidates import (
    Candidate,
    CandidateConfig,
    CandidateCounts,
    SourceArtifact,
)
from api.app.services.capabilities import CapabilityRecord
from api.app.services.feature_table import ScoringConfig, TileFeature
from api.app.services.interventions import (
    InterventionCatalog,
    InterventionDefinition,
)
from api.app.services.optimizer import OptimizerConfig
from api.app.services.processed_data import FixtureGeometry


class HealthResponse(BaseModel):
    """Service readiness response."""

    status: Literal["ok"] = "ok"


class LayerName(StrEnum):
    HEAT = "heat"
    PERSISTENCE = "persistence"
    EXPOSURE = "exposure"
    VULNERABILITY = "vulnerability"


class HeatLayerProperties(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    layer: Literal[LayerName.HEAT]
    tile_id: str
    average_temperature_c: float
    temperature_score: float = Field(ge=0, le=1)
    combined_heat_score: float = Field(ge=0, le=1)


class PersistenceLayerProperties(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    layer: Literal[LayerName.PERSISTENCE]
    tile_id: str
    persistence_hours: float = Field(ge=0)
    threshold_c: float
    direction: Literal["above", "below"]
    persistence_score: float = Field(ge=0, le=1)
    combined_heat_score: float = Field(ge=0, le=1)


class ExposureLayerProperties(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    layer: Literal[LayerName.EXPOSURE]
    tile_id: str
    exposure_score: float = Field(ge=0, le=1)
    transit_stop_count: int = Field(ge=0)
    published_patronage_activity: float | None = Field(default=None, ge=0)
    poi_count: int = Field(ge=0)
    school_count: int = Field(ge=0)
    park_count: int = Field(ge=0)
    library_count: int = Field(ge=0)
    acs_total_population_context: float | None = Field(default=None, ge=0)
    missing_fields: tuple[str, ...]


class VulnerabilityLayerProperties(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    layer: Literal[LayerName.VULNERABILITY]
    tile_id: str
    vulnerability_score: float = Field(ge=0, le=1)
    children_rate: float | None = Field(default=None, ge=0, le=1)
    older_adult_rate: float | None = Field(default=None, ge=0, le=1)
    poverty_rate: float | None = Field(default=None, ge=0, le=1)
    no_vehicle_rate: float | None = Field(default=None, ge=0, le=1)
    acs_tract_geoids: tuple[str, ...]
    missing_fields: tuple[str, ...]


LayerProperties = Annotated[
    HeatLayerProperties
    | PersistenceLayerProperties
    | ExposureLayerProperties
    | VulnerabilityLayerProperties,
    Field(discriminator="layer"),
]


class LayerFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["Feature"] = "Feature"
    geometry: PolygonGeometry
    properties: LayerProperties


class LayerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["FeatureCollection"] = "FeatureCollection"
    layer: LayerName
    source_date: date
    generated_at: datetime
    cached: Literal[True] = True
    features: tuple[LayerFeature, ...]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def require_matching_layer(self) -> Self:
        if any(feature.properties.layer != self.layer for feature in self.features):
            raise ValueError("feature properties do not match the response layer")
        return self


class PilotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["Pacoima, Los Angeles"] = "Pacoima, Los Angeles"
    boundary: BoundaryCollection
    area_sq_mi: float = Field(gt=0, lt=10)
    crs: Literal["EPSG:4326"] = "EPSG:4326"
    granularity_m: Literal[100] = 100
    analysis_date: date
    budget_presets_usd: tuple[int, ...]
    default_budget_usd: int
    candidate_count: int = Field(ge=20)
    available_layers: tuple[LayerName, ...]


class CandidateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    generated_at: datetime
    counts: CandidateCounts
    source_artifacts: tuple[SourceArtifact, ...]
    limitations: tuple[str, ...]
    candidates: tuple[Candidate, ...]


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_usd: int = Field(gt=0)


class ExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    budget_usd: int = Field(gt=0)
    regenerate: bool = False


class SiteOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: Candidate
    tile: TileFeature
    intervention: InterventionDefinition


class SiteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: str
    site_name: str
    geometry: FixtureGeometry
    options: tuple[SiteOption, ...] = Field(min_length=1)


class MethodologyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    scoring: ScoringConfig
    candidate_generation: CandidateConfig
    optimization: OptimizerConfig
    interventions: InterventionCatalog
    limitations: tuple[str, ...]


class CreditStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(gt=0)
    used: int = Field(ge=0)
    remaining: int = Field(ge=0)
    hard_reserve: int = Field(ge=0)


class DataStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["cached_demo", "live_refreshed"] = "cached_demo"
    external_calls_on_read: Literal[False] = False
    refresh_available: bool = False
    explanation_mode: Literal["template", "openrouter"] = "template"
    heat_data_date: date
    heat_data_generated_at: datetime
    public_data_retrieved_at: date
    capabilities_evaluated_at: date
    credits: CreditStatus
    capabilities: tuple[CapabilityRecord, ...]
    layers: tuple[LayerName, ...]
    candidate_count: int = Field(ge=20)
    candidate_source_artifacts: tuple[SourceArtifact, ...]
