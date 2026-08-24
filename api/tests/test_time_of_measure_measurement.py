"""Offline checks for the one-request time-of-measure measurement workflow."""

import asyncio
from pathlib import Path

from api.app.fortyguard_models import FortyGuardEndpoint
from api.app.services.credits import CreditSettings
from api.app.services.fortyguard import canonical_request_hash
from scripts.measure_fortyguard_heatmap import MeasurementReport
from scripts.measure_fortyguard_time_of_measure import (
    REPORT_PATH,
    build_time_of_measure_request,
    measure_time_of_measure,
)

EXPECTED_REQUEST_HASH = "393a609d34ae19d5124b911b0e2d94d6c59409976357519b301b88bc5da56991"


def test_time_of_measure_measurement_is_aligned_and_credit_governed() -> None:
    request = build_time_of_measure_request()

    assert request.analytic_type == "time_of_measure"
    assert request.date_time.filter_type == 3
    assert request.date_time.start_date.isoformat() == "2024-07-15"
    assert request.granularity == 100
    assert canonical_request_hash(FortyGuardEndpoint.HEATMAP, request) == (
        EXPECTED_REQUEST_HASH
    )
    assert CreditSettings().credit_reserve == 500_000


def test_real_time_of_measure_is_balanced_cached_and_above_reserve() -> None:
    report_text = Path(REPORT_PATH).read_text(encoding="utf-8")
    report = MeasurementReport.model_validate_json(report_text)

    assert report.status == "Completed"
    assert report.request_hash == EXPECTED_REQUEST_HASH
    assert report.activity_id == "eaa617ad-07b3-47db-9094-faa26c8eeb79"
    assert report.observed_credit_delta == 4_220
    assert report.usage_before == 193_100
    assert report.usage_after == 197_320
    assert report.remaining_after == 1_802_680
    assert report.remaining_after >= report.hard_reserve
    assert report.request["analytic_type"] == "time_of_measure"
    assert report.request["timezone"] == "UTC"
    assert "api_key" not in report_text.lower()
    assert asyncio.run(measure_time_of_measure()) == report
