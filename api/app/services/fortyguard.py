"""Async FortyGuard adapter with canonical request caching and resumable polling."""

import asyncio
import hashlib
import json
import os
import random
import re
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx2
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    ActivityHandle,
    ActivityLifecycle,
    ActivityStatus,
    CreditUsage,
    EndpointResult,
    EnvironmentalParametersRequest,
    EnvironmentalParametersResult,
    FortyGuardEndpoint,
    HeatIntelligenceRequest,
    HeatIntelligenceResult,
    HeatmapRequest,
    HeatmapResult,
    PollingPolicy,
    SatelliteRequest,
    SatelliteResult,
    StreetViewRequest,
    StreetViewResult,
)

SubmissionRequest = (
    HeatmapRequest
    | EnvironmentalParametersRequest
    | SatelliteRequest
    | StreetViewRequest
    | HeatIntelligenceRequest
)
JSON_OBJECT_ADAPTER = TypeAdapter(dict[str, JsonValue])
ENDPOINT_PATHS = {
    FortyGuardEndpoint.HEATMAP: "/v1/heatmap",
    FortyGuardEndpoint.ENV_PARAMS: "/v1/env_params",
    FortyGuardEndpoint.SATELLITE: "/v1/satellite",
    FortyGuardEndpoint.STREETVIEW: "/v1/streetview",
    FortyGuardEndpoint.HEAT_INTELLIGENCE: "/v1/heat_intelligence",
}


class FortyGuardError(RuntimeError):
    """Base exception for adapter failures."""


class FortyGuardHttpError(FortyGuardError):
    """A non-successful HTTP response from FortyGuard."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"FortyGuard HTTP {status_code}: {message}")


class FortyGuardProtocolError(FortyGuardError):
    """A response that does not match the documented API contract."""


class PollingExhaustedError(FortyGuardError):
    """The bounded polling policy ended while an activity was still processing."""


class TransportResponse(BaseModel):
    """Transport-neutral JSON response."""

    model_config = ConfigDict(extra="forbid")

    status_code: int = Field(ge=100, le=599)
    payload: object


class JsonTransport(Protocol):
    """Minimal async JSON transport used by the adapter and fixture tests."""

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: dict[str, JsonValue] | None,
    ) -> TransportResponse: ...

    async def request_bytes(self, url: str) -> "BinaryTransportResponse": ...


class BinaryTransportResponse(BaseModel):
    """Transport-neutral binary response used for temporary report downloads."""

    model_config = ConfigDict(extra="forbid")

    status_code: int = Field(ge=100, le=599)
    content: bytes
    media_type: str | None = None


class HttpxJsonTransport:
    """Production transport backed by a bounded httpx2 async client."""

    def __init__(self, *, timeout_seconds: float = 60) -> None:
        if timeout_seconds <= 0:
            raise ValueError("transport timeout must be positive")
        self._timeout_seconds = timeout_seconds

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: dict[str, JsonValue] | None,
    ) -> TransportResponse:
        try:
            async with httpx2.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.request(method, url, headers=headers, json=json_body)
        except httpx2.RequestError as error:
            raise FortyGuardError(
                "FortyGuard could not be reached. Check the server network connection and retry."
            ) from error
        try:
            payload = response.json()
        except ValueError as error:
            raise FortyGuardProtocolError("FortyGuard returned a non-JSON response") from error
        return TransportResponse(status_code=response.status_code, payload=payload)

    async def request_bytes(self, url: str) -> BinaryTransportResponse:
        """Download a temporary report without including its URL in errors or logs."""

        try:
            async with httpx2.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(url)
        except httpx2.RequestError as error:
            raise FortyGuardError("FortyGuard report download failed") from error
        return BinaryTransportResponse(
            status_code=response.status_code,
            content=response.content,
            media_type=response.headers.get("content-type"),
        )


class VendorModel(BaseModel):
    """Known vendor fields; additive response fields do not leak past this boundary."""

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class VendorSubmissionData(VendorModel):
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)


class VendorSubmissionEnvelope(VendorModel):
    error: bool
    status_code: int
    message: str
    data: VendorSubmissionData


class VendorStatusData(VendorModel):
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    status: ActivityLifecycle
    result: dict[str, JsonValue] | None = None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = {
                "processing": ActivityLifecycle.PROCESSING,
                "completed": ActivityLifecycle.COMPLETED,
                "succeeded": ActivityLifecycle.COMPLETED,
                "failed": ActivityLifecycle.FAILED,
                "error": ActivityLifecycle.FAILED,
            }.get(value.lower())
            if normalized is not None:
                return normalized
        return value


class VendorStatusEnvelope(VendorModel):
    error: bool
    status_code: int
    message: str
    data: VendorStatusData


class VendorHeatIntelligenceResult(VendorModel):
    download_link: str

    @field_validator("download_link")
    @classmethod
    def require_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("Heat Intelligence download link must use HTTPS")
        return value


class VendorCreditSummary(VendorModel):
    total_available_credits: int = Field(gt=0)
    cycle_credits_used: int = Field(ge=0)
    cycle_remaining_credits: int = Field(ge=0)


class VendorUsageResponse(VendorModel):
    credit_summary: VendorCreditSummary


class CachedActivity(BaseModel):
    """Server-side persistent request/activity state; never contains the API key."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: str = Field(default="1.0", pattern=r"^1\.0$")
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    endpoint: FortyGuardEndpoint
    request_payload: dict[str, JsonValue]
    status: ActivityLifecycle
    message: str
    submitted_at: datetime
    last_checked_at: datetime | None = None
    raw_response: dict[str, JsonValue]
    result: dict[str, JsonValue] | None = None


