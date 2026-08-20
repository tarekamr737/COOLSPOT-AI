"""Tests for deterministic, compatible candidates from real Pacoima sites."""

import hashlib
from pathlib import Path

from api.app.services.candidates import (
    DEFAULT_CANDIDATE_CONFIG_PATH,
    DEFAULT_CANDIDATES_PATH,
    CandidateSourceArtifact,
    TileSelection,
    canonical_candidate_bytes,
    load_candidates,
)
from api.app.services.feature_table import DEFAULT_FEATURE_TABLE_PATH, load_feature_table
from api.app.services.interventions import (
    DEFAULT_INTERVENTION_CATALOG_PATH,
    InterventionType,
    load_intervention_catalog,
)
from api.app.services.processed_data import FixtureGeometry, load_processed_fixture

PUBLIC_DATA_PATH = Path("data/processed/pacoima_public_data.json")


def test_real_candidates_are_complete_compatible_and_traceable() -> None:
    artifact = load_candidates()
    public = load_processed_fixture(PUBLIC_DATA_PATH)
    catalog = load_intervention_catalog()
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
        assert candidate.confidence == 0.5
        assert len(candidate.evidence) == 5


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
