"""Deterministic selection checks for environmental finalist enrichment."""

import asyncio
from pathlib import Path

import pytest

from api.app.fortyguard_models import FortyGuardEndpoint
from api.app.services.fortyguard import canonical_request_hash
from scripts import cache_environmental_finalists as batch
from scripts.cache_environmental_finalists import (
    OUTPUT_DIR,
    FinalistEnvironmentalArtifact,
    output_path,
    select_environmental_finalists,
)
from scripts.probe_fortyguard_env_params import (
    MAX_ENVIRONMENTAL_FINALISTS,
    OBSERVED_ENV_PARAMS_UNIT_COST,
    build_env_params_probe_request,
)


def test_environmental_finalists_are_top_ten_unique_and_request_aligned() -> None:
    finalists = select_environmental_finalists()
    modeled_impacts = tuple(
        candidate.benefit_score * candidate.feasibility_score * candidate.confidence
        for candidate in finalists
    )

    assert len(finalists) == MAX_ENVIRONMENTAL_FINALISTS == 10
    assert len({candidate.site_id for candidate in finalists}) == len(finalists)
    assert modeled_impacts == tuple(sorted(modeled_impacts, reverse=True))
    assert finalists[0].id == "shade_structure:metro-stop:6788"
    assert all(
        build_env_params_probe_request(candidate).date_time.filter_type == 1
        for candidate in finalists
    )


def test_completed_probe_seeds_first_finalist_without_a_vendor_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finalists = select_environmental_finalists()
    monkeypatch.setattr(batch, "OUTPUT_DIR", tmp_path)

    batch.seed_probe_artifact(finalists)

    artifact = FinalistEnvironmentalArtifact.model_validate_json(
        batch.output_path(finalists[0].site_id).read_text(encoding="utf-8")
    )
    assert artifact.finalist_rank == 1
    assert artifact.candidate_id == finalists[0].id
    assert artifact.observed_credit_delta == OBSERVED_ENV_PARAMS_UNIT_COST


def test_real_top_ten_batch_is_complete_cached_and_replay_safe() -> None:
    finalists = select_environmental_finalists()
    artifacts = asyncio.run(batch.cache_environmental_finalists())

    assert len(artifacts) == len(finalists) == MAX_ENVIRONMENTAL_FINALISTS
    assert tuple(artifact.finalist_rank for artifact in artifacts) == tuple(range(1, 11))
    assert tuple(artifact.candidate_id for artifact in artifacts) == tuple(
        candidate.id for candidate in finalists
    )
    assert {artifact.observed_credit_delta for artifact in artifacts} == {2_900}
    assert artifacts[-1].credits_remaining == 1_773_680
    assert all(len(artifact.result.locations) == 1 for artifact in artifacts)


def test_every_completed_finalist_response_has_one_secret_free_canonical_cache() -> None:
    finalists = select_environmental_finalists()
    expected_paths = {output_path(candidate.site_id) for candidate in finalists}
    actual_paths = set(OUTPUT_DIR.glob("*.json"))

    assert actual_paths == expected_paths
    artifacts = tuple(
        FinalistEnvironmentalArtifact.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(actual_paths)
    )
    assert len({artifact.activity_id for artifact in artifacts}) == len(artifacts)
    for artifact in artifacts:
        assert artifact.request_hash == canonical_request_hash(
            FortyGuardEndpoint.ENV_PARAMS, artifact.request
        )
        assert len(artifact.result.metadata.timestamps) == 1
        assert len(artifact.result.locations) == 1
        assert "api_key" not in output_path(artifact.site_id).read_text(
            encoding="utf-8"
        ).lower()
