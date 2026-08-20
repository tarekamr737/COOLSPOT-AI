"""Run/resume the matching persistence request and freeze both real heatmap layers."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    ActivityLifecycle,
    DateTimeRequest,
    FortyGuardEndpoint,
    HeatmapRequest,
    HeatmapResult,
)
from api.app.services.credits import CreditGovernor, CreditLedger, CreditLedgerEntry, CreditSettings
from api.app.services.fortyguard import FortyGuardClient, canonical_request_hash
from scripts.measure_fortyguard_heatmap import (
    AOI_PATH,
    CACHE_ROOT,
    LEDGER_PATH,
    RAW_ROOT,
    ROOT,
    MeasurementJournal,
    build_request,
    cached_request_exists,
    load_heatmap_config,
    load_journal,
    load_project_env,
    write_model,
)

PERSISTENCE_JOURNAL_PATH = RAW_ROOT / "persistence_measurement_journal.json"
OUTPUT_PATH = ROOT / "data" / "processed" / "pacoima_fortyguard_heatmaps.json"


class CachedHeatmapLayer(BaseModel):
    """One validated real layer plus immutable request and credit provenance."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    analytic_type: Literal["tcm", "persistence"]
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    completed_at: datetime
    granularity_m: Literal[100]
    date_time: DateTimeRequest
    threshold_c: float
    direction: Literal["above", "below"]
    observed_credit_delta: int = Field(ge=0)
    threshold_rationale: str = Field(min_length=20)
    feature_count: int = Field(gt=0)
    result: HeatmapResult

    @model_validator(mode="after")
    def validate_feature_count(self) -> Self:
        if self.feature_count != len(self.result.map_data.features):
            raise ValueError("feature_count does not match the heatmap result")
        return self


