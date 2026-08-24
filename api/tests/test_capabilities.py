"""Tests for explicit FortyGuard optional-feature gating."""

import pytest

from api.app.services.capabilities import (
    AccessState,
    FeatureDisabledError,
    FortyGuardFeature,
    load_capabilities,
)


def test_required_heatmaps_are_enabled_from_cache() -> None:
    manifest = load_capabilities()

    for feature in (
        FortyGuardFeature.HEATMAP_TCM,
        FortyGuardFeature.HEATMAP_PERSISTENCE,
    ):
        capability = manifest.require_enabled(feature)
        assert capability.access == AccessState.CONFIRMED
        assert capability.cached_artifact == (
            "data/processed/pacoima_fortyguard_heatmaps.json"
        )


def test_optional_features_are_explicitly_gated() -> None:
    manifest = load_capabilities()
    enabled = {
        FortyGuardFeature.HEATMAP_TCM,
        FortyGuardFeature.HEATMAP_PERSISTENCE,
        FortyGuardFeature.ENVIRONMENTAL_PARAMETERS,
        FortyGuardFeature.STREET_VIEW_SEGMENTATION,
    }

    assert manifest.optional_live_probes_made == 2
    assert manifest.credits_used == 200_220
    assert manifest.credits_remaining == 1_799_780
    env_params = manifest.require_enabled(FortyGuardFeature.ENVIRONMENTAL_PARAMETERS)
    assert env_params.cached_artifact == (
        "data/processed/fortyguard_env_params_probe.json"
    )
    street_view = manifest.require_enabled(FortyGuardFeature.STREET_VIEW_SEGMENTATION)
    assert street_view.cached_artifact == "data/processed/pacoima_streetview_sites"
    for feature in set(FortyGuardFeature) - enabled:
        capability = manifest.get(feature)
        assert capability.enabled is False
        assert capability.access == AccessState.UNCONFIRMED
        assert capability.probe_attempted is False
        with pytest.raises(FeatureDisabledError, match=feature.value):
            manifest.require_enabled(feature)
