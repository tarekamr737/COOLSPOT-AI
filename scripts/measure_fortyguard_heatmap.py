"""Run or resume the one authorized FortyGuard heatmap credit measurement."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    ActivityLifecycle,
    DateTimeRequest,
    FortyGuardEndpoint,
    HeatmapRequest,
    PolygonAoi,
)
from api.app.services.credits import CreditGovernor, CreditLedger, CreditSettings
from api.app.services.fortyguard import FortyGuardClient, canonical_request_hash

ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = ROOT / "data" / "processed" / "pacoima_aoi.geojson"
RAW_ROOT = ROOT / "data" / "raw" / "fortyguard"
CACHE_ROOT = RAW_ROOT / "cache"
LEDGER_PATH = RAW_ROOT / "credit_ledger.json"
JOURNAL_PATH = RAW_ROOT / "tcm_measurement_journal.json"
REPORT_PATH = ROOT / "data" / "processed" / "fortyguard_credit_measurements.json"


class MeasurementJournal(BaseModel):
    """Crash-safe marker preventing an uncertain submission from being repeated."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    request_hash: str = Field(pattern=SHA256_PATTERN)
    usage_before: int = Field(ge=0)
    prepared_at: datetime
    submission_attempted: bool = False


class MeasurementReport(BaseModel):
    """Committed, secret-free proof of the observed live credit delta."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    measured_at: datetime
    endpoint: Literal["heatmap"] = "heatmap"
    request_hash: str = Field(pattern=SHA256_PATTERN)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    request: dict[str, JsonValue]
    status: Literal["Completed", "Failed"]
    usage_before: int = Field(ge=0)
    usage_after: int = Field(ge=0)
    observed_credit_delta: int = Field(ge=0)
    total_allocation: int = Field(default=2_000_000, ge=500_001, le=2_000_000)
    hard_reserve: int = Field(default=500_000, ge=500_000)
    remaining_after: int = Field(ge=500_000)

    @model_validator(mode="after")
    def validate_credit_arithmetic(self) -> Self:
        if self.usage_after < self.usage_before:
            raise ValueError("usage cannot decrease during a measurement")
        if self.observed_credit_delta != self.usage_after - self.usage_before:
            raise ValueError("observed delta does not match the usage counters")
        if self.remaining_after != self.total_allocation - self.usage_after:
            raise ValueError("remaining credits do not match allocation minus usage")
        if self.remaining_after < self.hard_reserve:
            raise ValueError("measurement breached the hard reserve")
        return self


def load_project_env(path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE settings, with process variables taking precedence."""

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ)
    return values


def build_request() -> HeatmapRequest:
    """Build the one-hour, 100 m Pacoima TCM request used for measurement and demo data."""

    aoi = PolygonAoi.model_validate_json(AOI_PATH.read_text(encoding="utf-8"))
    return HeatmapRequest(
        polygon_aoi=aoi,
        date_time=DateTimeRequest(
            start_date=date(2024, 7, 15),
            start_time=time(14),
            filter_type=1,
        ),
        granularity=100,
        analytic_type="tcm",
    )


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    temporary_path = path.with_suffix(f"{path.suffix}.part")
    temporary_path.write_text(payload, encoding="utf-8")
    os.replace(temporary_path, path)


def load_journal(request_hash: str) -> MeasurementJournal | None:
    if not JOURNAL_PATH.exists():
        return None
    journal = MeasurementJournal.model_validate_json(JOURNAL_PATH.read_text(encoding="utf-8"))
    if journal.request_hash != request_hash:
        raise RuntimeError("measurement journal belongs to a different request")
    return journal


def cached_request_exists(request_hash: str) -> bool:
    return (CACHE_ROOT / "requests" / f"{request_hash}.json").exists()


