"""Offline checks for the one-request exceedance measurement workflow."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from api.app.fortyguard_models import (
    ActivityLifecycle,
    CreditUsage,
    FortyGuardEndpoint,
)
from api.app.services.credits import (
    CreditLedger,
    CreditReserveError,
    CreditSettings,
)
from api.app.services.fortyguard import canonical_request_hash
from scripts import measure_fortyguard_exceedance as measurement
from scripts.measure_fortyguard_exceedance import (
    REPORT_PATH,
    build_exceedance_request,
    measure_exceedance,
)
from scripts.measure_fortyguard_heatmap import (
    MeasurementReport,
)

EXPECTED_REQUEST_HASH = "01b10110a2455dd1c8a33769eca3b1d9eb2ee1949d4e626cb4236a28907d7a58"


def test_exceedance_measurement_is_aligned_and_credit_estimable() -> None:
    request = build_exceedance_request()
    request_hash = canonical_request_hash(FortyGuardEndpoint.HEATMAP, request)

    assert request.analytic_type == "exceedance"
    assert request.date_time.filter_type == 3
    assert request.granularity == 100
    assert request.threshold == 30
    assert request.direction == "above"
    assert request_hash == EXPECTED_REQUEST_HASH
    assert CreditSettings().credit_reserve == 500_000


def test_real_exceedance_measurement_is_balanced_cached_and_above_reserve() -> None:
    report_text = Path(REPORT_PATH).read_text(encoding="utf-8")
    report = MeasurementReport.model_validate_json(report_text)

    assert report.status == "Completed"
    assert report.request_hash == EXPECTED_REQUEST_HASH
    assert report.observed_credit_delta == 4_220
    assert report.usage_before == 188_880
    assert report.usage_after == 193_100
    assert report.remaining_after == 1_806_900
    assert report.remaining_after >= report.hard_reserve
    assert report.request["analytic_type"] == "exceedance"
    assert report.request["threshold_c"] == 30.0
    assert "api_key" not in report_text.lower()
    assert asyncio.run(measure_exceedance()) == report


def test_exceedance_measurement_aborts_before_submission_at_reserve_breach(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger = CreditLedger(ledger_path)
    ledger.record_submission(
        timestamp=datetime(2026, 8, 24, tzinfo=UTC),
        request_hash="a" * 64,
        endpoint=FortyGuardEndpoint.HEATMAP,
        request_summary={"analytic_type": "exceedance"},
        usage_before=0,
        activity_id="observed-heatmap-cost",
    )
    ledger.record_outcome(
        activity_id="observed-heatmap-cost",
        status=ActivityLifecycle.COMPLETED,
        usage_after=4_220,
        timestamp=datetime(2026, 8, 24, tzinfo=UTC),
    )

    client = AsyncMock()
    client.fetch_credit_usage.return_value = CreditUsage(
        total_available_credits=2_000_000,
        used_credits=1_495_781,
        remaining_credits=504_219,
    )
    journal_path = tmp_path / "journal.json"
    monkeypatch.setattr(measurement, "REPORT_PATH", tmp_path / "missing-report.json")
    monkeypatch.setattr(measurement, "LEDGER_PATH", ledger_path)
    monkeypatch.setattr(measurement, "JOURNAL_PATH", journal_path)
    monkeypatch.setattr(
        measurement,
        "load_project_env",
        lambda _path: {
            "FORTYGUARD_API_KEY": "test-key",
            "FORTYGUARD_LIVE": "1",
            "FORTYGUARD_CREDIT_TOTAL": "2000000",
            "FORTYGUARD_CREDIT_RESERVE": "500000",
        },
    )
    monkeypatch.setattr(measurement, "FortyGuardClient", lambda **_kwargs: client)

    with pytest.raises(CreditReserveError, match="499999.*reserve 500000"):
        asyncio.run(measurement.measure_exceedance())

    client.submit_heatmap.assert_not_awaited()
    assert not journal_path.exists()
    assert ledger.find_request(EXPECTED_REQUEST_HASH) is None
