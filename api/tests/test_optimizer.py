"""Tests for deterministic CP-SAT portfolio optimization."""

import pytest

from api.app.services.candidates import Candidate, load_candidates
from api.app.services.optimizer import load_optimizer_config, optimize_portfolio
from api.app.services.scenarios import ScoringPreset


def _candidate_with_suitability(candidate: Candidate, suitability: float) -> Candidate:
    payload = candidate.model_dump(mode="json")
    payload.update(
        {
            "planning_cost_usd": 50_000,
            "benefit_score": 0.8,
            "suitability_score": suitability,
            "feasibility_score": 1.0,
            "confidence": 1.0,
        }
    )
    factors = payload["value_explanation"]["factors"]
    factors.update(
        {
            "priority_score": 0.8,
            "suitability_score": suitability,
            "feasibility_score": 1.0,
            "confidence_score": 1.0,
        }
    )
    payload["value_explanation"]["modeled_benefit_score"] = 0.8 * suitability
    payload["value_explanation"]["suitability_basis"] = [
        f"Synthetic regression evidence sets suitability to {suitability:.1f}."
    ]
    return Candidate.model_validate(payload)


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
                candidate.value_explanation.modeled_benefit_score
                for candidate in selected
            ),
            8,
        )
        assert first.integer_objective_value == sum(
            round(
                candidate.value_explanation.modeled_benefit_score
                * config.objective_scale
            )
            for candidate in selected
        )
        assert sum(first.category_counts.model_dump().values()) == first.selected_count


def test_verified_cool_pavement_is_selectable_in_supported_budget_range() -> None:
    artifact = load_candidates()
    config = load_optimizer_config()

    result = optimize_portfolio(
        config.custom_budget_max_usd,
        candidates=artifact.candidates,
        config=config,
    )

    assert result.category_counts.cool_pavement >= 1


def test_scenario_reweights_cached_features_before_optimization() -> None:
    candidates = load_candidates().candidates

    balanced = optimize_portfolio(500_000, candidates=candidates)
    heat_first = optimize_portfolio(
        500_000,
        candidates=candidates,
        scoring_preset=ScoringPreset.HEAT_FIRST,
    )

    assert balanced.scoring_weights.heat == 0.4
    assert heat_first.scoring_weights.heat == 0.5
    assert heat_first.selected_candidate_ids != balanced.selected_candidate_ids


def test_site_constraint_blocks_two_interventions_at_one_site() -> None:
    source = tuple(
        candidate
        for candidate in load_candidates().candidates
        if candidate.intervention_type.value == "shade_structure"
    )
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
    alternate_payload["value_explanation"]["factors"]["priority_score"] = 1.0
    alternate_payload["value_explanation"]["modeled_benefit_score"] = (
        alternate_payload["suitability_score"]
        * alternate_payload["feasibility_score"]
        * alternate_payload["confidence"]
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


def test_intervention_evidence_can_change_portfolio_selection() -> None:
    first, second = load_candidates().candidates[:2]
    assert first.site_id != second.site_id

    first_high = _candidate_with_suitability(first, 0.9)
    second_low = _candidate_with_suitability(second, 0.1)
    first_result = optimize_portfolio(50_000, candidates=(second_low, first_high))

    first_low = _candidate_with_suitability(first, 0.1)
    second_high = _candidate_with_suitability(second, 0.9)
    second_result = optimize_portfolio(50_000, candidates=(first_low, second_high))

    assert first_result.selected_candidate_ids == (first.id,)
    assert second_result.selected_candidate_ids == (second.id,)
