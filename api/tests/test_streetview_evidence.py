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


def test_extractor_rejects_non_completed_cached_response() -> None:
    payload = _payload()
    payload["status"] = "Processing"

    with pytest.raises(ValueError, match="not completed"):
        extract_street_view_features(payload)
