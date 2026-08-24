"""Typed source registry and validators for cached public-data responses."""

import csv
import hashlib
import io
import os
import re
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import date
from functools import partial
from pathlib import Path
from typing import Generic, Literal, Self, TypeVar

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

PropertiesT = TypeVar("PropertiesT", bound=BaseModel)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class SourceArtifact(BaseModel):
    """One retrievable file belonging to a public source."""

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    retrieval_url: AnyHttpUrl
    cache_path: str
    media_type: Literal[
        "application/geo+json", "application/json", "application/zip", "text/plain"
    ]

    @field_validator("cache_path")
    @classmethod
    def require_raw_cache_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.parts[:2] != ("data", "raw"):
            raise ValueError("cache path must be a relative path under data/raw")
        return value


class GeometryProvenance(BaseModel):
    """Traceability for a derived, committed geometry snapshot."""

    model_config = ConfigDict(extra="forbid")

    processed_artifact_path: str
    acquisition_script: str
    query_aoi: str = Field(min_length=1)
    pagination_key: str = Field(min_length=1)
    record_count: int = Field(gt=0)
    source_geometry_type: str = Field(min_length=1)
    source_crs: str = Field(min_length=1)
    output_crs: str = Field(min_length=1)

    @field_validator("processed_artifact_path")
    @classmethod
    def require_processed_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.parts[:2] != (
            "data",
            "processed",
        ):
            raise ValueError("geometry artifact must be a relative path under data/processed")
        return value

    @field_validator("acquisition_script")
    @classmethod
    def require_script_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("scripts",):
            raise ValueError("acquisition script must be a relative path under scripts")
        return value


class SourceRecord(BaseModel):
    """Traceability and usage metadata for one authoritative dataset."""

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    dataset_url: AnyHttpUrl
    retrieved_at: date
    data_vintage: str = Field(min_length=1)
    license_notes: str = Field(min_length=1)
    license_url: AnyHttpUrl | None = None
    fields: dict[str, str]
    limitations: tuple[str, ...]
    artifacts: tuple[SourceArtifact, ...]
    geometry_provenance: GeometryProvenance | None = None


class SourcesDocument(BaseModel):
    """Versioned public-source registry."""

    version: Literal["1.0"]
    sources: tuple[SourceRecord, ...]

    @model_validator(mode="after")
    def require_unique_ids(self) -> Self:
        source_ids = [source.id for source in self.sources]
        artifact_ids = [artifact.id for source in self.sources for artifact in source.artifacts]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source IDs must be unique")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("artifact IDs must be unique")
        return self


class PointGeometry(BaseModel):
    """A WGS84 GeoJSON point."""

    type: Literal["Point"]
    coordinates: tuple[float, float]

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        longitude, latitude = self.coordinates
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError("point coordinates must be valid WGS84 longitude/latitude")
        return self


class PolygonGeometry(BaseModel):
    """A GeoJSON polygon returned by a public-data service."""

    type: Literal["Polygon"]
    coordinates: tuple[tuple[tuple[float, float], ...], ...]


class MultiPolygonGeometry(BaseModel):
    """A GeoJSON multipolygon returned by a public-data service."""

    type: Literal["MultiPolygon"]
    coordinates: tuple[tuple[tuple[tuple[float, float], ...], ...], ...]


class PointFeature(BaseModel, Generic[PropertiesT]):
    """A typed GeoJSON point feature."""

    type: Literal["Feature"]
    properties: PropertiesT
    geometry: PointGeometry


class PointFeatureCollection(BaseModel, Generic[PropertiesT]):
    """A typed GeoJSON point feature collection."""

    type: Literal["FeatureCollection"]
    features: tuple[PointFeature[PropertiesT], ...]


class PolygonFeature(BaseModel, Generic[PropertiesT]):
    """A typed GeoJSON polygon feature."""

    type: Literal["Feature"]
    properties: PropertiesT
    geometry: PolygonGeometry | MultiPolygonGeometry


