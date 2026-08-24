"""Run or resume one governed Pacoima time-of-measure credit measurement."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal

from api.app.fortyguard_models import (
    ActivityLifecycle,
    DateTimeRequest,
    FortyGuardEndpoint,
    HeatmapRequest,
)
from api.app.services.credits import CreditGovernor, CreditLedger, CreditSettings
from api.app.services.fortyguard import FortyGuardClient, canonical_request_hash
from scripts.measure_fortyguard_heatmap import (
    CACHE_ROOT,
    LEDGER_PATH,
    RAW_ROOT,
    ROOT,
    MeasurementJournal,
    MeasurementReport,
    build_request,
    cached_request_exists,
    load_heatmap_config,
    load_journal,
    load_project_env,
    write_model,
)

JOURNAL_PATH = RAW_ROOT / "time_of_measure_measurement_journal.json"
REPORT_PATH = ROOT / "data" / "processed" / "fortyguard_time_of_measure_credit_measurement.json"


def build_time_of_measure_request() -> HeatmapRequest:
    """Find the UTC peak-temperature hour for each tile on the frozen hot day."""

    config = load_heatmap_config()
    return build_request().model_copy(
        update={
            "date_time": DateTimeRequest(start_date=config.start_date, filter_type=3),
            "analytic_type": "time_of_measure",
        }
    )


async def measure_time_of_measure() -> MeasurementReport:
    """Submit at most once, poll the same activity, and record its credit delta."""

    request = build_time_of_measure_request()
    request_hash = canonical_request_hash(FortyGuardEndpoint.HEATMAP, request)
    if REPORT_PATH.exists():
        report = MeasurementReport.model_validate_json(
            REPORT_PATH.read_text(encoding="utf-8")
        )
        if report.request_hash != request_hash:
            raise RuntimeError("committed time-of-measure report belongs to another request")
        return report

    env = load_project_env(ROOT / ".env")
    settings = CreditSettings.from_env(env)
    client = FortyGuardClient(
        api_key=env.get("FORTYGUARD_API_KEY", ""),
        cache_root=CACHE_ROOT,
    )
    ledger = CreditLedger(LEDGER_PATH)
    entry = ledger.find_request(request_hash)
    journal = load_journal(request_hash, JOURNAL_PATH)

    if entry is None:
        if journal is None:
            usage = await client.fetch_credit_usage()
            if usage.total_available_credits != settings.credit_total:
                raise RuntimeError(
                    "FortyGuard cycle allocation does not match FORTYGUARD_CREDIT_TOTAL"
                )
            CreditGovernor(settings, ledger).authorize_observed_batch(
                endpoint=FortyGuardEndpoint.HEATMAP,
                request_hashes=(request_hash,),
                current_usage=usage.used_credits,
            )
            journal = MeasurementJournal(
                request_hash=request_hash,
                usage_before=usage.used_credits,
                prepared_at=datetime.now(UTC),
            )
            write_model(JOURNAL_PATH, journal)

        if journal.submission_attempted and not cached_request_exists(request_hash):
            raise RuntimeError(
                "a prior time-of-measure submission has no cached activity; refusing to resubmit"
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
                "analytic_type": "time_of_measure",
                "granularity_m": request.granularity,
                "filter_type": request.date_time.filter_type,
                "start_date": request.date_time.start_date.isoformat(),
                "area_sq_mi": 7.763214,
                "timezone": "UTC",
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
            raise RuntimeError("time-of-measure polling returned a non-terminal activity")
        usage_after = await client.fetch_credit_usage()
        if usage_after.total_available_credits != settings.credit_total:
            raise RuntimeError(
                "FortyGuard cycle allocation changed during time-of-measure measurement"
            )
        if usage_after.remaining_credits < settings.credit_reserve:
            raise RuntimeError("time-of-measure measurement breached the hard reserve")
        entry = ledger.record_outcome(
            activity_id=handle.activity_id,
            status=outcome_status,
            usage_after=usage_after.used_credits,
            timestamp=datetime.now(UTC),
        )

    if entry.status not in {ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED}:
        raise RuntimeError("time-of-measure measurement did not reach a terminal state")
    if entry.usage_after is None or entry.observed_cost is None or entry.updated_at is None:
        raise RuntimeError("time-of-measure measurement is missing terminal credit counters")

    report = MeasurementReport(
        measured_at=entry.updated_at,
        request_hash=entry.request_hash,
        activity_id=entry.activity_id,
        request=entry.request_summary,
        status="Completed" if entry.status == ActivityLifecycle.COMPLETED else "Failed",
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
    report = asyncio.run(measure_time_of_measure())
    print(
        f"{report.status}: delta={report.observed_credit_delta} "
        f"usage={report.usage_before}->{report.usage_after} "
        f"remaining={report.remaining_after} hash={report.request_hash}"
    )


if __name__ == "__main__":
    main()
