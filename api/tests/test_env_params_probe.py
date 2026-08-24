"""Offline checks for the one-request environmental-parameters probe."""

import asyncio

from api.app.fortyguard_models import FortyGuardEndpoint
from api.app.services.fortyguard import canonical_request_hash
from scripts.probe_fortyguard_env_params import (
    PORTFOLIO_BUDGET_USD,
    REPORT_PATH,
    EnvironmentalProbeReport,
    build_env_params_probe_request,
    probe_env_params,
    select_probe_candidate,
)


def test_env_params_probe_is_minimal_aligned_and_deterministic() -> None:
    candidate = select_probe_candidate()
    request = build_env_params_probe_request(candidate)

    assert PORTFOLIO_BUDGET_USD == 1_000_000
    assert candidate.id == "shade_structure:metro-stop:6788"
    assert candidate.site_name == "Van Nuys / Herrick"
    assert candidate.tile_id == "1355"
    assert request.latitude == 34.271105
    assert request.longitude == -118.414991
    assert request.temperature == 35.9398
    assert request.date_time.start_date.isoformat() == "2026-08-20"
    assert request.date_time.start_time is not None
    assert request.date_time.start_time.strftime("%H:%M") == "14:00"
    assert request.date_time.filter_type == 1
    assert canonical_request_hash(FortyGuardEndpoint.ENV_PARAMS, request) == (
        canonical_request_hash(
            FortyGuardEndpoint.ENV_PARAMS,
            build_env_params_probe_request(select_probe_candidate()),
        )
    )


def test_real_env_params_probe_is_completed_cached_and_above_reserve() -> None:
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    report = EnvironmentalProbeReport.model_validate_json(report_text)

    assert report.status == "Completed"
    assert report.result is not None
    assert len(report.result.locations) == 1
    assert len(report.result.metadata.timestamps) == 1
    assert report.remaining_after >= report.hard_reserve
    assert "api_key" not in report_text.lower()
    assert asyncio.run(probe_env_params()) == report
