"""Tests for deterministic, compatible candidates from real Pacoima sites."""

import hashlib
import json
from pathlib import Path

from shapely.geometry import shape

from api.app.services.candidates import (
    DEFAULT_CANDIDATE_CONFIG_PATH,
    DEFAULT_CANDIDATES_PATH,
    CandidateSourceArtifact,
    TileSelection,
    build_candidates,
    canonical_candidate_bytes,
    load_candidate_config,
    load_candidates,
)
from api.app.services.environmental_evidence import DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH
from api.app.services.feature_table import DEFAULT_FEATURE_TABLE_PATH, load_feature_table
from api.app.services.interventions import (
    DEFAULT_INTERVENTION_CATALOG_PATH,
    InterventionType,
    load_intervention_catalog,
)
from api.app.services.processed_data import FixtureGeometry, load_processed_fixture
from api.app.services.roadway_geometry import (
    DEFAULT_AOI_PATH,
    DEFAULT_PAVEMENT_PATH,
    load_pavement_conditions,
)
from api.app.services.satellite_evidence import DEFAULT_SATELLITE_EVIDENCE_PATH
from api.app.services.streetview_evidence import (
    DEFAULT_STREETVIEW_EVIDENCE_PATH,
    load_street_view_evidence_artifact,
)

PUBLIC_DATA_PATH = Path("data/processed/pacoima_public_data.json")


def test_real_candidates_are_complete_compatible_and_traceable() -> None:
    artifact = load_candidates()
    public = load_processed_fixture(PUBLIC_DATA_PATH)
    catalog = load_intervention_catalog()
    street_by_site = {
        site.site_id: site for site in load_street_view_evidence_artifact().sites
    }
    site_geometries: dict[str, FixtureGeometry] = {
        **{stop.id: stop.geometry for stop in public.transit_stops},
        **{poi.id: poi.geometry for poi in public.pois},
    }

    assert artifact.counts.total == 172
    assert artifact.counts.unique_sites == 172
    assert artifact.counts.shade_structure == 111
    assert artifact.counts.tree_canopy == 41
    assert artifact.counts.cool_pavement == 20
    assert artifact.counts.total >= 20

    for candidate in artifact.candidates:
        intervention = catalog.get(candidate.intervention_type)
        assert candidate.site_type in intervention.applicability.eligible_site_types
        assert candidate.planning_cost_usd == intervention.planning_cost.estimate_usd
        if candidate.intervention_type != InterventionType.COOL_PAVEMENT:
            assert candidate.geometry == site_geometries[candidate.site_id]
        assert candidate.suitability_score == (
            candidate.value_explanation.factors.suitability_score
        )
        assert candidate.value_explanation.factors.priority_score == candidate.benefit_score
        assert candidate.value_explanation.modeled_benefit_score == (
            candidate.value_explanation.factors.modeled_benefit()
        )
        assert candidate.value_explanation.suitability_basis
        assert candidate.feasibility_score == 0.5
        if candidate.site_id in street_by_site:
            assert candidate.confidence == (
                street_by_site[candidate.site_id].street_context_confidence.score
            )
            assert any(item.kind.value == "street_context" for item in candidate.evidence)
        else:
            assert candidate.confidence == 0.5
            assert not any(item.kind.value == "street_context" for item in candidate.evidence)
        if candidate.confidence == 0.5:
            assert candidate.site_id not in street_by_site
        assert any(
            "feasibility remains at the unverified screening scalar 0.5"
            in item.statement
            for item in candidate.evidence
        )
        assert len(candidate.evidence) == (
            7 if candidate.satellite_surface_context is not None else 6
        )

    assert len({candidate.confidence for candidate in artifact.candidates}) > 2
    assert all(candidate.feasibility_score == 0.5 for candidate in artifact.candidates)
    thermal_candidates = tuple(
        candidate for candidate in artifact.candidates if candidate.thermal_stress_context
    )
    assert len(thermal_candidates) == 10
    assert len({candidate.site_id for candidate in thermal_candidates}) == 10
    assert all(
        candidate.thermal_stress_context is None
        or candidate.thermal_stress_context.site_id == candidate.site_id
        for candidate in artifact.candidates
    )
    satellite_candidates = tuple(
        candidate for candidate in artifact.candidates if candidate.satellite_surface_context
    )
    assert len(satellite_candidates) == 1
    assert satellite_candidates[0].id == "cool_pavement:pavement:21486"
    assert satellite_candidates[0].satellite_surface_context is not None
    assert (
        satellite_candidates[0]
        .satellite_surface_context.surface_class_coverage.combined_surface_class_percent
        == 67.8
    )
    assert all(
        candidate.thermal_stress_context is None
        or candidate.thermal_stress_context.evidence_confidence.assessment
        == "source_complete"
        for candidate in artifact.candidates
    )


def test_candidate_confidence_rules_are_versioned_and_exact_site_only() -> None:
    config = load_candidate_config()

    assert config.confidence_rules.exact_street_view_match == (
        "use_street_context_confidence"
    )
    assert config.confidence_rules.unmatched_site == "use_unverified_confidence_score"
    assert "exact site_id match" in config.confidence_rules.note
    assert "outcome probability" in config.confidence_rules.note
    assert config.suitability_rules.exact_shade_street_view == (
        "mean_available_open_sky_and_low_tree_context"
    )
    assert config.suitability_rules.exact_tree_street_view == "use_low_tree_context"
    assert config.suitability_rules.unmatched_site == "use_unverified_suitability_score"
    assert config.unverified_suitability_score == 0.5
    assert config.cool_pavement_rules.max_candidates == 20
    assert config.cool_pavement_rules.eligibility == (
        "require_bss_pavement_geometry_surface_width_and_pci"
    )


