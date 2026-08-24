"""Tests for the frozen real Pacoima exceedance layer."""

import json
from pathlib import Path

from api.app.fortyguard_models import FortyGuardEndpoint
from api.app.services.fortyguard import canonical_request_hash
from api.app.services.heatmap_data import (
    PacoimaExceedanceArtifact,
    load_heatmap_artifact,
)
from scripts.cache_fortyguard_exceedance import OUTPUT_PATH
from scripts.measure_fortyguard_exceedance import build_exceedance_request


def test_real_exceedance_artifact_is_aligned_deterministic_and_secret_free() -> None:
    text = Path(OUTPUT_PATH).read_text(encoding="utf-8")
    artifact = PacoimaExceedanceArtifact.model_validate_json(text)
    layer = artifact.layer
    tcm = load_heatmap_artifact().layers[0]
    request = build_exceedance_request()

    assert layer.analytic_type == "exceedance"
    assert layer.feature_count == len(layer.result.map_data.features) == 2_001
    assert layer.observed_credit_delta == 4_220
    assert layer.date_time == request.date_time
    assert layer.granularity_m == request.granularity == tcm.granularity_m == 100
    assert tuple(
        (feature.id, feature.geometry) for feature in layer.result.map_data.features
    ) == tuple((feature.id, feature.geometry) for feature in tcm.result.map_data.features)
    assert layer.request_hash == canonical_request_hash(
        FortyGuardEndpoint.HEATMAP, request
    )
    assert all(
        isinstance(feature.properties["value"], (int, float))
        for feature in layer.result.map_data.features
    )
    assert '"api_key"' not in text
    assert '"subscription_id"' not in text
    assert text == json.dumps(
        artifact.model_dump(mode="json"), indent=2, sort_keys=True
    ) + "\n"
