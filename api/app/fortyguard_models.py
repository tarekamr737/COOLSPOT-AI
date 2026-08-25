"""Typed request, activity, and normalized result models for FortyGuard."""

from datetime import date, datetime, time
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_serializer,
    model_validator,
)

from api.app.services.boundary import PolygonGeometry, calculate_area_sq_mi

ACTIVITY_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class StrictModel(BaseModel):
    """Reject unknown request/internal fields and non-finite numbers."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class FortyGuardEndpoint(StrEnum):
    """Supported asynchronous submission endpoints."""

    HEATMAP = "heatmap"
    ENV_PARAMS = "env_params"
    SATELLITE = "satellite"
    STREETVIEW = "streetview"
    HEAT_INTELLIGENCE = "heat_intelligence"


class ActivityLifecycle(StrEnum):
    """Normalized vendor lifecycle states."""

    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class CreditUsage(StrictModel):
    """Validated current-cycle credit counters returned by FortyGuard."""

    total_available_credits: int = Field(gt=0)
    used_credits: int = Field(ge=0)
    remaining_credits: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_cycle_balance(self) -> Self:
        if self.used_credits + self.remaining_credits != self.total_available_credits:
            raise ValueError("FortyGuard cycle credit counters do not balance")
        return self


class DateTimeRequest(StrictModel):
    """FortyGuard date/time filters with documented conditional fields."""

    start_date: date
    filter_type: Literal[1, 2, 3, 4]
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None

    @field_serializer("start_time", "end_time")
    def serialize_time(self, value: time | None) -> str | None:
        return value.strftime("%H:%M") if value is not None else None

    @model_validator(mode="after")
    def validate_filter_fields(self) -> Self:
        if self.start_date < date(2019, 1, 1):
            raise ValueError("start_date must be on or after 2019-01-01")
        if self.filter_type == 1:
            if self.start_time is None or self.end_time is not None or self.end_date is not None:
                raise ValueError("filter_type 1 requires only start_time")
        elif self.filter_type == 2:
            if self.start_time is None or self.end_time is None or self.end_date is not None:
                raise ValueError("filter_type 2 requires start_time and end_time on one day")
            if self.end_time <= self.start_time:
                raise ValueError("filter_type 2 end_time must be after start_time")
        elif self.filter_type == 3:
            if (
                self.start_time is not None
                or self.end_time is not None
                or self.end_date is not None
            ):
                raise ValueError("filter_type 3 accepts only start_date")
        elif (
            self.end_date is None
            or self.start_time is not None
            or self.end_time is not None
        ):
            raise ValueError("filter_type 4 requires only start_date and end_date")
        elif self.end_date < self.start_date or (self.end_date - self.start_date).days > 31:
            raise ValueError("filter_type 4 must be a forward range of at most 31 days")
        return self


class AoiFeature(StrictModel):
    """One closed polygon feature accepted by the heatmap endpoint."""

    type: Literal["Feature"]
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    geometry: PolygonGeometry


class PolygonAoi(StrictModel):
    """The exact GeoJSON FeatureCollection accepted by FortyGuard."""

    type: Literal["FeatureCollection"]
    features: tuple[AoiFeature, ...]

    @model_validator(mode="after")
    def require_one_feature(self) -> Self:
        if len(self.features) != 1:
            raise ValueError("polygon_aoi must contain exactly one polygon feature")
        return self


class HeatmapRequest(StrictModel):
    """Documented heatmap submission payload for the Basic/Startup pilot limit."""

    polygon_aoi: PolygonAoi
    date_time: DateTimeRequest
    granularity: Literal[60, 80, 100]
    analytic_type: Literal["tcm", "time_of_measure", "exceedance", "persistence"] = "tcm"
    threshold: float = Field(default=30, ge=-100, le=100)
    direction: Literal["above", "below"] = "above"

    @model_validator(mode="after")
    def enforce_pilot_area_limit(self) -> Self:
        area_sq_mi = calculate_area_sq_mi(self.polygon_aoi.features[0].geometry)
        if area_sq_mi >= 10:
            raise ValueError(f"heatmap AOI is {area_sq_mi:.6f} mi²; limit is below 10 mi²")
        return self


class EnvironmentalParametersRequest(StrictModel):
    """Documented environmental-parameters submission payload."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    temperature: float = Field(ge=-100, le=100)
    date_time: DateTimeRequest

    @model_validator(mode="after")
    def reject_multi_day_filter(self) -> Self:
        if self.date_time.filter_type == 4:
            raise ValueError("environmental parameters support filter_type 1, 2, or 3")
        return self


class SatelliteCoordinates(StrictModel):
    """Satellite request location."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SatelliteRequest(StrictModel):
    """Documented satellite-segmentation submission payload."""

    sat: SatelliteCoordinates
    date_time: DateTimeRequest
    granularity: Literal[60, 80, 100]

    @model_validator(mode="after")
    def reject_multi_day_filter(self) -> Self:
        if self.date_time.filter_type == 4:
            raise ValueError("satellite segmentation supports filter_type 1, 2, or 3")
        return self


class StreetViewRequest(StrictModel):
    """Documented street-view-segmentation submission payload."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    vertical_angle: float = Field(ge=-90, le=90)
    horizontal_angle: float = Field(ge=0, le=360)
    back_view: bool


