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
        "retrieved_at": "2026-08-22T16:33:01+00:00",
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
    assert '"original_image":' not in serialized
    assert '"segmented_image":' not in serialized


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


def test_context_confidence_uses_views_images_age_and_completeness() -> None:
    payload = _payload()
    result = payload["result"]
    assert isinstance(result, dict)
    for direction in ("front", "back"):
        frame = result[direction]
        assert isinstance(frame, dict)
        frame["segments"] = {
            "tree": 10.0,
            "grass": 10.0,
            "sky": 20.0,
            "road": 30.0,
            "sidewalk": 20.0,
            "building": 10.0,
        }

    confidence = extract_street_view_features(payload).street_context_confidence

    assert confidence.score == 1
    assert confidence.usable_view_count == 2
    assert confidence.components.model_dump() == {
        "usable_views": 1.0,
        "imagery_availability": 1.0,
        "imagery_age": 1.0,
        "segmentation_completeness": 1.0,
    }


def test_incomplete_single_view_has_lower_context_confidence() -> None:
    payload = _payload()
    result = payload["result"]
    assert isinstance(result, dict)
    result["back"] = None
    front = result["front"]
    assert isinstance(front, dict)
    front["original_image"] = ""
    front["segments"] = {"road": 60.0}

    confidence = extract_street_view_features(payload).street_context_confidence

    assert 0 <= confidence.score < 1
    assert confidence.usable_view_count == 1
    assert confidence.components.usable_views == 0.5
    assert confidence.components.imagery_availability == 0.5
    assert confidence.components.segmentation_completeness == pytest.approx(1 / 6)


def test_shade_evidence_uses_visual_context_and_confidence() -> None:
    payload = _payload()
    result = payload["result"]
    assert isinstance(result, dict)
    for direction in ("front", "back"):
        frame = result[direction]
        assert isinstance(frame, dict)
        frame["segments"] = {
            "tree": 20.0,
            "grass": 0.0,
            "sky": 60.0,
            "road": 10.0,
            "sidewalk": 5.0,
            "building": 5.0,
        }

    evidence = extract_street_view_features(payload).shade_intervention_evidence

    assert evidence.open_sky_context == 0.6
    assert evidence.low_tree_context == 0.8
    assert evidence.street_context_confidence == 1
    assert evidence.score == 0.7
    assert "does not prove that a stop is unshaded" in evidence.limitation
    assert "all-day shade" in evidence.limitation


def test_shade_evidence_score_is_bounded() -> None:
    payload = _payload()

    evidence = extract_street_view_features(payload).shade_intervention_evidence

    assert 0 <= evidence.score <= 1


def test_extractor_rejects_non_completed_cached_response() -> None:
    payload = _payload()
    payload["status"] = "Processing"

    with pytest.raises(ValueError, match="not completed"):
        extract_street_view_features(payload)