class PolygonFeatureCollection(BaseModel, Generic[PropertiesT]):
    """A typed GeoJSON polygon feature collection."""

    type: Literal["FeatureCollection"]
    features: tuple[PolygonFeature[PropertiesT], ...]


class SchoolProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    FID: int
    LOCN: str | None = None
    CATEGORY: str | None = None
    MPD_NAME: str | None = None
    ADDRESS: str | None = None
    CITY: str | None = None
    ZIP: str | None = None
    FULLNAME: str | None = None
    CDSCODE: str | None = None
    ACTIVE: str | None = None
    SITE_ID: int | None = None
    LOGRD: int | None = None
    HIGRD: int | None = None


class ParkProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    FID: int
    AssetID: str | None = None
    Name: str | None = None
    Type: str | None = None
    Park_ID: str | None = None
    AddrNumber: float | None = None
    Street: str | None = None
    City: str | None = None
    Zip: str | None = None


class LibraryProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ObjectId: int
    Branch____Display_Name: str
    Address: str | None = None
    City: str | None = None
    State: str | None = None
    Zip: int | None = None


class PatronageProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    OBJECTID: int
    STOPID: str
    STOPNAME: str | None = None
    LAT: float
    LONG: float
    DX_Ons: float | None = None
    DX_Offs: float | None = None
    DX_Trips: float | None = None
    SA_Ons: float | None = None
    SA_Offs: float | None = None
    SA_Trips: float | None = None
    SU_Ons: float | None = None
    SU_Offs: float | None = None
    SU_Trips: float | None = None
    District: int | None = None


class CensusTractProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    GEOID: str = Field(pattern=r"^06\d{9}$")
    BASENAME: str
    STATE: Literal["06"]
    COUNTY: Literal["037"]
    TRACT: str = Field(pattern=r"^\d{6}$")


ACS_TRACT_PREFIX = "1400000US06037"
ACS_SUMMARY_FIELDS = {
    "census_acs_2024_b01001": (
        "B01001_E001",
        "B01001_E020",
        "B01001_E021",
        "B01001_E022",
        "B01001_E023",
        "B01001_E024",
        "B01001_E025",
        "B01001_E044",
        "B01001_E045",
        "B01001_E046",
        "B01001_E047",
        "B01001_E048",
        "B01001_E049",
    ),
    "census_acs_2024_b09001": ("B09001_E001",),
    "census_acs_2024_b17001": ("B17001_E001", "B17001_E002"),
    "census_acs_2024_b08201": ("B08201_E001", "B08201_E002"),
}


class AcsSummaryGeography(BaseModel):
    """LA County tract key used by an ACS table-based Summary File row."""

    model_config = ConfigDict(extra="allow")

    GEO_ID: str = Field(pattern=rf"^{ACS_TRACT_PREFIX}\d{{6}}$")


class GtfsStop(BaseModel):
    """Required stop fields from the LA Metro GTFS archive."""

    model_config = ConfigDict(extra="ignore")

    stop_id: str = Field(min_length=1)
    stop_name: str = Field(min_length=1)
    stop_lat: float = Field(ge=-90, le=90)
    stop_lon: float = Field(ge=-180, le=180)


class GtfsFeedInfo(BaseModel):
    """Publisher and validity metadata bundled with GTFS."""

    model_config = ConfigDict(extra="ignore")

    feed_publisher_name: str = Field(min_length=1)
    feed_publisher_url: AnyHttpUrl
    feed_lang: str = Field(min_length=2)
    feed_start_date: str | None = Field(default=None, pattern=r"^\d{8}$")
    feed_end_date: str | None = Field(default=None, pattern=r"^\d{8}$")
    feed_version: str | None = None


class ArtifactValidation(BaseModel):
    """Validated record count and non-sensitive artifact metadata."""

    record_count: int = Field(ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)


