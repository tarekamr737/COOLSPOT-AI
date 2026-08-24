"""Run or resume the one permitted governed satellite-segmentation probe."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shapely.geometry import Point, shape

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    ActivityLifecycle,
    FortyGuardEndpoint,
    SatelliteCoordinates,
    SatelliteRequest,
    SatelliteResult,
)
from api.app.services.candidates import Candidate, load_candidates
from api.app.services.credits import CreditGovernor, CreditLedger, CreditSettings
from api.app.services.fortyguard import FortyGuardClient, canonical_request_hash
from api.app.services.heatmap_data import load_heatmap_artifact
from api.app.services.interventions import InterventionType
from scripts.measure_fortyguard_heatmap import (
    CACHE_ROOT,
    LEDGER_PATH,
    RAW_ROOT,
    ROOT,
    MeasurementJournal,
    cached_request_exists,
    load_journal,
    load_project_env,
    write_model,
)

JOURNAL_PATH = RAW_ROOT / "satellite_probe_journal.json"
REPORT_PATH = ROOT / "data" / "processed" / "fortyguard_satellite_probe.json"


class SatelliteProbeReport(BaseModel):
    """Secret-free result and credit provenance for the sole satellite probe."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    measured_at: datetime
    endpoint: Literal["satellite"] = "satellite"
    request_hash: str = Field(pattern=SHA256_PATTERN)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    candidate_id: str
    site_id: str
    site_name: str
    tile_id: str
    request: SatelliteRequest
    status: Literal["Completed", "Failed"]
    result: SatelliteResult | None = None
    usage_before: int = Field(ge=0)
    usage_after: int = Field(ge=0)
    observed_credit_delta: int = Field(ge=0)
    total_allocation: int = Field(default=2_000_000, ge=500_001, le=2_000_000)
    hard_reserve: int = Field(default=500_000, ge=500_000)
    remaining_after: int = Field(ge=500_000)
    source_url: Literal["https://api.fortyguard.com/v1/satellite"] = (
        "https://api.fortyguard.com/v1/satellite"
    )
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_outcome(self) -> SatelliteProbeReport:
        if (self.status == "Completed") != (self.result is not None):
            raise ValueError("only a completed satellite probe may include a result")
        if self.observed_credit_delta != self.usage_after - self.usage_before:
            raise ValueError("observed delta does not match usage counters")
        if self.remaining_after != self.total_allocation - self.usage_after:
            raise ValueError("remaining credits do not match allocation minus usage")
        return self


def select_probe_candidate() -> Candidate:
    pavement = tuple(
        candidate
        for candidate in load_candidates().candidates
        if candidate.intervention_type == InterventionType.COOL_PAVEMENT
    )
    if not pavement:
        raise RuntimeError("satellite probe requires a verified pavement candidate")
    return min(
        pavement,
        key=lambda candidate: (
            -candidate.value_explanation.modeled_benefit_score,
            candidate.id,
        ),
    )


def build_satellite_probe_request(candidate: Candidate | None = None) -> SatelliteRequest:
    selected = candidate or select_probe_candidate()
    geometry = shape(selected.geometry.model_dump(mode="json"))
    point: Point = geometry.representative_point()
    tcm = next(
        layer for layer in load_heatmap_artifact().layers if layer.analytic_type == "tcm"
    )
    return SatelliteRequest(
        sat=SatelliteCoordinates(latitude=point.y, longitude=point.x),
        date_time=tcm.date_time,
        granularity=100,
    )


