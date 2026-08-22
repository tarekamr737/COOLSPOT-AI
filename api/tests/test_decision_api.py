"""Integration tests for the complete cached decision API surface."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.app.main import app
from api.app.schemas import (
    CandidateListResponse,
    DataStatusResponse,
    LayerName,
    LayerResponse,
    MethodologyResponse,
    PilotResponse,
    SiteResponse,
    StreetViewContextResponse,
)
from api.app.services.explanations import GroundedExplanation
from api.app.services.live_refresh import RefreshPreflightError
from api.app.services.optimizer import PortfolioResult

client = TestClient(app)


def test_pilot_layers_candidates_site_and_methodology_routes() -> None:
    pilot_response = client.get("/v1/pilot")
    assert pilot_response.status_code == 200
    pilot = PilotResponse.model_validate(pilot_response.json())
    assert pilot.area_sq_mi < 10
    assert pilot.budget_presets_usd == (250_000, 500_000, 1_000_000)
    assert pilot.candidate_count == 152

    for layer_name in LayerName:
        response = client.get(f"/v1/layers/{layer_name.value}")
        assert response.status_code == 200
        layer = LayerResponse.model_validate(response.json())
        assert layer.layer == layer_name
        assert layer.cached is True
        assert len(layer.features) == 2_001

    candidates_response = client.get("/v1/candidates")
    assert candidates_response.status_code == 200
    candidates = CandidateListResponse.model_validate(candidates_response.json())
    assert candidates.counts.total == 152
    first = candidates.candidates[0]

    site_response = client.get(f"/v1/sites/{first.site_id}")
    assert site_response.status_code == 200
    site = SiteResponse.model_validate(site_response.json())
    assert site.site_id == first.site_id
    assert site.options[0].candidate.id == first.id
    assert site.options[0].tile.tile_id == first.tile_id
    assert site.options[0].intervention.id == first.intervention_type

    methodology_response = client.get("/v1/methodology")
    assert methodology_response.status_code == 200
    methodology = MethodologyResponse.model_validate(methodology_response.json())
    assert methodology.scoring.version == "1.0"
    assert methodology.interventions.version == "1.0"
    assert methodology.optimization.objective_scale == 1_000_000


def test_optimize_is_cached_only_and_validates_budget() -> None:
    with (
        patch(
            "api.app.services.fortyguard.FortyGuardClient.submit_heatmap",
            new_callable=AsyncMock,
        ) as submit_heatmap,
        patch(
            "api.app.services.fortyguard.FortyGuardClient.fetch_credit_usage",
            new_callable=AsyncMock,
        ) as fetch_usage,
    ):
        response = client.post("/v1/optimize", json={"budget_usd": 500_000})

    assert response.status_code == 200
    result = PortfolioResult.model_validate(response.json())
    assert result.solver_status == "optimal"
    assert result.total_cost_usd <= result.budget_usd
    assert submit_heatmap.await_count == 0
    assert fetch_usage.await_count == 0

    invalid = client.post("/v1/optimize", json={"budget_usd": 49_999})
    assert invalid.status_code == 422
    assert "budget must be between" in invalid.json()["detail"]


def test_data_status_and_missing_site_are_explicit() -> None:
    response = client.get("/v1/data-status")
    assert response.status_code == 200
    status = DataStatusResponse.model_validate(response.json())
    assert status.mode in {"cached_demo", "live_refreshed"}
    assert status.external_calls_on_read is False
    assert status.credits.used >= 8_440
    assert status.credits.remaining == status.credits.total - status.credits.used
    assert status.credits.remaining >= status.credits.hard_reserve
    assert status.candidate_count == 152

    missing = client.get("/v1/sites/not-a-real-site")
    assert missing.status_code == 404
    assert "was not found" in missing.json()["detail"]


def test_street_view_is_exact_site_cached_evidence() -> None:
    available_response = client.get("/v1/sites/metro-stop%3A10794/street-view")
    assert available_response.status_code == 200
    available = StreetViewContextResponse.model_validate(available_response.json())
    assert available.available is True
    assert available.image_date is not None
    assert available.original_image_url is not None
    assert available.original_image_url.startswith("data:image/jpeg;base64,")
    assert available.segmented_image_url is not None
    assert available.segmented_image_url.startswith("data:image/png;base64,")
    assert available.segments["road"] > 0

    unavailable_response = client.get("/v1/sites/metro-stop%3A10554/street-view")
    assert unavailable_response.status_code == 200
    unavailable = StreetViewContextResponse.model_validate(unavailable_response.json())
    assert unavailable.available is False
    assert unavailable.segmented_image_url is None


def test_live_refresh_requires_an_administrator_token_before_any_vendor_call() -> None:
    env = {
        "FORTYGUARD_LIVE": "1",
        "FORTYGUARD_API_KEY": "vendor-key",
        "FORTYGUARD_CREDIT_TOTAL": "2000000",
        "FORTYGUARD_CREDIT_RESERVE": "500000",
        "COOLSPOT_REFRESH_TOKEN": "admin-secret",
    }
    with (
        patch("api.app.services.live_refresh.load_project_env", return_value=env),
        patch(
            "api.app.services.live_refresh.FortyGuardClient.fetch_credit_usage",
            new_callable=AsyncMock,
        ) as fetch_usage,
    ):
        response = client.post(
            "/v1/refresh",
            headers={"X-Refresh-Token": "wrong-token"},
            json={"analysis_date": "2026-08-20"},
        )

    assert response.status_code == 401
    assert fetch_usage.await_count == 0


def test_live_refresh_returns_a_useful_preflight_connectivity_error() -> None:
    message = (
        "FortyGuard is unreachable during the credit preflight. No paid jobs were "
        "submitted; cached evidence remains active."
    )
    with patch(
        "api.app.routers.decision.refresh_coordinator.start",
        new_callable=AsyncMock,
        side_effect=RefreshPreflightError(message),
    ):
        response = client.post(
            "/v1/refresh",
            headers={"X-Refresh-Token": "admin-secret"},
            json={"analysis_date": "2026-08-20"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == message


def test_selected_site_explanation_restates_only_structured_evidence() -> None:
    portfolio = PortfolioResult.model_validate(
        client.post("/v1/optimize", json={"budget_usd": 500_000}).json()
    )
    candidates = CandidateListResponse.model_validate(client.get("/v1/candidates").json())
    selected = next(
        candidate
        for candidate in candidates.candidates
        if candidate.id in portfolio.selected_candidate_ids
    )

    with (
        patch(
            "api.app.services.fortyguard.FortyGuardClient.submit_heatmap",
            new_callable=AsyncMock,
        ) as submit_heatmap,
        patch(
            "api.app.services.fortyguard.FortyGuardClient.fetch_credit_usage",
            new_callable=AsyncMock,
        ) as fetch_usage,
        patch(
            "api.app.services.explanations.load_project_env",
            return_value={"EXPLANATION_MODE": "template"},
        ),
    ):
        response = client.post(
            f"/v1/sites/{selected.site_id}/explanation",
            json={"candidate_id": selected.id, "budget_usd": 500_000},
        )

    assert response.status_code == 200
    explanation = GroundedExplanation.model_validate(response.json())
    assert explanation.mode == "template"
    assert explanation.candidate_id == selected.id
    assert explanation.why_selected == tuple(
        evidence.statement for evidence in selected.evidence
    )
    assert f"{selected.benefit_score:.3f}" in explanation.summary
    assert "does not predict a site temperature reduction" in explanation.limitations[0]
    assert submit_heatmap.await_count == 0
    assert fetch_usage.await_count == 0

    not_selected = next(
        candidate
        for candidate in candidates.candidates
        if candidate.id not in portfolio.selected_candidate_ids
    )
    rejected = client.post(
        f"/v1/sites/{not_selected.site_id}/explanation",
        json={"candidate_id": not_selected.id, "budget_usd": 500_000},
    )
    assert rejected.status_code == 409
    assert "is not selected" in rejected.json()["detail"]