class HeatIntelligenceRequest(StrictModel):
    """Documented Heat Intelligence point-report submission payload."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    temperature: float = Field(ge=-100, le=100)
    date: date
    analysis: tuple[
        Literal["geographic", "environmental", "urban", "events", "anthropogenic"],
        ...,
    ] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_report_request(self) -> Self:
        if self.date < date(2019, 1, 1):
            raise ValueError("Heat Intelligence date must be on or after 2019-01-01")
        if len(self.analysis) != len(set(self.analysis)):
            raise ValueError("Heat Intelligence analysis categories must be unique")
        return self


class HeatmapFeature(StrictModel):
    """One normalized polygon tile from a completed heatmap."""

    type: Literal["Feature"]
    id: str | int | None = None
    properties: dict[str, JsonValue]
    geometry: PolygonGeometry


class HeatmapMapData(StrictModel):
    """Normalized tile collection from a completed heatmap."""

    type: Literal["FeatureCollection"]
    features: tuple[HeatmapFeature, ...]


class HeatmapResult(StrictModel):
    """Internal heatmap result independent of the vendor envelope."""

    map_data: HeatmapMapData
    stats_data: dict[str, JsonValue]


class ResultCoordinates(StrictModel):
    """Normalized coordinates returned by segmentation endpoints."""

    latitude: float
    longitude: float


class EnvironmentTimeRange(StrictModel):
    """Time bounds returned with environmental parameters."""

    start: datetime
    end: datetime
    interval: str
    count: int = Field(ge=0)


class EnvironmentMetadata(StrictModel):
    """Normalized environmental time metadata."""

    timezone: str
    timezone_offset_hours: float
    time_range: EnvironmentTimeRange
    timestamps: tuple[datetime, ...]


class EnvironmentLocation(StrictModel):
    """Environmental values for one analyzed location."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    elevation: float | None = None
    temperature: float
    parameters: dict[str, tuple[JsonValue, ...]]
    solar_irradiance: dict[str, JsonValue]


class EnvironmentalParametersResult(StrictModel):
    """Internal environmental result independent of the vendor envelope."""

    metadata: EnvironmentMetadata
    locations: tuple[EnvironmentLocation, ...]


class ImageDimensions(StrictModel):
    """Segmentation image dimensions."""

    height: int = Field(gt=0)
    width: int = Field(gt=0)


class SatelliteSegmentation(StrictModel):
    """Normalized satellite segmentation output."""

    image_dimensions: ImageDimensions
    mode: str
    processing_time_seconds: float = Field(ge=0)
    request_id: str
    segments: dict[str, JsonValue]
    image_legend: dict[str, JsonValue]
    image_content: str


class SatelliteResult(StrictModel):
    """Internal satellite result with the vendor typo removed."""

    coordinates: ResultCoordinates
    original_images: tuple[str, ...]
    image_year: int = Field(ge=1900, le=2200)
    segmentation: SatelliteSegmentation


class StreetViewFrame(StrictModel):
    """One normalized street-view segmentation frame."""

    original_image: str
    segments: dict[str, JsonValue]
    image_legend: dict[str, JsonValue]
    segmented_image: str
    image_date: date


class StreetViewResult(StrictModel):
    """Internal street-view result independent of the vendor envelope."""

    coordinates: ResultCoordinates
    front: StreetViewFrame
    back: StreetViewFrame | None = None


EndpointResult = (
    HeatmapResult | EnvironmentalParametersResult | SatelliteResult | StreetViewResult
)


class ActivityHandle(StrictModel):
    """Persistent reference returned for a new or reused submission."""

    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    endpoint: FortyGuardEndpoint
    status: ActivityLifecycle
    reused: bool


class ActivityStatus(StrictModel):
    """Normalized activity state returned to application code."""

    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    endpoint: FortyGuardEndpoint
    status: ActivityLifecycle
    message: str
    result: EndpointResult | None = None

    @model_validator(mode="after")
    def require_terminal_result_shape(self) -> Self:
        if self.status == ActivityLifecycle.COMPLETED and self.result is None:
            raise ValueError("completed activity must include a normalized result")
        if self.status != ActivityLifecycle.COMPLETED and self.result is not None:
            raise ValueError("non-completed activity cannot include a result")
        return self


class PollingPolicy(StrictModel):
    """Bounded exponential-backoff policy."""

    max_attempts: int = Field(default=20, ge=1, le=100)
    initial_delay_seconds: float = Field(default=2, ge=0, le=60)
    maximum_delay_seconds: float = Field(default=30, ge=0, le=300)
    multiplier: float = Field(default=2, ge=1, le=10)
    jitter_ratio: float = Field(default=0.2, ge=0, le=1)

    @model_validator(mode="after")
    def validate_delays(self) -> Self:
        if self.maximum_delay_seconds < self.initial_delay_seconds:
            raise ValueError("maximum poll delay must be at least the initial delay")
        return self