async def probe_satellite() -> SatelliteProbeReport:
    candidate = select_probe_candidate()
    request = build_satellite_probe_request(candidate)
    request_hash = canonical_request_hash(FortyGuardEndpoint.SATELLITE, request)
    if REPORT_PATH.exists():
        report = SatelliteProbeReport.model_validate_json(
            REPORT_PATH.read_text(encoding="utf-8")
        )
        if report.request_hash != request_hash:
            raise RuntimeError("committed satellite probe belongs to another request")
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
                raise RuntimeError("FortyGuard allocation does not match configured total")
            CreditGovernor(settings, ledger).authorize_estimate(
                request_hashes=(request_hash,),
                current_usage=usage.used_credits,
                estimated_unit_cost=usage.remaining_credits - settings.credit_reserve,
            )
            journal = MeasurementJournal(
                request_hash=request_hash,
                usage_before=usage.used_credits,
                prepared_at=datetime.now(UTC),
            )
            write_model(JOURNAL_PATH, journal)
        if journal.submission_attempted and not cached_request_exists(request_hash):
            raise RuntimeError("uncertain prior satellite submission; refusing to resubmit")
        if not journal.submission_attempted:
            journal = journal.model_copy(update={"submission_attempted": True})
            write_model(JOURNAL_PATH, journal)
        handle = await client.submit_satellite(request)
        entry = ledger.record_submission(
            timestamp=journal.prepared_at,
            request_hash=request_hash,
            endpoint=FortyGuardEndpoint.SATELLITE,
            request_summary={
                "candidate_id": candidate.id,
                "site_id": candidate.site_id,
                "tile_id": candidate.tile_id,
                "latitude": request.sat.latitude,
                "longitude": request.sat.longitude,
                "start_date": request.date_time.start_date.isoformat(),
                "granularity": request.granularity,
            },
            usage_before=journal.usage_before,
            activity_id=handle.activity_id,
        )
    else:
        handle = await client.submit_satellite(request)

    result: SatelliteResult | None = None
    if entry.status == ActivityLifecycle.PROCESSING:
        terminal = await client.poll(handle.activity_id)
        if terminal.status == ActivityLifecycle.COMPLETED:
            outcome: Literal[
                ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED
            ] = ActivityLifecycle.COMPLETED
            if not isinstance(terminal.result, SatelliteResult):
                raise RuntimeError("satellite activity returned an unexpected result type")
            result = terminal.result
        elif terminal.status == ActivityLifecycle.FAILED:
            outcome = ActivityLifecycle.FAILED
        else:
            raise RuntimeError("satellite polling returned a non-terminal activity")
        usage_after = await client.fetch_credit_usage()
        if usage_after.remaining_credits < settings.credit_reserve:
            raise RuntimeError("satellite probe breached the hard reserve")
        entry = ledger.record_outcome(
            activity_id=handle.activity_id,
            status=outcome,
            usage_after=usage_after.used_credits,
            timestamp=datetime.now(UTC),
        )
    elif entry.status == ActivityLifecycle.COMPLETED:
        terminal = await client.get_status(handle.activity_id)
        if not isinstance(terminal.result, SatelliteResult):
            raise RuntimeError("cached satellite activity has an unexpected result type")
        result = terminal.result

    if entry.usage_after is None or entry.observed_cost is None or entry.updated_at is None:
        raise RuntimeError("satellite probe is missing terminal credit counters")
    report = SatelliteProbeReport(
        measured_at=entry.updated_at,
        request_hash=entry.request_hash,
        activity_id=entry.activity_id,
        candidate_id=candidate.id,
        site_id=candidate.site_id,
        site_name=candidate.site_name,
        tile_id=candidate.tile_id,
        request=request,
        status="Completed" if entry.status == ActivityLifecycle.COMPLETED else "Failed",
        result=result,
        usage_before=entry.usage_before,
        usage_after=entry.usage_after,
        observed_credit_delta=entry.observed_cost,
        total_allocation=settings.credit_total,
        hard_reserve=settings.credit_reserve,
        remaining_after=settings.credit_total - entry.usage_after,
        limitations=(
            "Satellite segmentation is dated overhead context, not field verification of "
            "surface condition, ownership, traction, glare, drainage, or product compatibility.",
            "The one permitted probe covers only the deterministic top pavement candidate.",
        ),
    )
    write_model(REPORT_PATH, report)
    return report


def main() -> None:
    report = asyncio.run(probe_satellite())
    print(
        f"{report.status}: site={report.site_name} delta={report.observed_credit_delta} "
        f"usage={report.usage_before}->{report.usage_after} "
        f"remaining={report.remaining_after} hash={report.request_hash}"
    )


if __name__ == "__main__":
    main()
