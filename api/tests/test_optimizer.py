"""Tests for deterministic CP-SAT portfolio optimization."""

import pytest

from api.app.services.candidates import Candidate, load_candidates
from api.app.services.optimizer import load_optimizer_config, optimize_portfolio


def test_preset_portfolios_are_deterministic_feasible_and_site_exclusive() -> None:
    artifact = load_candidates()
    config = load_optimizer_config()

    for budget in config.budget_presets_usd:
        first = optimize_portfolio(budget, candidates=artifact.candidates, config=config)
        second = optimize_portfolio(
            budget,
            candidates=tuple(reversed(artifact.candidates)),
            config=config,
        )
        by_id = {candidate.id: candidate for candidate in artifact.candidates}
        selected = tuple(by_id[candidate_id] for candidate_id in first.selected_candidate_ids)

        assert first == second
        assert first.solver_status == "optimal"
        assert first.total_cost_usd <= budget
        assert first.unused_budget_usd == budget - first.total_cost_usd
        assert len({candidate.site_id for candidate in selected}) == len(selected)
        assert first.total_modeled_impact_score == round(
            sum(
                candidate.benefit_score
                * candidate.feasibility_score
                * candidate.confidence
                for candidate in selected
            ),
            8,
        )
        assert first.integer_objective_value == sum(
            round(
                candidate.benefit_score
                * candidate.feasibility_score
                * candidate.confidence
                * config.objective_scale
            )
            for candidate in selected
        )
        assert first.category_counts.shade_structure + first.category_counts.tree_canopy == (
            first.selected_count
        )


def test_site_constraint_blocks_two_interventions_at_one_site() -> None:
    source = load_candidates().candidates
    first = source[0]
    alternate_payload = first.model_dump(mode="json")
    alternate_payload.update(
        {
            "id": f"tree_canopy:{first.site_id}",
            "intervention_type": "tree_canopy",
            "benefit_score": 1.0,
            "planning_cost_usd": 50_000,
        }
    )
    alternate = Candidate.model_validate(alternate_payload)
    unrelated = source[1]

    result = optimize_portfolio(100_000, candidates=(first, alternate, unrelated))

    selected = {result_id for result_id in result.selected_candidate_ids}
    same_site = {first.id, alternate.id}
    assert len(selected & same_site) == 1
    assert unrelated.id in selected
    assert result.total_cost_usd <= result.budget_usd


def test_custom_budget_bounds_fail_visibly() -> None:
    config = load_optimizer_config()

    with pytest.raises(ValueError, match="budget must be between"):
        optimize_portfolio(config.custom_budget_min_usd - 1)
    with pytest.raises(ValueError, match="budget must be between"):
        optimize_portfolio(config.custom_budget_max_usd + 1)
