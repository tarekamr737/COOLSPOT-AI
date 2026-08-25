"""Decision-level ranking comparison for the exceedance heat component."""

import json
import math
from pathlib import Path

from api.app.services.candidates import build_candidates, load_candidates
from api.app.services.feature_table import (
    build_feature_table,
    canonical_feature_table_bytes,
    load_scoring_config,
)
from api.app.services.optimizer import load_optimizer_config, optimize_portfolio


def test_exceedance_materially_changes_ranking_and_measures_portfolio_effect(
    tmp_path: Path,
) -> None:
    baseline_config = load_scoring_config().model_dump(mode="json")
    baseline_config["heat_weights"] = {
        "temperature": 0.5,
        "persistence": 0.5,
        "exceedance": 0.0,
    }
    baseline_config_path = tmp_path / "baseline-scoring.json"
    baseline_config_path.write_text(
        json.dumps(baseline_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    baseline_feature_path = tmp_path / "baseline-features.json"
    baseline_feature_path.write_bytes(
        canonical_feature_table_bytes(
            build_feature_table(config_path=baseline_config_path)
        )
    )

    current_candidates = load_candidates().candidates
    baseline_candidates = build_candidates(feature_table_path=baseline_feature_path).candidates
    current_rank = tuple(
        item.id
        for item in sorted(current_candidates, key=lambda item: (-item.benefit_score, item.id))
    )
    baseline_rank = tuple(
        item.id
        for item in sorted(
            baseline_candidates, key=lambda item: (-item.benefit_score, item.id)
        )
    )
    current_positions = {
        candidate_id: position for position, candidate_id in enumerate(current_rank, start=1)
    }
    baseline_positions = {
        candidate_id: position for position, candidate_id in enumerate(baseline_rank, start=1)
    }
    common_ids = current_positions.keys() & baseline_positions.keys()
    changed_common_rank_count = sum(
        current_positions[candidate_id] != baseline_positions[candidate_id]
        for candidate_id in common_ids
    )
    candidate_set_change_count = len(current_positions.keys() ^ baseline_positions.keys())
    maximum_rank_shift = max(
        abs(current_positions[candidate_id] - baseline_positions[candidate_id])
        for candidate_id in common_ids
    )

    optimizer_config = load_optimizer_config()
    replacement_rates: dict[int, float] = {}
    for budget in optimizer_config.budget_presets_usd:
        current = optimize_portfolio(
            budget, candidates=current_candidates, config=optimizer_config
        )
        baseline = optimize_portfolio(
            budget, candidates=baseline_candidates, config=optimizer_config
        )
        current_ids = set(current.selected_candidate_ids)
        baseline_ids = set(baseline.selected_candidate_ids)
        replacement_rates[budget] = len(current_ids - baseline_ids) / len(current_ids)

    materially_changed = changed_common_rank_count + candidate_set_change_count
    assert materially_changed >= math.ceil(len(current_candidates) * 0.10)
    assert maximum_rank_shift > 0
    assert set(replacement_rates) == set(optimizer_config.budget_presets_usd)
    assert all(0 <= rate <= 1 for rate in replacement_rates.values())