class CachedArtifact(BaseModel):
    """Integrity record for one local raw cache file."""

    source_id: str
    artifact_id: str
    path: str
    sha256: str
    byte_count: int = Field(gt=0)
    record_count: int = Field(ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def require_raw_cache_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.parts[:2] != ("data", "raw"):
            raise ValueError("cached artifact path must be relative and under data/raw")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not SHA256_PATTERN.fullmatch(value):
            raise ValueError("sha256 must be a lowercase hexadecimal digest")
        return value


class CacheManifest(BaseModel):
    """Deterministic inventory of fetched raw public data."""

    version: Literal["1.0"] = "1.0"
    retrieved_at: date
    artifacts: tuple[CachedArtifact, ...]


def load_sources(path: Path) -> SourcesDocument:
    """Load and validate the public source registry."""

    return SourcesDocument.model_validate_json(path.read_text(encoding="utf-8"))


def fetch_bytes(url: str, *, timeout_seconds: float = 120) -> bytes:
    """Fetch a known registry URL with a bounded timeout."""

    request = urllib.request.Request(url, headers={"User-Agent": "COOLSPOT-AI/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read()
    if not isinstance(payload, bytes):
        raise TypeError("public-data response must be bytes")
    return payload


def fetch_acs_summary_subset(url: str, *, timeout_seconds: float = 600) -> bytes:
    """Stream an ACS national table and retain only LA County tract rows."""

    request = urllib.request.Request(url, headers={"User-Agent": "COOLSPOT-AI/0.1"})
    with (
        urllib.request.urlopen(request, timeout=timeout_seconds) as response,
        io.TextIOWrapper(response, encoding="utf-8-sig", newline="") as stream,
    ):
        header = stream.readline()
        rows = [line for line in stream if line.startswith(ACS_TRACT_PREFIX)]
    if not header or not rows:
        raise ValueError(f"ACS Summary File has no LA County tract rows: {url}")
    return (header + "".join(rows)).encode()


def read_or_fetch(
    destination: Path,
    url: str,
    *,
    refresh: bool,
    validator: Callable[[bytes], ArtifactValidation],
    fetcher: Callable[[str], bytes] = fetch_bytes,
) -> tuple[bytes, bool, ArtifactValidation]:
    """Return a validated cache, promoting new bytes only after validation."""

    if destination.exists() and not refresh:
        payload = destination.read_bytes()
        return payload, False, validator(payload)

    payload = fetcher(url)
    if not payload:
        raise ValueError(f"empty response for {url}")
    validation = validator(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_suffix(f"{destination.suffix}.part")
    temporary_path.write_bytes(payload)
    os.replace(temporary_path, destination)
    return payload, True, validation


def validate_acs_summary(artifact_id: str, payload: bytes) -> ArtifactValidation:
    """Validate required estimates in an LA County ACS Summary File subset."""

    expected_fields = ACS_SUMMARY_FIELDS.get(artifact_id)
    if expected_fields is None:
        raise ValueError(f"no ACS Summary File schema configured for {artifact_id}")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter="|")
    header = set(reader.fieldnames or ())
    required_fields = {"GEO_ID", *expected_fields}
    if missing := required_fields.difference(header):
        raise ValueError(f"ACS Summary File is missing required fields: {sorted(missing)}")

    geographies: set[str] = set()
    for row in reader:
        geography = AcsSummaryGeography.model_validate(row)
        if geography.GEO_ID in geographies:
            raise ValueError(f"ACS Summary File repeats geography {geography.GEO_ID}")
        geographies.add(geography.GEO_ID)
        for field_name in expected_fields:
            value = row.get(field_name)
            try:
                int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"ACS Summary File has a non-integer {field_name} value"
                ) from error
    if not geographies:
        raise ValueError("ACS Summary File subset must contain at least one tract")
    return ArtifactValidation(
        record_count=len(geographies),
        metadata={"table_id": artifact_id.rsplit("_", maxsplit=1)[-1].upper()},
    )


def validate_gtfs(payload: bytes) -> ArtifactValidation:
    """Validate the GTFS archive and all published stop coordinates."""

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        required = {"feed_info.txt", "routes.txt", "stops.txt", "trips.txt"}
        missing = required.difference(archive.namelist())
        if missing:
            raise ValueError(f"GTFS archive is missing required files: {sorted(missing)}")
        if bad_file := archive.testzip():
            raise ValueError(f"GTFS archive has a corrupt member: {bad_file}")

        with archive.open("feed_info.txt") as stream:
            feed_rows = list(csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")))
        if len(feed_rows) != 1:
            raise ValueError("GTFS feed_info.txt must contain exactly one record")
        feed = GtfsFeedInfo.model_validate(feed_rows[0])

        stop_count = 0
        with archive.open("stops.txt") as stream:
            for row in csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")):
                GtfsStop.model_validate(row)
                stop_count += 1
        if stop_count == 0:
            raise ValueError("GTFS stops.txt must contain at least one stop")

    metadata = {
        "feed_publisher_name": feed.feed_publisher_name,
        "feed_start_date": feed.feed_start_date or "",
        "feed_end_date": feed.feed_end_date or "",
        "feed_version": feed.feed_version or "",
    }
    return ArtifactValidation(record_count=stop_count, metadata=metadata)


def validate_artifact(artifact_id: str, payload: bytes) -> ArtifactValidation:
    """Dispatch a cached response to its exact typed boundary schema."""

    text = payload.decode("utf-8-sig") if artifact_id != "la_metro_gtfs_bus_zip" else ""
    if artifact_id == "lausd_schools_bbox":
        school_document = PointFeatureCollection[SchoolProperties].model_validate_json(text)
        return ArtifactValidation(record_count=len(school_document.features))
    if artifact_id == "la_city_parks_bbox":
        park_document = PolygonFeatureCollection[ParkProperties].model_validate_json(text)
        return ArtifactValidation(record_count=len(park_document.features))
    if artifact_id == "lapl_branches_bbox":
        library_document = PointFeatureCollection[LibraryProperties].model_validate_json(text)
        return ArtifactValidation(record_count=len(library_document.features))
    if artifact_id == "la_metro_patronage_bbox":
        patronage_document = PointFeatureCollection[PatronageProperties].model_validate_json(text)
        return ArtifactValidation(record_count=len(patronage_document.features))
    if artifact_id == "census_tiger_acs2024_tracts_bbox":
        tract_document = PolygonFeatureCollection[CensusTractProperties].model_validate_json(text)
        return ArtifactValidation(record_count=len(tract_document.features))
    if artifact_id in ACS_SUMMARY_FIELDS:
        return validate_acs_summary(artifact_id, payload)
    if artifact_id == "la_metro_gtfs_bus_zip":
        return validate_gtfs(payload)
    raise ValueError(f"no validator configured for artifact {artifact_id}")


def cache_public_sources(
    registry: SourcesDocument,
    workspace: Path,
    *,
    retrieved_at: date,
    refresh: bool = False,
) -> CacheManifest:
    """Fetch or reuse every configured raw artifact, validate it, and record integrity."""

    raw_root = (workspace / "data" / "raw").resolve()
    cached = []
    for source in registry.sources:
        for artifact in source.artifacts:
            destination = (workspace / artifact.cache_path).resolve()
            if not destination.is_relative_to(raw_root):
                raise ValueError(f"cache destination escapes data/raw: {destination}")
            validator = partial(validate_artifact, artifact.id)
            fetcher = (
                fetch_acs_summary_subset
                if artifact.id in ACS_SUMMARY_FIELDS
                else fetch_bytes
            )
            payload, _, validation = read_or_fetch(
                destination,
                str(artifact.retrieval_url),
                refresh=refresh,
                validator=validator,
                fetcher=fetcher,
            )
            cached.append(
                CachedArtifact(
                    source_id=source.id,
                    artifact_id=artifact.id,
                    path=artifact.cache_path,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    byte_count=len(payload),
                    record_count=validation.record_count,
                    metadata=validation.metadata,
                )
            )
    return CacheManifest(retrieved_at=retrieved_at, artifacts=tuple(cached))
