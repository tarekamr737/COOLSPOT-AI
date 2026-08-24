"""Assemble typed offline API responses from committed decision artifacts."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from api.app.schemas import (
    CandidateListResponse,
    CreditStatus,
    DataStatusResponse,
    ExposureLayerProperties,
    HeatLayerProperties,
    HeatProvenance,
    LayerFeature,
    LayerName,
    LayerProperties,
    LayerResponse,
    MethodologyResponse,
    PeakHourProvenance,
    PersistenceLayerProperties,
    PilotResponse,
    SiteOption,
    SiteResponse,
    StreetViewContextResponse,
    VulnerabilityLayerProperties,
)
from api.app.services.boundary import BoundaryCollection, load_boundary
from api.app.services.candidates import (
    CandidateArtifact,
    load_candidate_config,
    load_candidates,
)
from api.app.services.capabilities import CapabilityManifest, load_capabilities
from api.app.services.credits import CreditLedger
from api.app.services.feature_table import (
    TileFeatureTable,
    load_feature_table,
    load_scoring_config,
)
from api.app.services.heatmap_data import (
    PacoimaExceedanceArtifact,
    PacoimaHeatmapArtifact,
    PacoimaTimeOfMeasureArtifact,
    load_exceedance_artifact,
    load_heatmap_artifact,
    load_time_of_measure_artifact,
)
from api.app.services.interventions import InterventionCatalog, load_intervention_catalog
from api.app.services.optimizer import load_optimizer_config
from api.app.services.processed_data import ProcessedPublicData, load_processed_fixture
from api.app.services.scenarios import ScoringPreset
from api.app.services.streetview_evidence import (
    StreetViewEvidenceArtifact,
    load_street_view_evidence_artifact,
)
from api.app.settings import load_project_env

ROOT = Path(__file__).resolve().parents[3]
AOI_PATH = ROOT / "data" / "processed" / "pacoima_aoi.geojson"
PUBLIC_DATA_PATH = ROOT / "data" / "processed" / "pacoima_public_data.json"
STREET_VIEW_PATH = ROOT / "data" / "processed" / "pacoima_streetview.json"
STREET_VIEW_SITE_DIR = ROOT / "data" / "processed" / "pacoima_streetview_sites"


def clear_decision_caches() -> None:
    """Reload atomically replaced decision artifacts after an authorized refresh."""

    loaders = (
        _boundary,
        _heatmaps,
        _exceedance,
        _time_of_measure,
        _features,
        _candidates,
        _catalog,
        _public_data,
        _capabilities,
        _street_view_evidence,
    )
    for loader in loaders:
        loader.cache_clear()


@lru_cache(maxsize=1)
def _boundary() -> BoundaryCollection:
    return load_boundary(AOI_PATH)


@lru_cache(maxsize=1)
def _heatmaps() -> PacoimaHeatmapArtifact:
    return load_heatmap_artifact()


@lru_cache(maxsize=1)
def _exceedance() -> PacoimaExceedanceArtifact:
    return load_exceedance_artifact()


@lru_cache(maxsize=1)
def _time_of_measure() -> PacoimaTimeOfMeasureArtifact:
    return load_time_of_measure_artifact()


@lru_cache(maxsize=1)
def _features() -> TileFeatureTable:
    return load_feature_table()


@lru_cache(maxsize=1)
def _candidates() -> CandidateArtifact:
    return load_candidates()


@lru_cache(maxsize=1)
def _catalog() -> InterventionCatalog:
    return load_intervention_catalog()


@lru_cache(maxsize=1)
def _public_data() -> ProcessedPublicData:
    return load_processed_fixture(PUBLIC_DATA_PATH)


@lru_cache(maxsize=1)
def _capabilities() -> CapabilityManifest:
    return load_capabilities()


@lru_cache(maxsize=1)
def _street_view_evidence() -> StreetViewEvidenceArtifact:
    return load_street_view_evidence_artifact()


def pilot_response() -> PilotResponse:
    boundary = _boundary()
    heatmaps = _heatmaps()
    optimizer = load_optimizer_config()
    return PilotResponse(
        boundary=boundary,
        area_sq_mi=boundary.features[0].properties.area_sq_mi,
        analysis_date=heatmaps.layers[0].date_time.start_date,
        budget_presets_usd=optimizer.budget_presets_usd,
        default_budget_usd=500_000,
        scoring_presets=tuple(ScoringPreset),
        candidate_count=_candidates().counts.total,
        available_layers=tuple(LayerName),
    )


def _layer_properties(layer: LayerName) -> tuple[LayerFeature, ...]:
    table = _features()
    persistence = next(
        item for item in _heatmaps().layers if item.analytic_type == "persistence"
    )
    output: list[LayerFeature] = []
    for tile in table.tiles:
        properties: LayerProperties
        if layer == LayerName.HEAT:
            properties = HeatLayerProperties(
                layer=LayerName.HEAT,
                tile_id=tile.tile_id,
                average_temperature_c=tile.heat.average_temperature_c,
                temperature_score=tile.heat.temperature_score,
                combined_heat_score=tile.scores.heat,
            )
        elif layer == LayerName.PERSISTENCE:
            properties = PersistenceLayerProperties(
                layer=LayerName.PERSISTENCE,
                tile_id=tile.tile_id,
                persistence_hours=tile.heat.persistence_hours,
                threshold_c=persistence.threshold_c,
                direction=persistence.direction,
                persistence_score=tile.heat.persistence_score,
                combined_heat_score=tile.scores.heat,
            )
        elif layer == LayerName.EXPOSURE:
            properties = ExposureLayerProperties(
                layer=LayerName.EXPOSURE,
                tile_id=tile.tile_id,
                exposure_score=tile.scores.exposure,
                transit_stop_count=tile.exposure.transit_stop_count,
                published_patronage_activity=tile.exposure.published_patronage_activity,
                poi_count=tile.exposure.poi_count,
                school_count=tile.exposure.school_count,
                park_count=tile.exposure.park_count,
                library_count=tile.exposure.library_count,
                acs_total_population_context=tile.exposure.acs_total_population_context,
                missing_fields=tile.missing_fields,
            )
        else:
            properties = VulnerabilityLayerProperties(
                layer=LayerName.VULNERABILITY,
                tile_id=tile.tile_id,
                vulnerability_score=tile.scores.vulnerability,
                children_rate=tile.vulnerability.children_rate,
                older_adult_rate=tile.vulnerability.older_adult_rate,
                poverty_rate=tile.vulnerability.poverty_rate,
                no_vehicle_rate=tile.vulnerability.no_vehicle_rate,
                acs_tract_geoids=tile.exposure.acs_tract_geoids,
                missing_fields=tile.missing_fields,
            )
        output.append(
            LayerFeature(
                geometry=tile.geometry,
                properties=properties,
            )
        )
    return tuple(output)


def layer_response(layer: LayerName) -> LayerResponse:
    table = _features()
    heatmaps = _heatmaps()
    return LayerResponse(
        layer=layer,
        source_date=heatmaps.layers[0].date_time.start_date,
        generated_at=table.generated_at,
        features=_layer_properties(layer),
        limitations=table.limitations,
    )


def candidates_response() -> CandidateListResponse:
    artifact = _candidates()
    return CandidateListResponse(
        version=artifact.version,
        generated_at=artifact.generated_at,
        counts=artifact.counts,
        source_artifacts=artifact.source_artifacts,
        limitations=artifact.limitations,
        candidates=artifact.candidates,
    )


def site_response(site_id: str) -> SiteResponse | None:
    artifact = _candidates()
    candidates = tuple(
        candidate for candidate in artifact.candidates if candidate.site_id == site_id
    )
    if not candidates:
        return None
    tiles = {tile.tile_id: tile for tile in _features().tiles}
    catalog = _catalog()
    street_evidence = {
        site.site_id: site for site in _street_view_evidence().sites
    }.get(site_id)
    return SiteResponse(
        site_id=site_id,
        site_name=candidates[0].site_name,
        geometry=candidates[0].geometry,
        street_view_evidence=street_evidence,
        options=tuple(
            SiteOption(
                candidate=candidate,
                tile=tiles[candidate.tile_id],
                intervention=catalog.get(candidate.intervention_type),
            )
            for candidate in candidates
        ),
    )


def street_view_response(site_id: str) -> StreetViewContextResponse:
    site_path = STREET_VIEW_SITE_DIR / f"{site_id.replace(':', '__')}.json"
    payload = None
    for path in (site_path, STREET_VIEW_PATH):
        if path.exists():
            candidate_payload = json.loads(path.read_text(encoding="utf-8"))
            if candidate_payload.get("site_id") == site_id:
                payload = candidate_payload
                break
    if payload is None:
        return StreetViewContextResponse(
            site_id=site_id,
            available=False,
            limitation=(
                "Street segmentation is shown only for the exact site analyzed by FortyGuard; "
                "selecting another site never triggers a paid request."
            ),
        )
    if payload.get("status") != "Completed" or payload.get("result") is None:
        return StreetViewContextResponse(
            site_id=site_id,
            available=False,
            limitation="The cached FortyGuard street-view job did not produce verified imagery.",
        )
    front = payload["result"]["front"]
    return StreetViewContextResponse(
        site_id=site_id,
        available=True,
        image_date=front["image_date"],
        original_image_url=f"data:image/jpeg;base64,{front['original_image']}",
        segmented_image_url=f"data:image/png;base64,{front['segmented_image']}",
        segments=front["segments"],
        limitation=(
            "One dated street-view frame supports visual screening only; verify current shade, "
            "right-of-way, utilities, safety, and constructability in the field."
        ),
    )
def methodology_response() -> MethodologyResponse:
    artifact = _candidates()
    features = _features()
    heatmaps = _heatmaps()
    exceedance = _exceedance().layer
    time_of_measure = _time_of_measure().layer
    active_analysis_date = heatmaps.layers[0].date_time.start_date
    exceedance_analysis_date = exceedance.date_time.start_date
    optimizer = load_optimizer_config()
    catalog = _catalog()
    return MethodologyResponse(
        scoring=load_scoring_config(),
        heat_provenance=HeatProvenance(
            active_analysis_date=active_analysis_date,
            exceedance_analysis_date=exceedance_analysis_date,
            exceedance_threshold_c=exceedance.threshold_c,
            exceedance_direction=exceedance.direction,
            exceedance_request_hash=exceedance.request_hash,
            exceedance_activity_id=exceedance.activity_id,
            exceedance_artifact_sha256=features.exceedance_artifact_sha256,
            observed_credit_delta=exceedance.observed_credit_delta,
            limitation=(
                f"Exceedance is historical context from {exceedance_analysis_date.isoformat()}, "
                "while active TCM and persistence evidence is dated "
                f"{active_analysis_date.isoformat()}; the inputs are not contemporaneous."
            ),
        ),
        peak_hour_provenance=PeakHourProvenance(
            analysis_date=time_of_measure.date_time.start_date,
            request_hash=time_of_measure.request_hash,
            activity_id=time_of_measure.activity_id,
            artifact_sha256=features.time_of_measure_artifact_sha256,
            observed_credit_delta=time_of_measure.observed_credit_delta,
            limitation=(
                "Peak temperature hour is historical heat context only; it is not evidence of "
                "peak pedestrian volume and is not used in scoring."
            ),
        ),
        candidate_generation=load_candidate_config(),
        optimization=optimizer,
        interventions=catalog,
        limitations=(
            *artifact.limitations,
            catalog.cost_basis.disclaimer,
            optimizer.objective_note,
            optimizer.equity_note,
        ),
    )


def data_status_response() -> DataStatusResponse:
    heatmaps = _heatmaps()
    capabilities = _capabilities()
    artifact = _candidates()
    env = load_project_env()
    live_enabled = env.get("FORTYGUARD_LIVE", "0") == "1"
    refresh_token_configured = bool(env.get("COOLSPOT_REFRESH_TOKEN", "").strip())
    explanation_mode: Literal["template", "openrouter"] = (
        "openrouter"
        if env.get("EXPLANATION_MODE") == "openrouter"
        and bool(env.get("OPENROUTER_API_KEY", "").strip())
        else "template"
    )
    credit_used = capabilities.credits_used
    ledger_path = ROOT / "data" / "raw" / "fortyguard" / "credit_ledger.json"
    if ledger_path.exists():
        terminal_usage = [
            entry.usage_after
            for entry in CreditLedger(ledger_path).load().entries
            if entry.usage_after is not None
        ]
        if terminal_usage:
            credit_used = max(credit_used, max(terminal_usage))
    return DataStatusResponse(
        mode=(
            "live_refreshed"
            if (ROOT / "data" / "runtime" / "fortyguard" / "last_refresh.json").exists()
            else "cached_demo"
        ),
        refresh_available=live_enabled and refresh_token_configured,
        explanation_mode=explanation_mode,
        heat_data_date=heatmaps.layers[0].date_time.start_date,
        heat_data_generated_at=heatmaps.generated_at,
        public_data_retrieved_at=_public_data().source_retrieved_at,
        capabilities_evaluated_at=capabilities.evaluated_at,
        credits=CreditStatus(
            total=capabilities.total_credits,
            used=credit_used,
            remaining=capabilities.total_credits - credit_used,
            hard_reserve=capabilities.hard_reserve,
        ),
        capabilities=capabilities.capabilities,
        layers=tuple(LayerName),
        candidate_count=artifact.counts.total,
        candidate_source_artifacts=artifact.source_artifacts,
    )
