"""Tests for the committed Pacoima analysis boundary."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from api.app.services.boundary import BoundaryCollection, load_boundary, validate_boundary_file

AOI_PATH = Path(__file__).parents[2] / "data" / "processed" / "pacoima_aoi.geojson"


def test_pacoima_aoi_is_valid_and_below_limit() -> None:
    document = load_boundary(AOI_PATH)
    area_sq_mi = validate_boundary_file(AOI_PATH)

    assert document.features[0].geometry.type == "Polygon"
    assert area_sq_mi == pytest.approx(document.features[0].properties.area_sq_mi, abs=0.000001)
    assert area_sq_mi < 10


def test_boundary_validation_rejects_an_open_ring() -> None:
    payload: dict[str, Any] = json.loads(AOI_PATH.read_text(encoding="utf-8"))
    ring = payload["features"][0]["geometry"]["coordinates"][0]
    ring[-1] = [-118.0, 34.0]

    with pytest.raises(ValidationError, match="polygon rings must be closed"):
        BoundaryCollection.model_validate(payload)


def test_boundary_validation_enforces_configured_area_limit() -> None:
    area_sq_mi = validate_boundary_file(AOI_PATH)

    with pytest.raises(ValueError, match="exceeds limit"):
        validate_boundary_file(AOI_PATH, max_area_sq_mi=area_sq_mi - 0.1)