def test_every_non_neutral_adjustment_has_traceable_evidence() -> None:
    artifact = load_candidates()

    for candidate in artifact.candidates:
        if candidate.confidence != 0.5:
            records = [
                item for item in candidate.evidence if item.kind.value == "street_context"
            ]
            assert len(records) == 1
            record = records[0]
            assert f"confidence {candidate.confidence:.3f}" in record.statement
            assert "component scores" in record.statement
            assert "imagery availability" in record.statement
            assert "segmentation completeness" in record.statement
            assert record.source_artifact_ids == (
                CandidateSourceArtifact.STREET_VIEW_EVIDENCE,
            )
        if candidate.feasibility_score != 0.5:
            assert any(
                "feasibility" in item.statement.lower() for item in candidate.evidence
            )


def test_candidate_scores_and_representative_tiles_come_from_feature_table() -> None:
    artifact = load_candidates()
    table = load_feature_table()
    tiles = {tile.tile_id: tile for tile in table.tiles}

    for candidate in artifact.candidates:
        tile = tiles[candidate.tile_id]
        assert candidate.benefit_score == tile.scores.priority
        assert candidate.equity_score == tile.scores.vulnerability
        if candidate.intersecting_tile_count == 1:
            assert candidate.tile_selection == TileSelection.CONTAINING_TILE
        else:
            assert (
                candidate.tile_selection
                == TileSelection.HIGHEST_PRIORITY_INTERSECTING_TILE
            )


def test_candidate_artifact_is_canonical_and_hashes_all_inputs() -> None:
    artifact = load_candidates()
    expected_paths = {
        CandidateSourceArtifact.FEATURE_TABLE: DEFAULT_FEATURE_TABLE_PATH,
        CandidateSourceArtifact.PUBLIC_DATA: PUBLIC_DATA_PATH,
        CandidateSourceArtifact.INTERVENTION_CATALOG: DEFAULT_INTERVENTION_CATALOG_PATH,
        CandidateSourceArtifact.CANDIDATE_CONFIG: DEFAULT_CANDIDATE_CONFIG_PATH,
        CandidateSourceArtifact.STREET_VIEW_EVIDENCE: DEFAULT_STREETVIEW_EVIDENCE_PATH,
        CandidateSourceArtifact.ENVIRONMENTAL_EVIDENCE: DEFAULT_ENVIRONMENTAL_EVIDENCE_PATH,
        CandidateSourceArtifact.PAVEMENT_CONDITION: DEFAULT_PAVEMENT_PATH,
        CandidateSourceArtifact.SATELLITE_EVIDENCE: DEFAULT_SATELLITE_EVIDENCE_PATH,
    }

    assert DEFAULT_CANDIDATES_PATH.read_bytes() == canonical_candidate_bytes(artifact)
    for source in artifact.source_artifacts:
        assert source.sha256 == hashlib.sha256(expected_paths[source.id].read_bytes()).hexdigest()

    all_text = " ".join(
        evidence.statement.lower()
        for candidate in artifact.candidates
        for evidence in candidate.evidence
    )
    for prohibited_claim in ("people protected", "lives saved", "deaths prevented"):
        assert prohibited_claim not in all_text
    assert sum(
        candidate.intervention_type == InterventionType.COOL_PAVEMENT
        for candidate in artifact.candidates
    ) == 20


def test_cool_pavement_candidates_require_exact_official_pavement_geometry() -> None:
    candidates = tuple(
        candidate
        for candidate in load_candidates().candidates
        if candidate.intervention_type == InterventionType.COOL_PAVEMENT
    )
    pavement_by_asset = {
        feature.properties.ASSETID: feature for feature in load_pavement_conditions().features
    }
    aoi_document = json.loads(DEFAULT_AOI_PATH.read_text(encoding="utf-8"))
    aoi = shape(aoi_document["features"][0]["geometry"])

    assert len(candidates) == 20
    assert len({candidate.tile_id for candidate in candidates}) == 20
    for candidate in candidates:
        asset_id = int(candidate.site_id.removeprefix("pavement:"))
        source = pavement_by_asset[asset_id]
        geometry = shape(candidate.geometry.model_dump())

        assert source.properties.Surface
        assert source.properties.Width > 0
        assert source.properties.PCI_Category in {"Good", "Fair", "Poor"}
        assert source.properties.Datasource_DT > 0
        assert aoi.covers(geometry)
        assert shape(source.geometry.model_dump()).covers(geometry)
        assert candidate.site_source_ids == ("la_city_pavement_condition",)
        pavement_text = " ".join(
            evidence.statement.lower() for evidence in candidate.evidence
        )
        for required_gate in (
            "surface condition",
            "traction",
            "glare",
            "drainage",
            "radiant exposure",
            "product compatibility",
        ):
            assert required_gate in pavement_text
        assert any(
            evidence.kind.value == "pavement"
            and evidence.source_artifact_ids
            == (CandidateSourceArtifact.PAVEMENT_CONDITION,)
            for evidence in candidate.evidence
        )


def test_pavement_candidates_do_not_require_optional_satellite_access(
    tmp_path: Path,
) -> None:
    artifact = build_candidates(
        satellite_evidence_path=tmp_path / "unsupported-satellite.json"
    )

    pavement = tuple(
        candidate
        for candidate in artifact.candidates
        if candidate.intervention_type == InterventionType.COOL_PAVEMENT
    )
    assert len(pavement) == 20
    assert all(candidate.satellite_surface_context is None for candidate in pavement)
    assert CandidateSourceArtifact.SATELLITE_EVIDENCE not in {
        source.id for source in artifact.source_artifacts
    }
