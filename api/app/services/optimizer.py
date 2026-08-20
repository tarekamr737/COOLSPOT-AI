"""Deterministic integer CP-SAT portfolio optimization."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Literal, Self

from ortools.sat.python import cp_model
from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.app.services.candidates import Candidate, load_candidates
from api.app.services.interventions import InterventionType

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OPTIMIZER_CONFIG_PATH = ROOT / "config" / "optimizer.json"


class OptimizerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    version: str = Field(pattern=r"^1\.0$")
    budget_presets_usd: tuple[int, ...] = Field(min_length=1)
    custom_budget_min_usd: int = Field(gt=0)
    custom_budget_max_usd: int = Field(gt=0)
    objective_scale: int = Field(ge=1_000, le=1_000_000_000)
    max_solve_seconds: float = Field(gt=0, le=60)
    determinism_note: str = Field(min_length=40)
    objective_note: str = Field(min_length=40)
    equity_note: str = Field(min_length=40)

    @model_validator(mode="after")
    def validate_budgets(self) -> Self:
        presets = self.budget_presets_usd
        if presets != tuple(sorted(set(presets))):
            raise ValueError("budget presets must be unique and sorted")
        if self.custom_budget_min_usd > self.custom_budget_max_usd:
            raise ValueError("custom budget minimum must not exceed maximum")
        if any(
            budget < self.custom_budget_min_usd
            or budget > self.custom_budget_max_usd
            for budget in presets
        ):
            raise ValueError("budget presets must fall within custom budget bounds")
        return self


class PortfolioCategoryCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shade_structure: int = Field(ge=0)
    tree_canopy: int = Field(ge=0)
    cool_pavement: int = Field(ge=0)


class EquitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    mean_selected_vulnerability_score: float | None = Field(default=None, ge=0, le=1)
    score_sum: float = Field(ge=0)
    note: str = Field(min_length=40)


class PortfolioResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    solver_status: Literal["optimal"] = "optimal"
    budget_usd: int = Field(gt=0)
    total_cost_usd: int = Field(ge=0)
    unused_budget_usd: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    selected_candidate_ids: tuple[str, ...]
    total_modeled_impact_score: float = Field(ge=0)
    integer_objective_value: int = Field(ge=0)
    objective_scale: int = Field(gt=0)
    category_counts: PortfolioCategoryCounts
    equity_summary: EquitySummary

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        if self.total_cost_usd + self.unused_budget_usd != self.budget_usd:
            raise ValueError("portfolio costs do not balance to the budget")
        if self.selected_count != len(self.selected_candidate_ids):
            raise ValueError("selected count does not match candidate IDs")
        if self.selected_candidate_ids != tuple(sorted(set(self.selected_candidate_ids))):
            raise ValueError("selected candidate IDs must be unique and sorted")
        category_total = sum(self.category_counts.model_dump().values())
        if category_total != self.selected_count:
            raise ValueError("category counts do not match selected count")
        return self


class OptimizationError(RuntimeError):
    """The deterministic model could not return a proven optimal solution."""


def load_optimizer_config(path: Path = DEFAULT_OPTIMIZER_CONFIG_PATH) -> OptimizerConfig:
    return OptimizerConfig.model_validate_json(path.read_text(encoding="utf-8"))


def _modeled_impact(candidate: Candidate) -> float:
    return candidate.benefit_score * candidate.feasibility_score * candidate.confidence


def _primary_coefficient(candidate: Candidate, scale: int) -> int:
    return max(0, round(_modeled_impact(candidate) * scale))


def optimize_portfolio(
    budget_usd: int,
    *,
    candidates: tuple[Candidate, ...] | None = None,
    config: OptimizerConfig | None = None,
) -> PortfolioResult:
    active_config = config or load_optimizer_config()
    if not (
        active_config.custom_budget_min_usd
        <= budget_usd
        <= active_config.custom_budget_max_usd
    ):
        raise ValueError(
            f"budget must be between ${active_config.custom_budget_min_usd:,} and "
            f"${active_config.custom_budget_max_usd:,}"
        )

    supplied_candidates = candidates if candidates is not None else load_candidates().candidates
    if not supplied_candidates:
        raise ValueError("at least one candidate is required")
    candidate_ids = [candidate.id for candidate in supplied_candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate IDs must be unique")
    active_candidates = tuple(
        sorted(supplied_candidates, key=lambda candidate: candidate.id)
    )

    model = cp_model.CpModel()
    variables = [
        model.new_bool_var(f"candidate_{index}")
        for index in range(len(active_candidates))
    ]
    model.add(
        sum(
            candidate.planning_cost_usd * variable
            for candidate, variable in zip(active_candidates, variables, strict=True)
        )
        <= budget_usd
    )

    variables_by_site: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    for candidate, variable in zip(active_candidates, variables, strict=True):
        variables_by_site[candidate.site_id].append(variable)
    for site_variables in variables_by_site.values():
        model.add(sum(site_variables) <= 1)

    primary_coefficients = tuple(
        _primary_coefficient(candidate, active_config.objective_scale)
        for candidate in active_candidates
    )
    tie_break_factor = sum(range(1, len(active_candidates) + 1)) + 1
    combined_coefficients = tuple(
        coefficient * tie_break_factor + len(active_candidates) - index
        for index, coefficient in enumerate(primary_coefficients)
    )
    model.maximize(
        sum(
            coefficient * variable
            for coefficient, variable in zip(
                combined_coefficients, variables, strict=True
            )
        )
    )
    model.add_decision_strategy(
        variables,
        cp_model.CHOOSE_FIRST,
        cp_model.SELECT_MAX_VALUE,
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = active_config.max_solve_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.search_branching = cp_model.FIXED_SEARCH
    status = solver.solve(model)
    if status != cp_model.OPTIMAL:
        status_name = solver.status_name(status)
        raise OptimizationError(
            f"CP-SAT did not prove an optimal portfolio within "
            f"{active_config.max_solve_seconds:g}s (status={status_name})"
        )

    selected_indexes = tuple(
        index for index, variable in enumerate(variables) if solver.value(variable) == 1
    )
    selected = tuple(active_candidates[index] for index in selected_indexes)
    selected_ids = tuple(sorted(candidate.id for candidate in selected))
    total_cost = sum(candidate.planning_cost_usd for candidate in selected)
    impacts = tuple(_modeled_impact(candidate) for candidate in selected)
    equity_scores = tuple(candidate.equity_score for candidate in selected)
    equity_sum = math.fsum(equity_scores)
    return PortfolioResult(
        budget_usd=budget_usd,
        total_cost_usd=total_cost,
        unused_budget_usd=budget_usd - total_cost,
        selected_count=len(selected),
        selected_candidate_ids=selected_ids,
        total_modeled_impact_score=round(math.fsum(impacts), 8),
        integer_objective_value=sum(primary_coefficients[index] for index in selected_indexes),
        objective_scale=active_config.objective_scale,
        category_counts=PortfolioCategoryCounts(
            shade_structure=sum(
                candidate.intervention_type == InterventionType.SHADE_STRUCTURE
                for candidate in selected
            ),
            tree_canopy=sum(
                candidate.intervention_type == InterventionType.TREE_CANOPY
                for candidate in selected
            ),
            cool_pavement=sum(
                candidate.intervention_type == InterventionType.COOL_PAVEMENT
                for candidate in selected
            ),
        ),
        equity_summary=EquitySummary(
            mean_selected_vulnerability_score=(
                round(equity_sum / len(selected), 8) if selected else None
            ),
            score_sum=round(equity_sum, 8),
            note=active_config.equity_note,
        ),
    )
