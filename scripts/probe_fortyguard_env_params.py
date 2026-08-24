"""Run or resume one governed environmental-parameters capability probe."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shapely.geometry import Point, shape

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    ActivityLifecycle,
    EnvironmentalParametersRequest,
    EnvironmentalParametersResult,
    FortyGuardEndpoint,
)
from api.app.services.candidates import Candidate, load_candidates
from api.app.services.credits import CreditGovernor, CreditLedger, CreditSettings
from api.app.services.feature_table import load_feature_table
from api.app.services.fortyguard import FortyGuardClient, canonical_request_hash
from api.app.services.heatmap_data import load_heatmap_artifact
from api.app.services.optimizer import optimize_portfolio
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

JOURNAL_PATH = RAW_ROOT / "env_params_probe_journal.json"
REPORT_PATH = ROOT / "data" / "processed" / "fortyguard_env_params_probe.json"
PORTFOLIO_BUDGET_USD = 1_000_000


class EnvironmentalProbeReport(BaseModel):
    """Secret-free probe result with request, response, and credit provenance."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    measured_at: datetime
    endpoint: Literal["env_params"] = "env_params"
    request_hash: str = Field(pattern=SHA256_PATTERN)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    pilot: Literal["Pacoima, Los Angeles"] = "Pacoima, Los Angeles"
    portfolio_budget_usd: Literal[1_000_000] = 1_000_000
    candidate_id: str
    site_id: str
    site_name: str
    tile_id: str
    request: EnvironmentalParametersRequest
    status: Literal["Completed", "Failed"]
    result: EnvironmentalParametersResult | None = None
    usage_before: int = Field(ge=0)
    usage_after: int = Field(ge=0)
    observed_credit_delta: int = Field(ge=0)
    total_allocation: int = Field(default=2_000_000, ge=500_001, le=2_000_000)
    hard_reserve: int = Field(default=500_000, ge=500_000)
    remaining_after: int = Field(ge=500_000)
    source_url: Literal["https://api.fortyguard.com/v1/env_params"] = (
        "https://api.fortyguard.com/v1/env_params"
    )
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result_and_credits(self) -> Self:
        if (self.status == "Completed") != (self.result is not None):
            raise ValueError("only a completed probe may include an environmental result")
        if self.usage_after < self.usage_before:
            raise ValueError("usage cannot decrease during a probe")
        if self.observed_credit_delta != self.usage_after - self.usage_before:
            raise ValueError("observed delta does not match the usage counters")
        if self.remaining_after != self.total_allocation - self.usage_after:
            raise ValueError("remaining credits do not match allocation minus usage")
        if self.remaining_after < self.hard_reserve:
            raise ValueError("probe breached the hard reserve")
        return self


def select_probe_candidate() -> Candidate:
    """Select the highest-impact member of the deterministic $1M portfolio."""

    candidates = load_candidates().candidates
    portfolio = optimize_portfolio(PORTFOLIO_BUDGET_USD, candidates=candidates)
    by_id = {candidate.id: candidate for candidate in candidates}
    selected = tuple(by_id[candidate_id] for candidate_id in portfolio.selected_candidate_ids)
    return min(
        selected,
        key=lambda candidate: (
            -(candidate.benefit_score * candidate.feasibility_score * candidate.confidence),
            candidate.id,
        ),
    )


def build_env_params_probe_request(
    candidate: Candidate | None = None,
) -> EnvironmentalParametersRequest:
    """Build one point request aligned to the candidate's active TCM observation."""

    selected = candidate or select_probe_candidate()
    geometry = shape(selected.geometry.model_dump(mode="json"))
    point = cast(
        Point,
        geometry if geometry.geom_type == "Point" else geometry.representative_point(),
    )
    feature_by_id = {tile.tile_id: tile for tile in load_feature_table().tiles}
    tile = feature_by_id[selected.tile_id]
    tcm = next(
        layer for layer in load_heatmap_artifact().layers if layer.analytic_type == "tcm"
    )
    return EnvironmentalParametersRequest(
        latitude=point.y,
        longitude=point.x,
        temperature=tile.heat.average_temperature_c,
        date_time=tcm.date_time,
    )


