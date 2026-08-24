"""Tests for deterministic, compatible candidates from real Pacoima sites."""

import hashlib
from pathlib import Path

from api.app.services.candidates import (
    DEFAULT_CANDIDATE_CONFIG_PATH,
    DEFAULT_CANDIDATES_PATH,
    CandidateSourceArtifact,
    TileSelection,
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

    assert artifact.counts.total == 152
    assert artifact.counts.unique_sites == 152
    assert artifact.counts.shade_structure == 111
    assert artifact.counts.tree_canopy == 41
    assert artifact.counts.cool_pavement == 0
    assert artifact.counts.total >= 20

    for candidate in artifact.candidates:
        intervention = catalog.get(candidate.intervention_type)
        assert candidate.site_type in intervention.applicability.eligible_site_types
        assert candidate.planning_cost_usd == intervention.planning_cost.estimate_usd
        assert candidate.geometry == site_geometries[candidate.site_id]
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
        assert len(candidate.evidence) == 6

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
    assert all(
        candidate.intervention_type != InterventionType.COOL_PAVEMENT
        for candidate in artifact.candidates
    )