class PacoimaHeatmapArtifact(BaseModel):
    """Offline-ready pair of real, spatially matching Pacoima heatmap layers."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: Literal["1.0"] = "1.0"
    source: Literal["FortyGuard Heatmap API"] = "FortyGuard Heatmap API"
    source_url: Literal["https://api.fortyguard.com/v1/heatmap"] = (
        "https://api.fortyguard.com/v1/heatmap"
    )
    license_notes: str
    pilot: Literal["Pacoima, Los Angeles"] = "Pacoima, Los Angeles"
    aoi_sha256: str = Field(pattern=r"^[0-9A-F]{64}$")
    generated_at: datetime
    layers: tuple[CachedHeatmapLayer, CachedHeatmapLayer]

    @model_validator(mode="after")
    def require_matching_tcm_and_persistence(self) -> Self:
        by_type = {layer.analytic_type: layer for layer in self.layers}
        if set(by_type) != {"tcm", "persistence"}:
            raise ValueError("artifact requires exactly one tcm and one persistence layer")
        tcm = by_type["tcm"]
        persistence = by_type["persistence"]
        if tcm.granularity_m != persistence.granularity_m:
            raise ValueError("heatmap granularities do not match")
        if tcm.date_time.start_date != persistence.date_time.start_date:
            raise ValueError("heatmap dates do not match")
        tcm_tiles = tuple(
            (feature.id, feature.geometry) for feature in tcm.result.map_data.features
        )
        persistence_tiles = tuple(
            (feature.id, feature.geometry)
            for feature in persistence.result.map_data.features
        )
        if tcm_tiles != persistence_tiles:
            raise ValueError("heatmap tile IDs/geometries do not align")
        return self


def build_persistence_request() -> HeatmapRequest:
    """Use the same hot date/AOI at 100 m and count daily persistence above 30 °C."""

    config = load_heatmap_config()
    tcm = build_request()
    return tcm.model_copy(
        update={
            "date_time": DateTimeRequest(start_date=config.start_date, filter_type=3),
            "analytic_type": "persistence",
            "threshold": config.persistence_threshold_c,
            "direction": config.persistence_direction,
        }
    )


def require_completed(entry: CreditLedgerEntry, label: str) -> CreditLedgerEntry:
    if entry.status != ActivityLifecycle.COMPLETED:
        raise RuntimeError(f"{label} heatmap is not completed")
    if entry.updated_at is None or entry.observed_cost is None:
        raise RuntimeError(f"{label} heatmap has no completed credit measurement")
    return entry


async def ensure_persistence(
    client: FortyGuardClient,
    settings: CreditSettings,
    ledger: CreditLedger,
    request: HeatmapRequest,
) -> CreditLedgerEntry:
    request_hash = canonical_request_hash(FortyGuardEndpoint.HEATMAP, request)
    entry = ledger.find_request(request_hash)
    journal = load_journal(request_hash, PERSISTENCE_JOURNAL_PATH)

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
            write_model(PERSISTENCE_JOURNAL_PATH, journal)

        if journal.submission_attempted and not cached_request_exists(request_hash):
            raise RuntimeError(
                "a prior persistence submission has no cached activity; refusing to resubmit"
            )
        if not journal.submission_attempted:
            journal = journal.model_copy(update={"submission_attempted": True})
            write_model(PERSISTENCE_JOURNAL_PATH, journal)

        handle = await client.submit_heatmap(request)
        entry = ledger.record_submission(
            timestamp=journal.prepared_at,
            request_hash=request_hash,
            endpoint=FortyGuardEndpoint.HEATMAP,
            request_summary={
                "pilot": "Pacoima, Los Angeles",
                "analytic_type": "persistence",
                "granularity_m": 100,
                "filter_type": 3,
                "start_date": "2024-07-15",
                "threshold_c": request.threshold,
                "direction": request.direction,
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
            raise RuntimeError("polling returned a non-terminal persistence activity")
        usage_after = await client.fetch_credit_usage()
        if usage_after.total_available_credits != settings.credit_total:
            raise RuntimeError("FortyGuard cycle allocation changed during persistence request")
        if usage_after.remaining_credits < settings.credit_reserve:
            raise RuntimeError("FortyGuard persistence request breached the hard reserve")
        entry = ledger.record_outcome(
            activity_id=handle.activity_id,
            status=outcome_status,
            usage_after=usage_after.used_credits,
            timestamp=datetime.now(UTC),
        )
    return require_completed(entry, "persistence")


async def cache_layers() -> PacoimaHeatmapArtifact:
    env = load_project_env(ROOT / ".env")
    settings = CreditSettings.from_env(env)
    client = FortyGuardClient(
        api_key=env.get("FORTYGUARD_API_KEY", ""),
        cache_root=CACHE_ROOT,
    )
    ledger = CreditLedger(LEDGER_PATH)
    config = load_heatmap_config()
    tcm_request = build_request()
    persistence_request = build_persistence_request()
    persistence_entry = await ensure_persistence(
        client, settings, ledger, persistence_request
    )

    tcm_hash = canonical_request_hash(FortyGuardEndpoint.HEATMAP, tcm_request)
    tcm_entry = ledger.find_request(tcm_hash)
    if tcm_entry is None:
        raise RuntimeError("the measured TCM ledger entry is missing")
    tcm_entry = require_completed(tcm_entry, "tcm")
    assert tcm_entry.updated_at is not None
    assert tcm_entry.observed_cost is not None
    assert persistence_entry.updated_at is not None
    assert persistence_entry.observed_cost is not None

    tcm_handle = await client.submit_heatmap(tcm_request)
    persistence_handle = await client.submit_heatmap(persistence_request)
    tcm_status = await client.get_status(tcm_handle.activity_id)
    persistence_status = await client.get_status(persistence_handle.activity_id)
    if not isinstance(tcm_status.result, HeatmapResult) or not isinstance(
        persistence_status.result, HeatmapResult
    ):
        raise RuntimeError("cached heatmap activities do not contain heatmap results")

    layers = (
        CachedHeatmapLayer(
            analytic_type="tcm",
            activity_id=tcm_entry.activity_id,
            request_hash=tcm_entry.request_hash,
            completed_at=tcm_entry.updated_at,
            granularity_m=100,
            date_time=tcm_request.date_time,
            threshold_c=tcm_request.threshold,
            direction=tcm_request.direction,
            observed_credit_delta=tcm_entry.observed_cost,
            threshold_rationale="Threshold fields are not used by the TCM analytic.",
            feature_count=len(tcm_status.result.map_data.features),
            result=tcm_status.result,
        ),
        CachedHeatmapLayer(
            analytic_type="persistence",
            activity_id=persistence_entry.activity_id,
            request_hash=persistence_entry.request_hash,
            completed_at=persistence_entry.updated_at,
            granularity_m=100,
            date_time=persistence_request.date_time,
            threshold_c=persistence_request.threshold,
            direction=persistence_request.direction,
            observed_credit_delta=persistence_entry.observed_cost,
            threshold_rationale=config.persistence_threshold_rationale,
            feature_count=len(persistence_status.result.map_data.features),
            result=persistence_status.result,
        ),
    )
    artifact = PacoimaHeatmapArtifact(
        license_notes=(
            "FortyGuard hackathon API output cached for the COOLSPOT AI demonstration; "
            "not a ground-observation dataset."
        ),
        aoi_sha256=hashlib.sha256(AOI_PATH.read_bytes()).hexdigest().upper(),
        generated_at=max(tcm_entry.updated_at, persistence_entry.updated_at),
        layers=layers,
    )
    write_model(OUTPUT_PATH, artifact)
    return artifact


def main() -> None:
    artifact = asyncio.run(cache_layers())
    summary = ", ".join(
        f"{layer.analytic_type}={layer.feature_count} tiles/{layer.observed_credit_delta} credits"
        for layer in artifact.layers
    )
    print(f"Cached {summary}")


if __name__ == "__main__":
    main()
