"""Complete the single already-submitted Pacoima street-view capability probe."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from api.app.fortyguard_models import ActivityLifecycle, FortyGuardEndpoint
from api.app.services.fortyguard import (
    HttpxJsonTransport,
    VendorStatusEnvelope,
    VendorUsageResponse,
    _normalize_result,
)
from api.app.settings import load_project_env

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "processed" / "pacoima_streetview.json"
BASELINE_USAGE = 16_880


async def complete(activity_id: str) -> None:
    api_key = load_project_env().get("FORTYGUARD_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("FORTYGUARD_API_KEY is required")
    transport = HttpxJsonTransport()
    headers = {"api-key": api_key}
    envelope: VendorStatusEnvelope | None = None
    for _ in range(30):
        response = await transport.request_json(
            "GET",
            f"https://api.fortyguard.com/v1/status/{activity_id}",
            headers=headers,
            json_body=None,
        )
        envelope = VendorStatusEnvelope.model_validate(response.payload)
        if envelope.data.status != ActivityLifecycle.PROCESSING:
            break
        await asyncio.sleep(5)
    if envelope is None or envelope.data.status == ActivityLifecycle.PROCESSING:
        raise TimeoutError(f"street-view activity {activity_id} is still processing")

    usage_response = await transport.request_json(
        "POST",
        "https://api.fortyguard.com/v1/system/fetch-api-key-usage",
        headers={"Content-Type": "application/json"},
        json_body={"api_key": api_key},
    )
    usage = VendorUsageResponse.model_validate(usage_response.payload).credit_summary
    result = None
    if envelope.data.status == ActivityLifecycle.COMPLETED:
        if envelope.data.result is None:
            raise RuntimeError("completed street-view activity has no result")
        result = _normalize_result(FortyGuardEndpoint.STREETVIEW, envelope.data.result)
    document = {
        "version": "1.0",
        "pilot": "Pacoima, Los Angeles",
        "site_id": "metro-stop:10794",
        "activity_id": activity_id,
        "status": envelope.data.status.value,
        "message": envelope.message,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "usage_before": BASELINE_USAGE,
        "usage_after": usage.cycle_credits_used,
        "observed_credit_delta": usage.cycle_credits_used - BASELINE_USAGE,
        "credits_remaining": usage.cycle_remaining_credits,
        "result": result.model_dump(mode="json") if result is not None else None,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.part")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, OUTPUT)
    print(
        f"{envelope.data.status.value}: usage={BASELINE_USAGE}->{usage.cycle_credits_used} "
        f"remaining={usage.cycle_remaining_credits}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: complete_streetview_probe.py ACTIVITY_ID")
    asyncio.run(complete(sys.argv[1]))
