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
        FortyGuardFeature.HEATMAP_EXCEEDANCE,
        FortyGuardFeature.HEATMAP_TIME_OF_MEASURE,
        FortyGuardFeature.ENVIRONMENTAL_PARAMETERS,
        FortyGuardFeature.SATELLITE_SEGMENTATION,
        FortyGuardFeature.STREET_VIEW_SEGMENTATION,
    }

    assert manifest.optional_live_probes_made == 6
    assert manifest.credits_used == 240_720
    assert manifest.credits_remaining == 1_759_280
    exceedance = manifest.require_enabled(FortyGuardFeature.HEATMAP_EXCEEDANCE)
    assert exceedance.cached_artifact == (
        "data/processed/pacoima_fortyguard_exceedance.json"
    )
    peak_time = manifest.require_enabled(FortyGuardFeature.HEATMAP_TIME_OF_MEASURE)
    assert peak_time.cached_artifact == (
        "data/processed/pacoima_fortyguard_time_of_measure.json"
    )
    env_params = manifest.require_enabled(FortyGuardFeature.ENVIRONMENTAL_PARAMETERS)
    assert env_params.cached_artifact == (
        "data/processed/pacoima_environmental_sites"
    )
    street_view = manifest.require_enabled(FortyGuardFeature.STREET_VIEW_SEGMENTATION)
    assert street_view.cached_artifact == "data/processed/pacoima_streetview_sites"
    satellite = manifest.require_enabled(FortyGuardFeature.SATELLITE_SEGMENTATION)
    assert satellite.cached_artifact == "data/processed/fortyguard_satellite_probe.json"
    heat_intelligence = manifest.get(FortyGuardFeature.HEAT_INTELLIGENCE_REPORT)
    assert heat_intelligence.probe_attempted is True
    assert heat_intelligence.access == AccessState.UNCONFIRMED
    assert heat_intelligence.enabled is False
    for feature in set(FortyGuardFeature) - enabled:
        capability = manifest.get(feature)
        assert capability.enabled is False
        assert capability.access == AccessState.UNCONFIRMED
        with pytest.raises(FeatureDisabledError, match=feature.value):
            manifest.require_enabled(feature)
