"""Regression tests for the controlled live-measurement request and artifact."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from api.app.fortyguard_models import FortyGuardEndpoint
from api.app.services.fortyguard import canonical_request_hash
from scripts.measure_fortyguard_heatmap import (
    REPORT_PATH,
    MeasurementReport,
    build_request,
)

EXPECTED_REQUEST_HASH = "b10fe0b3fd039fa01ccce197f0aaa8167c3c51f6dfce1b0678a363a39fa8fdd7"


def test_live_measurement_uses_exact_single_hour_pacoima_request() -> None:
    request = build_request()

    assert request.analytic_type == "tcm"
    assert request.granularity == 100
    assert request.date_time.filter_type == 1
    assert canonical_request_hash(FortyGuardEndpoint.HEATMAP, request) == EXPECTED_REQUEST_HASH


def test_committed_measurement_is_completed_balanced_and_above_reserve() -> None:
    report = MeasurementReport.model_validate_json(
        Path(REPORT_PATH).read_text(encoding="utf-8")
    )

    assert report.status == "Completed"
    assert report.request_hash == EXPECTED_REQUEST_HASH
    assert report.observed_credit_delta == report.usage_after - report.usage_before
    assert report.remaining_after >= report.hard_reserve

    with pytest.raises(ValidationError, match="observed delta"):
        MeasurementReport.model_validate(
            {
                **report.model_dump(mode="python"),
                "observed_credit_delta": report.observed_credit_delta + 1,
            }
        )
