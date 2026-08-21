"""Grounding and fallback tests for optional OpenRouter explanations."""

import asyncio
from pathlib import Path

from api.app.services.decision_api import candidates_response, site_response
from api.app.services.explanations import explain_with_optional_llm
from api.app.services.optimizer import optimize_portfolio


class StubTransport:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete(self, *, api_key: str, model: str, prompt: str) -> str:
        assert api_key == "test-key"
        assert model == "google/gemma-4-26b-a4b-it:free"
        assert "Verified summary:" in prompt
        self.calls += 1
        return self.content


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
        "feasibility, and confidence evidence supports its place in the selected portfolio."
    )
    kwargs = {
        "candidate": candidate,
        "tile": tile,
        "intervention": intervention,
        "portfolio": portfolio,
        "environ": {
            "EXPLANATION_MODE": "openrouter",
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_MODEL": "google/gemma-4-26b-a4b-it:free",
        },
        "transport": transport,
        "cache_root": tmp_path,
    }

    first = asyncio.run(explain_with_optional_llm(**kwargs))  # type: ignore[arg-type]
    second = asyncio.run(explain_with_optional_llm(**kwargs))  # type: ignore[arg-type]

    assert first.mode == "openrouter"
    assert first.why_selected == second.why_selected
    assert first.limitations == second.limitations
    assert transport.calls == 1


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
