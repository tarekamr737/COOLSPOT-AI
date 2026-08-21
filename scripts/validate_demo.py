"""Validate the deployed COOLSPOT AI API's cached golden path."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx2  # noqa: E402

from api.app.schemas import (  # noqa: E402
    CandidateListResponse,
    DataStatusResponse,
    HealthResponse,
    LayerResponse,
    MethodologyResponse,
    PilotResponse,
    SiteResponse,
)
from api.app.services.explanations import GroundedExplanation  # noqa: E402
from api.app.services.optimizer import PortfolioResult  # noqa: E402

GOLDEN_BUDGETS = (500_000, 1_000_000)


def _response(
    client: httpx2.Client,
    method: str,
    path: str,
    *,
    json: Mapping[str, int | str] | None = None,
) -> httpx2.Response:
    response = client.request(method, path, json=json)
    response.raise_for_status()
    return response


def validate_demo(base_url: str) -> str:
    """Exercise and validate the cached decision-support API."""

    with httpx2.Client(base_url=base_url.rstrip("/"), timeout=60) as client:
        health = HealthResponse.model_validate(_response(client, "GET", "/health").json())
        if health.status != "ok":
            raise ValueError("health endpoint did not report ok")

        before = DataStatusResponse.model_validate(
            _response(client, "GET", "/v1/data-status").json()
        )
        if before.credits.remaining < before.credits.hard_reserve:
            raise ValueError("FortyGuard credit reserve is breached")

        pilot = PilotResponse.model_validate(_response(client, "GET", "/v1/pilot").json())
        candidates = CandidateListResponse.model_validate(
            _response(client, "GET", "/v1/candidates").json()
        )
        MethodologyResponse.model_validate(_response(client, "GET", "/v1/methodology").json())

        if not set(GOLDEN_BUDGETS).issubset(pilot.budget_presets_usd):
            raise ValueError("pilot response is missing a golden-path budget preset")
        if candidates.counts.total != len(candidates.candidates):
            raise ValueError("candidate count does not match candidate records")

        for layer_name in pilot.available_layers:
            layer = LayerResponse.model_validate(
                _response(client, "GET", f"/v1/layers/{layer_name.value}").json()
            )
            if layer.layer != layer_name or not layer.features:
                raise ValueError(f"layer '{layer_name.value}' is empty or mismatched")

        candidate_by_id = {candidate.id: candidate for candidate in candidates.candidates}
        portfolios: dict[int, PortfolioResult] = {}
        for budget in GOLDEN_BUDGETS:
            payload = {"budget_usd": budget}
            first = PortfolioResult.model_validate(
                _response(client, "POST", "/v1/optimize", json=payload).json()
            )
            repeated = PortfolioResult.model_validate(
                _response(client, "POST", "/v1/optimize", json=payload).json()
            )
            if first != repeated:
                raise ValueError(f"optimizer result is not deterministic at ${budget:,}")
            if first.total_cost_usd > budget:
                raise ValueError(f"portfolio exceeds its ${budget:,} budget")
            selected = [
                candidate_by_id[candidate_id]
                for candidate_id in first.selected_candidate_ids
            ]
            if len({candidate.site_id for candidate in selected}) != len(selected):
                raise ValueError(
                    f"portfolio selects multiple interventions at one site for ${budget:,}"
                )
            portfolios[budget] = first

        selected_id = portfolios[1_000_000].selected_candidate_ids[0]
        selected_candidate = candidate_by_id[selected_id]
        site = SiteResponse.model_validate(
            _response(client, "GET", f"/v1/sites/{selected_candidate.site_id}").json()
        )
        if selected_id not in {option.candidate.id for option in site.options}:
            raise ValueError("selected candidate is missing from its site response")
        explanation = GroundedExplanation.model_validate(
            _response(
                client,
                "POST",
                f"/v1/sites/{selected_candidate.site_id}/explanation",
                json={"candidate_id": selected_id, "budget_usd": 1_000_000},
            ).json()
        )
        if explanation.candidate_id != selected_id:
            raise ValueError("explanation does not match the selected candidate")

        after = DataStatusResponse.model_validate(
            _response(client, "GET", "/v1/data-status").json()
        )
        if after.credits != before.credits:
            raise ValueError("credit counters changed while exercising the cached demo")

    return (
        f"PASS: {pilot.name}; {len(pilot.available_layers)} layers; "
        f"{candidates.counts.total} candidates; budgets $500,000/$1,000,000; "
        f"credits unchanged at {after.credits.remaining:,} remaining"
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("COOLSPOT_API_BASE_URL", "http://127.0.0.1:8000"),
        help="API origin (default: %(default)s)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run validation and return a process exit code."""

    args = _parse_args(argv)
    print(validate_demo(args.base_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
