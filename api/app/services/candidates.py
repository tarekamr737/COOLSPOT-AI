"""Deterministic candidates from real Pacoima sites and versioned assumptions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.app.services.feature_table import (
    DEFAULT_FEATURE_TABLE_PATH,
    TileFeature,
    load_feature_table,
    published_patronage_activity,
)
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


class CandidateSourceArtifact(StrEnum):
    FEATURE_TABLE = "pacoima_tile_feature_table"
    PUBLIC_DATA = "pacoima_public_data"
    INTERVENTION_CATALOG = "intervention_catalog"
    CANDIDATE_CONFIG = "candidate_config"
    STREET_VIEW_EVIDENCE = "pacoima_streetview_evidence"


class EvidenceKind(StrEnum):
    OBSERVED_HEAT = "observed_heat"
    EXPOSURE = "exposure"
    VULNERABILITY = "vulnerability"
    APPLICABILITY = "applicability"
    PLANNING_ASSUMPTION = "planning_assumption"
    STREET_CONTEXT = "street_context"


class TileSelection(StrEnum):
    CONTAINING_TILE = "containing_tile"
    HIGHEST_PRIORITY_INTERSECTING_TILE = "highest_priority_intersecting_tile"


class CandidateConfidenceRules(BaseModel):
    """Versioned mapping from evidence availability to candidate confidence."""

    model_config = ConfigDict(extra="forbid")

    exact_street_view_match: Literal["use_street_context_confidence"]
    unmatched_site: Literal["use_unverified_confidence_score"]
    note: str = Field(min_length=80)


class CandidateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: str = Field(pattern=r"^1\.0$")
    unverified_feasibility_score: float = Field(ge=0, le=1)
    unverified_confidence_score: float = Field(ge=0, le=1)
    confidence_rules: CandidateConfidenceRules
    benefit_score_basis: str = Field(min_length=30)
    equity_score_basis: str = Field(min_length=30)
    screening_score_note: str = Field(min_length=50)
    representative_tile_rule: str = Field(min_length=50)


class SourceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: CandidateSourceArtifact
    path: str = Field(pattern=r"^(config|data)/.+\.json$")
    sha256: str = Field(pattern=SHA256_PATTERN)


class CandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    statement: str = Field(min_length=20)
    source_artifact_ids: tuple[CandidateSourceArtifact, ...] = Field(min_length=1)


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
    benefit_score: float = Field(ge=0, le=1)
    equity_score: float = Field(ge=0, le=1)
    feasibility_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence: tuple[CandidateEvidence, ...] = Field(min_length=5)
    geometry: FixtureGeometry

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.id != f"{self.intervention_type.value}:{self.site_id}":
            raise ValueError("candidate ID must combine intervention type and site ID")
        if len(self.site_source_ids) != len(set(self.site_source_ids)):
            raise ValueError("candidate site source IDs must be unique")
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
        if len(source_ids) != len(set(source_ids)) or set(source_ids) != set(
            CandidateSourceArtifact
        ):
            raise ValueError("candidate artifact must reference each source artifact once")

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
            kind=EvidenceKind.EXPOSURE,
            statement=site_statement,
            source_artifact_ids=(
                CandidateSourceArtifact.PUBLIC_DATA,
                CandidateSourceArtifact.FEATURE_TABLE,
            ),
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
    if street_context is not None:
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
    else:
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
        equity_score=selected_tile.scores.vulnerability,
        feasibility_score=config.unverified_feasibility_score,
        confidence=_candidate_confidence(config, street_context),
        evidence=_common_evidence(
            tile=selected_tile,
            intervention=intervention,
            site_statement=site_statement,
            config=config,
            street_context=street_context,
        ),
        geometry=geometry,
    )


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


def build_candidates(
    *,
    feature_table_path: Path = DEFAULT_FEATURE_TABLE_PATH,
    public_data_path: Path = DEFAULT_PUBLIC_DATA_PATH,
    catalog_path: Path = DEFAULT_INTERVENTION_CATALOG_PATH,
    config_path: Path = DEFAULT_CANDIDATE_CONFIG_PATH,
    streetview_evidence_path: Path = DEFAULT_STREETVIEW_EVIDENCE_PATH,
) -> CandidateArtifact:
    table = load_feature_table(feature_table_path)
    public = load_processed_fixture(public_data_path)
    catalog = load_intervention_catalog(catalog_path)
    config = load_candidate_config(config_path)
    street_artifact = load_street_view_evidence_artifact(streetview_evidence_path)
    street_by_site = {site.site_id: site for site in street_artifact.sites}

    tiles_by_stop: dict[str, list[TileFeature]] = {}
    tiles_by_poi: dict[str, list[TileFeature]] = {}
    for tile in table.tiles:
        for stop_id in tile.exposure.transit_stop_ids:
            tiles_by_stop.setdefault(stop_id, []).append(tile)
        for poi_id in tile.exposure.poi_ids:
            tiles_by_poi.setdefault(poi_id, []).append(tile)

    shade = catalog.get(InterventionType.SHADE_STRUCTURE)
    trees = catalog.get(InterventionType.TREE_CANOPY)
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
        )
        for poi in public.pois
        if poi.kind in {SiteType.SCHOOL.value, SiteType.PARK.value}
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
            "No cool-pavement candidate is generated because the cached pilot inputs contain no "
            "verified public paved-surface or corridor geometry.",
            "Site geometry and heat-tile evidence do not establish existing shade, canopy gaps, "
            "ownership approval, constructability, or a guaranteed cooling effect.",
            "Modeled benefit and equity scores are relative Pacoima tile scores, not counts of "
            "people served or predicted temperature reductions.",
        ),
        candidates=ordered,
    )


def canonical_candidate_bytes(document: CandidateArtifact) -> bytes:
    return (json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()


def load_candidates(path: Path = DEFAULT_CANDIDATES_PATH) -> CandidateArtifact:
    return CandidateArtifact.model_validate_json(path.read_text(encoding="utf-8"))
