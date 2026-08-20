"""Tests for the hard-reserve FortyGuard credit governor and ledger."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.app.fortyguard_models import ActivityLifecycle, FortyGuardEndpoint
from api.app.services.credits import (
    CreditGovernor,
    CreditLedger,
    CreditReserveError,
    CreditSettings,
    DuplicateCreditRequestError,
    LiveModeDisabledError,
    UnknownEndpointCostError,
)

NOW = datetime(2026, 8, 20, 12, tzinfo=UTC)
FIRST_HASH = "a" * 64
SECOND_HASH = "b" * 64


def test_live_mode_defaults_off_and_reserve_cannot_be_weakened(tmp_path: Path) -> None:
    settings = CreditSettings.from_env({})
    governor = CreditGovernor(settings, CreditLedger(tmp_path / "ledger.json"))

    assert settings.live is False
    assert settings.credit_total == 2_000_000
    assert settings.credit_reserve == 500_000
    with pytest.raises(LiveModeDisabledError, match="FORTYGUARD_LIVE=0"):
        governor.authorize_estimate(
            request_hashes=(FIRST_HASH,),
            current_usage=0,
            estimated_unit_cost=1,
        )
    with pytest.raises(ValidationError, match="greater than or equal to 500000"):
        CreditSettings(live=True, credit_reserve=499_999)
    with pytest.raises(ValueError, match="exactly 0 or 1"):
        CreditSettings.from_env({"FORTYGUARD_LIVE": "true"})


def test_governor_allows_reserve_floor_and_rejects_one_credit_below_it(
    tmp_path: Path,
) -> None:
    governor = CreditGovernor(
        CreditSettings(live=True),
        CreditLedger(tmp_path / "ledger.json"),
    )

    authorization = governor.authorize_estimate(
        request_hashes=(FIRST_HASH,),
        current_usage=1_400_000,
        estimated_unit_cost=100_000,
    )

    assert authorization.remaining_after == 500_000
    with pytest.raises(CreditReserveError, match="499999"):
        governor.authorize_estimate(
            request_hashes=(SECOND_HASH,),
            current_usage=1_400_000,
            estimated_unit_cost=100_001,
        )


def test_ledger_persists_measured_delta_and_drives_conservative_batch(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger = CreditLedger(ledger_path)
    ledger.record_submission(
        timestamp=NOW,
        request_hash=FIRST_HASH,
        endpoint=FortyGuardEndpoint.HEATMAP,
        request_summary={"analytic_type": "tcm", "granularity": 100},
        usage_before=100_000,
        activity_id="heatmap-ledger-001",
    )
    completed = ledger.record_outcome(
        activity_id="heatmap-ledger-001",
        status=ActivityLifecycle.COMPLETED,
        usage_after=112_345,
        timestamp=NOW,
    )

    reloaded = CreditLedger(ledger_path)
    assert completed.observed_cost == 12_345
    assert reloaded.conservative_observed_cost(FortyGuardEndpoint.HEATMAP) == 12_345
    assert (
        reloaded.record_outcome(
            activity_id="heatmap-ledger-001",
            status=ActivityLifecycle.COMPLETED,
            usage_after=112_345,
            timestamp=NOW,
        )
        == completed
    )
    with pytest.raises(ValueError, match="cannot be changed"):
        reloaded.record_outcome(
            activity_id="heatmap-ledger-001",
            status=ActivityLifecycle.FAILED,
            usage_after=112_345,
            timestamp=NOW,
        )

    governor = CreditGovernor(CreditSettings(live=True), reloaded)
    authorization = governor.authorize_observed_batch(
        endpoint=FortyGuardEndpoint.HEATMAP,
        request_hashes=(SECOND_HASH, "c" * 64),
        current_usage=112_345,
    )

    assert authorization.estimated_unit_cost == 12_345
    assert authorization.projected_cost == 24_690
    with pytest.raises(DuplicateCreditRequestError, match="already submitted or complete"):
        governor.authorize_estimate(
            request_hashes=(FIRST_HASH,),
            current_usage=112_345,
            estimated_unit_cost=12_345,
        )


def test_failed_activity_requires_measured_after_usage_but_not_batch_cost(
    tmp_path: Path,
) -> None:
    ledger = CreditLedger(tmp_path / "ledger.json")
    ledger.record_submission(
        timestamp=NOW,
        request_hash=FIRST_HASH,
        endpoint=FortyGuardEndpoint.SATELLITE,
        request_summary={"probe": True},
        usage_before=25,
        activity_id="satellite-ledger-001",
    )
    failed = ledger.record_outcome(
        activity_id="satellite-ledger-001",
        status=ActivityLifecycle.FAILED,
        usage_after=25,
        timestamp=NOW,
    )

    assert failed.observed_cost == 0
    with pytest.raises(UnknownEndpointCostError, match="no completed cost observation"):
        ledger.conservative_observed_cost(FortyGuardEndpoint.SATELLITE)
