"""Tests for the frozen real Pacoima TCM and persistence layers."""

import json
from pathlib import Path

from api.app.fortyguard_models import FortyGuardEndpoint
from api.app.services.fortyguard import canonical_request_hash
from api.app.services.heatmap_data import PacoimaHeatmapArtifact
from scripts.cache_fortyguard_heatmaps import (
    OUTPUT_PATH,
    build_persistence_request,
)
from scripts.measure_fortyguard_heatmap import build_request, load_heatmap_config


def test_persistence_request_matches_config_and_tcm_spatial_context() -> None:
    config = load_heatmap_config()
    tcm = build_request()
    persistence = build_persistence_request()

    assert persistence.polygon_aoi == tcm.polygon_aoi
    assert persistence.granularity == tcm.granularity == 100
    assert persistence.date_time.start_date == tcm.date_time.start_date
    assert persistence.date_time.filter_type == 3
    assert persistence.analytic_type == "persistence"
    assert persistence.threshold == config.persistence_threshold_c == 30
    assert persistence.direction == config.persistence_direction == "above"
    assert len(config.persistence_threshold_rationale) >= 20
    assert canonical_request_hash(FortyGuardEndpoint.HEATMAP, persistence) == (
        "31f95902a1ee11fd073b3be2f2afdb4b083cb3a3c9ff50182efbab013a4dcd81"
    )


def test_real_heatmap_artifact_is_deterministic_aligned_and_secret_free() -> None:
    text = Path(OUTPUT_PATH).read_text(encoding="utf-8")
    artifact = PacoimaHeatmapArtifact.model_validate_json(text)
    by_type = {layer.analytic_type: layer for layer in artifact.layers}
    tcm = by_type["tcm"]
    persistence = by_type["persistence"]

    assert tcm.feature_count == persistence.feature_count == 2_001
    assert tcm.observed_credit_delta == persistence.observed_credit_delta == 4_220
    assert all(
        isinstance(feature.properties["average_temperature"], (int, float))
        for feature in tcm.result.map_data.features
    )
    assert all(
        isinstance(feature.properties["value"], (int, float))
        for feature in persistence.result.map_data.features
    )
    assert '"api_key"' not in text
    assert '"subscription_id"' not in text
    assert text == json.dumps(
        artifact.model_dump(mode="json"), indent=2, sort_keys=True
    ) + "\n"
