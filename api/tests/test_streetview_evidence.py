"""Tests for deterministic extraction of cached Street View evidence."""

from copy import deepcopy

import pytest

from api.app.services.streetview_evidence import (
    StreetViewDirection,
    extract_street_view_features,
)


def _frame(segments: dict[str, float]) -> dict[str, object]:
    return {
        "original_image": "base64-original-is-not-a-feature",
        "segments": segments,
        "image_legend": {},
        "segmented_image": "base64-segmentation-is-not-a-feature",
        "image_date": "2024-10-01",
    }


def _payload() -> dict[str, object]:
    return {
        "site_id": "metro-stop:10794",
        "status": "Completed",
        "result": {
            "coordinates": {"latitude": 34.273715, "longitude": -118.411903},
            "front": _frame({"tree": 13.1, "road": 26.93, "sky": 31.57}),
            "back": _frame({"sky": 22.0, "tree": 18.0, "road": 30.0}),
        },
    }


def test_extractor_is_compact_and_deterministic() -> None:
    payload = _payload()
    reordered = deepcopy(payload)
    result = reordered["result"]
    assert isinstance(result, dict)
    front = result["front"]
    assert isinstance(front, dict)
    front["segments"] = {"sky": 31.57, "road": 26.93, "tree": 13.1}

    extracted = extract_street_view_features(payload)
    repeated = extract_street_view_features(reordered)

    assert extracted == repeated
    assert [frame.direction for frame in extracted.frames] == [
        StreetViewDirection.FRONT,
        StreetViewDirection.BACK,
    ]
    assert [segment.label for segment in extracted.frames[0].segments] == [
        "road",
        "sky",
        "tree",
    ]
    serialized = extracted.model_dump_json()
    assert "base64" not in serialized
    assert "original_image" not in serialized
    assert "segmented_image" not in serialized


def test_extractor_derives_only_exact_per_view_metrics() -> None:
    payload = _payload()
    result = payload["result"]
    assert isinstance(result, dict)
    front = result["front"]
    assert isinstance(front, dict)
    front["segments"] = {
        "tree": 13.1,
        "grass": 7.28,
        "sky": 31.57,
        "road": 26.93,
        "sidewalk": 8.9,
        "building": 1.37,
        "fence": 4.28,
    }

    metrics = extract_street_view_features(payload).frames[0].metrics

    assert metrics.model_dump() == {
        "tree_pct": 13.1,
        "grass_pct": 7.28,
        "sky_pct": 31.57,
        "road_pct": 26.93,
        "sidewalk_pct": 8.9,
        "building_pct": 1.37,
    }


def test_absent_per_view_categories_remain_unknown() -> None:
    payload = _payload()
    result = payload["result"]
    assert isinstance(result, dict)
    front = result["front"]
    assert isinstance(front, dict)
    front["segments"] = {"road": 60.0, "others": 40.0}

    frame = extract_street_view_features(payload).frames[0]

    assert frame.image_date.isoformat() == "2024-10-01"
    assert frame.metrics.road_pct == 60
    assert frame.metrics.tree_pct is None
    assert frame.metrics.sky_pct is None


def test_front_and_back_aggregation_uses_only_observed_values() -> None:
    payload = _payload()
    result = payload["result"]
    assert isinstance(result, dict)
    front = result["front"]
    back = result["back"]
    assert isinstance(front, dict)
    assert isinstance(back, dict)
    front["segments"] = {"tree": 10.0, "sky": 20.0}
    back["segments"] = {"tree": 30.0, "road": 40.0}

    aggregate = extract_street_view_features(payload).aggregate

    assert aggregate.view_count == 2
    assert aggregate.metrics.tree_pct == 20
    assert aggregate.metrics.sky_pct == 20
    assert aggregate.metrics.road_pct == 40
    assert aggregate.metrics.grass_pct is None
    assert aggregate.contributing_views.tree_pct == 2
    assert aggregate.contributing_views.sky_pct == 1
    assert aggregate.contributing_views.grass_pct == 0


def test_extractor_rejects_non_completed_cached_response() -> None:
    payload = _payload()
    payload["status"] = "Processing"

    with pytest.raises(ValueError, match="not completed"):
        extract_street_view_features(payload)
