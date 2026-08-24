"""Tests for deterministic scoring, missing data, and the real tile feature table."""

import hashlib
import math
from pathlib import Path

from api.app.services.feature_table import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_FEATURE_TABLE_PATH,
    DEFAULT_PUBLIC_DATA_PATH,
    NormalizedFeature,
    canonical_feature_table_bytes,
    load_feature_table,
    load_scoring_config,
    normalize_values,
    weighted_available,
)
from api.app.services.heatmap_data import DEFAULT_EXCEEDANCE_PATH, DEFAULT_HEATMAP_PATH
from api.app.services.processed_data import load_processed_fixture


def test_normalization_winsorizes_constants_and_preserves_missing_values() -> None:
    output = normalize_values(
        NormalizedFeature.TEMPERATURE,
        (None, 0.0, 5.0, 10.0),
        lower_quantile=0,
        upper_quantile=1,
        constant_score=0,
    )
    assert output.values == (None, 0.0, 0.5, 1.0)
    assert output.metadata.missing_count == 1
    assert output.metadata.constant is False

    winsorized = normalize_values(
        NormalizedFeature.PERSISTENCE,
        (0.0, 1.0, 2.0, 100.0),
        lower_quantile=0.25,
        upper_quantile=0.75,
        constant_score=0,
    )
    assert winsorized.values[0] == 0
    assert winsorized.values[-1] == 1

    constant = normalize_values(
        NormalizedFeature.POI_COUNT,
        (5.0, None, 5.0),
        lower_quantile=0.02,
        upper_quantile=0.98,
        constant_score=0,
    )
    assert constant.values == (0.0, None, 0.0)
    assert constant.metadata.constant is True


def test_weighted_composite_reweights_available_inputs() -> None:
    score = weighted_available(((1.0, 0.5), (None, 0.25), (0.0, 0.25)))

    assert math.isclose(score, 2 / 3)
    assert weighted_available(((None, 0.5), (None, 0.5))) == 0


def test_real_feature_table_is_canonical_complete_and_traceable() -> None:
    table = load_feature_table()
    public = load_processed_fixture(DEFAULT_PUBLIC_DATA_PATH)
    transit_ids = {
        stop_id for tile in table.tiles for stop_id in tile.exposure.transit_stop_ids
    }
    poi_ids = {poi_id for tile in table.tiles for poi_id in tile.exposure.poi_ids}
    proximity_stop_ids = {
        stop_id
        for tile in table.tiles
        for stop_id in tile.exposure.proximity_joined_transit_stop_ids
    }

    assert DEFAULT_FEATURE_TABLE_PATH.read_bytes() == canonical_feature_table_bytes(table)
    assert table.counts.tiles == 2_001
    assert table.counts.unjoined_transit_stops == 0
    assert table.counts.unjoined_pois == 0
    assert table.counts.proximity_joined_transit_stops == 2
    assert proximity_stop_ids == {"metro-stop:10560", "metro-stop:1842"}
    assert transit_ids == {stop.id for stop in public.transit_stops}
    assert poi_ids == {poi.id for poi in public.pois}
    assert table.heatmap_artifact_sha256 == hashlib.sha256(
        Path(DEFAULT_HEATMAP_PATH).read_bytes()
    ).hexdigest()
    assert table.exceedance_artifact_sha256 == hashlib.sha256(
        Path(DEFAULT_EXCEEDANCE_PATH).read_bytes()
    ).hexdigest()
    assert table.public_data_artifact_sha256 == hashlib.sha256(
        Path(DEFAULT_PUBLIC_DATA_PATH).read_bytes()
    ).hexdigest()
    assert table.scoring_config_sha256 == hashlib.sha256(
        Path(DEFAULT_CONFIG_PATH).read_bytes()
    ).hexdigest()
    assert all(
        0 <= component <= 1
        for tile in table.tiles
        for component in tile.scores.model_dump().values()
    )
    assert all(
        0 <= tile.heat.exceedance_score <= 1 and tile.heat.exceedance_hours >= 0
        for tile in table.tiles
    )
    heat_weights = load_scoring_config().heat_weights
    assert heat_weights.model_dump() == {
        "temperature": 0.4,
        "persistence": 0.35,
        "exceedance": 0.25,
    }
    assert all(
        math.isclose(
            tile.scores.heat,
            0.4 * tile.heat.temperature_score
            + 0.35 * tile.heat.persistence_score
            + 0.25 * tile.heat.exceedance_score,
            abs_tol=1e-12,
        )
        for tile in table.tiles
    )
    exceedance = next(
        item for item in table.normalization if item.feature == NormalizedFeature.EXCEEDANCE
    )
    assert exceedance.valid_count == 2_001
    assert exceedance.missing_count == 0
    no_vehicle = next(
        item for item in table.normalization if item.feature == NormalizedFeature.NO_VEHICLE_RATE
    )
    assert no_vehicle.missing_count == table.counts.tiles_with_missing_fields
    assert all(
        "no_vehicle_rate" in tile.missing_fields
        for tile in table.tiles
        if tile.missing_fields
    )