async def probe_env_params() -> EnvironmentalProbeReport:
    """Submit at most once, poll the same activity, and persist the exact result."""

    candidate = select_probe_candidate()
    request = build_env_params_probe_request(candidate)
    request_hash = canonical_request_hash(FortyGuardEndpoint.ENV_PARAMS, request)
    if REPORT_PATH.exists():
        report = EnvironmentalProbeReport.model_validate_json(
            REPORT_PATH.read_text(encoding="utf-8")
        )
        if report.request_hash != request_hash:
            raise RuntimeError("committed env-params probe belongs to another request")
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
            spendable_credits = usage.remaining_credits - settings.credit_reserve
            CreditGovernor(settings, ledger).authorize_estimate(
                request_hashes=(request_hash,),
                current_usage=usage.used_credits,
                estimated_unit_cost=spendable_credits,
            )
            journal = MeasurementJournal(
                request_hash=request_hash,
                usage_before=usage.used_credits,
                prepared_at=datetime.now(UTC),
            )
            write_model(JOURNAL_PATH, journal)

        if journal.submission_attempted and not cached_request_exists(request_hash):
            raise RuntimeError(
                "a prior env-params submission has no cached activity; refusing to resubmit"
            )
        if not journal.submission_attempted:
            journal = journal.model_copy(update={"submission_attempted": True})
            write_model(JOURNAL_PATH, journal)

        handle = await client.submit_env_params(request)
        entry = ledger.record_submission(
            timestamp=journal.prepared_at,
            request_hash=request_hash,
            endpoint=FortyGuardEndpoint.ENV_PARAMS,
            request_summary={
                "pilot": "Pacoima, Los Angeles",
                "portfolio_budget_usd": PORTFOLIO_BUDGET_USD,
                "candidate_id": candidate.id,
                "site_id": candidate.site_id,
                "site_name": candidate.site_name,
                "tile_id": candidate.tile_id,
                "latitude": request.latitude,
                "longitude": request.longitude,
                "temperature_c": request.temperature,
                "start_date": request.date_time.start_date.isoformat(),
                "start_time": request.date_time.start_time.strftime("%H:%M")
                if request.date_time.start_time
                else None,
                "filter_type": request.date_time.filter_type,
            },
            usage_before=journal.usage_before,
            activity_id=handle.activity_id,
        )
    else:
        handle = await client.submit_env_params(request)

    result: EnvironmentalParametersResult | None = None
    if entry.status == ActivityLifecycle.PROCESSING:
        terminal = await client.poll(handle.activity_id)
        if terminal.status == ActivityLifecycle.COMPLETED:
            outcome_status: Literal[
                ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED
            ] = ActivityLifecycle.COMPLETED
            if not isinstance(terminal.result, EnvironmentalParametersResult):
                raise RuntimeError("env-params activity returned an unexpected result type")
            result = terminal.result
        elif terminal.status == ActivityLifecycle.FAILED:
            outcome_status = ActivityLifecycle.FAILED
        else:
            raise RuntimeError("env-params polling returned a non-terminal activity")
        usage_after = await client.fetch_credit_usage()
        if usage_after.total_available_credits != settings.credit_total:
            raise RuntimeError("FortyGuard cycle allocation changed during env-params probe")
        if usage_after.remaining_credits < settings.credit_reserve:
            raise RuntimeError("env-params probe breached the hard reserve")
        entry = ledger.record_outcome(
            activity_id=handle.activity_id,
            status=outcome_status,
            usage_after=usage_after.used_credits,
            timestamp=datetime.now(UTC),
        )
    elif entry.status == ActivityLifecycle.COMPLETED:
        terminal = await client.get_status(handle.activity_id)
        if not isinstance(terminal.result, EnvironmentalParametersResult):
            raise RuntimeError("cached env-params activity has an unexpected result type")
        result = terminal.result

    if entry.status not in {ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED}:
        raise RuntimeError("env-params probe did not reach a terminal state")
    if entry.usage_after is None or entry.observed_cost is None or entry.updated_at is None:
        raise RuntimeError("env-params probe is missing terminal credit counters")

    report = EnvironmentalProbeReport(
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
            "Point-level environmental context is not a medical-risk score or a "
            "guaranteed intervention outcome.",
            "The request enriches one deterministic finalist and does not characterize "
            "every Pacoima site.",
        ),
    )
    write_model(REPORT_PATH, report)
    return report


def main() -> None:
    report = asyncio.run(probe_env_params())
    print(
        f"{report.status}: site={report.site_name} delta={report.observed_credit_delta} "
        f"usage={report.usage_before}->{report.usage_after} "
        f"remaining={report.remaining_after} hash={report.request_hash}"
    )


if __name__ == "__main__":
    main()