async def measure() -> MeasurementReport:
    env = load_project_env(ROOT / ".env")
    settings = CreditSettings.from_env(env)
    api_key = env.get("FORTYGUARD_API_KEY", "")
    client = FortyGuardClient(api_key=api_key, cache_root=CACHE_ROOT)
    ledger = CreditLedger(LEDGER_PATH)
    governor = CreditGovernor(settings, ledger)
    request = build_request()
    request_hash = canonical_request_hash(FortyGuardEndpoint.HEATMAP, request)
    entry = ledger.find_request(request_hash)
    journal = load_journal(request_hash)

    if entry is None:
        if journal is None:
            usage = await client.fetch_credit_usage()
            if usage.total_available_credits != settings.credit_total:
                raise RuntimeError(
                    "FortyGuard cycle allocation does not match FORTYGUARD_CREDIT_TOTAL"
                )
            spendable = usage.remaining_credits - settings.credit_reserve
            governor.authorize_estimate(
                request_hashes=(request_hash,),
                current_usage=usage.used_credits,
                estimated_unit_cost=spendable,
            )
            journal = MeasurementJournal(
                request_hash=request_hash,
                usage_before=usage.used_credits,
                prepared_at=datetime.now(UTC),
            )
            write_model(JOURNAL_PATH, journal)

        if journal.submission_attempted and not cached_request_exists(request_hash):
            raise RuntimeError(
                "a prior submission attempt has no cached activity; refusing to resubmit"
            )
        if not journal.submission_attempted:
            journal = journal.model_copy(update={"submission_attempted": True})
            write_model(JOURNAL_PATH, journal)

        handle = await client.submit_heatmap(request)
        entry = ledger.record_submission(
            timestamp=journal.prepared_at,
            request_hash=request_hash,
            endpoint=FortyGuardEndpoint.HEATMAP,
            request_summary={
                "pilot": "Pacoima, Los Angeles",
                "analytic_type": "tcm",
                "granularity_m": 100,
                "filter_type": 1,
                "start_date": "2024-07-15",
                "start_time": "14:00",
                "area_sq_mi": 7.763214,
            },
            usage_before=journal.usage_before,
            activity_id=handle.activity_id,
        )
    else:
        handle = await client.submit_heatmap(request)

    if entry.status == ActivityLifecycle.PROCESSING:
        terminal = await client.poll(handle.activity_id)
        if terminal.status == ActivityLifecycle.COMPLETED:
            outcome_status: Literal[
                ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED
            ] = ActivityLifecycle.COMPLETED
        elif terminal.status == ActivityLifecycle.FAILED:
            outcome_status = ActivityLifecycle.FAILED
        else:
            raise RuntimeError("polling returned a non-terminal activity")
        usage_after = await client.fetch_credit_usage()
        if usage_after.total_available_credits != settings.credit_total:
            raise RuntimeError("FortyGuard cycle allocation changed during measurement")
        entry = ledger.record_outcome(
            activity_id=handle.activity_id,
            status=outcome_status,
            usage_after=usage_after.used_credits,
            timestamp=datetime.now(UTC),
        )

    if entry.status not in {ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED}:
        raise RuntimeError("measurement activity did not reach a terminal state")
    if entry.usage_after is None or entry.observed_cost is None or entry.updated_at is None:
        raise RuntimeError("terminal measurement is missing its credit counters")

    report_status: Literal["Completed", "Failed"] = (
        "Completed" if entry.status == ActivityLifecycle.COMPLETED else "Failed"
    )
    report = MeasurementReport(
        measured_at=entry.updated_at,
        request_hash=entry.request_hash,
        activity_id=entry.activity_id,
        request={key: value for key, value in entry.request_summary.items()},
        status=report_status,
        usage_before=entry.usage_before,
        usage_after=entry.usage_after,
        observed_credit_delta=entry.observed_cost,
        total_allocation=settings.credit_total,
        hard_reserve=settings.credit_reserve,
        remaining_after=settings.credit_total - entry.usage_after,
    )
    write_model(REPORT_PATH, report)
    return report


def main() -> None:
    report = asyncio.run(measure())
    print(
        f"{report.status}: delta={report.observed_credit_delta} "
        f"usage={report.usage_before}->{report.usage_after} "
        f"remaining={report.remaining_after} hash={report.request_hash}"
    )


if __name__ == "__main__":
    main()
