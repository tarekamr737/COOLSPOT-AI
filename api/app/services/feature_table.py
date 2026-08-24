"""Deterministic spatial feature table built from cached real Pacoima data."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from api.app.services.boundary import PolygonGeometry
from api.app.services.heatmap_data import (
    DEFAULT_EXCEEDANCE_PATH,
    DEFAULT_HEATMAP_PATH,
    PacoimaExceedanceArtifact,
    PacoimaHeatmapArtifact,
    load_exceedance_artifact,
    load_heatmap_artifact,
)
from api.app.services.processed_data import (
    ProcessedPublicData,
    ProcessedTransitStop,
    VulnerabilityEstimates,
    load_processed_fixture,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_DATA_PATH = ROOT / "data" / "processed" / "pacoima_public_data.json"
DEFAULT_CONFIG_PATH = ROOT / "config" / "scoring.json"
DEFAULT_FEATURE_TABLE_PATH = ROOT / "data" / "processed" / "pacoima_tile_features.json"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


def _require_unit_sum(values: tuple[float, ...], label: str) -> None:
    if not math.isclose(sum(values), 1.0, abs_tol=1e-9):
        raise ValueError(f"{label} weights must sum to 1")


class HeatWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    temperature: float = Field(ge=0, le=1)
    persistence: float = Field(ge=0, le=1)
    exceedance: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> Self:
        _require_unit_sum(
            (self.temperature, self.persistence, self.exceedance), "heat"
        )
        return self


class ExposureWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    population_context: float = Field(ge=0, le=1)
    published_patronage: float = Field(ge=0, le=1)
    poi_count: float = Field(ge=0, le=1)
    transit_stop_count: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> Self:
        _require_unit_sum(
            (
                self.population_context,
                self.published_patronage,
                self.poi_count,
                self.transit_stop_count,
            ),
            "exposure",
        )
        return self


class VulnerabilityWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    children: float = Field(ge=0, le=1)
    older_adults: float = Field(ge=0, le=1)
    poverty: float = Field(ge=0, le=1)
    no_vehicle: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> Self:
        _require_unit_sum(
            (self.children, self.older_adults, self.poverty, self.no_vehicle),
            "vulnerability",
        )
        return self


class OpportunityWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    public_site: float = Field(ge=0, le=1)
    transit_stop: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> Self:
        _require_unit_sum((self.public_site, self.transit_stop), "opportunity")
        return self


class PriorityWeights(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    heat: float = Field(ge=0, le=1)
    exposure: float = Field(ge=0, le=1)
    vulnerability: float = Field(ge=0, le=1)
    cooling_opportunity: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_sum(self) -> Self:
        _require_unit_sum(
            (self.heat, self.exposure, self.vulnerability, self.cooling_opportunity),
            "priority",
        )
        return self


class ScoringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: str = Field(pattern=r"^1\.0$")
    lower_quantile: float = Field(ge=0, lt=0.5)
    upper_quantile: float = Field(gt=0.5, le=1)
    constant_feature_score: float = Field(ge=0, le=1)
    missing_strategy: str = Field(min_length=20)
    patronage_metric: str = Field(min_length=20)
    population_context_note: str = Field(min_length=20)
    cooling_opportunity_note: str = Field(min_length=20)
    point_join_max_distance_m: float = Field(ge=0, le=100)
    point_join_note: str = Field(min_length=20)
    heat_weights: HeatWeights
    exposure_weights: ExposureWeights
    vulnerability_weights: VulnerabilityWeights
    opportunity_weights: OpportunityWeights
    priority_weights: PriorityWeights

    @model_validator(mode="after")
    def validate_quantiles(self) -> Self:
        if self.lower_quantile >= self.upper_quantile:
            raise ValueError("lower quantile must be below upper quantile")
        return self


class NormalizedFeature(StrEnum):
    TEMPERATURE = "temperature_c"
    PERSISTENCE = "persistence_hours"
    EXCEEDANCE = "exceedance_hours"
    POPULATION_CONTEXT = "acs_total_population_context"
    PATRONAGE = "published_patronage_activity"
    POI_COUNT = "poi_count"
    TRANSIT_STOP_COUNT = "transit_stop_count"
    CHILDREN_RATE = "children_rate"
    OLDER_ADULT_RATE = "older_adult_rate"
    POVERTY_RATE = "poverty_rate"
    NO_VEHICLE_RATE = "no_vehicle_rate"


class NormalizationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    feature: NormalizedFeature
    lower_quantile: float = Field(ge=0, le=1)
    upper_quantile: float = Field(ge=0, le=1)
    lower_value: float | None = None
    upper_value: float | None = None
    valid_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    constant: bool


class NormalizationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    values: tuple[float | None, ...]
    metadata: NormalizationMetadata


class HeatEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    average_temperature_c: float
    persistence_hours: float = Field(ge=0)
    exceedance_hours: float = Field(ge=0)
    temperature_score: float = Field(ge=0, le=1)
    persistence_score: float = Field(ge=0, le=1)
    exceedance_score: float = Field(ge=0, le=1)


class ExposureEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    transit_stop_ids: tuple[str, ...]
    proximity_joined_transit_stop_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    transit_stop_count: int = Field(ge=0)
    stops_with_published_patronage: int = Field(ge=0)
    stops_missing_published_patronage: int = Field(ge=0)
    published_patronage_activity: float | None = Field(default=None, ge=0)
    poi_ids: tuple[str, ...]
    proximity_joined_poi_ids: tuple[str, ...]
    poi_count: int = Field(ge=0)
    school_count: int = Field(ge=0)
    park_count: int = Field(ge=0)
    library_count: int = Field(ge=0)
    acs_tract_geoids: tuple[str, ...]
    acs_total_population_context: float | None = Field(default=None, ge=0)
    population_context_score: float | None = Field(default=None, ge=0, le=1)
    patronage_score: float | None = Field(default=None, ge=0, le=1)
    poi_score: float = Field(ge=0, le=1)
    transit_stop_score: float = Field(ge=0, le=1)


class VulnerabilityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    children_rate: float | None = Field(default=None, ge=0, le=1)
    older_adult_rate: float | None = Field(default=None, ge=0, le=1)
    poverty_rate: float | None = Field(default=None, ge=0, le=1)
    no_vehicle_rate: float | None = Field(default=None, ge=0, le=1)
    children_score: float | None = Field(default=None, ge=0, le=1)
    older_adult_score: float | None = Field(default=None, ge=0, le=1)
    poverty_score: float | None = Field(default=None, ge=0, le=1)
    no_vehicle_score: float | None = Field(default=None, ge=0, le=1)


class CoolingOpportunityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    public_site_count: int = Field(ge=0)
    transit_stop_count: int = Field(ge=0)
    public_site_score: float = Field(ge=0, le=1)
    transit_stop_score: float = Field(ge=0, le=1)
    evidence_basis: str = Field(min_length=20)


class TileScores(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    heat: float = Field(ge=0, le=1)
    exposure: float = Field(ge=0, le=1)
    vulnerability: float = Field(ge=0, le=1)
    cooling_opportunity: float = Field(ge=0, le=1)
    priority: float = Field(ge=0, le=1)


class TileFeature(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    tile_id: str = Field(min_length=1)
    geometry: PolygonGeometry
    heat: HeatEvidence
    exposure: ExposureEvidence
    vulnerability: VulnerabilityEvidence
    cooling_opportunity: CoolingOpportunityEvidence
    scores: TileScores
    missing_fields: tuple[str, ...]

    @model_validator(mode="after")
    def validate_sorted_unique_references(self) -> Self:
        collections = (
            self.exposure.transit_stop_ids,
            self.exposure.proximity_joined_transit_stop_ids,
            self.exposure.route_ids,
            self.exposure.poi_ids,
            self.exposure.proximity_joined_poi_ids,
            self.exposure.acs_tract_geoids,
            self.missing_fields,
        )
        if any(values != tuple(sorted(set(values))) for values in collections):
            raise ValueError("tile references and missing fields must be sorted and unique")
        return self


class FeatureTableCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tiles: int = Field(gt=0)
    tiles_with_transit: int = Field(ge=0)
    tiles_with_pois: int = Field(ge=0)
    tiles_with_missing_fields: int = Field(ge=0)
    unjoined_transit_stops: int = Field(ge=0)
    unjoined_pois: int = Field(ge=0)
    proximity_joined_transit_stops: int = Field(ge=0)
    proximity_joined_pois: int = Field(ge=0)


class TileFeatureTable(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: str = Field(pattern=r"^1\.0$")
    pilot: str = Field(pattern=r"^Pacoima, Los Angeles$")
    crs: str = Field(pattern=r"^EPSG:4326$")
    generated_at: datetime
    heatmap_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    exceedance_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    public_data_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    scoring_config_sha256: str = Field(pattern=SHA256_PATTERN)
    counts: FeatureTableCounts
    limitations: tuple[str, ...]
    normalization: tuple[NormalizationMetadata, ...]
    tiles: tuple[TileFeature, ...]

    @model_validator(mode="after")
    def validate_integrity(self) -> Self:
        tile_ids = [tile.tile_id for tile in self.tiles]
        if len(tile_ids) != len(set(tile_ids)) or tile_ids != sorted(
            tile_ids, key=lambda value: int(value)
        ):
            raise ValueError("tile IDs must be unique and numerically sorted")
        expected = FeatureTableCounts(
            tiles=len(self.tiles),
            tiles_with_transit=sum(tile.exposure.transit_stop_count > 0 for tile in self.tiles),
            tiles_with_pois=sum(tile.exposure.poi_count > 0 for tile in self.tiles),
            tiles_with_missing_fields=sum(bool(tile.missing_fields) for tile in self.tiles),
            unjoined_transit_stops=self.counts.unjoined_transit_stops,
            unjoined_pois=self.counts.unjoined_pois,
            proximity_joined_transit_stops=sum(
                len(tile.exposure.proximity_joined_transit_stop_ids)
                for tile in self.tiles
            ),
            proximity_joined_pois=sum(
                len(tile.exposure.proximity_joined_poi_ids) for tile in self.tiles
            ),
        )
        if self.counts != expected:
            raise ValueError("feature-table counts do not match its tiles")
        features = [item.feature for item in self.normalization]
        if len(features) != len(set(features)) or set(features) != set(NormalizedFeature):
            raise ValueError("normalization metadata must cover every normalized feature")
        return self


@dataclass(frozen=True)
class RawTile:
    tile_id: str
    geometry: PolygonGeometry
    temperature_c: float
    persistence_hours: float
    exceedance_hours: float
    transit_stop_ids: tuple[str, ...]
    proximity_joined_transit_stop_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    stops_with_patronage: int
    stops_missing_patronage: int
    patronage_activity: float | None
    poi_ids: tuple[str, ...]
    proximity_joined_poi_ids: tuple[str, ...]
    school_count: int
    park_count: int
    library_count: int
    tract_geoids: tuple[str, ...]
    population_context: float | None
    children_rate: float | None
    older_adult_rate: float | None
    poverty_rate: float | None
    no_vehicle_rate: float | None


def _quantile(sorted_values: tuple[float, ...], quantile: float) -> float:
    if not sorted_values:
        raise ValueError("cannot calculate a quantile without values")
    position = (len(sorted_values) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]
    fraction = position - lower_index
    return sorted_values[lower_index] + (
        sorted_values[upper_index] - sorted_values[lower_index]
    ) * fraction


def normalize_values(
    feature: NormalizedFeature,
    values: tuple[float | None, ...],
    *,
    lower_quantile: float,
    upper_quantile: float,
    constant_score: float,
) -> NormalizationOutput:
    """Winsorized min-max normalization that preserves missing values."""

    if not 0 <= lower_quantile < upper_quantile <= 1:
        raise ValueError("normalization quantiles must satisfy 0 <= lower < upper <= 1")
    if not 0 <= constant_score <= 1:
        raise ValueError("constant score must be in [0, 1]")
    present = tuple(value for value in values if value is not None)
    if any(not math.isfinite(value) for value in present):
        raise ValueError("normalization values must be finite")
    if not present:
        return NormalizationOutput(
            values=tuple(None for _ in values),
            metadata=NormalizationMetadata(
                feature=feature,
                lower_quantile=lower_quantile,
                upper_quantile=upper_quantile,
                valid_count=0,
                missing_count=len(values),
                constant=True,
            ),
        )
    sorted_values = tuple(sorted(present))
    lower = _quantile(sorted_values, lower_quantile)
    upper = _quantile(sorted_values, upper_quantile)
    constant = math.isclose(lower, upper, abs_tol=1e-12)
    normalized = tuple(
        None
        if value is None
        else constant_score
        if constant
        else min(1.0, max(0.0, (value - lower) / (upper - lower)))
        for value in values
    )
    return NormalizationOutput(
        values=normalized,
        metadata=NormalizationMetadata(
            feature=feature,
            lower_quantile=lower_quantile,
            upper_quantile=upper_quantile,
            lower_value=lower,
            upper_value=upper,
            valid_count=len(present),
            missing_count=len(values) - len(present),
            constant=constant,
        ),
    )


def weighted_available(values: tuple[tuple[float | None, float], ...]) -> float:
    """Weighted mean that explicitly reweights around missing inputs."""

    available = tuple((value, weight) for value, weight in values if value is not None)
    total_weight = sum(weight for _, weight in available)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in available) / total_weight


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _safe_rate(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _vulnerability_rates(
    estimates: VulnerabilityEstimates,
) -> tuple[float | None, float | None, float | None, float | None]:
    return (
        _safe_rate(estimates.children_under_18, estimates.total_population),
        _safe_rate(estimates.older_adults_65_plus, estimates.total_population),
        _safe_rate(
            estimates.population_below_poverty,
            estimates.poverty_universe_population,
        ),
        _safe_rate(
            estimates.households_without_vehicle,
            estimates.vehicle_availability_households,
        ),
    )


def _area_weighted(values: tuple[tuple[float | int | None, float], ...]) -> float | None:
    available = tuple((float(value), area) for value, area in values if value is not None)
    total_area = sum(area for _, area in available)
    if total_area <= 0:
        return None
    return sum(value * area for value, area in available) / total_area


def published_patronage_activity(stop: ProcessedTransitStop) -> float | None:
    if stop.patronage is None:
        return None
    pairs = (
        (stop.patronage.dx_ons, stop.patronage.dx_offs),
        (stop.patronage.sa_ons, stop.patronage.sa_offs),
        (stop.patronage.su_ons, stop.patronage.su_offs),
    )
    totals = tuple(
        float(ons + offs) for ons, offs in pairs if ons is not None and offs is not None
    )
    return max(totals) if totals else None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_scoring_config(path: Path = DEFAULT_CONFIG_PATH) -> ScoringConfig:
    return ScoringConfig.model_validate_json(path.read_text(encoding="utf-8"))


def _assign_point(
    point: Point,
    projected_point: BaseGeometry,
    tile_shapes: tuple[BaseGeometry, ...],
    projected_tiles: tuple[BaseGeometry, ...],
    maximum_distance_m: float,
) -> tuple[int | None, bool]:
    matches = [index for index, tile in enumerate(tile_shapes) if tile.covers(point)]
    if matches:
        return min(matches), False
    distance, index = min(
        (tile.distance(projected_point), tile_index)
        for tile_index, tile in enumerate(projected_tiles)
    )
    return (index, True) if distance <= maximum_distance_m else (None, False)


def _build_raw_tiles(
    heatmaps: PacoimaHeatmapArtifact,
    exceedance: PacoimaExceedanceArtifact,
    public: ProcessedPublicData,
    config: ScoringConfig,
) -> tuple[tuple[RawTile, ...], int, int]:
    layers = {layer.analytic_type: layer for layer in heatmaps.layers}
    tcm_features = layers["tcm"].result.map_data.features
    persistence_features = layers["persistence"].result.map_data.features
    exceedance_features = exceedance.layer.result.map_data.features
    tile_shapes = tuple(shape(feature.geometry.model_dump()) for feature in tcm_features)
    projector = Transformer.from_crs("EPSG:4326", "EPSG:32611", always_xy=True).transform
    projected_tiles = tuple(transform(projector, tile) for tile in tile_shapes)

    stops_by_tile: list[list[ProcessedTransitStop]] = [[] for _ in tile_shapes]
    proximity_stop_ids_by_tile: list[list[str]] = [[] for _ in tile_shapes]
    unjoined_stops = 0
    for stop in public.transit_stops:
        coordinates = stop.geometry.coordinates
        point = Point(coordinates[0], coordinates[1])
        index, proximity_joined = _assign_point(
            point,
            transform(projector, point),
            tile_shapes,
            projected_tiles,
            config.point_join_max_distance_m,
        )
        if index is None:
            unjoined_stops += 1
        else:
            stops_by_tile[index].append(stop)
            if proximity_joined:
                proximity_stop_ids_by_tile[index].append(stop.id)

    pois_by_tile: list[list[tuple[str, str]]] = [[] for _ in tile_shapes]
    proximity_poi_ids_by_tile: list[list[str]] = [[] for _ in tile_shapes]
    unjoined_pois = 0
    for poi in public.pois:
        poi_shape = shape(poi.geometry.model_dump())
        joined_indexes: tuple[int, ...]
        if isinstance(poi_shape, Point):
            index, proximity_joined = _assign_point(
                poi_shape,
                transform(projector, poi_shape),
                tile_shapes,
                projected_tiles,
                config.point_join_max_distance_m,
            )
            joined_indexes = () if index is None else (index,)
            if index is not None and proximity_joined:
                proximity_poi_ids_by_tile[index].append(poi.id)
        else:
            projected_poi = transform(projector, poi_shape)
            joined_indexes = tuple(
                index
                for index, tile in enumerate(projected_tiles)
                if tile.intersection(projected_poi).area > 0
            )
        if not joined_indexes:
            unjoined_pois += 1
        for index in joined_indexes:
            pois_by_tile[index].append((poi.id, poi.kind))

    tract_shapes = tuple(
        shape(tract.geometry.model_dump()) for tract in public.vulnerability_tracts
    )
    projected_tracts = tuple(transform(projector, tract) for tract in tract_shapes)
    raw_tiles: list[RawTile] = []
    for index, (tcm, persistence, exceedance_feature) in enumerate(
        zip(tcm_features, persistence_features, exceedance_features, strict=True)
    ):
        if (
            tcm.id is None
            or persistence.id != tcm.id
            or exceedance_feature.id != tcm.id
            or exceedance_feature.geometry != tcm.geometry
        ):
            raise ValueError("heatmap tile IDs are missing or misaligned")
        tile_id = str(tcm.id)
        tcm_property_id = str(tcm.properties.get("tile_id"))
        persistence_property_id = str(persistence.properties.get("tile_id"))
        exceedance_property_id = str(exceedance_feature.properties.get("tile_id"))
        if (
            tile_id != tcm_property_id
            or tile_id != persistence_property_id
            or tile_id != exceedance_property_id
        ):
            raise ValueError("heatmap feature and property tile IDs do not match")

        stops = tuple(sorted(stops_by_tile[index], key=lambda stop: stop.id))
        activities = tuple(published_patronage_activity(stop) for stop in stops)
        present_activities = tuple(value for value in activities if value is not None)
        patronage_activity = (
            sum(present_activities) if present_activities else 0.0 if not stops else None
        )
        poi_refs = tuple(sorted(pois_by_tile[index]))

        overlaps: list[tuple[int, float]] = []
        for tract_index, tract in enumerate(projected_tracts):
            area = projected_tiles[index].intersection(tract).area
            if area > 0:
                overlaps.append((tract_index, area))
        tract_geoids = tuple(
            public.vulnerability_tracts[tract_index].geoid
            for tract_index, _ in overlaps
        )
        estimates_and_areas = tuple(
            (public.vulnerability_tracts[tract_index].estimates, area)
            for tract_index, area in overlaps
        )
        rate_rows = tuple(
            (_vulnerability_rates(estimates), area)
            for estimates, area in estimates_and_areas
        )

        raw_tiles.append(
            RawTile(
                tile_id=tile_id,
                geometry=tcm.geometry,
                temperature_c=_number(
                    tcm.properties.get("average_temperature"),
                    "average_temperature",
                ),
                persistence_hours=_number(
                    persistence.properties.get("value"), "persistence value"
                ),
                exceedance_hours=_number(
                    exceedance_feature.properties.get("value"), "exceedance value"
                ),
                transit_stop_ids=tuple(stop.id for stop in stops),
                proximity_joined_transit_stop_ids=tuple(
                    sorted(proximity_stop_ids_by_tile[index])
                ),
                route_ids=tuple(sorted({route for stop in stops for route in stop.route_ids})),
                stops_with_patronage=len(present_activities),
                stops_missing_patronage=len(stops) - len(present_activities),
                patronage_activity=patronage_activity,
                poi_ids=tuple(poi_id for poi_id, _ in poi_refs),
                proximity_joined_poi_ids=tuple(
                    sorted(proximity_poi_ids_by_tile[index])
                ),
                school_count=sum(kind == "school" for _, kind in poi_refs),
                park_count=sum(kind == "park" for _, kind in poi_refs),
                library_count=sum(kind == "library" for _, kind in poi_refs),
                tract_geoids=tuple(sorted(tract_geoids)),
                population_context=_area_weighted(
                    tuple(
                        (estimates.total_population, area)
                        for estimates, area in estimates_and_areas
                    )
                ),
                children_rate=_area_weighted(
                    tuple((rates[0], area) for rates, area in rate_rows)
                ),
                older_adult_rate=_area_weighted(
                    tuple((rates[1], area) for rates, area in rate_rows)
                ),
                poverty_rate=_area_weighted(
                    tuple((rates[2], area) for rates, area in rate_rows)
                ),
                no_vehicle_rate=_area_weighted(
                    tuple((rates[3], area) for rates, area in rate_rows)
                ),
            )
        )
    return tuple(raw_tiles), unjoined_stops, unjoined_pois


def _normalize_raw(
    raw_tiles: tuple[RawTile, ...], config: ScoringConfig
) -> dict[NormalizedFeature, NormalizationOutput]:
    values: dict[NormalizedFeature, tuple[float | None, ...]] = {
        NormalizedFeature.TEMPERATURE: tuple(tile.temperature_c for tile in raw_tiles),
        NormalizedFeature.PERSISTENCE: tuple(tile.persistence_hours for tile in raw_tiles),
        NormalizedFeature.EXCEEDANCE: tuple(tile.exceedance_hours for tile in raw_tiles),
        NormalizedFeature.POPULATION_CONTEXT: tuple(
            tile.population_context for tile in raw_tiles
        ),
        NormalizedFeature.PATRONAGE: tuple(tile.patronage_activity for tile in raw_tiles),
        NormalizedFeature.POI_COUNT: tuple(float(len(tile.poi_ids)) for tile in raw_tiles),
        NormalizedFeature.TRANSIT_STOP_COUNT: tuple(
            float(len(tile.transit_stop_ids)) for tile in raw_tiles
        ),
        NormalizedFeature.CHILDREN_RATE: tuple(tile.children_rate for tile in raw_tiles),
        NormalizedFeature.OLDER_ADULT_RATE: tuple(
            tile.older_adult_rate for tile in raw_tiles
        ),
        NormalizedFeature.POVERTY_RATE: tuple(tile.poverty_rate for tile in raw_tiles),
        NormalizedFeature.NO_VEHICLE_RATE: tuple(
            tile.no_vehicle_rate for tile in raw_tiles
        ),
    }
    return {
        feature: normalize_values(
            feature,
            feature_values,
            lower_quantile=config.lower_quantile,
            upper_quantile=config.upper_quantile,
            constant_score=config.constant_feature_score,
        )
        for feature, feature_values in values.items()
    }


def _required_score(value: float | None, feature: NormalizedFeature) -> float:
    if value is None:
        raise ValueError(f"required normalized feature {feature.value} is missing")
    return value


def build_feature_table(
    *,
    heatmap_path: Path = DEFAULT_HEATMAP_PATH,
    exceedance_path: Path = DEFAULT_EXCEEDANCE_PATH,
    public_data_path: Path = DEFAULT_PUBLIC_DATA_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> TileFeatureTable:
    heatmaps = load_heatmap_artifact(heatmap_path)
    exceedance = load_exceedance_artifact(exceedance_path)
    public = load_processed_fixture(public_data_path)
    config = load_scoring_config(config_path)
    raw_tiles, unjoined_stops, unjoined_pois = _build_raw_tiles(
        heatmaps, exceedance, public, config
    )
    normalized = _normalize_raw(raw_tiles, config)

    tiles: list[TileFeature] = []
    for index, raw in enumerate(raw_tiles):
        score = {
            feature: output.values[index] for feature, output in normalized.items()
        }
        temperature_score = _required_score(
            score[NormalizedFeature.TEMPERATURE], NormalizedFeature.TEMPERATURE
        )
        persistence_score = _required_score(
            score[NormalizedFeature.PERSISTENCE], NormalizedFeature.PERSISTENCE
        )
        exceedance_score = _required_score(
            score[NormalizedFeature.EXCEEDANCE], NormalizedFeature.EXCEEDANCE
        )
        poi_score = _required_score(score[NormalizedFeature.POI_COUNT], NormalizedFeature.POI_COUNT)
        transit_score = _required_score(
            score[NormalizedFeature.TRANSIT_STOP_COUNT],
            NormalizedFeature.TRANSIT_STOP_COUNT,
        )
        heat_score = weighted_available(
            (
                (temperature_score, config.heat_weights.temperature),
                (persistence_score, config.heat_weights.persistence),
                (exceedance_score, config.heat_weights.exceedance),
            )
        )
        exposure_score = weighted_available(
            (
                (
                    score[NormalizedFeature.POPULATION_CONTEXT],
                    config.exposure_weights.population_context,
                ),
                (
                    score[NormalizedFeature.PATRONAGE],
                    config.exposure_weights.published_patronage,
                ),
                (poi_score, config.exposure_weights.poi_count),
                (transit_score, config.exposure_weights.transit_stop_count),
            )
        )
        vulnerability_score = weighted_available(
            (
                (
                    score[NormalizedFeature.CHILDREN_RATE],
                    config.vulnerability_weights.children,
                ),
                (
                    score[NormalizedFeature.OLDER_ADULT_RATE],
                    config.vulnerability_weights.older_adults,
                ),
                (
                    score[NormalizedFeature.POVERTY_RATE],
                    config.vulnerability_weights.poverty,
                ),
                (
                    score[NormalizedFeature.NO_VEHICLE_RATE],
                    config.vulnerability_weights.no_vehicle,
                ),
            )
        )
        opportunity_score = weighted_available(
            (
                (poi_score, config.opportunity_weights.public_site),
                (transit_score, config.opportunity_weights.transit_stop),
            )
        )
        priority_score = weighted_available(
            (
                (heat_score, config.priority_weights.heat),
                (exposure_score, config.priority_weights.exposure),
                (vulnerability_score, config.priority_weights.vulnerability),
                (opportunity_score, config.priority_weights.cooling_opportunity),
            )
        )
        missing_fields = tuple(
            sorted(
                feature.value
                for feature in (
                    NormalizedFeature.POPULATION_CONTEXT,
                    NormalizedFeature.PATRONAGE,
                    NormalizedFeature.CHILDREN_RATE,
                    NormalizedFeature.OLDER_ADULT_RATE,
                    NormalizedFeature.POVERTY_RATE,
                    NormalizedFeature.NO_VEHICLE_RATE,
                )
                if score[feature] is None
            )
        )
        tiles.append(
            TileFeature(
                tile_id=raw.tile_id,
                geometry=raw.geometry,
                heat=HeatEvidence(
                    average_temperature_c=raw.temperature_c,
                    persistence_hours=raw.persistence_hours,
                    exceedance_hours=raw.exceedance_hours,
                    temperature_score=temperature_score,
                    persistence_score=persistence_score,
                    exceedance_score=exceedance_score,
                ),
                exposure=ExposureEvidence(
                    transit_stop_ids=raw.transit_stop_ids,
                    proximity_joined_transit_stop_ids=(
                        raw.proximity_joined_transit_stop_ids
                    ),
                    route_ids=raw.route_ids,
                    transit_stop_count=len(raw.transit_stop_ids),
                    stops_with_published_patronage=raw.stops_with_patronage,
                    stops_missing_published_patronage=raw.stops_missing_patronage,
                    published_patronage_activity=raw.patronage_activity,
                    poi_ids=raw.poi_ids,
                    proximity_joined_poi_ids=raw.proximity_joined_poi_ids,
                    poi_count=len(raw.poi_ids),
                    school_count=raw.school_count,
                    park_count=raw.park_count,
                    library_count=raw.library_count,
                    acs_tract_geoids=raw.tract_geoids,
                    acs_total_population_context=raw.population_context,
                    population_context_score=score[NormalizedFeature.POPULATION_CONTEXT],
                    patronage_score=score[NormalizedFeature.PATRONAGE],
                    poi_score=poi_score,
                    transit_stop_score=transit_score,
                ),
                vulnerability=VulnerabilityEvidence(
                    children_rate=raw.children_rate,
                    older_adult_rate=raw.older_adult_rate,
                    poverty_rate=raw.poverty_rate,
                    no_vehicle_rate=raw.no_vehicle_rate,
                    children_score=score[NormalizedFeature.CHILDREN_RATE],
                    older_adult_score=score[NormalizedFeature.OLDER_ADULT_RATE],
                    poverty_score=score[NormalizedFeature.POVERTY_RATE],
                    no_vehicle_score=score[NormalizedFeature.NO_VEHICLE_RATE],
                ),
                cooling_opportunity=CoolingOpportunityEvidence(
                    public_site_count=len(raw.poi_ids),
                    transit_stop_count=len(raw.transit_stop_ids),
                    public_site_score=poi_score,
                    transit_stop_score=transit_score,
                    evidence_basis=config.cooling_opportunity_note,
                ),
                scores=TileScores(
                    heat=heat_score,
                    exposure=exposure_score,
                    vulnerability=vulnerability_score,
                    cooling_opportunity=opportunity_score,
                    priority=priority_score,
                ),
                missing_fields=missing_fields,
            )
        )

    ordered_tiles = tuple(sorted(tiles, key=lambda tile: int(tile.tile_id)))
    return TileFeatureTable(
        version="1.0",
        pilot="Pacoima, Los Angeles",
        crs="EPSG:4326",
        generated_at=heatmaps.generated_at,
        heatmap_artifact_sha256=_sha256(heatmap_path),
        exceedance_artifact_sha256=_sha256(exceedance_path),
        public_data_artifact_sha256=_sha256(public_data_path),
        scoring_config_sha256=_sha256(config_path),
        counts=FeatureTableCounts(
            tiles=len(ordered_tiles),
            tiles_with_transit=sum(
                tile.exposure.transit_stop_count > 0 for tile in ordered_tiles
            ),
            tiles_with_pois=sum(tile.exposure.poi_count > 0 for tile in ordered_tiles),
            tiles_with_missing_fields=sum(bool(tile.missing_fields) for tile in ordered_tiles),
            unjoined_transit_stops=unjoined_stops,
            unjoined_pois=unjoined_pois,
            proximity_joined_transit_stops=sum(
                len(tile.exposure.proximity_joined_transit_stop_ids)
                for tile in ordered_tiles
            ),
            proximity_joined_pois=sum(
                len(tile.exposure.proximity_joined_poi_ids) for tile in ordered_tiles
            ),
        ),
        limitations=(
            *public.limitations,
            config.population_context_note,
            config.patronage_metric,
            config.cooling_opportunity_note,
            config.point_join_note,
            "Exceedance hours are normalized from the frozen 2024-07-15 layer; the active TCM "
            "and persistence layers are dated 2026-08-20. The weighted heat score therefore uses "
            "exceedance as historical context, not as a contemporaneous observation.",
            "Scores are relative modeled priorities normalized within this frozen Pacoima dataset; "
            "they are not measured cooling effects or predictions of people protected.",
        ),
        normalization=tuple(normalized[feature].metadata for feature in NormalizedFeature),
        tiles=ordered_tiles,
    )


def canonical_feature_table_bytes(document: TileFeatureTable) -> bytes:
    return (json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()


def load_feature_table(path: Path = DEFAULT_FEATURE_TABLE_PATH) -> TileFeatureTable:
    return TileFeatureTable.model_validate_json(path.read_text(encoding="utf-8"))
