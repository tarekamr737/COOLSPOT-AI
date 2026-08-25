"""Submit or resume the one permitted governed Heat Intelligence access probe."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shapely.geometry import Point, shape

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    ActivityLifecycle,
    FortyGuardEndpoint,
    HeatIntelligenceRequest,
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

JOURNAL_PATH = RAW_ROOT / "heat_intelligence_probe_journal.json"
RECEIPT_PATH = ROOT / "data" / "processed" / "fortyguard_heat_intelligence_probe.json"


class HeatIntelligenceProbeReceipt(BaseModel):
    """Secret-free receipt proving one accepted report submission."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    submitted_at: datetime
    request_hash: str = Field(pattern=SHA256_PATTERN)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    candidate_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    site_name: str = Field(min_length=1)
    tile_id: str = Field(min_length=1)
    request: HeatIntelligenceRequest
    status: Literal["Processing"] = "Processing"
    usage_before: int = Field(ge=0)
    credits_remaining_before: int = Field(ge=500_000)
    total_allocation: int = Field(ge=500_001, le=2_000_000)
    hard_reserve: int = Field(ge=500_000)

    @model_validator(mode="after")
    def validate_credit_arithmetic(self) -> Self:
        if self.credits_remaining_before != self.total_allocation - self.usage_before:
            raise ValueError("probe receipt credit counters do not balance")
        if self.credits_remaining_before <= self.hard_reserve:
            raise ValueError("no credits are available above the hard reserve")
        return self


def select_probe_candidate() -> Candidate:
    """Choose the highest-impact recommendation in the balanced $500k portfolio."""

    candidates = load_candidates().candidates
    by_id = {candidate.id: candidate for candidate in candidates}
    portfolio = optimize_portfolio(500_000, candidates=candidates)
    top_score = max(
        portfolio.selected_candidate_scores,
        key=lambda score: (score.modeled_impact_score, score.candidate_id),
    )
    return by_id[top_score.candidate_id]


def build_probe_request(candidate: Candidate | None = None) -> HeatIntelligenceRequest:
    selected = candidate or select_probe_candidate()
    geometry = shape(selected.geometry.model_dump(mode="json"))
    point: Point = geometry.representative_point()
    tile = next(
        item for item in load_feature_table().tiles if item.tile_id == selected.tile_id
    )
    tcm = next(
        layer for layer in load_heatmap_artifact().layers if layer.analytic_type == "tcm"
    )
    return HeatIntelligenceRequest(
        latitude=point.y,
        longitude=point.x,
        temperature=tile.heat.average_temperature_c,
        date=tcm.date_time.start_date,
        analysis=("urban",),
    )


async def probe_heat_intelligence() -> HeatIntelligenceProbeReceipt:
    candidate = select_probe_candidate()
    request = build_probe_request(candidate)
    request_hash = canonical_request_hash(FortyGuardEndpoint.HEAT_INTELLIGENCE, request)
    if RECEIPT_PATH.exists():
        receipt = HeatIntelligenceProbeReceipt.model_validate_json(
            RECEIPT_PATH.read_text(encoding="utf-8")
        )
        if receipt.request_hash != request_hash:
            raise RuntimeError("committed Heat Intelligence probe belongs to another request")
        return receipt

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
            spendable = usage.remaining_credits - settings.credit_reserve
            CreditGovernor(settings, ledger).authorize_estimate(
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
                "uncertain prior Heat Intelligence submission; refusing to resubmit"
            )
        if not journal.submission_attempted:
            journal = journal.model_copy(update={"submission_attempted": True})
            write_model(JOURNAL_PATH, journal)
        handle = await client.submit_heat_intelligence(request)
        entry = ledger.record_submission(
            timestamp=journal.prepared_at,
            request_hash=request_hash,
            endpoint=FortyGuardEndpoint.HEAT_INTELLIGENCE,
            request_summary={
                "candidate_id": candidate.id,
                "site_id": candidate.site_id,
                "tile_id": candidate.tile_id,
                "analysis": list(request.analysis),
                "date": request.date.isoformat(),
            },
            usage_before=journal.usage_before,
            activity_id=handle.activity_id,
        )
    else:
        handle = await client.submit_heat_intelligence(request)

    if entry.status != ActivityLifecycle.PROCESSING:
        raise RuntimeError("Heat Intelligence access probe must stop after submission")
    receipt = HeatIntelligenceProbeReceipt(
        submitted_at=entry.timestamp,
        request_hash=entry.request_hash,
        activity_id=handle.activity_id,
        candidate_id=candidate.id,
        site_id=candidate.site_id,
        site_name=candidate.site_name,
        tile_id=candidate.tile_id,
        request=request,
        usage_before=entry.usage_before,
        credits_remaining_before=settings.credit_total - entry.usage_before,
        total_allocation=settings.credit_total,
        hard_reserve=settings.credit_reserve,
    )
    write_model(RECEIPT_PATH, receipt)
    return receipt


def main() -> None:
    receipt = asyncio.run(probe_heat_intelligence())
    print(
        f"{receipt.status}: site={receipt.site_name} activity={receipt.activity_id} "
        f"remaining_before={receipt.credits_remaining_before} hash={receipt.request_hash}"
    )


if __name__ == "__main__":
    main()
