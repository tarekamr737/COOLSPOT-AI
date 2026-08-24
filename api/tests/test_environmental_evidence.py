"""Tests for the intentionally narrow environmental evidence contract."""

from api.app.services.environmental_evidence import (
    EnvironmentalMetricId,
    EnvironmentalMetricSource,
    load_environmental_evidence_config,
)
from scripts.probe_fortyguard_env_params import REPORT_PATH, EnvironmentalProbeReport


def test_exactly_three_approved_metrics_exist_in_the_live_response() -> None:
    config = load_environmental_evidence_config()
    report = EnvironmentalProbeReport.model_validate_json(
        REPORT_PATH.read_text(encoding="utf-8")
    )
    assert report.result is not None
    location = report.result.locations[0]

    assert len(config.metrics) == 3
    assert {metric.id for metric in config.metrics} == set(EnvironmentalMetricId)
    for metric in config.metrics:
        if metric.source == EnvironmentalMetricSource.PARAMETERS:
            assert metric.vendor_key in location.parameters
        else:
            clear_sky = location.solar_irradiance.get("clear_sky")
            assert isinstance(clear_sky, dict)
            assert metric.vendor_key in clear_sky


def test_promoted_metrics_do_not_claim_health_or_intervention_outcomes() -> None:
    config = load_environmental_evidence_config()
    combined = " ".join(
        f"{metric.planning_context} {metric.limitation}" for metric in config.metrics
    ).lower()

    assert "medical-risk classification" in combined
    assert "individual exposure or health effects" in combined
    assert "guaranteed" not in combined
