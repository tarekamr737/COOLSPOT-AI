"""Fixture-backed tests for the async FortyGuard adapter."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from pydantic import JsonValue, ValidationError

from api.app.fortyguard_models import (
    ActivityLifecycle,
    AoiFeature,
    DateTimeRequest,
    EnvironmentalParametersRequest,
    FortyGuardEndpoint,
    HeatmapRequest,
    HeatmapResult,
    PollingPolicy,
    PolygonAoi,
    SatelliteCoordinates,
    SatelliteRequest,
    StreetViewRequest,
)
from api.app.services.boundary import PolygonGeometry
from api.app.services.fortyguard import (
    FortyGuardClient,
    FortyGuardError,
    HttpxJsonTransport,
    TransportResponse,
    canonical_request_hash,
)

FIXTURES = Path(__file__).parent / "fixtures" / "fortyguard"
FIXED_NOW = datetime(2026, 8, 20, 12, tzinfo=UTC)


class FakeTransport:
    """Deterministic in-memory transport that returns committed response fixtures."""

    def __init__(self, responses: list[TransportResponse]) -> None:
        self.responses = responses
        self.calls: list[
            tuple[str, str, Mapping[str, str], dict[str, JsonValue] | None]
        ] = []

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: dict[str, JsonValue] | None,
    ) -> TransportResponse:
        self.calls.append((method, url, headers, json_body))
        if not self.responses:
            raise AssertionError("unexpected FortyGuard transport call")
        return self.responses.pop(0)


def test_http_transport_wraps_network_failures_without_leaking_internals() -> None:
    async def scenario() -> None:
        with (
            patch(
                "api.app.services.fortyguard.httpx2.AsyncClient.request",
                new_callable=AsyncMock,
                side_effect=httpx2.ConnectError("socket detail"),
            ),
            pytest.raises(FortyGuardError, match="could not be reached") as captured,
        ):
            await HttpxJsonTransport().request_json(
                "GET",
                "https://api.fortyguard.com/v1/system/fetch-api-key-usage",
                headers={"X-API-KEY": "secret"},
                json_body=None,
            )
        assert "socket detail" not in str(captured.value)

    asyncio.run(scenario())


def fixture_response(name: str) -> TransportResponse:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return TransportResponse(status_code=200, payload=payload)


def heatmap_request(*, properties: dict[str, JsonValue] | None = None) -> HeatmapRequest:
    geometry = PolygonGeometry(
        type="Polygon",
        coordinates=(
            (
                (-118.42, 34.25),
                (-118.41, 34.25),
                (-118.41, 34.26),
                (-118.42, 34.26),
                (-118.42, 34.25),
            ),
        ),
    )
    return HeatmapRequest(
        polygon_aoi=PolygonAoi(
            type="FeatureCollection",
            features=(
                AoiFeature(type="Feature", properties=properties or {}, geometry=geometry),
            ),
        ),
        date_time=DateTimeRequest(
            start_date=date(2024, 7, 15),
            start_time=time(14),
            filter_type=1,
        ),
        granularity=100,
    )


def test_request_hash_is_canonical_and_request_validation_enforces_limits() -> None:
    first = heatmap_request(properties={"b": 2, "a": 1})
    second = heatmap_request(properties={"a": 1, "b": 2})

    assert canonical_request_hash(FortyGuardEndpoint.HEATMAP, first) == canonical_request_hash(
        FortyGuardEndpoint.HEATMAP, second
    )
    assert first.model_dump(mode="json", exclude_none=True)["date_time"]["start_time"] == "14:00"

    with pytest.raises(ValidationError, match="filter_type 2 requires"):
        DateTimeRequest(start_date=date(2024, 7, 15), start_time=time(14), filter_type=2)

    large_geometry = PolygonGeometry(
        type="Polygon",
        coordinates=(
            (
                (-118.5, 34.2),
                (-118.3, 34.2),
                (-118.3, 34.4),
                (-118.5, 34.4),
                (-118.5, 34.2),
            ),
        ),
    )
    with pytest.raises(ValidationError, match="limit is below 10"):
        HeatmapRequest(
            polygon_aoi=PolygonAoi(
                type="FeatureCollection",
                features=(AoiFeature(type="Feature", geometry=large_geometry),),
            ),
            date_time=first.date_time,
            granularity=100,
        )


def test_documented_exceedance_schema_matches_adapter_payload(tmp_path: Path) -> None:
    """Pin the 2026-08-24 Create Heatmap documentation contract."""

    base_request = heatmap_request()
    request = HeatmapRequest(
        polygon_aoi=base_request.polygon_aoi,
        date_time=DateTimeRequest(start_date=date(2024, 7, 15), filter_type=3),
        granularity=100,
        analytic_type="exceedance",
        threshold=30,
        direction="above",
    )
    transport = FakeTransport([fixture_response("submit_heatmap.json")])
    client = FortyGuardClient(
        api_key="server-secret",
        cache_root=tmp_path,
        transport=transport,
        clock=lambda: FIXED_NOW,
    )

    asyncio.run(client.submit_heatmap(request))

    method, url, headers, payload = transport.calls[0]
    assert method == "POST"
    assert url == "https://api.fortyguard.com/v1/heatmap"
    assert headers["api-key"] == "server-secret"
    assert payload is not None
    assert set(payload) == {
        "polygon_aoi",
        "date_time",
        "granularity",
        "analytic_type",
        "threshold",
        "direction",
    }
    assert payload["date_time"] == {"start_date": "2024-07-15", "filter_type": 3}
    assert payload["granularity"] == 100
    assert payload["analytic_type"] == "exceedance"
    assert payload["threshold"] == 30.0
    assert payload["direction"] == "above"


def test_usage_query_uses_runtime_body_contract_and_validates_balance(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            TransportResponse(
                status_code=200,
                payload={
                    "subscription_id": "not-retained",
                    "credit_summary": {
                        "total_available_credits": 2_000_000,
                        "cycle_credits_used": 12_345,
                        "cycle_remaining_credits": 1_987_655,
                    },
                },
            )
        ]
    )
    client = FortyGuardClient(
        api_key="server-secret",
        cache_root=tmp_path,
        transport=transport,
    )

    usage = asyncio.run(client.fetch_credit_usage())

    assert usage.used_credits == 12_345
    assert transport.calls == [
        (
            "POST",
            "https://api.fortyguard.com/v1/system/fetch-api-key-usage",
            {"Content-Type": "application/json"},
            {"api_key": "server-secret"},
        )
    ]


def test_adapter_reuses_request_and_resumes_polling_after_restart(tmp_path: Path) -> None:
    request = heatmap_request()
    first_transport = FakeTransport([fixture_response("submit_heatmap.json")])
    first_client = FortyGuardClient(
        api_key="fixture-secret",
        cache_root=tmp_path,
        transport=first_transport,
        clock=lambda: FIXED_NOW,
    )

    first_handle = asyncio.run(first_client.submit_heatmap(request))
    duplicate_handle = asyncio.run(first_client.submit_heatmap(request))

    assert first_handle.reused is False
    assert duplicate_handle.reused is True
    assert duplicate_handle.activity_id == first_handle.activity_id
    assert len(first_transport.calls) == 1

    resumed_transport = FakeTransport(
        [
            fixture_response("status_processing.json"),
            fixture_response("status_completed_heatmap.json"),
        ]
    )
    resumed_client = FortyGuardClient(
        api_key="fixture-secret",
        cache_root=tmp_path,
        transport=resumed_transport,
        clock=lambda: FIXED_NOW,
    )
    processing = asyncio.run(resumed_client.get_status(first_handle.activity_id))
    completed = asyncio.run(resumed_client.get_status(first_handle.activity_id))

    assert processing.status == ActivityLifecycle.PROCESSING
    assert completed.status == ActivityLifecycle.COMPLETED
    assert isinstance(completed.result, HeatmapResult)
    assert completed.result.map_data.features[0].properties["value"] == 38.5

    offline_transport = FakeTransport([])
    offline_client = FortyGuardClient(
        api_key="fixture-secret",
        cache_root=tmp_path,
        transport=offline_transport,
        clock=lambda: FIXED_NOW,
    )
    cached_handle = asyncio.run(offline_client.submit_heatmap(request))
    cached_status = asyncio.run(offline_client.get_status(first_handle.activity_id))

    assert cached_handle.reused is True
    assert cached_handle.status == ActivityLifecycle.COMPLETED
    assert cached_status.status == ActivityLifecycle.COMPLETED
    assert offline_transport.calls == []
    assert all(
        "fixture-secret" not in path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*.json")
    )


def test_polling_uses_bounded_exponential_backoff(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            fixture_response("submit_heatmap.json"),
            fixture_response("status_processing.json"),
            fixture_response("status_processing.json"),
            fixture_response("status_completed_heatmap.json"),
        ]
    )
    delays: list[float] = []

    async def record_delay(delay: float) -> None:
        delays.append(delay)

    async def run_poll() -> ActivityLifecycle:
        client = FortyGuardClient(
            api_key="fixture-secret",
            cache_root=tmp_path,
            transport=transport,
            clock=lambda: FIXED_NOW,
            sleeper=record_delay,
            jitter_source=lambda: 0.5,
        )
        handle = await client.submit_heatmap(heatmap_request())
        status = await client.poll(
            handle.activity_id,
            policy=PollingPolicy(
                max_attempts=3,
                initial_delay_seconds=1,
                maximum_delay_seconds=5,
                multiplier=2,
                jitter_ratio=0.2,
            ),
        )
        return status.status

    assert asyncio.run(run_poll()) == ActivityLifecycle.COMPLETED
    assert delays == [1, 2]


def test_typed_optional_endpoint_submissions_use_documented_paths(tmp_path: Path) -> None:
    def submitted(activity_id: str) -> TransportResponse:
        return TransportResponse(
            status_code=200,
            payload={
                "error": False,
                "status_code": 200,
                "message": "Submitted Successfully",
                "data": {"activity_id": activity_id},
            },
        )

    transport = FakeTransport(
        [submitted("env-fixture-001"), submitted("sat-fixture-001"), submitted("sv-fixture-001")]
    )
    date_time = DateTimeRequest(
        start_date=date(2024, 7, 15),
        start_time=time(14),
        filter_type=1,
    )

    async def submit_all() -> None:
        client = FortyGuardClient(
            api_key="fixture-secret",
            cache_root=tmp_path,
            transport=transport,
            clock=lambda: FIXED_NOW,
        )
        await client.submit_env_params(
            EnvironmentalParametersRequest(
                latitude=34.26,
                longitude=-118.42,
                temperature=38.5,
                date_time=date_time,
            )
        )
        await client.submit_satellite(
            SatelliteRequest(
                sat=SatelliteCoordinates(latitude=34.26, longitude=-118.42),
                date_time=date_time,
                granularity=100,
            )
        )
        await client.submit_streetview(
            StreetViewRequest(
                latitude=34.26,
                longitude=-118.42,
                vertical_angle=10,
                horizontal_angle=90,
                back_view=False,
            )
        )

    asyncio.run(submit_all())

    assert [call[1] for call in transport.calls] == [
        "https://api.fortyguard.com/v1/env_params",
        "https://api.fortyguard.com/v1/satellite",
        "https://api.fortyguard.com/v1/streetview",
    ]
