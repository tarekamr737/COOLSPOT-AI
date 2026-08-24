"""Deterministic candidates from real Pacoima sites and versioned assumptions."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from shapely.geometry import mapping, shape

from api.app.services.environmental_evidence import (
    DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH,
    FinalistEnvironmentalEvidence,
    load_environmental_evidence,
)
from api.app.services.feature_table import (
    DEFAULT_FEATURE_TABLE_PATH,
    TileFeature,
    load_feature_table,
    published_patronage_activity,
)
from api.app.services.intervention_value import InterventionValueFactors, UnitInterval
from api.app.services.interventions import (
    DEFAULT_INTERVENTION_CATALOG_PATH,
    InterventionDefinition,
    InterventionType,
    SiteType,
    load_intervention_catalog,
)
from api.app.services.processed_data import (
    FixtureGeometry,
    ProcessedPoi,
    ProcessedTransitStop,
    load_processed_fixture,
)
from api.app.services.roadway_geometry import (
    DEFAULT_AOI_PATH,
    DEFAULT_PAVEMENT_PATH,
    PavementConditionFeature,
    load_pavement_conditions,
)
from api.app.services.satellite_evidence import (
    DEFAULT_SATELLITE_EVIDENCE_PATH,
    SatelliteSurfaceEvidence,
    load_satellite_evidence,
)
from api.app.services.streetview_evidence import (
    DEFAULT_STREETVIEW_EVIDENCE_PATH,
    ExtractedStreetViewFeatures,
    load_street_view_evidence_artifact,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_DATA_PATH = ROOT / "data" / "processed" / "pacoima_public_data.json"
DEFAULT_CANDIDATE_CONFIG_PATH = ROOT / "config" / "candidates.json"
DEFAULT_CANDIDATES_PATH = ROOT / "data" / "processed" / "pacoima_candidates.json"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
FIXTURE_GEOMETRY_ADAPTER: TypeAdapter[FixtureGeometry] = TypeAdapter(FixtureGeometry)


class CandidateSourceArtifact(StrEnum):
    FEATURE_TABLE = "pacoima_tile_feature_table"
    PUBLIC_DATA = "pacoima_public_data"
    INTERVENTION_CATALOG = "intervention_catalog"
    CANDIDATE_CONFIG = "candidate_config"
    STREET_VIEW_EVIDENCE = "pacoima_streetview_evidence"
    ENVIRONMENTAL_EVIDENCE = "pacoima_environmental_evidence"
    PAVEMENT_CONDITION = "pacoima_pavement_condition"
    SATELLITE_EVIDENCE = "pacoima_satellite_evidence"


class EvidenceKind(StrEnum):
    OBSERVED_HEAT = "observed_heat"
    EXPOSURE = "exposure"
    VULNERABILITY = "vulnerability"
    APPLICABILITY = "applicability"
    PLANNING_ASSUMPTION = "planning_assumption"
    STREET_CONTEXT = "street_context"
    PAVEMENT = "pavement"
    SATELLITE_SURFACE = "satellite_surface"


class TileSelection(StrEnum):
    CONTAINING_TILE = "containing_tile"
    HIGHEST_PRIORITY_INTERSECTING_TILE = "highest_priority_intersecting_tile"


class CandidateConfidenceRules(BaseModel):
    """Versioned mapping from evidence availability to candidate confidence."""

    model_config = ConfigDict(extra="forbid")

    exact_street_view_match: Literal["use_street_context_confidence"]
    unmatched_site: Literal["use_unverified_confidence_score"]
    note: str = Field(min_length=80)


class CandidateSuitabilityRules(BaseModel):
    """Versioned mapping from intervention evidence to suitability."""

    model_config = ConfigDict(extra="forbid")

    exact_shade_street_view: Literal["mean_available_open_sky_and_low_tree_context"]
    exact_tree_street_view: Literal["use_low_tree_context"]
    unmatched_site: Literal["use_unverified_suitability_score"]
    note: str = Field(min_length=120)


class CoolPavementCandidateRules(BaseModel):
    """Versioned eligibility and bounded candidate-volume rules."""

    model_config = ConfigDict(extra="forbid")

    max_candidates: int = Field(gt=0, le=100)
    eligibility: Literal["require_bss_pavement_geometry_surface_width_and_pci"]
    verified_geometry_suitability_score: UnitInterval
    selection: Literal["one_longest_segment_per_priority_tile"]
    note: str = Field(min_length=120)


class CandidateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: str = Field(pattern=r"^1\.0$")
    unverified_feasibility_score: float = Field(ge=0, le=1)
    unverified_confidence_score: float = Field(ge=0, le=1)
    unverified_suitability_score: UnitInterval
    confidence_rules: CandidateConfidenceRules
    suitability_rules: CandidateSuitabilityRules
    cool_pavement_rules: CoolPavementCandidateRules
    benefit_score_basis: str = Field(min_length=30)
    equity_score_basis: str = Field(min_length=30)
    screening_score_note: str = Field(min_length=50)
    representative_tile_rule: str = Field(min_length=50)


class SourceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: CandidateSourceArtifact
    path: str = Field(pattern=r"^(config|data)/.+\.(json|geojson)$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class CandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    statement: str = Field(min_length=20)
    source_artifact_ids: tuple[CandidateSourceArtifact, ...] = Field(min_length=1)


class CandidateValueExplanation(BaseModel):
    """Auditable factors behind one intervention's modeled benefit."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    formula: Literal[
        "priority_score × suitability_score × feasibility_score × confidence_score"
    ]
    factors: InterventionValueFactors
    modeled_benefit_score: UnitInterval
    suitability_basis: tuple[str, ...] = Field(min_length=1)
    limitation: str = Field(min_length=60)

    @model_validator(mode="after")
    def validate_product(self) -> Self:
        if not math.isclose(
            self.modeled_benefit_score,
            self.factors.modeled_benefit(),
            abs_tol=1e-12,
        ):
            raise ValueError("modeled benefit must equal the four-factor product")
        return self


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str = Field(pattern=r"^(shade_structure|tree_canopy|cool_pavement):.+$")
    site_id: str = Field(min_length=1)
    site_name: str = Field(min_length=1)
    site_type: SiteType
    site_source_ids: tuple[str, ...] = Field(min_length=1)
    tile_id: str = Field(min_length=1)
    intersecting_tile_count: int = Field(gt=0)
    tile_selection: TileSelection
    intervention_type: InterventionType
    planning_cost_usd: int = Field(gt=0)
    benefit_score: UnitInterval
    suitability_score: UnitInterval
    equity_score: UnitInterval
    feasibility_score: UnitInterval
    confidence: UnitInterval
    value_explanation: CandidateValueExplanation
    thermal_stress_context: FinalistEnvironmentalEvidence | None = None
    satellite_surface_context: SatelliteSurfaceEvidence | None = None
    evidence: tuple[CandidateEvidence, ...] = Field(min_length=5)
    geometry: FixtureGeometry

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.id != f"{self.intervention_type.value}:{self.site_id}":
            raise ValueError("candidate ID must combine intervention type and site ID")
        if len(self.site_source_ids) != len(set(self.site_source_ids)):
            raise ValueError("candidate site source IDs must be unique")
        factors = self.value_explanation.factors
        if not (
            factors.priority_score == self.benefit_score
            and factors.suitability_score == self.suitability_score
            and factors.feasibility_score == self.feasibility_score
            and factors.confidence_score == self.confidence
        ):
            raise ValueError("candidate scores must match the value explanation factors")
        return self


class CandidateCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=20)
    unique_sites: int = Field(ge=20)
    shade_structure: int = Field(ge=0)
    tree_canopy: int = Field(ge=0)
    cool_pavement: int = Field(ge=0)


class CandidateArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: str = Field(pattern=r"^1\.0$")
    pilot: str = Field(pattern=r"^Pacoima, Los Angeles$")
    crs: str = Field(pattern=r"^EPSG:4326$")
    generated_at: datetime
    source_artifacts: tuple[SourceArtifact, ...]
    counts: CandidateCounts
    scoring_notes: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    candidates: tuple[Candidate, ...] = Field(min_length=20)

    @model_validator(mode="after")
    def validate_integrity(self) -> Self:
        source_ids = [source.id for source in self.source_artifacts]
        required_sources = set(CandidateSourceArtifact) - {
            CandidateSourceArtifact.SATELLITE_EVIDENCE
        }
        if len(source_ids) != len(set(source_ids)) or not required_sources <= set(
            source_ids
        ):
            raise ValueError("candidate artifact must reference each required source once")

        candidate_ids = [candidate.id for candidate in self.candidates]
        if candidate_ids != sorted(candidate_ids) or len(candidate_ids) != len(
            set(candidate_ids)
        ):
            raise ValueError("candidate IDs must be unique and sorted")

        known_sources = set(source_ids)
        for candidate in self.candidates:
            for evidence in candidate.evidence:
                if not set(evidence.source_artifact_ids) <= known_sources:
                    raise ValueError("candidate evidence references an unknown source artifact")

        expected_counts = CandidateCounts(
            total=len(self.candidates),
            unique_sites=len({candidate.site_id for candidate in self.candidates}),
            shade_structure=sum(
                candidate.intervention_type == InterventionType.SHADE_STRUCTURE
                for candidate in self.candidates
            ),
            tree_canopy=sum(
                candidate.intervention_type == InterventionType.TREE_CANOPY
                for candidate in self.candidates
            ),
            cool_pavement=sum(
                candidate.intervention_type == InterventionType.COOL_PAVEMENT
                for candidate in self.candidates
            ),
        )
        if self.counts != expected_counts:
            raise ValueError("candidate counts do not match candidate records")
        return self


