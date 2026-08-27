"""Grounding and fallback tests for optional OpenRouter explanations."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import httpx2

from api.app.services.decision_api import candidates_response, site_response
from api.app.services.explanations import (
    explain_selected_candidate,
    explain_with_optional_llm,
)
from api.app.services.feature_table import TileFeature
from api.app.services.optimizer import optimize_portfolio
from api.app.services.scenarios import ScoringPreset


class StubTransport:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0
        self.prompts: list[str] = []

    async def complete(self, *, api_key: str, model: str, prompt: str) -> str:
        assert api_key == "test-key"
        assert model == "nvidia/nemotron-3-ultra-550b-a55b:free"
        assert "Verified summary:" in prompt
        self.calls += 1
        self.prompts.append(prompt)
        return self.content


class RateLimitedTransport:
    async def complete(self, *, api_key: str, model: str, prompt: str) -> str:
        request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        response = httpx2.Response(429, request=request)
        raise httpx2.HTTPStatusError("rate limited", request=request, response=response)


class RepairTransport:
    def __init__(self, first: str, repaired: str) -> None:
        self.responses = iter((first, repaired))
        self.calls = 0
        self.prompts: list[str] = []

    async def complete(self, *, api_key: str, model: str, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        return next(self.responses)


def selected_context() -> tuple[object, object, object, object]:
    portfolio = optimize_portfolio(500_000)
    candidate = next(
        item
        for item in candidates_response().candidates
        if item.id in portfolio.selected_candidate_ids
    )
    site = site_response(candidate.site_id)
    assert site is not None
    option = next(item for item in site.options if item.candidate.id == candidate.id)
    return candidate, option.tile, option.intervention, portfolio


def test_openrouter_rewrites_only_the_summary_and_is_cached(tmp_path: Path) -> None:
    candidate, tile, intervention, portfolio = selected_context()
    transport = StubTransport(
        "This location ranks well because the supplied heat, activity, vulnerability, "
        "feasibility, and confidence evidence supports its place in the selected portfolio; "
        "the outcome is not guaranteed."
    )
    kwargs = {
        "candidate": candidate,
        "tile": tile,
        "intervention": intervention,
        "portfolio": portfolio,
        "environ": {
            "EXPLANATION_MODE": "openrouter",
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "nvidia/nemotron-3-ultra-550b-a55b:free",
        },
        "transport": transport,
        "cache_root": tmp_path,
    }

    first = asyncio.run(explain_with_optional_llm(**kwargs))  # type: ignore[arg-type]
    second = asyncio.run(explain_with_optional_llm(**kwargs))  # type: ignore[arg-type]
    regenerated = asyncio.run(
        explain_with_optional_llm(**kwargs, regenerate=True)  # type: ignore[arg-type]
    )

    assert first.mode == "openrouter"
    assert first.why_selected == second.why_selected
    assert first.limitations == second.limitations
    assert regenerated.mode == "openrouter"
    assert transport.calls == 2
    assert "Previous wording to avoid:" in transport.prompts[1]


def test_valid_explanation_survives_read_only_serverless_cache(tmp_path: Path) -> None:
    candidate, tile, intervention, portfolio = selected_context()
    transport = StubTransport(
        "This site ranks in the selected portfolio because the supplied heat and planning "
        "evidence supports it; the planning cost is an assumption and field checks remain "
        "required."
    )

    with patch.object(Path, "mkdir", side_effect=OSError("read-only filesystem")):
        result = asyncio.run(
            explain_with_optional_llm(
                candidate=candidate,  # type: ignore[arg-type]
                tile=tile,  # type: ignore[arg-type]
                intervention=intervention,  # type: ignore[arg-type]
                portfolio=portfolio,  # type: ignore[arg-type]
                environ={
                    "EXPLANATION_MODE": "openrouter",
                    "OPENROUTER_API_KEY": "test-key",
                },
                transport=transport,
                cache_root=tmp_path / "unavailable",
            )
        )

    assert result.mode == "openrouter"
    assert result.fallback_reason is None
    assert transport.calls == 1


def test_peak_heat_hour_is_explanation_context_only() -> None:
    candidate, tile, intervention, portfolio = selected_context()
    assert isinstance(tile, TileFeature)
    result = explain_selected_candidate(
        candidate=candidate,  # type: ignore[arg-type]
        tile=tile,
        intervention=intervention,  # type: ignore[arg-type]
        portfolio=portfolio,  # type: ignore[arg-type]
    )
    heat_statement = next(
        statement for statement in result.why_selected if "Peak temperature" in statement
    )

    assert f"{tile.heat.peak_heat_hour_utc:02d}:00 UTC" in heat_statement
    assert "explanation-only" in heat_statement
    assert "not used in scoring" in heat_statement
    assert "not used in scoring or pedestrian-activity inference" in heat_statement
    assert "peak pedestrian" not in heat_statement.lower()


def test_explanation_uses_the_active_planning_scenario() -> None:
    portfolio = optimize_portfolio(
        500_000,
        scoring_preset=ScoringPreset.HEAT_FIRST,
    )
    candidate = next(
        item
        for item in candidates_response().candidates
        if item.id in portfolio.selected_candidate_ids
    )
    site = site_response(candidate.site_id)
    assert site is not None
    option = next(item for item in site.options if item.candidate.id == candidate.id)

    result = explain_selected_candidate(
        candidate=candidate,
        tile=option.tile,
        intervention=option.intervention,
        portfolio=portfolio,
    )

    assert result.scoring_preset == ScoringPreset.HEAT_FIRST
    assert "heat-first portfolio" in result.summary


def test_unsafe_model_claim_falls_back_to_template(tmp_path: Path) -> None:
    candidate, tile, intervention, portfolio = selected_context()
    result = asyncio.run(
        explain_with_optional_llm(
            candidate=candidate,  # type: ignore[arg-type]
            tile=tile,  # type: ignore[arg-type]
            intervention=intervention,  # type: ignore[arg-type]
            portfolio=portfolio,  # type: ignore[arg-type]
            environ={
                "EXPLANATION_MODE": "openrouter",
                "OPENROUTER_API_KEY": "test-key",
            },
            transport=StubTransport("This will reduce temperatures and save lives."),
            cache_root=tmp_path,
        )
    )

    assert result.mode == "template"
    assert result.fallback_reason is not None
    assert "grounding checks" in result.fallback_reason


def test_rejected_model_wording_gets_one_grounded_repair_attempt(tmp_path: Path) -> None:
    candidate, tile, intervention, portfolio = selected_context()
    transport = RepairTransport(
        "This investment will reduce temperatures for 999 people.",
        "This site ranks in the selected portfolio because the supplied heat and planning "
        "evidence supports it; the planning cost is an assumption and field checks remain "
        "required.",
    )
    result = asyncio.run(
        explain_with_optional_llm(
            candidate=candidate,  # type: ignore[arg-type]
            tile=tile,  # type: ignore[arg-type]
            intervention=intervention,  # type: ignore[arg-type]
            portfolio=portfolio,  # type: ignore[arg-type]
            environ={
                "EXPLANATION_MODE": "openrouter",
                "OPENROUTER_API_KEY": "test-key",
            },
            transport=transport,
            cache_root=tmp_path,
        )
    )

    assert result.mode == "openrouter"
    assert result.fallback_reason is None
    assert transport.calls == 2
    assert "Correction required:" in transport.prompts[1]


def test_model_cannot_add_a_number_absent_from_supplied_evidence(tmp_path: Path) -> None:
    candidate, tile, intervention, portfolio = selected_context()
    result = asyncio.run(
        explain_with_optional_llm(
            candidate=candidate,  # type: ignore[arg-type]
            tile=tile,  # type: ignore[arg-type]
            intervention=intervention,  # type: ignore[arg-type]
            portfolio=portfolio,  # type: ignore[arg-type]
            environ={
                "EXPLANATION_MODE": "openrouter",
                "OPENROUTER_API_KEY": "test-key",
            },
            transport=StubTransport("The verified evidence gives this site a score of 999."),
            cache_root=tmp_path,
        )
    )

    assert result.mode == "template"
    assert result.fallback_reason is not None
    assert "grounding checks" in result.fallback_reason


def test_openrouter_rate_limit_is_visible_with_a_safe_fallback(tmp_path: Path) -> None:
    candidate, tile, intervention, portfolio = selected_context()
    result = asyncio.run(
        explain_with_optional_llm(
            candidate=candidate,  # type: ignore[arg-type]
            tile=tile,  # type: ignore[arg-type]
            intervention=intervention,  # type: ignore[arg-type]
            portfolio=portfolio,  # type: ignore[arg-type]
            environ={
                "EXPLANATION_MODE": "openrouter",
                "OPENROUTER_API_KEY": "test-key",
            },
            transport=RateLimitedTransport(),
            cache_root=tmp_path,
        )
    )

    assert result.mode == "template"
    assert result.fallback_reason is not None
    assert "temporarily rate limited" in result.fallback_reason
