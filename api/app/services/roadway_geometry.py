"""Acquire and validate the official LA street-centerline snapshot for Pacoima."""

import json
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.app.services.public_data import fetch_bytes

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AOI_PATH = ROOT / "data" / "processed" / "pacoima_aoi.geojson"
DEFAULT_ROADWAY_PATH = ROOT / "data" / "processed" / "pacoima_street_centerlines.geojson"
STREET_CENTERLINE_URL = (
    "https://maps.lacity.org/lahub/rest/services/Street_Information/MapServer/36/query"
)
PAGE_SIZE = 1_000
Coordinate = tuple[float, float]
Line = Annotated[tuple[Coordinate, ...], Field(min_length=2)]


class LineStringGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["LineString"]
    coordinates: Line


class MultiLineStringGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["MultiLineString"]
    coordinates: Annotated[tuple[Line, ...], Field(min_length=1)]


class StreetCenterlineProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    AutoID: int
    OBJECTID: int
    ASSETID: int | None = None
    STNAME: str | None = None
    STSFX: str | None = None
    SFXDIR: str | None = None
    STATUS: str | None = None
    ST_SUBTYPE: int | None = None
    LST_MODF_DT: int | None = None
    BSS_ST_CLASS: str | None = None
    Street_Designation: str | None = None
    Street_Designation_WO_Mod: str | None = None


class StreetCenterlineFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["Feature"]
    id: int
    geometry: LineStringGeometry | MultiLineStringGeometry
    properties: StreetCenterlineProperties


class GeoJsonCrsProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["EPSG:4326"]


class GeoJsonCrs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["name"]
    properties: GeoJsonCrsProperties


class StreetCenterlineCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["FeatureCollection"]
    crs: GeoJsonCrs
    features: tuple[StreetCenterlineFeature, ...]


class ArcGisStreetCenterlinePage(StreetCenterlineCollection):
    """ArcGIS GeoJSON page, including its service pagination signal."""

    exceededTransferLimit: bool | None = None


class ArcGisCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(gt=0)


def _aoi_envelope(path: Path = DEFAULT_AOI_PATH) -> str:
    document = json.loads(path.read_text(encoding="utf-8"))
    coordinates: list[Coordinate] = []

    def collect(value: object) -> None:
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            coordinates.append((float(value[0]), float(value[1])))
            return
        if isinstance(value, list):
            for item in value:
                collect(item)

    collect(document["features"][0]["geometry"]["coordinates"])
    if not coordinates:
        raise ValueError("Pacoima AOI has no coordinates")
    longitudes, latitudes = zip(*coordinates, strict=True)
    return ",".join(
        str(value)
        for value in (min(longitudes), min(latitudes), max(longitudes), max(latitudes))
    )


def _url(parameters: dict[str, str | int]) -> str:
    return f"{STREET_CENTERLINE_URL}?{urllib.parse.urlencode(parameters)}"


def acquire_street_centerlines(
    *,
    aoi_path: Path = DEFAULT_AOI_PATH,
    fetcher: Callable[[str], bytes] = fetch_bytes,
) -> StreetCenterlineCollection:
    """Fetch every paginated centerline intersecting the Pacoima bounding envelope."""

    common: dict[str, str | int] = {
        "where": "1=1",
        "geometry": _aoi_envelope(aoi_path),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": 4326,
    }
    count = ArcGisCount.model_validate_json(
        fetcher(_url({**common, "returnCountOnly": "true", "f": "json"}))
    ).count
    fields = ",".join(StreetCenterlineProperties.model_fields)
    features: list[StreetCenterlineFeature] = []

    for offset in range(0, count, PAGE_SIZE):
        page = ArcGisStreetCenterlinePage.model_validate_json(
            fetcher(
                _url(
                    {
                        **common,
                        "outFields": fields,
                        "returnGeometry": "true",
                        "orderByFields": "AutoID",
                        "resultOffset": offset,
                        "resultRecordCount": PAGE_SIZE,
                        "f": "geojson",
                    }
                )
            )
        )
        features.extend(page.features)

    features.sort(key=lambda feature: feature.properties.AutoID)
    object_ids = [feature.properties.AutoID for feature in features]
    if len(features) != count:
        raise ValueError(f"ArcGIS returned {len(features)} of {count} street centerlines")
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("ArcGIS street-centerline pages contain duplicate AutoIDs")
    return StreetCenterlineCollection(
        type="FeatureCollection",
        crs=GeoJsonCrs(type="name", properties=GeoJsonCrsProperties(name="EPSG:4326")),
        features=tuple(features),
    )


def canonical_street_centerline_bytes(document: StreetCenterlineCollection) -> bytes:
    return (
        json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()


def load_street_centerlines(
    path: Path = DEFAULT_ROADWAY_PATH,
) -> StreetCenterlineCollection:
    return StreetCenterlineCollection.model_validate_json(path.read_text(encoding="utf-8"))
