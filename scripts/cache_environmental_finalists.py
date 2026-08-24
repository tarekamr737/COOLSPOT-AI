"""Cache one-hour environmental responses for deterministic Pacoima finalists."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    ActivityLifecycle,
    EnvironmentalParametersRequest,
    EnvironmentalParametersResult,
    FortyGuardEndpoint,
    PollingPolicy,
)
from api.app.services.candidates import Candidate, load_candidates
from api.app.services.credits import CreditGovernor, CreditLedger, CreditSettings
from api.app.services.fortyguard import FortyGuardClient, canonical_request_hash
from api.app.services.optimizer import optimize_portfolio
from scripts.measure_fortyguard_heatmap import (
    CACHE_ROOT,
    LEDGER_PATH,
    RAW_ROOT,
    ROOT,
    MeasurementJournal,
    cached_request_exists,
    load_project_env,
    write_model,
)
from scripts.probe_fortyguard_env_params import (
    MAX_ENVIRONMENTAL_FINALISTS,
    OBSERVED_ENV_PARAMS_UNIT_COST,
    PORTFOLIO_BUDGET_USD,
    REPORT_PATH,
    EnvironmentalProbeReport,
    build_env_params_probe_request,
)

OUTPUT_DIR = ROOT / "data" / "processed" / "pacoima_environmental_sites"
JOURNAL_DIR = RAW_ROOT / "env_params_finalist_journals"


class FinalistEnvironmentalArtifact(BaseModel):
    """Exact completed response for one deterministic finalist."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    pilot: Literal["Pacoima, Los Angeles"] = "Pacoima, Los Angeles"
    portfolio_budget_usd: Literal[1_000_000] = 1_000_000
    finalist_rank: int = Field(ge=1, le=MAX_ENVIRONMENTAL_FINALISTS)
    candidate_id: str
    site_id: str
    site_name: str
    tile_id: str
    request_hash: str = Field(pattern=SHA256_PATTERN)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    retrieved_at: datetime
    request: EnvironmentalParametersRequest
    result: EnvironmentalParametersResult
    usage_before: int = Field(ge=0)
    usage_after: int = Field(ge=0)
    observed_credit_delta: int = Field(ge=0)
    credits_remaining: int = Field(ge=500_000)
    source_url: Literal["https://api.fortyguard.com/v1/env_params"] = (
        "https://api.fortyguard.com/v1/env_params"
    )

    @model_validator(mode="after")
    def validate_credits(self) -> Self:
        if self.usage_after < self.usage_before:
            raise ValueError("environmental usage cannot decrease")
        if self.observed_credit_delta != self.usage_after - self.usage_before:
            raise ValueError("environmental observed cost does not match usage counters")
        if self.credits_remaining != CreditSettings().credit_total - self.usage_after:
            raise ValueError("environmental remaining credits do not balance")
        return self


def select_environmental_finalists() -> tuple[Candidate, ...]:
    """Return the highest-impact ten members of the deterministic $1M portfolio."""

    candidates = load_candidates().candidates
    by_id = {candidate.id: candidate for candidate in candidates}
    portfolio = optimize_portfolio(PORTFOLIO_BUDGET_USD, candidates=candidates)
    selected = (by_id[candidate_id] for candidate_id in portfolio.selected_candidate_ids)
    ordered = sorted(
        selected,
        key=lambda candidate: (
            -(candidate.benefit_score * candidate.feasibility_score * candidate.confidence),
            candidate.id,
        ),
    )
    return tuple(ordered[:MAX_ENVIRONMENTAL_FINALISTS])


def output_path(site_id: str) -> Path:
    return OUTPUT_DIR / f"{site_id.replace(':', '__')}.json"


def load_cached_artifact(candidate: Candidate) -> FinalistEnvironmentalArtifact | None:
    path = output_path(candidate.site_id)
    if not path.exists():
        return None
    artifact = FinalistEnvironmentalArtifact.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    request = build_env_params_probe_request(candidate)
    expected_hash = canonical_request_hash(FortyGuardEndpoint.ENV_PARAMS, request)
    if artifact.candidate_id != candidate.id or artifact.request_hash != expected_hash:
        raise RuntimeError(f"cached environmental artifact mismatches {candidate.site_id}")
    return artifact


def seed_probe_artifact(finalists: tuple[Candidate, ...]) -> None:
    """Promote the completed one-site probe into the finalist artifact set."""

    if not REPORT_PATH.exists():
        raise RuntimeError("completed environmental probe report is required")
    report = EnvironmentalProbeReport.model_validate_json(
        REPORT_PATH.read_text(encoding="utf-8")
    )
    if report.status != "Completed" or report.result is None:
        raise RuntimeError("environmental probe did not complete successfully")
    candidate = next(
        (item for item in finalists if item.id == report.candidate_id), None
    )
    if candidate is None:
        raise RuntimeError("environmental probe site is not in the deterministic finalist set")
    path = output_path(candidate.site_id)
    if path.exists():
        return
    artifact = FinalistEnvironmentalArtifact(
        finalist_rank=finalists.index(candidate) + 1,
        candidate_id=candidate.id,
        site_id=candidate.site_id,
        site_name=candidate.site_name,
        tile_id=candidate.tile_id,
        request_hash=report.request_hash,
        activity_id=report.activity_id,
        retrieved_at=report.measured_at,
        request=report.request,
        result=report.result,
        usage_before=report.usage_before,
        usage_after=report.usage_after,
        observed_credit_delta=report.observed_credit_delta,
        credits_remaining=report.remaining_after,
    )
    write_model(path, artifact)


