"""Offline tests for the single governed Heat Intelligence probe target."""

import inspect

import pytest
from pydantic import ValidationError

from api.app.fortyguard_models import HeatIntelligenceRequest
from api.app.services import candidates, optimizer
from api.app.services.heatmap_data import load_heatmap_artifact
from scripts.probe_fortyguard_heat_intelligence import (
    RECEIPT_PATH,
    HeatIntelligenceProbeReceipt,
    build_probe_request,
    select_probe_candidate,
)


def test_probe_targets_top_balanced_500k_recommendation_deterministically() -> None:
    candidate = select_probe_candidate()
    request = build_probe_request(candidate)

    assert candidate.id == "tree_canopy:school:53"
    assert candidate.site_name == "Pacoima Early Education Center"
    tcm = next(
        layer for layer in load_heatmap_artifact().layers if layer.analytic_type == "tcm"
    )
    assert request.date == tcm.date_time.start_date
    assert request.analysis == ("urban",)
    assert 34 <= request.latitude <= 35
    assert -119 <= request.longitude <= -118
    assert request.temperature > 0


def test_heat_intelligence_request_rejects_invalid_or_duplicate_analysis() -> None:
    payload = {
        "latitude": 34.26,
        "longitude": -118.42,
        "temperature": 38.5,
        "date": "2024-07-15",
    }
    with pytest.raises(ValidationError, match="at least 1 item"):
        HeatIntelligenceRequest.model_validate({**payload, "analysis": []})
    with pytest.raises(ValidationError, match="must be unique"):
        HeatIntelligenceRequest.model_validate(
            {**payload, "analysis": ["urban", "urban"]}
        )
    with pytest.raises(ValidationError, match="analysis.0"):
        HeatIntelligenceRequest.model_validate({**payload, "analysis": ["medical"]})


def test_committed_probe_receipt_matches_canonical_request() -> None:
    receipt = HeatIntelligenceProbeReceipt.model_validate_json(
        RECEIPT_PATH.read_text(encoding="utf-8")
    )
    candidate = select_probe_candidate()

    assert receipt.status == "Processing"
    assert receipt.candidate_id == candidate.id
    assert receipt.request == build_probe_request(candidate)
    assert receipt.credits_remaining_before == 1_759_280
    assert receipt.hard_reserve == 500_000


def test_heat_intelligence_is_not_a_ranking_or_optimizer_dependency() -> None:
    """Fail if the optional report is wired into either deterministic decision path."""

    for module in (candidates, optimizer):
        source = inspect.getsource(module).lower()
        assert "heat_intelligence" not in source
        assert "fortyguard_heat_intelligence_probe" not in source
