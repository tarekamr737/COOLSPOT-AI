"""Validation and projected-area calculation for the Pacoima pilot boundary."""

import math
from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator
from pyproj import Transformer
from shapely.geometry import Polygon, shape
from shapely.ops import transform
from shapely.validation import explain_validity

SQUARE_METERS_PER_SQUARE_MILE = 2_589_988.110336
PACOIMA_PROJECTED_CRS = "EPSG:32611"


class PolygonGeometry(BaseModel):
    """A closed WGS84 GeoJSON Polygon."""

    type: Literal["Polygon"]
    coordinates: tuple[tuple[tuple[float, float], ...], ...]

    @model_validator(mode="after")
    def validate_rings(self) -> Self:
        if not self.coordinates:
            raise ValueError("polygon must contain at least one ring")

        for ring in self.coordinates:
            if len(ring) < 4:
                raise ValueError("polygon rings must contain at least four positions")
            if ring[0] != ring[-1]:
                raise ValueError("polygon rings must be closed")
            for longitude, latitude in ring:
                if not math.isfinite(longitude) or not math.isfinite(latitude):
                    raise ValueError("coordinates must be finite")
                if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                    raise ValueError("coordinates must be valid WGS84 longitude/latitude")
        return self


class SourceBoundaryProperties(BaseModel):
    """Fields retained from the City of Los Angeles boundary service."""

    OBJECTID: int
    NAME: Literal["PACOIMA NC"]
    NC_ID: int


class SourceBoundaryFeature(BaseModel):
    """One source boundary feature."""

    type: Literal["Feature"]
    properties: SourceBoundaryProperties
    geometry: PolygonGeometry


class SourceBoundaryCollection(BaseModel):
    """Expected response shape for the authoritative source query."""

    type: Literal["FeatureCollection"]
    features: tuple[SourceBoundaryFeature, ...]

    @model_validator(mode="after")
    def require_one_feature(self) -> Self:
        if len(self.features) != 1:
            raise ValueError("source query must return exactly one Pacoima feature")
        return self


class BoundaryProperties(BaseModel):
    """Traceable metadata attached to the committed analysis boundary."""

    name: Literal["Pacoima"]
    boundary_label: Literal["Official Certified Neighborhood Council boundary"]
    storage_crs: Literal["EPSG:4326"]
    area_sq_mi: float = Field(gt=0, lt=10)
    source_dataset: str = Field(min_length=1)
    source_dataset_url: AnyHttpUrl
    source_query_url: AnyHttpUrl
    source_feature_name: Literal["PACOIMA NC"]
    source_object_id: int
    source_nc_id: int
    retrieved_at: date
    license_notes: str = Field(min_length=1)
    license_url: AnyHttpUrl


class BoundaryFeature(BaseModel):
    """The single pilot feature."""

    type: Literal["Feature"]
    properties: BoundaryProperties
    geometry: PolygonGeometry


class BoundaryCollection(BaseModel):
    """Committed Pacoima AOI document."""

    type: Literal["FeatureCollection"]
    features: tuple[BoundaryFeature, ...]

    @model_validator(mode="after")
    def require_one_feature(self) -> Self:
        if len(self.features) != 1:
            raise ValueError("AOI must contain exactly one feature")
        return self


def calculate_area_sq_mi(geometry: PolygonGeometry) -> float:
    """Calculate polygon area after projection to UTM zone 11N."""

    polygon = shape(geometry.model_dump())
    if not isinstance(polygon, Polygon):
        raise ValueError("AOI geometry must be a Polygon")
    if polygon.is_empty or not polygon.is_valid:
        raise ValueError(f"AOI polygon is invalid: {explain_validity(polygon)}")

    projector = Transformer.from_crs("EPSG:4326", PACOIMA_PROJECTED_CRS, always_xy=True)
    projected_polygon = transform(projector.transform, polygon)
    return float(projected_polygon.area / SQUARE_METERS_PER_SQUARE_MILE)


def load_boundary(path: Path) -> BoundaryCollection:
    """Load and schema-validate a committed GeoJSON AOI."""

    return BoundaryCollection.model_validate_json(path.read_text(encoding="utf-8"))


def validate_boundary_file(path: Path, *, max_area_sq_mi: float = 10) -> float:
    """Validate the AOI geometry, recorded area, and configured area ceiling."""

    document = load_boundary(path)
    feature = document.features[0]
    calculated_area = calculate_area_sq_mi(feature.geometry)

    if calculated_area >= max_area_sq_mi:
        raise ValueError(
            f"AOI area {calculated_area:.6f} sq mi exceeds limit {max_area_sq_mi:.6f} sq mi"
        )
    if not math.isclose(
        calculated_area,
        feature.properties.area_sq_mi,
        rel_tol=0,
        abs_tol=0.000001,
    ):
        raise ValueError("recorded AOI area does not match the projected geometry")
    return calculated_area


def parse_source_boundary(payload: str) -> SourceBoundaryCollection:
    """Validate the external ArcGIS GeoJSON response before preprocessing."""

    return SourceBoundaryCollection.model_validate_json(payload)