async def cache_environmental_finalists() -> tuple[FinalistEnvironmentalArtifact, ...]:
    """Submit only uncached finalist requests and preserve the hard reserve."""

    finalists = select_environmental_finalists()
    if len(finalists) > MAX_ENVIRONMENTAL_FINALISTS:
        raise RuntimeError("environmental finalist selection exceeded its hard cap")
    if len({candidate.site_id for candidate in finalists}) != len(finalists):
        raise RuntimeError("environmental finalists must be unique sites")
    seed_probe_artifact(finalists)
    pending = tuple(
        candidate for candidate in finalists if load_cached_artifact(candidate) is None
    )
    if not pending:
        return tuple(
            artifact
            for candidate in finalists
            if (artifact := load_cached_artifact(candidate)) is not None
        )

    env = load_project_env(ROOT / ".env")
    settings = CreditSettings.from_env(env)
    client = FortyGuardClient(
        api_key=env.get("FORTYGUARD_API_KEY", ""),
        cache_root=CACHE_ROOT,
    )
    ledger = CreditLedger(LEDGER_PATH)
    requests = tuple(
        (candidate, build_env_params_probe_request(candidate)) for candidate in pending
    )
    hashes = tuple(
        canonical_request_hash(FortyGuardEndpoint.ENV_PARAMS, request)
        for _, request in requests
    )
    usage = await client.fetch_credit_usage()
    if usage.total_available_credits != settings.credit_total:
        raise RuntimeError("FortyGuard allocation differs from configured total")
    authorization = CreditGovernor(settings, ledger).authorize_estimate(
        request_hashes=hashes,
        current_usage=usage.used_credits,
        estimated_unit_cost=OBSERVED_ENV_PARAMS_UNIT_COST,
    )
    print(
        f"Preflight: {len(finalists)} finalists, {len(pending)} new, "
        f"projected {authorization.projected_cost} credits, "
        f"projected remaining {authorization.remaining_after}"
    )

    for index, (candidate, request) in enumerate(requests, start=1):
        request_hash = canonical_request_hash(FortyGuardEndpoint.ENV_PARAMS, request)
        journal_path = JOURNAL_DIR / f"{request_hash}.json"
        journal = (
            MeasurementJournal.model_validate_json(journal_path.read_text(encoding="utf-8"))
            if journal_path.exists()
            else None
        )
        entry = ledger.find_request(request_hash)
        if entry is None:
            if journal is None:
                before = await client.fetch_credit_usage()
                if (
                    before.remaining_credits - OBSERVED_ENV_PARAMS_UNIT_COST
                    < settings.credit_reserve
                ):
                    raise RuntimeError("next environmental request would breach the reserve")
                journal = MeasurementJournal(
                    request_hash=request_hash,
                    usage_before=before.used_credits,
                    prepared_at=datetime.now(UTC),
                )
                write_model(journal_path, journal)
            if journal.submission_attempted and not cached_request_exists(request_hash):
                raise RuntimeError(
                    f"uncertain prior environmental submission for {candidate.site_id}; "
                    "refusing duplicate"
                )
            if not journal.submission_attempted:
                journal = journal.model_copy(update={"submission_attempted": True})
                write_model(journal_path, journal)
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
                    "filter_type": request.date_time.filter_type,
                },
                usage_before=journal.usage_before,
                activity_id=handle.activity_id,
            )
        else:
            handle = await client.submit_env_params(request)

        if entry.status == ActivityLifecycle.PROCESSING:
            status = await client.poll(
                handle.activity_id,
                policy=PollingPolicy(max_attempts=40, maximum_delay_seconds=15),
            )
            after = await client.fetch_credit_usage()
            terminal: Literal[ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED] = (
                ActivityLifecycle.COMPLETED
                if status.status == ActivityLifecycle.COMPLETED
                else ActivityLifecycle.FAILED
            )
            entry = ledger.record_outcome(
                activity_id=handle.activity_id,
                status=terminal,
                usage_after=after.used_credits,
                timestamp=datetime.now(UTC),
            )
        else:
            status = await client.get_status(handle.activity_id)

        if status.status != ActivityLifecycle.COMPLETED or not isinstance(
            status.result, EnvironmentalParametersResult
        ):
            raise RuntimeError(f"environmental job failed for {candidate.site_id}")
        if entry.usage_after is None or entry.observed_cost is None or entry.updated_at is None:
            raise RuntimeError("completed environmental ledger entry lacks credit evidence")
        if settings.credit_total - entry.usage_after < settings.credit_reserve:
            raise RuntimeError("environmental finalist batch breached the reserve")
        artifact = FinalistEnvironmentalArtifact(
            finalist_rank=finalists.index(candidate) + 1,
            candidate_id=candidate.id,
            site_id=candidate.site_id,
            site_name=candidate.site_name,
            tile_id=candidate.tile_id,
            request_hash=request_hash,
            activity_id=handle.activity_id,
            retrieved_at=entry.updated_at,
            request=request,
            result=status.result,
            usage_before=entry.usage_before,
            usage_after=entry.usage_after,
            observed_credit_delta=entry.observed_cost,
            credits_remaining=settings.credit_total - entry.usage_after,
        )
        write_model(output_path(candidate.site_id), artifact)
        print(
            f"[{index}/{len(requests)}] rank={artifact.finalist_rank} "
            f"{candidate.site_name}: cost={artifact.observed_credit_delta}, "
            f"remaining={artifact.credits_remaining}"
        )

    return tuple(
        artifact
        for candidate in finalists
        if (artifact := load_cached_artifact(candidate)) is not None
    )


def main() -> None:
    artifacts = asyncio.run(cache_environmental_finalists())
    print(f"Completed: cached {len(artifacts)} environmental finalist responses")


if __name__ == "__main__":
    main()
