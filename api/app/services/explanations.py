"""Deterministic, evidence-only explanations for selected recommendations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.app.services.candidates import Candidate, CandidateEvidence
from api.app.services.feature_table import TileFeature
from api.app.services.interventions import InterventionDefinition
from api.app.services.optimizer import PortfolioResult


class GroundedExplanation(BaseModel):
    """A claim-safe explanation assembled only from validated decision records."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    mode: Literal["template"] = "template"
    site_id: str
    candidate_id: str
    budget_usd: int = Field(gt=0)
    summary: str = Field(min_length=80)
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
    modeled_impact = (
        candidate.benefit_score * candidate.feasibility_score * candidate.confidence
    )
    summary = (
        f"At the ${portfolio.budget_usd:,} screening budget, {candidate.site_name} is one of "
        f"{portfolio.selected_count} sites in the optimal portfolio for a "
        f"{intervention.label.lower()}. Its representative tile has modeled priority score "
        f"{tile.scores.priority:.3f}; after the disclosed feasibility and confidence screening "
        f"scalars, this candidate contributes {modeled_impact:.3f} modeled impact score."
    )
    return GroundedExplanation(
        site_id=candidate.site_id,
        candidate_id=candidate.id,
        budget_usd=portfolio.budget_usd,
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
