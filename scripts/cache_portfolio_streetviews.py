"""Cache street-view segmentation for the deterministic $1M portfolio."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from shapely.geometry import Point, shape

from api.app.fortyguard_models import (
    ActivityLifecycle,
    FortyGuardEndpoint,
    PollingPolicy,
    StreetViewRequest,
    StreetViewResult,
)
from api.app.services.candidates import Candidate, load_candidates
from api.app.services.credits import CreditGovernor, CreditLedger, CreditSettings
from api.app.services.fortyguard import FortyGuardClient, canonical_request_hash
from api.app.services.optimizer import optimize_portfolio
from api.app.settings import load_project_env

ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "data" / "raw" / "fortyguard" / "requests"
LEDGER_PATH = ROOT / "data" / "raw" / "fortyguard" / "credit_ledger.json"
OUTPUT_DIR = ROOT / "data" / "processed" / "pacoima_streetview_sites"
LEGACY_PATH = ROOT / "data" / "processed" / "pacoima_streetview.json"
BUDGET_USD = 1_000_000
OBSERVED_UNIT_COST = 8_600


def request_for(candidate: Candidate) -> StreetViewRequest:
    geometry = shape(candidate.geometry.model_dump(mode="json"))
    point = cast(
        Point,
        geometry if geometry.geom_type == "Point" else geometry.representative_point(),
    )
    return StreetViewRequest(
        latitude=point.y,
        longitude=point.x,
        vertical_angle=0,
        horizontal_angle=0,
        back_view=False,
    )


def output_path(site_id: str) -> Path:
    return OUTPUT_DIR / f"{site_id.replace(':', '__')}.json"


def is_cached(site_id: str) -> bool:
    for path in (output_path(site_id), LEGACY_PATH):
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("site_id") == site_id
            and payload.get("status") == ActivityLifecycle.COMPLETED.value
            and payload.get("result") is not None
        ):
            return True
    return False


def write_result(
    candidate: Candidate,
    activity_id: str,
    result: StreetViewResult,
    usage_before: int,
    usage_after: int,
) -> None:
    document = {
        "version": "1.0",
        "pilot": "Pacoima, Los Angeles",
        "portfolio_budget_usd": BUDGET_USD,
        "site_id": candidate.site_id,
        "site_name": candidate.site_name,
        "activity_id": activity_id,
        "status": ActivityLifecycle.COMPLETED.value,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "usage_before": usage_before,
        "usage_after": usage_after,
        "observed_credit_delta": usage_after - usage_before,
        "credits_remaining": CreditSettings().credit_total - usage_after,
        "result": result.model_dump(mode="json"),
    }
    path = output_path(candidate.site_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


async def cache_portfolio() -> None:
    env = load_project_env()
    settings = CreditSettings.from_env(env)
    client = FortyGuardClient(
        api_key=env.get("FORTYGUARD_API_KEY", ""),
        cache_root=CACHE_ROOT,
    )
    ledger = CreditLedger(LEDGER_PATH)
    candidates = load_candidates().candidates
    by_id = {candidate.id: candidate for candidate in candidates}
    portfolio = optimize_portfolio(BUDGET_USD, candidates=candidates)
    selected = tuple(by_id[candidate_id] for candidate_id in portfolio.selected_candidate_ids)
    pending = tuple(candidate for candidate in selected if not is_cached(candidate.site_id))
    requests = tuple((candidate, request_for(candidate)) for candidate in pending)
    hashes = tuple(
        canonical_request_hash(FortyGuardEndpoint.STREETVIEW, request)
        for _, request in requests
    )

    usage = await client.fetch_credit_usage()
    if usage.total_available_credits != settings.credit_total:
        raise RuntimeError("FortyGuard cycle allocation differs from configured total")
    authorization = CreditGovernor(settings, ledger).authorize_estimate(
        request_hashes=hashes,
        current_usage=usage.used_credits,
        estimated_unit_cost=OBSERVED_UNIT_COST,
    )
    print(
        f"Preflight: {len(selected)} selected, {len(pending)} new, "
        f"projected {authorization.projected_cost} credits, "
        f"projected remaining {authorization.remaining_after}"
    )

    for index, (candidate, request) in enumerate(requests, start=1):
        before = await client.fetch_credit_usage()
        if before.remaining_credits - OBSERVED_UNIT_COST < settings.credit_reserve:
            raise RuntimeError("next street-view request would breach the hard reserve")
        request_hash = canonical_request_hash(FortyGuardEndpoint.STREETVIEW, request)
        entry = ledger.find_request(request_hash)
        handle = await client.submit_streetview(request)
        if entry is None:
            entry = ledger.record_submission(
                timestamp=datetime.now(UTC),
                request_hash=request_hash,
                endpoint=FortyGuardEndpoint.STREETVIEW,
                request_summary={
                    "pilot": "Pacoima, Los Angeles",
                    "portfolio_budget_usd": BUDGET_USD,
                    "site_id": candidate.site_id,
                    "site_name": candidate.site_name,
                    "latitude": request.latitude,
                    "longitude": request.longitude,
                },
                usage_before=before.used_credits,
                activity_id=handle.activity_id,
            )
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
        ledger.record_outcome(
            activity_id=handle.activity_id,
            status=terminal,
            usage_after=after.used_credits,
            timestamp=datetime.now(UTC),
        )
        if status.status != ActivityLifecycle.COMPLETED or not isinstance(
            status.result, StreetViewResult
        ):
            raise RuntimeError(f"street-view job failed for {candidate.site_id}")
        if after.remaining_credits < settings.credit_reserve:
            raise RuntimeError("street-view batch breached the hard reserve")
        write_result(
            candidate,
            handle.activity_id,
            status.result,
            before.used_credits,
            after.used_credits,
        )
        print(
            f"[{index}/{len(requests)}] {candidate.site_name}: "
            f"{before.used_credits}->{after.used_credits}, remaining={after.remaining_credits}"
        )


if __name__ == "__main__":
    asyncio.run(cache_portfolio())
