"""Authenticated, credit-governed refresh of the Pacoima heat evidence."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from api.app.fortyguard_models import (
    ActivityLifecycle,
    DateTimeRequest,
    FortyGuardEndpoint,
    HeatmapRequest,
    HeatmapResult,
    PolygonAoi,
)
from api.app.services.candidates import (
    DEFAULT_CANDIDATES_PATH,
    build_candidates,
    canonical_candidate_bytes,
)
from api.app.services.capabilities import (
    DEFAULT_CAPABILITIES_PATH,
    canonical_capability_bytes,
    load_capabilities,
)
from api.app.services.credits import (
    CreditGovernor,
    CreditLedger,
    CreditSettings,
    LiveModeDisabledError,
)
from api.app.services.decision_api import clear_decision_caches
from api.app.services.feature_table import (
    DEFAULT_FEATURE_TABLE_PATH,
    build_feature_table,
    canonical_feature_table_bytes,
)
from api.app.services.fortyguard import (
    FortyGuardClient,
    FortyGuardError,
    canonical_request_hash,
)
from api.app.services.heatmap_data import (
    DEFAULT_HEATMAP_PATH,
    CachedHeatmapLayer,
    PacoimaHeatmapArtifact,
    canonical_heatmap_bytes,
)
from api.app.settings import load_project_env

ROOT = Path(__file__).resolve().parents[3]
AOI_PATH = ROOT / "data" / "processed" / "pacoima_aoi.geojson"
RUNTIME_ROOT = ROOT / "data" / "runtime" / "fortyguard"
CACHE_ROOT = RUNTIME_ROOT / "cache"
LEDGER_PATH = ROOT / "data" / "raw" / "fortyguard" / "credit_ledger.json"
REFRESH_MARKER_PATH = RUNTIME_ROOT / "last_refresh.json"


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_date: date


class RefreshStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["idle", "running", "completed", "failed", "unavailable"]
    message: str
    requested_date: date | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    estimated_credit_cost: int | None = Field(default=None, ge=0)
    credits_remaining: int | None = Field(default=None, ge=0)
    hard_reserve: int = Field(default=500_000, ge=500_000)


class RefreshPreflightError(RuntimeError):
    """The safe checks failed before any paid refresh job was submitted."""


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.part")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _build_requests(analysis_date: date) -> tuple[HeatmapRequest, HeatmapRequest]:
    if analysis_date > datetime.now(UTC).date():
        raise ValueError("analysis date cannot be in the future")
    if analysis_date < datetime.now(UTC).date() - timedelta(days=365):
        raise ValueError("analysis date must be within the last 365 days")
    aoi = PolygonAoi.model_validate_json(AOI_PATH.read_text(encoding="utf-8"))
    tcm = HeatmapRequest(
        polygon_aoi=aoi,
        date_time=DateTimeRequest(
            start_date=analysis_date,
            start_time=time(hour=14),
            filter_type=1,
        ),
        granularity=100,
        analytic_type="tcm",
    )
    persistence = HeatmapRequest(
        polygon_aoi=aoi,
        date_time=DateTimeRequest(start_date=analysis_date, filter_type=3),
        granularity=100,
        analytic_type="persistence",
        threshold=30,
        direction="above",
    )
    return tcm, persistence


class RefreshCoordinator:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._status = RefreshStatus(
            state="idle",
            message="Cached evidence is ready. An administrator can request newer heat data.",
        )

    def status(self) -> RefreshStatus:
        env = load_project_env()
        if env.get("FORTYGUARD_LIVE", "0") != "1":
            return RefreshStatus(
                state="unavailable",
                message="Live refresh is disabled by FORTYGUARD_LIVE=0.",
            )
        if not env.get("COOLSPOT_REFRESH_TOKEN", "").strip():
            return RefreshStatus(
                state="unavailable",
                message="Live refresh needs COOLSPOT_REFRESH_TOKEN on the server.",
            )
        return self._status

    async def start(self, *, token: str, analysis_date: date) -> RefreshStatus:
        env = load_project_env()
        expected = env.get("COOLSPOT_REFRESH_TOKEN", "").strip()
        if not expected or not secrets.compare_digest(token, expected):
            raise PermissionError("Invalid refresh administrator token")
        settings = CreditSettings.from_env(env)
        if not settings.live:
            raise LiveModeDisabledError("FORTYGUARD_LIVE=0 blocks live refresh")
        requests = _build_requests(analysis_date)
        async with self._lock:
            if self._task is not None and not self._task.done():
                raise RuntimeError("A live refresh is already running")
            client = FortyGuardClient(
                api_key=env.get("FORTYGUARD_API_KEY", ""),
                cache_root=CACHE_ROOT,
            )
            ledger = CreditLedger(LEDGER_PATH)
            try:
                usage = await client.fetch_credit_usage()
            except FortyGuardError as error:
                message = (
                    "FortyGuard is unreachable during the credit preflight. No paid jobs "
                    "were submitted; cached evidence remains active. Check the server "
                    "network connection and retry."
                )
                self._status = RefreshStatus(state="failed", message=message)
                raise RefreshPreflightError(message) from error
            hashes = tuple(
                canonical_request_hash(FortyGuardEndpoint.HEATMAP, request)
                for request in requests
            )
            authorization = CreditGovernor(settings, ledger).authorize_observed_batch(
                endpoint=FortyGuardEndpoint.HEATMAP,
                request_hashes=hashes,
                current_usage=usage.used_credits,
            )
            now = datetime.now(UTC)
            self._status = RefreshStatus(
                state="running",
                message="FortyGuard is generating TCM and persistence layers.",
                requested_date=analysis_date,
                started_at=now,
                estimated_credit_cost=authorization.projected_cost,
                credits_remaining=usage.remaining_credits,
                hard_reserve=settings.credit_reserve,
            )
            self._task = asyncio.create_task(
                self._run(
                    client=client,
                    ledger=ledger,
                    settings=settings,
                    requests=requests,
                )
            )
            return self._status

    async def _run(
        self,
        *,
        client: FortyGuardClient,
        ledger: CreditLedger,
        settings: CreditSettings,
        requests: tuple[HeatmapRequest, HeatmapRequest],
    ) -> None:
        completed: list[tuple[HeatmapRequest, HeatmapResult, int, str, str, datetime]] = []
        try:
            for request in requests:
                before = await client.fetch_credit_usage()
                handle = await client.submit_heatmap(request)
                ledger.record_submission(
                    timestamp=datetime.now(UTC),
                    request_hash=handle.request_hash,
                    endpoint=FortyGuardEndpoint.HEATMAP,
                    request_summary={
                        "pilot": "Pacoima, Los Angeles",
                        "analytic_type": request.analytic_type,
                        "granularity_m": request.granularity,
                        "start_date": request.date_time.start_date.isoformat(),
                    },
                    usage_before=before.used_credits,
                    activity_id=handle.activity_id,
                )
                terminal = await client.poll(handle.activity_id)
                after = await client.fetch_credit_usage()
                ledger.record_outcome(
                    activity_id=handle.activity_id,
                    status=(
                        ActivityLifecycle.COMPLETED
                        if terminal.status == ActivityLifecycle.COMPLETED
                        else ActivityLifecycle.FAILED
                    ),
                    usage_after=after.used_credits,
                    timestamp=datetime.now(UTC),
                )
                if terminal.status != ActivityLifecycle.COMPLETED or not isinstance(
                    terminal.result, HeatmapResult
                ):
                    raise RuntimeError(f"{request.analytic_type} refresh failed")
                measured = ledger.find_request(handle.request_hash)
                if (
                    measured is None
                    or measured.observed_cost is None
                    or measured.updated_at is None
                ):
                    raise RuntimeError("completed refresh is missing credit provenance")
                if after.remaining_credits < settings.credit_reserve:
                    raise RuntimeError("live refresh breached the hard credit reserve")
                completed.append(
                    (
                        request,
                        terminal.result,
                        measured.observed_cost,
                        handle.activity_id,
                        handle.request_hash,
                        measured.updated_at,
                    )
                )

            layers = tuple(
                CachedHeatmapLayer(
                    analytic_type=cast(
                        Literal["tcm", "persistence"], request.analytic_type
                    ),
                    activity_id=activity_id,
                    request_hash=request_hash,
                    completed_at=completed_at,
                    granularity_m=100,
                    date_time=request.date_time,
                    threshold_c=request.threshold,
                    direction=request.direction,
                    observed_credit_delta=cost,
                    threshold_rationale=(
                        "Threshold fields are not used by the TCM analytic."
                        if request.analytic_type == "tcm"
                        else "Planning duration above 30 degrees Celsius, not a health cutoff."
                    ),
                    feature_count=len(result.map_data.features),
                    result=result,
                )
                for request, result, cost, activity_id, request_hash, completed_at in completed
            )
            artifact = PacoimaHeatmapArtifact(
                license_notes=(
                    "FortyGuard API output refreshed by an authorized COOLSPOT administrator; "
                    "not a ground-observation dataset."
                ),
                aoi_sha256=hashlib.sha256(AOI_PATH.read_bytes()).hexdigest().upper(),
                generated_at=max(item[5] for item in completed),
                layers=layers,  # type: ignore[arg-type]
            )
            staged_heatmap = RUNTIME_ROOT / "staged_heatmaps.json"
            staged_features = RUNTIME_ROOT / "staged_features.json"
            _write_bytes(staged_heatmap, canonical_heatmap_bytes(artifact))
            feature_payload = canonical_feature_table_bytes(
                build_feature_table(heatmap_path=staged_heatmap)
            )
            _write_bytes(staged_features, feature_payload)
            candidate_payload = canonical_candidate_bytes(
                build_candidates(feature_table_path=staged_features)
            )
            _write_bytes(DEFAULT_HEATMAP_PATH, staged_heatmap.read_bytes())
            _write_bytes(DEFAULT_FEATURE_TABLE_PATH, feature_payload)
            _write_bytes(DEFAULT_CANDIDATES_PATH, candidate_payload)
            completed_at = datetime.now(UTC)
            marker = {
                "analysis_date": requests[0].date_time.start_date.isoformat(),
                "completed_at": completed_at.isoformat(),
            }
            _write_bytes(REFRESH_MARKER_PATH, json.dumps(marker, indent=2).encode())
            final_usage = await client.fetch_credit_usage()
            capability_snapshot = load_capabilities().model_copy(
                update={
                    "evaluated_at": completed_at.date(),
                    "credits_used": final_usage.used_credits,
                    "credits_remaining": final_usage.remaining_credits,
                }
            )
            _write_bytes(
                DEFAULT_CAPABILITIES_PATH,
                canonical_capability_bytes(capability_snapshot),
            )
            clear_decision_caches()
            self._status = self._status.model_copy(
                update={
                    "state": "completed",
                    "message": "Fresh FortyGuard heat evidence is active.",
                    "completed_at": completed_at,
                    "credits_remaining": final_usage.remaining_credits,
                }
            )
        except Exception as error:
            self._status = self._status.model_copy(
                update={
                    "state": "failed",
                    "message": f"Refresh failed; the last validated cache remains active. {error}",
                    "completed_at": datetime.now(UTC),
                }
            )


refresh_coordinator = RefreshCoordinator()