class ActivityLink(BaseModel):
    """Lookup from activity ID to its canonical request hash."""

    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    request_hash: str = Field(pattern=SHA256_PATTERN)


def canonical_request_hash(
    endpoint: FortyGuardEndpoint, request: SubmissionRequest
) -> str:
    """Hash a normalized endpoint + payload without credentials or unstable whitespace."""

    payload = JSON_OBJECT_ADAPTER.validate_python(
        request.model_dump(mode="json", exclude_none=True)
    )
    canonical = json.dumps(
        {"endpoint": endpoint.value, "payload": payload},
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_result(
    endpoint: FortyGuardEndpoint, payload: dict[str, JsonValue]
) -> EndpointResult:
    if endpoint == FortyGuardEndpoint.HEATMAP:
        return HeatmapResult.model_validate(payload)
    if endpoint == FortyGuardEndpoint.ENV_PARAMS:
        return EnvironmentalParametersResult.model_validate(payload)
    if endpoint == FortyGuardEndpoint.SATELLITE:
        normalized = dict(payload)
        documented_images = normalized.pop("orignal_image", None)
        runtime_images = normalized.pop("original_image", None)
        normalized_images = normalized.pop("original_images", None)
        image_variants = tuple(
            images
            for images in (documented_images, runtime_images, normalized_images)
            if images is not None
        )
        if len(image_variants) > 1 and any(
            images != image_variants[0] for images in image_variants[1:]
        ):
            raise FortyGuardProtocolError(
                "satellite response returned conflicting original-image fields"
            )
        original_images = image_variants[0] if image_variants else None
        normalized["original_images"] = original_images
        return SatelliteResult.model_validate(normalized)
    if endpoint == FortyGuardEndpoint.STREETVIEW:
        return StreetViewResult.model_validate(payload)
    if endpoint == FortyGuardEndpoint.HEAT_INTELLIGENCE:
        return HeatIntelligenceResult.model_validate(payload)
    raise AssertionError(f"unsupported endpoint {endpoint}")


class FortyGuardClient:
    """Narrow, server-side FortyGuard interface with durable idempotency."""

    def __init__(
        self,
        *,
        api_key: str,
        cache_root: Path,
        base_url: str = "https://api.fortyguard.com",
        transport: JsonTransport | None = None,
        clock: Callable[[], datetime] = _utc_now,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter_source: Callable[[], float] = random.random,
    ) -> None:
        if not api_key.strip():
            raise ValueError("FortyGuard API key is required")
        if not base_url.startswith("https://"):
            raise ValueError("FortyGuard base URL must use HTTPS")
        self._api_key = api_key
        self._cache_root = cache_root.resolve()
        self._base_url = base_url.rstrip("/")
        self._transport = transport or HttpxJsonTransport()
        self._clock = clock
        self._sleeper = sleeper
        self._jitter_source = jitter_source
        self._submission_lock = asyncio.Lock()

    async def submit_heatmap(self, request: HeatmapRequest) -> ActivityHandle:
        """Submit or reuse a canonical heatmap activity."""

        self._validate_date_bounds(request.date_time.start_date, request.date_time.end_date, 12)
        return await self._submit(FortyGuardEndpoint.HEATMAP, request)

    async def fetch_credit_usage(self) -> CreditUsage:
        """Fetch current-cycle usage using the body field required by the runtime API."""

        response = await self._transport.request_json(
            "POST",
            f"{self._base_url}/v1/system/fetch-api-key-usage",
            headers={"Content-Type": "application/json"},
            json_body={"api_key": self._api_key},
        )
        payload = self._require_successful_object(response)
        summary = VendorUsageResponse.model_validate(payload).credit_summary
        return CreditUsage(
            total_available_credits=summary.total_available_credits,
            used_credits=summary.cycle_credits_used,
            remaining_credits=summary.cycle_remaining_credits,
        )

    async def submit_env_params(
        self, request: EnvironmentalParametersRequest
    ) -> ActivityHandle:
        """Submit or reuse a canonical environmental-parameters activity."""

        self._validate_date_bounds(request.date_time.start_date, request.date_time.end_date, 0)
        return await self._submit(FortyGuardEndpoint.ENV_PARAMS, request)

    async def submit_satellite(self, request: SatelliteRequest) -> ActivityHandle:
        """Submit or reuse a canonical satellite-segmentation activity."""

        self._validate_date_bounds(request.date_time.start_date, request.date_time.end_date, 5)
        return await self._submit(FortyGuardEndpoint.SATELLITE, request)

    async def submit_streetview(self, request: StreetViewRequest) -> ActivityHandle:
        """Submit or reuse a canonical street-view-segmentation activity."""

        return await self._submit(FortyGuardEndpoint.STREETVIEW, request)

    async def submit_heat_intelligence(
        self, request: HeatIntelligenceRequest
    ) -> ActivityHandle:
        """Submit or reuse a canonical Heat Intelligence report activity."""

        self._validate_date_bounds(request.date, None, 12)
        return await self._submit(FortyGuardEndpoint.HEAT_INTELLIGENCE, request)

    async def get_status(self, activity_id: str) -> ActivityStatus:
        """Return cached terminal state or refresh a known in-flight activity."""

        record = self._load_by_activity_id(activity_id)
        if record.endpoint == FortyGuardEndpoint.HEAT_INTELLIGENCE:
            if record.status in {ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED}:
                return self._to_activity_status(record)
            raise FortyGuardProtocolError(
                "Heat Intelligence status requires an immediate secure PDF destination"
            )
        if record.status in {ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED}:
            return self._to_activity_status(record)

        response = await self._transport.request_json(
            "GET",
            f"{self._base_url}/v1/status/{activity_id}",
            headers=self._headers(),
            json_body=None,
        )
        payload = self._require_successful_object(response)
        envelope = VendorStatusEnvelope.model_validate(payload)
        if envelope.error:
            raise FortyGuardProtocolError(envelope.message)
        if envelope.data.activity_id != activity_id:
            raise FortyGuardProtocolError("status response activity_id does not match request")

        result: dict[str, JsonValue] | None = None
        if envelope.data.status == ActivityLifecycle.COMPLETED:
            if envelope.data.result is None:
                raise FortyGuardProtocolError("completed status response has no result")
            normalized_result = _normalize_result(record.endpoint, envelope.data.result)
            result = JSON_OBJECT_ADAPTER.validate_python(
                normalized_result.model_dump(mode="json")
            )
        elif envelope.data.result is not None:
            raise FortyGuardProtocolError("non-completed status unexpectedly includes a result")

        updated = CachedActivity.model_validate(
            {
                **record.model_dump(mode="python"),
                "status": envelope.data.status,
                "message": envelope.message,
                "last_checked_at": self._now(),
                "raw_response": payload,
                "result": result,
            }
        )
        self._store_record(updated)
        return self._to_activity_status(updated)

    async def get_heat_intelligence_status(
        self, activity_id: str, *, destination: Path
    ) -> ActivityStatus:
        """Poll one report and immediately cache a completed PDF without its signed URL."""

        record = self._load_by_activity_id(activity_id)
        if record.endpoint != FortyGuardEndpoint.HEAT_INTELLIGENCE:
            raise ValueError("activity is not a Heat Intelligence report")
        if destination.suffix.lower() != ".pdf":
            raise ValueError("Heat Intelligence destination must be a PDF path")
        if record.status in {ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED}:
            return self._to_activity_status(record)

        response = await self._transport.request_json(
            "GET",
            f"{self._base_url}/v1/status/{activity_id}",
            headers=self._headers(),
            json_body=None,
        )
        payload = self._require_successful_object(response)
        envelope = VendorStatusEnvelope.model_validate(payload)
        if envelope.error:
            raise FortyGuardProtocolError(envelope.message)
        if envelope.data.activity_id != activity_id:
            raise FortyGuardProtocolError("status response activity_id does not match request")

        normalized_result: HeatIntelligenceResult | None = None
        stored_payload = dict(payload)
        if envelope.data.status == ActivityLifecycle.COMPLETED:
            if envelope.data.result is None:
                raise FortyGuardProtocolError("completed report has no download link")
            report = VendorHeatIntelligenceResult.model_validate(envelope.data.result)
            download = await self._transport.request_bytes(report.download_link)
            if not 200 <= download.status_code < 300:
                raise FortyGuardHttpError(download.status_code, "report download failed")
            if not download.content.startswith(b"%PDF-"):
                raise FortyGuardProtocolError("Heat Intelligence result is not a PDF")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = destination.with_suffix(f"{destination.suffix}.part")
            temporary_path.write_bytes(download.content)
            os.replace(temporary_path, destination)
            normalized_result = HeatIntelligenceResult(
                report_sha256=hashlib.sha256(download.content).hexdigest(),
                report_size_bytes=len(download.content),
                report_filename=destination.name,
            )
            stored_payload = {
                **payload,
                "data": {
                    **dict(payload["data"]),  # type: ignore[arg-type]
                    "result": {"download_link": "[REDACTED]"},
                },
            }
        elif envelope.data.result is not None:
            raise FortyGuardProtocolError("non-completed status unexpectedly includes a result")

        updated = CachedActivity.model_validate(
            {
                **record.model_dump(mode="python"),
                "status": envelope.data.status,
                "message": envelope.message,
                "last_checked_at": self._now(),
                "raw_response": stored_payload,
                "result": (
                    normalized_result.model_dump(mode="json")
                    if normalized_result is not None
                    else None
                ),
            }
        )
        self._store_record(updated)
        return self._to_activity_status(updated)

    async def poll_heat_intelligence(
        self,
        activity_id: str,
        *,
        destination: Path,
        policy: PollingPolicy | None = None,
    ) -> ActivityStatus:
        """Boundedly poll and securely cache one Heat Intelligence PDF."""

        active_policy = policy or PollingPolicy()
        delay = active_policy.initial_delay_seconds
        for attempt in range(active_policy.max_attempts):
            status = await self.get_heat_intelligence_status(
                activity_id, destination=destination
            )
            if status.status != ActivityLifecycle.PROCESSING:
                return status
            if attempt == active_policy.max_attempts - 1:
                break
            random_value = self._jitter_source()
            jitter = delay * active_policy.jitter_ratio * ((2 * random_value) - 1)
            await self._sleeper(max(0, delay + jitter))
            delay = min(active_policy.maximum_delay_seconds, delay * active_policy.multiplier)
        raise PollingExhaustedError(
            f"activity {activity_id} remained Processing after "
            f"{active_policy.max_attempts} checks"
        )

    async def poll(
        self, activity_id: str, *, policy: PollingPolicy | None = None
    ) -> ActivityStatus:
        """Poll a known activity with bounded exponential backoff and jitter."""

        active_policy = policy or PollingPolicy()
        delay = active_policy.initial_delay_seconds
        last_status: ActivityStatus | None = None
        for attempt in range(active_policy.max_attempts):
            last_status = await self.get_status(activity_id)
            if last_status.status != ActivityLifecycle.PROCESSING:
                return last_status
            if attempt == active_policy.max_attempts - 1:
                break
            random_value = self._jitter_source()
            if not 0 <= random_value <= 1:
                raise ValueError("jitter source must return a value in [0, 1]")
            jitter = delay * active_policy.jitter_ratio * ((2 * random_value) - 1)
            await self._sleeper(max(0, delay + jitter))
            delay = min(
                active_policy.maximum_delay_seconds,
                delay * active_policy.multiplier,
            )
        raise PollingExhaustedError(
            f"activity {activity_id} remained Processing after "
            f"{active_policy.max_attempts} checks"
        )

    async def _submit(
        self, endpoint: FortyGuardEndpoint, request: SubmissionRequest
    ) -> ActivityHandle:
        request_hash = canonical_request_hash(endpoint, request)
        async with self._submission_lock:
            existing = self._load_by_hash(request_hash)
            if existing is not None:
                return ActivityHandle(
                    activity_id=existing.activity_id,
                    request_hash=existing.request_hash,
                    endpoint=existing.endpoint,
                    status=existing.status,
                    reused=True,
                )

            request_payload = JSON_OBJECT_ADAPTER.validate_python(
                request.model_dump(mode="json", exclude_none=True)
            )
            response = await self._transport.request_json(
                "POST",
                f"{self._base_url}{ENDPOINT_PATHS[endpoint]}",
                headers=self._headers(),
                json_body=request_payload,
            )
            response_payload = self._require_successful_object(response)
            envelope = VendorSubmissionEnvelope.model_validate(response_payload)
            if envelope.error:
                raise FortyGuardProtocolError(envelope.message)

            record = CachedActivity(
                activity_id=envelope.data.activity_id,
                request_hash=request_hash,
                endpoint=endpoint,
                request_payload=request_payload,
                status=ActivityLifecycle.PROCESSING,
                message=envelope.message,
                submitted_at=self._now(),
                raw_response=response_payload,
            )
            self._store_record(record)
            return ActivityHandle(
                activity_id=record.activity_id,
                request_hash=record.request_hash,
                endpoint=record.endpoint,
                status=record.status,
                reused=False,
            )

    def _headers(self) -> dict[str, str]:
        return {"api-key": self._api_key, "Content-Type": "application/json"}

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("FortyGuard clock must return a timezone-aware datetime")
        return now

    def _validate_date_bounds(
        self, start_date: date, end_date: date | None, future_hours: int
    ) -> None:
        latest_date = (self._now() + timedelta(hours=future_hours)).date()
        if start_date > latest_date or (end_date is not None and end_date > latest_date):
            raise ValueError(f"FortyGuard request date cannot be after {latest_date.isoformat()}")

    def _require_successful_object(
        self, response: TransportResponse
    ) -> dict[str, JsonValue]:
        if not 200 <= response.status_code < 300:
            message = "request failed"
            if isinstance(response.payload, dict) and isinstance(
                response.payload.get("message"), str
            ):
                message = response.payload["message"]
            raise FortyGuardHttpError(response.status_code, message)
        try:
            return JSON_OBJECT_ADAPTER.validate_python(response.payload)
        except ValueError as error:
            raise FortyGuardProtocolError("FortyGuard response must be a JSON object") from error

    def _request_path(self, request_hash: str) -> Path:
        if not re.fullmatch(SHA256_PATTERN, request_hash):
            raise ValueError("invalid request hash")
        return self._cache_root / "requests" / f"{request_hash}.json"

    def _activity_path(self, activity_id: str) -> Path:
        if not re.fullmatch(ACTIVITY_ID_PATTERN, activity_id):
            raise ValueError("invalid activity ID")
        return self._cache_root / "activities" / f"{activity_id}.json"

    def _load_by_hash(self, request_hash: str) -> CachedActivity | None:
        path = self._request_path(request_hash)
        if not path.exists():
            return None
        record = CachedActivity.model_validate_json(path.read_text(encoding="utf-8"))
        if record.request_hash != request_hash:
            raise FortyGuardProtocolError("cached request hash does not match its filename")
        return record

    def _load_by_activity_id(self, activity_id: str) -> CachedActivity:
        link_path = self._activity_path(activity_id)
        if link_path.exists():
            link = ActivityLink.model_validate_json(link_path.read_text(encoding="utf-8"))
            if link.activity_id != activity_id:
                raise FortyGuardProtocolError("cached activity link does not match its filename")
            record = self._load_by_hash(link.request_hash)
            if record is None:
                raise FortyGuardProtocolError("cached activity link points to a missing request")
            return record

        requests_root = self._cache_root / "requests"
        if requests_root.exists():
            for request_path in sorted(requests_root.glob("*.json")):
                record = CachedActivity.model_validate_json(
                    request_path.read_text(encoding="utf-8")
                )
                if record.activity_id == activity_id:
                    self._write_model(
                        link_path,
                        ActivityLink(activity_id=activity_id, request_hash=record.request_hash),
                    )
                    return record
        raise KeyError(f"unknown FortyGuard activity {activity_id}")

    def _store_record(self, record: CachedActivity) -> None:
        self._write_model(self._request_path(record.request_hash), record)
        self._write_model(
            self._activity_path(record.activity_id),
            ActivityLink(activity_id=record.activity_id, request_hash=record.request_hash),
        )

    @staticmethod
    def _write_model(path: Path, model: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            model.model_dump(mode="json"),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        temporary_path = path.with_suffix(f"{path.suffix}.part")
        temporary_path.write_text(payload, encoding="utf-8")
        os.replace(temporary_path, path)

    @staticmethod
    def _to_activity_status(record: CachedActivity) -> ActivityStatus:
        result = (
            _normalize_result(record.endpoint, record.result)
            if record.result is not None
            else None
        )
        return ActivityStatus(
            activity_id=record.activity_id,
            request_hash=record.request_hash,
            endpoint=record.endpoint,
            status=record.status,
            message=record.message,
            result=result,
        )
