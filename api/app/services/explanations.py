"""Grounded explanations for selected recommendations."""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Literal, Protocol

import httpx2
from pydantic import BaseModel, ConfigDict, Field

from api.app.services.candidates import Candidate, CandidateEvidence
from api.app.services.feature_table import TileFeature
from api.app.services.interventions import InterventionDefinition
from api.app.services.optimizer import PortfolioResult
from api.app.services.scenarios import ScoringPreset, scenario_priority
from api.app.settings import load_project_env


class GroundedExplanation(BaseModel):
    """A claim-safe explanation assembled only from validated decision records."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: Literal["template", "openrouter"] = "template"
    model: str | None = None
    fallback_reason: str | None = None
    site_id: str
    candidate_id: str
    budget_usd: int = Field(gt=0)
    scoring_preset: ScoringPreset
    summary: str = Field(min_length=80, max_length=700)
    why_selected: tuple[str, ...] = Field(min_length=5)
    limitations: tuple[str, ...] = Field(min_length=3)
    evidence: tuple[CandidateEvidence, ...] = Field(min_length=5)


def explain_selected_candidate(
    *,
    candidate: Candidate,
    tile: TileFeature,
    intervention: InterventionDefinition,
    portfolio: PortfolioResult,
) -> GroundedExplanation:
    """Explain a selected candidate without generating or inferring new evidence."""

    if candidate.id not in portfolio.selected_candidate_ids:
        raise ValueError(
            f"candidate '{candidate.id}' is not selected at the "
            f"${portfolio.budget_usd:,} budget"
        )
    priority_score = scenario_priority(tile.scores, portfolio.scoring_weights)
    factors = candidate.value_explanation.factors
    modeled_impact = (
        priority_score
        * factors.suitability_score
        * factors.feasibility_score
        * factors.confidence_score
    )
    preset_label = portfolio.scoring_preset.value.replace("_", "-")
    summary = (
        f"At the ${portfolio.budget_usd:,} screening budget, {candidate.site_name} is one of "
        f"{portfolio.selected_count} sites in the optimal {preset_label} portfolio for a "
        f"{intervention.label.lower()}. Its representative tile has modeled priority score "
        f"{priority_score:.3f}; after the disclosed suitability, feasibility, and "
        f"confidence scalars, this candidate contributes "
        f"{modeled_impact:.3f} modeled impact score."
    )
    return GroundedExplanation(
        site_id=candidate.site_id,
        candidate_id=candidate.id,
        budget_usd=portfolio.budget_usd,
        scoring_preset=portfolio.scoring_preset,
        summary=summary,
        why_selected=tuple(item.statement for item in candidate.evidence),
        limitations=(
            "This explanation restates structured screening evidence; it does not predict a "
            "site temperature reduction, people protected, or a guaranteed outcome.",
            intervention.uncertainty.summary,
            f"The ${intervention.planning_cost.estimate_usd:,} planning cost and "
            f"${intervention.planning_cost.low_usd:,} to "
            f"${intervention.planning_cost.high_usd:,} range are assumptions, not a contractor "
            "quote; field and preconstruction checks remain required.",
        ),
        evidence=candidate.evidence,
    )


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
PROMPT_VERSION = "2"
ROOT = Path(__file__).resolve().parents[3]
EXPLANATION_CACHE = ROOT / "data" / "runtime" / "explanations"


class ExplanationTransport(Protocol):
    async def complete(self, *, api_key: str, model: str, prompt: str) -> str: ...


class OpenRouterTransport:
    async def complete(self, *, api_key: str, model: str, prompt: str) -> str:
        async with httpx2.AsyncClient(timeout=30) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": os.environ.get("COOLSPOT_PUBLIC_URL", "http://localhost"),
                    "X-OpenRouter-Title": "COOLSPOT AI",
                },
                json={
                    "model": model,
                    "temperature": 0,
                    "max_tokens": 1400,
                    "reasoning": {"effort": "low", "exclude": True},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Rewrite the supplied planning explanation in 45 to 70 words and "
                                "no more than three sentences. "
                                "Use only supplied facts and numbers. Do not add predictions, "
                                "causal claims, people protected, lives saved, or temperature "
                                "reductions. Lead with why the site was selected, then state the "
                                "price basis and the most important limitation. Return one "
                                "paragraph only."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenRouter returned an empty explanation")
        return content.strip()


def _cache_key(explanation: GroundedExplanation, model: str) -> str:
    payload = json.dumps(
        {
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "candidate_id": explanation.candidate_id,
            "budget_usd": explanation.budget_usd,
            "scoring_preset": explanation.scoring_preset,
            "summary": explanation.summary,
            "why_selected": explanation.why_selected,
            "limitations": explanation.limitations,
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _safe_model_summary(content: str, template: GroundedExplanation) -> bool:
    lowered = content.lower()
    prohibited = (
        "will save",
        "saves lives",
        "will protect",
        "people will be protected",
        "is guaranteed",
        "guaranteed to",
        "will reduce",
        "will lower",
    )
    if any(phrase in lowered for phrase in prohibited):
        return False
    supplied_text = " ".join(
        (template.summary, *template.why_selected, *template.limitations)
    )
    supplied_numbers = set(re.findall(r"-?\d+(?:\.\d+)?", supplied_text.replace(",", "")))
    output_numbers = set(re.findall(r"-?\d+(?:\.\d+)?", content.replace(",", "")))
    return output_numbers <= supplied_numbers


async def explain_with_optional_llm(
    *,
    candidate: Candidate,
    tile: TileFeature,
    intervention: InterventionDefinition,
    portfolio: PortfolioResult,
    environ: dict[str, str] | None = None,
    transport: ExplanationTransport | None = None,
    cache_root: Path = EXPLANATION_CACHE,
    regenerate: bool = False,
) -> GroundedExplanation:
    """Use OpenRouter when configured, preserving a deterministic safe fallback."""

    template = explain_selected_candidate(
        candidate=candidate,
        tile=tile,
        intervention=intervention,
        portfolio=portfolio,
    )
    source = load_project_env(environ)
    if source.get("EXPLANATION_MODE", "template") != "openrouter":
        return template
    api_key = source.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return template
    model = source.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip()
    key = _cache_key(template, model)
    cache_path = cache_root / f"{key}.json"
    previous_summary: str | None = None
    if cache_path.exists():
        try:
            cached = GroundedExplanation.model_validate_json(
                cache_path.read_text(encoding="utf-8")
            )
            if not regenerate:
                return cached
            previous_summary = cached.summary
        except ValueError:
            pass

    prompt = (
        f"Verified summary: {template.summary}\n"
        f"Evidence: {' | '.join(template.why_selected)}\n"
        f"Limitations: {' | '.join(template.limitations)}"
        + (
            f"\nPrevious wording to avoid: {previous_summary}"
            if previous_summary is not None
            else ""
        )
    )
    try:
        content = await (transport or OpenRouterTransport()).complete(
            api_key=api_key,
            model=model,
            prompt=prompt,
        )
        if not _safe_model_summary(content, template):
            return template.model_copy(
                update={
                    "fallback_reason": (
                        "OpenRouter returned wording that did not pass COOLSPOT's grounding "
                        "checks. The deterministic explanation is shown instead."
                    )
                }
            )
        generated = GroundedExplanation.model_validate(
            {
                **template.model_dump(mode="python"),
                "mode": "openrouter",
                "model": model,
                "summary": content,
            }
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".json.part")
        temporary.write_text(generated.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, cache_path)
        return generated
    except httpx2.HTTPStatusError as error:
        reason = (
            "OpenRouter is temporarily rate limited. The deterministic explanation is shown; "
            "use Run AI again later."
            if error.response.status_code == 429
            else "OpenRouter rejected the request. The deterministic explanation is shown."
        )
        return template.model_copy(update={"fallback_reason": reason})
    except httpx2.HTTPError:
        return template.model_copy(
            update={
                "fallback_reason": (
                    "OpenRouter could not be reached. The deterministic explanation is shown; "
                    "use Run AI again when the provider is available."
                )
            }
        )
    except (KeyError, TypeError, ValueError):
        return template.model_copy(
            update={
                "fallback_reason": (
                    "OpenRouter returned an invalid response. The deterministic explanation "
                    "is shown instead."
                )
            }
        )