def load_candidate_config(
    path: Path = DEFAULT_CANDIDATE_CONFIG_PATH,
) -> CandidateConfig:
    return CandidateConfig.model_validate_json(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _select_tile(tiles: tuple[TileFeature, ...]) -> TileFeature:
    if not tiles:
        raise ValueError("candidate site has no intersecting heat tile")
    return sorted(
        tiles,
        key=lambda tile: (-tile.scores.priority, -tile.scores.heat, int(tile.tile_id)),
    )[0]


def _site_sources(stop: ProcessedTransitStop) -> tuple[str, ...]:
    sources: list[str] = []
    if stop.in_current_gtfs:
        sources.append("la_metro_gtfs_bus")
    if stop.patronage is not None:
        sources.append("la_metro_bus_patronage_2024")
    if not sources:
        raise ValueError(f"transit stop {stop.id} has no authoritative source")
    return tuple(sources)


def _common_evidence(
    *,
    tile: TileFeature,
    intervention: InterventionDefinition,
    site_statement: str,
    config: CandidateConfig,
    street_context: ExtractedStreetViewFeatures | None,
    site_evidence_kind: EvidenceKind = EvidenceKind.EXPOSURE,
    site_source_artifact_ids: tuple[CandidateSourceArtifact, ...] = (
        CandidateSourceArtifact.PUBLIC_DATA,
        CandidateSourceArtifact.FEATURE_TABLE,
    ),
    uses_street_context: bool = True,
) -> tuple[CandidateEvidence, ...]:
    evidence = [
        CandidateEvidence(
            kind=EvidenceKind.OBSERVED_HEAT,
            statement=(
                f"FortyGuard tile {tile.tile_id} reports {tile.heat.average_temperature_c:.2f} "
                f"°C average temperature and {tile.heat.persistence_hours:g} persistence hours "
                f"for the active analysis, plus {tile.heat.exceedance_hours:g} historical "
                "exceedance hours; its threshold and source dates are disclosed in methodology. "
                f"Peak temperature occurred around {tile.heat.peak_heat_hour_utc:02d}:00 UTC in "
                "the historical heatmap; this timing is explanation-only and is not used in "
                "scoring or pedestrian-activity inference."
            ),
            source_artifact_ids=(CandidateSourceArtifact.FEATURE_TABLE,),
        ),
        CandidateEvidence(
            kind=site_evidence_kind,
            statement=site_statement,
            source_artifact_ids=site_source_artifact_ids,
        ),
        CandidateEvidence(
            kind=EvidenceKind.VULNERABILITY,
            statement=(
                f"The selected tile has modeled vulnerability score "
                f"{tile.scores.vulnerability:.4f}; ACS values are tract context and not a site "
                "population count."
            ),
            source_artifact_ids=(CandidateSourceArtifact.FEATURE_TABLE,),
        ),
        CandidateEvidence(
            kind=EvidenceKind.APPLICABILITY,
            statement=(
                f"The site type passes the {intervention.label} data-level screening rule. "
                f"{intervention.applicability.screening_rule}"
            ),
            source_artifact_ids=(CandidateSourceArtifact.INTERVENTION_CATALOG,),
        ),
        CandidateEvidence(
            kind=EvidenceKind.PLANNING_ASSUMPTION,
            statement=(
                f"Planning cost is ${intervention.planning_cost.estimate_usd:,} per "
                f"{intervention.planning_cost.unit}; feasibility remains at the unverified "
                f"screening scalar {config.unverified_feasibility_score:.1f}."
            ),
            source_artifact_ids=(
                CandidateSourceArtifact.INTERVENTION_CATALOG,
                CandidateSourceArtifact.CANDIDATE_CONFIG,
            ),
        ),
    ]
    if uses_street_context and street_context is not None:
        confidence = street_context.street_context_confidence
        components = confidence.components
        image_dates = ", ".join(
            sorted({frame.image_date.isoformat() for frame in street_context.frames})
        )
        evidence.append(
            CandidateEvidence(
                kind=EvidenceKind.STREET_CONTEXT,
                statement=(
                    f"Cached dated Street View segmentation provides context confidence "
                    f"{confidence.score:.3f} from {confidence.usable_view_count} usable view "
                    f"dated {image_dates}; component scores are usable views "
                    f"{components.usable_views:.3f}, imagery availability "
                    f"{components.imagery_availability:.3f}, imagery age "
                    f"{components.imagery_age:.3f}, and segmentation completeness "
                    f"{components.segmentation_completeness:.3f}. "
                    f"{street_context.shade_intervention_evidence.limitation}"
                ),
                source_artifact_ids=(CandidateSourceArtifact.STREET_VIEW_EVIDENCE,),
            )
        )
    elif uses_street_context:
        evidence.append(
            CandidateEvidence(
                kind=EvidenceKind.PLANNING_ASSUMPTION,
                statement=(
                    f"No normalized Street View evidence is cached for this site, so confidence "
                    f"remains at the neutral unverified scalar "
                    f"{config.unverified_confidence_score:.1f}."
                ),
                source_artifact_ids=(CandidateSourceArtifact.CANDIDATE_CONFIG,),
            )
        )
    else:
        evidence.append(
            CandidateEvidence(
                kind=EvidenceKind.PAVEMENT,
                statement=(
                    "The official pavement segment establishes direct mapped pavement context, "
                    "but confidence remains at the neutral unverified scalar 0.5 until current "
                    "surface condition and project feasibility are field-checked."
                ),
                source_artifact_ids=(CandidateSourceArtifact.PAVEMENT_CONDITION,),
            )
        )
    return tuple(evidence)


def _candidate(
    *,
    site_id: str,
    site_name: str,
    site_type: SiteType,
    site_source_ids: tuple[str, ...],
    geometry: FixtureGeometry,
    tiles: tuple[TileFeature, ...],
    intervention: InterventionDefinition,
    site_statement: str,
    config: CandidateConfig,
    street_context: ExtractedStreetViewFeatures | None,
    thermal_stress_context: FinalistEnvironmentalEvidence | None,
    satellite_surface_context: SatelliteSurfaceEvidence | None = None,
    suitability_override: tuple[float, tuple[str, ...]] | None = None,
    confidence_override: float | None = None,
    site_evidence_kind: EvidenceKind = EvidenceKind.EXPOSURE,
    site_source_artifact_ids: tuple[CandidateSourceArtifact, ...] = (
        CandidateSourceArtifact.PUBLIC_DATA,
        CandidateSourceArtifact.FEATURE_TABLE,
    ),
    uses_street_context: bool = True,
) -> Candidate:
    if site_type not in intervention.applicability.eligible_site_types:
        raise ValueError(
            f"{intervention.id.value} is incompatible with site type {site_type.value}"
        )
    selected_tile = _select_tile(tiles)
    selection = (
        TileSelection.CONTAINING_TILE
        if len(tiles) == 1
        else TileSelection.HIGHEST_PRIORITY_INTERSECTING_TILE
    )
    confidence = (
        _candidate_confidence(config, street_context)
        if confidence_override is None
        else confidence_override
    )
    suitability, suitability_basis = suitability_override or _candidate_suitability(
        intervention.id, config, street_context
    )
    factors = InterventionValueFactors(
        priority_score=selected_tile.scores.priority,
        suitability_score=suitability,
        feasibility_score=config.unverified_feasibility_score,
        confidence_score=confidence,
    )
    evidence = list(
        _common_evidence(
            tile=selected_tile,
            intervention=intervention,
            site_statement=site_statement,
            config=config,
            street_context=street_context,
            site_evidence_kind=site_evidence_kind,
            site_source_artifact_ids=site_source_artifact_ids,
            uses_street_context=uses_street_context,
        )
    )
    if satellite_surface_context is not None:
        surface = satellite_surface_context.surface_class_coverage
        evidence.append(
            CandidateEvidence(
                kind=EvidenceKind.SATELLITE_SURFACE,
                statement=(
                    f"The exact finalist's {satellite_surface_context.image_year} FortyGuard "
                    f"satellite segmentation reports {surface.road_route_percent:.2f}% road, "
                    f"route and {surface.sidewalk_pavement_percent:.2f}% sidewalk, pavement "
                    f"class coverage ({surface.combined_surface_class_percent:.2f}% combined). "
                    f"{satellite_surface_context.limitation}"
                ),
                source_artifact_ids=(CandidateSourceArtifact.SATELLITE_EVIDENCE,),
            )
        )
    return Candidate(
        id=f"{intervention.id.value}:{site_id}",
        site_id=site_id,
        site_name=site_name,
        site_type=site_type,
        site_source_ids=site_source_ids,
        tile_id=selected_tile.tile_id,
        intersecting_tile_count=len(tiles),
        tile_selection=selection,
        intervention_type=intervention.id,
        planning_cost_usd=intervention.planning_cost.estimate_usd,
        benefit_score=selected_tile.scores.priority,
        suitability_score=suitability,
        equity_score=selected_tile.scores.vulnerability,
        feasibility_score=config.unverified_feasibility_score,
        confidence=confidence,
        value_explanation=CandidateValueExplanation(
            formula=(
                "priority_score × suitability_score × feasibility_score × confidence_score"
            ),
            factors=factors,
            modeled_benefit_score=factors.modeled_benefit(),
            suitability_basis=suitability_basis,
            limitation=(
                "This is a relative screening product, not a measured cooling effect, "
                "construction-feasibility finding, or guaranteed outcome."
            ),
        ),
        thermal_stress_context=thermal_stress_context,
        satellite_surface_context=satellite_surface_context,
        evidence=tuple(evidence),
        geometry=geometry,
    )


def _candidate_suitability(
    intervention_type: InterventionType,
    config: CandidateConfig,
    street_context: ExtractedStreetViewFeatures | None,
) -> tuple[float, tuple[str, ...]]:
    """Derive intervention fit only from exact-site normalized evidence."""

    fallback = config.unverified_suitability_score
    if street_context is None:
        return fallback, (
            f"No exact-site Street View evidence; neutral suitability {fallback:.3f} applies.",
        )

    shade = street_context.shade_intervention_evidence
    if intervention_type == InterventionType.SHADE_STRUCTURE:
        contexts = tuple(
            value
            for value in (shade.open_sky_context, shade.low_tree_context)
            if value is not None
        )
        if not contexts:
            return fallback, (
                f"Exact-site segmentation lacks sky/tree values; neutral suitability "
                f"{fallback:.3f} applies.",
            )
        score = math.fsum(contexts) / len(contexts)
        return score, (
            f"Exact-site open-sky context: {shade.open_sky_context!s}.",
            f"Exact-site low-tree context: {shade.low_tree_context!s}.",
            "Suitability is the equal mean of available normalized contexts; confidence is "
            "applied separately.",
        )

    if intervention_type == InterventionType.TREE_CANOPY:
        if shade.low_tree_context is None:
            return fallback, (
                f"Exact-site segmentation lacks tree context; neutral suitability "
                f"{fallback:.3f} applies.",
            )
        return shade.low_tree_context, (
            f"Exact-site low-tree context: {shade.low_tree_context:.3f}.",
            "The mapped school/park already passed catalog compatibility; planting space, soil, "
            "utilities, ownership, and irrigation remain unverified.",
        )

    raise ValueError("cool pavement requires verified paved/public geometry before scoring")


def _candidate_confidence(
    config: CandidateConfig,
    street_context: ExtractedStreetViewFeatures | None,
) -> float:
    """Apply the versioned exact-match/fallback confidence rule."""

    if street_context is not None:
        if (
            config.confidence_rules.exact_street_view_match
            != "use_street_context_confidence"
        ):
            raise AssertionError("unsupported exact Street View confidence rule")
        return street_context.street_context_confidence.score
    if config.confidence_rules.unmatched_site != "use_unverified_confidence_score":
        raise AssertionError("unsupported unmatched-site confidence rule")
    return config.unverified_confidence_score


def _stop_statement(stop: ProcessedTransitStop) -> str:
    activity = published_patronage_activity(stop)
    activity_text = (
        "published patronage is missing"
        if activity is None
        else f"published patronage activity is {activity:g} boardings plus alightings"
    )
    routes = ", ".join(stop.route_ids) if stop.route_ids else "no current route IDs"
    return (
        f"LA Metro identifies {stop.name} as stop {stop.stop_id}, served by routes {routes}; "
        f"{activity_text}, using the maximum across retained DX/SA/SU fields without assigning "
        "meanings to those prefixes."
    )


def _poi_statement(poi: ProcessedPoi) -> str:
    return (
        f"{poi.name} is an authoritative mapped {poi.kind} record from {poi.source_id}; its "
        "location is public-site screening evidence, not proof of canopy, planting space, "
        "ownership approval, or measured attendance."
    )


def _pavement_statement(feature: PavementConditionFeature) -> str:
    properties = feature.properties
    return (
        f"City Bureau of Street Services Pavement Condition asset {properties.ASSETID} "
        f"maps {properties.Street} from {properties.From_Street} to "
        f"{properties.To_Street}, with published surface code {properties.Surface}, "
        f"width {properties.Width}, PCI {properties.PCI} ({properties.PCI_Category}), and "
        "direct line geometry. Codes and dimensions are retained as published; they do not "
        "establish engineering clearance. Surface condition, wet traction, glare, drainage, "
        "pedestrian radiant exposure, and product compatibility all require field and "
        "engineering review before this screening option can advance."
    )


def _cool_pavement_candidates(
    *,
    table_tiles: tuple[TileFeature, ...],
    pavement_features: tuple[PavementConditionFeature, ...],
    aoi_path: Path,
    intervention: InterventionDefinition,
    config: CandidateConfig,
    satellite_by_candidate: dict[str, SatelliteSurfaceEvidence],
) -> tuple[Candidate, ...]:
    """Create a bounded set only from exact-AOI official pavement-condition lines."""

    aoi_document = json.loads(aoi_path.read_text(encoding="utf-8"))
    aoi = shape(aoi_document["features"][0]["geometry"])
    tile_shapes = {tile.tile_id: shape(tile.geometry.model_dump()) for tile in table_tiles}
    eligible_by_tile: dict[
        str, tuple[float, PavementConditionFeature, FixtureGeometry, tuple[TileFeature, ...]]
    ] = {}
    for feature in pavement_features:
        properties = feature.properties
        if not properties.Surface or properties.Width <= 0 or not properties.PCI_Category:
            continue
        clipped = shape(feature.geometry.model_dump()).intersection(aoi)
        if clipped.is_empty or clipped.geom_type not in {"LineString", "MultiLineString"}:
            continue
        intersecting = tuple(
            tile
            for tile in table_tiles
            if clipped.intersection(tile_shapes[tile.tile_id]).length > 0
        )
        if not intersecting:
            continue
        selected_tile = _select_tile(intersecting)
        overlap = clipped.intersection(tile_shapes[selected_tile.tile_id]).length
        geometry = FIXTURE_GEOMETRY_ADAPTER.validate_python(mapping(clipped))
        existing = eligible_by_tile.get(selected_tile.tile_id)
        if existing is None or (overlap, -properties.AutoID) > (
            existing[0],
            -existing[1].properties.AutoID,
        ):
            eligible_by_tile[selected_tile.tile_id] = (
                overlap,
                feature,
                geometry,
                intersecting,
            )

    selected = sorted(
        eligible_by_tile.values(),
        key=lambda item: (
            -_select_tile(item[3]).scores.priority,
            int(_select_tile(item[3]).tile_id),
            item[1].properties.AutoID,
        ),
    )[: config.cool_pavement_rules.max_candidates]
    verified_suitability = (
        config.cool_pavement_rules.verified_geometry_suitability_score
    )
    return tuple(
        _candidate(
            site_id=f"pavement:{feature.properties.ASSETID}",
            site_name=(
                f"{feature.properties.Street}: {feature.properties.From_Street} / "
                f"{feature.properties.To_Street}"
            ),
            site_type=SiteType.PUBLIC_CORRIDOR,
            site_source_ids=("la_city_pavement_condition",),
            geometry=geometry,
            tiles=intersecting,
            intervention=intervention,
            site_statement=_pavement_statement(feature),
            config=config,
            street_context=None,
            thermal_stress_context=None,
            satellite_surface_context=satellite_by_candidate.get(
                f"cool_pavement:pavement:{feature.properties.ASSETID}"
            ),
            suitability_override=(
                verified_suitability,
                (
                    "An exact official pavement-condition segment with published surface, width, "
                    "and PCI passes the versioned geometry-suitability rule; unresolved surface "
                    "condition, product, and engineering checks remain in feasibility.",
                ),
            ),
            confidence_override=config.unverified_confidence_score,
            site_evidence_kind=EvidenceKind.PAVEMENT,
            site_source_artifact_ids=(CandidateSourceArtifact.PAVEMENT_CONDITION,),
            uses_street_context=False,
        )
        for _, feature, geometry, intersecting in selected
    )


def build_candidates(
    *,
    feature_table_path: Path = DEFAULT_FEATURE_TABLE_PATH,
    public_data_path: Path = DEFAULT_PUBLIC_DATA_PATH,
    catalog_path: Path = DEFAULT_INTERVENTION_CATALOG_PATH,
    config_path: Path = DEFAULT_CANDIDATE_CONFIG_PATH,
    streetview_evidence_path: Path = DEFAULT_STREETVIEW_EVIDENCE_PATH,
    environmental_evidence_path: Path = DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH,
    pavement_path: Path = DEFAULT_PAVEMENT_PATH,
    aoi_path: Path = DEFAULT_AOI_PATH,
    satellite_evidence_path: Path = DEFAULT_SATELLITE_EVIDENCE_PATH,
) -> CandidateArtifact:
    table = load_feature_table(feature_table_path)
    public = load_processed_fixture(public_data_path)
    catalog = load_intervention_catalog(catalog_path)
    config = load_candidate_config(config_path)
    street_artifact = load_street_view_evidence_artifact(streetview_evidence_path)
    street_by_site = {site.site_id: site for site in street_artifact.sites}
    environmental_artifact = load_environmental_evidence(environmental_evidence_path)
    environment_by_site = {site.site_id: site for site in environmental_artifact.sites}
    pavement = load_pavement_conditions(pavement_path)
    satellite_by_candidate = (
        {
            site.candidate_id: site
            for site in load_satellite_evidence(satellite_evidence_path).sites
        }
        if satellite_evidence_path.exists()
        else {}
    )

    tiles_by_stop: dict[str, list[TileFeature]] = {}
    tiles_by_poi: dict[str, list[TileFeature]] = {}
    for tile in table.tiles:
        for stop_id in tile.exposure.transit_stop_ids:
            tiles_by_stop.setdefault(stop_id, []).append(tile)
        for poi_id in tile.exposure.poi_ids:
            tiles_by_poi.setdefault(poi_id, []).append(tile)

    shade = catalog.get(InterventionType.SHADE_STRUCTURE)
    trees = catalog.get(InterventionType.TREE_CANOPY)
    cool_pavement = catalog.get(InterventionType.COOL_PAVEMENT)
    candidates = [
        _candidate(
            site_id=stop.id,
            site_name=stop.name,
            site_type=SiteType.TRANSIT_STOP,
            site_source_ids=_site_sources(stop),
            geometry=stop.geometry,
            tiles=tuple(tiles_by_stop.get(stop.id, ())),
            intervention=shade,
            site_statement=_stop_statement(stop),
            config=config,
            street_context=street_by_site.get(stop.id),
            thermal_stress_context=environment_by_site.get(stop.id),
        )
        for stop in public.transit_stops
    ]
    candidates.extend(
        _candidate(
            site_id=poi.id,
            site_name=poi.name,
            site_type=SiteType(poi.kind),
            site_source_ids=(poi.source_id,),
            geometry=poi.geometry,
            tiles=tuple(tiles_by_poi.get(poi.id, ())),
            intervention=trees,
            site_statement=_poi_statement(poi),
            config=config,
            street_context=street_by_site.get(poi.id),
            thermal_stress_context=environment_by_site.get(poi.id),
        )
        for poi in public.pois
        if poi.kind in {SiteType.SCHOOL.value, SiteType.PARK.value}
    )
    candidates.extend(
        _cool_pavement_candidates(
            table_tiles=table.tiles,
            pavement_features=pavement.features,
            aoi_path=aoi_path,
            intervention=cool_pavement,
            config=config,
            satellite_by_candidate=satellite_by_candidate,
        )
    )
    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.id))
    return CandidateArtifact(
        version="1.0",
        pilot="Pacoima, Los Angeles",
        crs="EPSG:4326",
        generated_at=table.generated_at,
        source_artifacts=(
            SourceArtifact(
                id=CandidateSourceArtifact.FEATURE_TABLE,
                path="data/processed/pacoima_tile_features.json",
                sha256=_sha256(feature_table_path),
            ),
            SourceArtifact(
                id=CandidateSourceArtifact.PUBLIC_DATA,
                path="data/processed/pacoima_public_data.json",
                sha256=_sha256(public_data_path),
            ),
            SourceArtifact(
                id=CandidateSourceArtifact.INTERVENTION_CATALOG,
                path="data/processed/interventions.json",
                sha256=_sha256(catalog_path),
            ),
            SourceArtifact(
                id=CandidateSourceArtifact.CANDIDATE_CONFIG,
                path="config/candidates.json",
                sha256=_sha256(config_path),
            ),
            SourceArtifact(
                id=CandidateSourceArtifact.STREET_VIEW_EVIDENCE,
                path="data/processed/pacoima_streetview_evidence.json",
                sha256=_sha256(streetview_evidence_path),
            ),
            SourceArtifact(
                id=CandidateSourceArtifact.ENVIRONMENTAL_EVIDENCE,
                path="data/processed/pacoima_environmental_evidence.json",
                sha256=_sha256(environmental_evidence_path),
            ),
            SourceArtifact(
                id=CandidateSourceArtifact.PAVEMENT_CONDITION,
                path="data/processed/pacoima_pavement_condition.geojson",
                sha256=_sha256(pavement_path),
            ),
            *(
                (
                    SourceArtifact(
                        id=CandidateSourceArtifact.SATELLITE_EVIDENCE,
                        path="data/processed/pacoima_satellite_evidence.json",
                        sha256=_sha256(satellite_evidence_path),
                    ),
                )
                if satellite_evidence_path.exists()
                else ()
            ),
        ),
        counts=CandidateCounts(
            total=len(ordered),
            unique_sites=len({candidate.site_id for candidate in ordered}),
            shade_structure=sum(
                candidate.intervention_type == InterventionType.SHADE_STRUCTURE
                for candidate in ordered
            ),
            tree_canopy=sum(
                candidate.intervention_type == InterventionType.TREE_CANOPY
                for candidate in ordered
            ),
            cool_pavement=sum(
                candidate.intervention_type == InterventionType.COOL_PAVEMENT
                for candidate in ordered
            ),
        ),
        scoring_notes=(
            config.benefit_score_basis,
            config.equity_score_basis,
            config.screening_score_note,
            config.representative_tile_rule,
        ),
        limitations=(
            "Candidates are screening options, not construction recommendations or procurement "
            "estimates; catalog preconstruction checks remain unresolved.",
            "Cool-pavement candidates use exact-AOI City Bureau of Street Services pavement-"
            "condition lines only; eligibility does not establish treatment compatibility, "
            "permits, safety, or constructability.",
            "Site geometry and heat-tile evidence do not establish existing shade, canopy gaps, "
            "ownership approval, constructability, or a guaranteed cooling effect.",
            "Modeled benefit and equity scores are relative Pacoima tile scores, not counts of "
            "people served or predicted temperature reductions.",
            "Thermal stress context is available only for the deterministic top 10 finalists and "
            "is not used in candidate scores or optimization.",
        ),
        candidates=ordered,
    )


def canonical_candidate_bytes(document: CandidateArtifact) -> bytes:
    return (json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()


def load_candidates(path: Path = DEFAULT_CANDIDATES_PATH) -> CandidateArtifact:
    return CandidateArtifact.model_validate_json(path.read_text(encoding="utf-8"))
