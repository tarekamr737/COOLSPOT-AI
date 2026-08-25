"""Poll the stored Heat Intelligence activity and cache its PDF plus provenance."""

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
    HeatIntelligenceResult,
    PollingPolicy,
)
from api.app.services.credits import CreditLedger, CreditSettings
from api.app.services.fortyguard import FortyGuardClient
from scripts.measure_fortyguard_heatmap import (
    CACHE_ROOT,
    LEDGER_PATH,
    ROOT,
    load_project_env,
    write_model,
)
from scripts.probe_fortyguard_heat_intelligence import (
    RECEIPT_PATH,
    HeatIntelligenceProbeReceipt,
)

REPORT_PDF_PATH = ROOT / "data" / "processed" / "pacoima_heat_intelligence_report.pdf"
REPORT_METADATA_PATH = (
    ROOT / "data" / "processed" / "pacoima_heat_intelligence_report.json"
)


class HeatIntelligenceReportArtifact(BaseModel):
    """Portable provenance and credit record for the optional cached report."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    checked_at: datetime
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    candidate_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    site_name: str = Field(min_length=1)
    tile_id: str = Field(min_length=1)
    status: Literal["Completed", "Failed"]
    report_path: str | None = None
    result: HeatIntelligenceResult | None = None
    usage_before: int = Field(ge=0)
    usage_after: int = Field(ge=0)
    observed_credit_delta: int = Field(ge=0)
    credits_remaining: int = Field(ge=500_000)
    total_allocation: int = Field(ge=500_001, le=2_000_000)
    hard_reserve: int = Field(ge=500_000)
    source_urls: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)
    quality_status: Literal["quarantined"] = "quarantined"
    eligible_for_explanation: Literal[False] = False
    quality_findings: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_artifact(self) -> Self:
        if self.usage_after - self.usage_before != self.observed_credit_delta:
            raise ValueError("observed report cost does not match usage counters")
        if self.credits_remaining != self.total_allocation - self.usage_after:
            raise ValueError("report credit counters do not balance")
        if self.status == "Completed":
            if self.result is None or self.report_path is None:
                raise ValueError("completed report requires cached PDF metadata")
        elif self.result is not None or self.report_path is not None:
            raise ValueError("failed report cannot claim a cached PDF")
        return self


def _portable_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


async def cache_report() -> HeatIntelligenceReportArtifact:
    receipt = HeatIntelligenceProbeReceipt.model_validate_json(
        RECEIPT_PATH.read_text(encoding="utf-8")
    )
    if REPORT_METADATA_PATH.exists():
        artifact = HeatIntelligenceReportArtifact.model_validate_json(
            REPORT_METADATA_PATH.read_text(encoding="utf-8")
        )
        if artifact.request_hash != receipt.request_hash:
            raise RuntimeError("cached report belongs to another request")
        return artifact

    env = load_project_env(ROOT / ".env")
    settings = CreditSettings.from_env(env)
    client = FortyGuardClient(
        api_key=env.get("FORTYGUARD_API_KEY", ""),
        cache_root=CACHE_ROOT,
    )
    ledger = CreditLedger(LEDGER_PATH)
    entry = ledger.find_request(receipt.request_hash)
    if entry is None or entry.activity_id != receipt.activity_id:
        raise RuntimeError("Heat Intelligence probe ledger entry is missing or mismatched")

    handle = await client.submit_heat_intelligence(receipt.request)
    if handle.activity_id != receipt.activity_id or not handle.reused:
        raise RuntimeError("Heat Intelligence completion must reuse the stored activity")
    if entry.status == ActivityLifecycle.PROCESSING:
        terminal = await client.poll_heat_intelligence(
            handle.activity_id,
            destination=REPORT_PDF_PATH,
            policy=PollingPolicy(
                max_attempts=12,
                initial_delay_seconds=2,
                maximum_delay_seconds=10,
                multiplier=1.5,
                jitter_ratio=0.1,
            ),
        )
        if terminal.status not in {
            ActivityLifecycle.COMPLETED,
            ActivityLifecycle.FAILED,
        }:
            raise RuntimeError("report polling returned a non-terminal activity")
        outcome: Literal[
            ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED
        ] = (
            ActivityLifecycle.COMPLETED
            if terminal.status == ActivityLifecycle.COMPLETED
            else ActivityLifecycle.FAILED
        )
        usage = await client.fetch_credit_usage()
        if usage.total_available_credits != settings.credit_total:
            raise RuntimeError("FortyGuard allocation changed during report generation")
        if usage.remaining_credits < settings.credit_reserve:
            raise RuntimeError("Heat Intelligence report breached the hard reserve")
        entry = ledger.record_outcome(
            activity_id=handle.activity_id,
            status=outcome,
            usage_after=usage.used_credits,
            timestamp=datetime.now(UTC),
        )
    else:
        terminal = await client.get_status(handle.activity_id)

    if entry.usage_after is None or entry.observed_cost is None or entry.updated_at is None:
        raise RuntimeError("terminal report is missing credit counters")
    result = terminal.result
    if result is not None and not isinstance(result, HeatIntelligenceResult):
        raise RuntimeError("Heat Intelligence activity returned an unexpected result")
    status: Literal["Completed", "Failed"] = (
        "Completed"
        if entry.status == ActivityLifecycle.COMPLETED
        else "Failed"
    )
    artifact = HeatIntelligenceReportArtifact(
        checked_at=entry.updated_at,
        activity_id=entry.activity_id,
        request_hash=entry.request_hash,
        candidate_id=receipt.candidate_id,
        site_id=receipt.site_id,
        site_name=receipt.site_name,
        tile_id=receipt.tile_id,
        status=status,
        report_path=_portable_path(REPORT_PDF_PATH) if result is not None else None,
        result=result,
        usage_before=entry.usage_before,
        usage_after=entry.usage_after,
        observed_credit_delta=entry.observed_cost,
        credits_remaining=settings.credit_total - entry.usage_after,
        total_allocation=settings.credit_total,
        hard_reserve=settings.credit_reserve,
        source_urls=(
            "https://docs-api.fortyguard.com/docs/heat-intelligence",
            "https://docs-api.fortyguard.com/docs/limitations",
        ),
        limitations=(
            "This optional vendor report supports explanation for one top recommendation only; "
            "it is not an optimizer input or a guaranteed intervention outcome.",
            "The report reflects the supplied point, temperature, date, and urban analysis; it "
            "does not replace field, engineering, ownership, or procurement verification.",
        ),
        quality_findings=(
            "The report interpreted the supplied 35.9398 °C value as 35.94 °F / 2.18 °C.",
            "The report described the Pacoima coordinates as Long Beach / Signal Hill.",
            "The report introduced uncited local estimates and projections absent from the "
            "structured COOLSPOT evidence payload.",
        ),
    )
    write_model(REPORT_METADATA_PATH, artifact)
    return artifact


def main() -> None:
    artifact = asyncio.run(cache_report())
    print(
        f"{artifact.status}: site={artifact.site_name} "
        f"delta={artifact.observed_credit_delta} remaining={artifact.credits_remaining}"
    )


if __name__ == "__main__":
    main()
