"""Deterministic preprocessing for the committed Pacoima public-data fixture."""

import csv
import hashlib
import io
import json
import zipfile
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from api.app.services.boundary import load_boundary
from api.app.services.public_data import (
    ACS_SUMMARY_FIELDS,
    AcsSummaryGeography,
    CacheManifest,
    CensusTractProperties,
    GtfsStop,
    LibraryProperties,
    MultiPolygonGeometry,
    ParkProperties,
    PatronageProperties,
    PointFeatureCollection,
    PointGeometry,
    PolygonFeatureCollection,
    PolygonGeometry,
    SchoolProperties,
    validate_artifact,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"
AreaGeometry = PolygonGeometry | MultiPolygonGeometry
FixtureGeometry = PointGeometry | PolygonGeometry | MultiPolygonGeometry


class ProcessedPoi(BaseModel):
    """One authoritative public destination clipped to the pilot AOI."""

    id: str
    source_id: Literal["lausd_school_sites", "la_city_parks", "lapl_branches"]
    kind: Literal["school", "park", "library"]
    source_record_id: str
    name: str = Field(min_length=1)
    category: str | None = None
    address: str | None = None
    geometry: FixtureGeometry


class PatronageSnapshot(BaseModel):
    """Published LA Metro patronage fields with uninterpreted day-code prefixes."""

    period: Literal["April 2024"] = "April 2024"
    dx_ons: float | None = None
    dx_offs: float | None = None
    dx_trips: float | None = None
    sa_ons: float | None = None
    sa_offs: float | None = None
    sa_trips: float | None = None
    su_ons: float | None = None
    su_offs: float | None = None
    su_trips: float | None = None


class ProcessedTransitStop(BaseModel):
    """A current GTFS or published-patronage stop inside the pilot AOI."""

    id: str
    stop_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    in_current_gtfs: bool
    route_ids: tuple[str, ...]
    patronage: PatronageSnapshot | None = None
    geometry: PointGeometry


class ProcessedTransitRoute(BaseModel):
    """A current GTFS route serving at least one retained Pacoima stop."""

    id: str
    short_name: str
    long_name: str
    route_type: int = Field(ge=0)


class VulnerabilityEstimates(BaseModel):
    """Minimal ACS estimates with the denominators needed for later rates."""

    total_population: int | None = Field(default=None, ge=0)
    children_under_18: int | None = Field(default=None, ge=0)
    older_adults_65_plus: int | None = Field(default=None, ge=0)
    poverty_universe_population: int | None = Field(default=None, ge=0)
    population_below_poverty: int | None = Field(default=None, ge=0)
    vehicle_availability_households: int | None = Field(default=None, ge=0)
    households_without_vehicle: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_valid_denominators(self) -> Self:
        comparisons = (
            (self.children_under_18, self.total_population, "children"),
            (self.older_adults_65_plus, self.total_population, "older adults"),
            (
                self.population_below_poverty,
                self.poverty_universe_population,
                "population below poverty",
            ),
            (
                self.households_without_vehicle,
                self.vehicle_availability_households,
                "households without vehicles",
            ),
        )
        for numerator, denominator, label in comparisons:
            if numerator is not None and denominator is not None and numerator > denominator:
                raise ValueError(f"{label} estimate exceeds its denominator")
        return self


class ProcessedVulnerabilityTract(BaseModel):
    """An intersecting ACS tract clipped to the Pacoima AOI."""

    geoid: str = Field(pattern=r"^06037\d{6}$")
    estimates: VulnerabilityEstimates
    geometry: AreaGeometry


class FixtureCounts(BaseModel):
    """Integrity counts for quick API/UI data-status checks."""

    pois: int = Field(ge=0)
    schools: int = Field(ge=0)
    parks: int = Field(ge=0)
    libraries: int = Field(ge=0)
    transit_routes: int = Field(ge=0)
    transit_stops: int = Field(ge=0)
    transit_stops_with_patronage: int = Field(ge=0)
    vulnerability_tracts: int = Field(ge=0)


class ProcessedPublicData(BaseModel):
    """One deployable public-data document for the Pacoima demo."""

    version: Literal["1.0"] = "1.0"
    pilot: Literal["Pacoima"] = "Pacoima"
    crs: Literal["EPSG:4326"] = "EPSG:4326"
    source_retrieved_at: date
    source_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    aoi_sha256: str = Field(pattern=SHA256_PATTERN)
    source_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    counts: FixtureCounts
    pois: tuple[ProcessedPoi, ...]
    transit_routes: tuple[ProcessedTransitRoute, ...]
    transit_stops: tuple[ProcessedTransitStop, ...]
    vulnerability_tracts: tuple[ProcessedVulnerabilityTract, ...]

    @model_validator(mode="after")
    def validate_integrity(self) -> Self:
        expected_counts = FixtureCounts(
            pois=len(self.pois),
            schools=sum(poi.kind == "school" for poi in self.pois),
            parks=sum(poi.kind == "park" for poi in self.pois),
            libraries=sum(poi.kind == "library" for poi in self.pois),
            transit_routes=len(self.transit_routes),
            transit_stops=len(self.transit_stops),
            transit_stops_with_patronage=sum(
                stop.patronage is not None for stop in self.transit_stops
            ),
            vulnerability_tracts=len(self.vulnerability_tracts),
        )
        if self.counts != expected_counts:
            raise ValueError("fixture counts do not match its records")
        collections = (
            [poi.id for poi in self.pois],
            [route.id for route in self.transit_routes],
            [stop.id for stop in self.transit_stops],
            [tract.geoid for tract in self.vulnerability_tracts],
        )
        if any(len(values) != len(set(values)) for values in collections):
            raise ValueError("fixture record IDs must be unique within each collection")
        if self.source_ids != tuple(sorted(set(self.source_ids))):
            raise ValueError("source IDs must be sorted and unique")
        return self


class GtfsTrip(BaseModel):
    """GTFS trip fields needed to link retained stops to routes."""

    model_config = ConfigDict(extra="ignore")

    route_id: str = Field(min_length=1)
    trip_id: str = Field(min_length=1)


class GtfsStopTime(BaseModel):
    """GTFS stop-time fields needed for the route join."""

    model_config = ConfigDict(extra="ignore")

    trip_id: str = Field(min_length=1)
    stop_id: str = Field(min_length=1)


class GtfsRoute(BaseModel):
    """GTFS route fields retained in the processed fixture."""

    model_config = ConfigDict(extra="ignore")

    route_id: str = Field(min_length=1)
    route_short_name: str
    route_long_name: str
    route_type: int = Field(ge=0)


def load_processed_fixture(path: Path) -> ProcessedPublicData:
    """Load and validate the committed processed public-data fixture."""

    return ProcessedPublicData.model_validate_json(path.read_text(encoding="utf-8"))


def canonical_fixture_bytes(document: ProcessedPublicData) -> bytes:
    """Serialize the fixture with stable record and object-key ordering."""

    payload = json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    return payload.encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validated_cache_paths(workspace: Path, manifest: CacheManifest) -> dict[str, Path]:
    raw_root = (workspace / "data" / "raw").resolve()
    paths: dict[str, Path] = {}
    for artifact in manifest.artifacts:
        path = (workspace / artifact.path).resolve()
        if not path.is_relative_to(raw_root):
            raise ValueError(f"cache path escapes data/raw: {path}")
        payload = path.read_bytes()
        if _sha256(payload) != artifact.sha256:
            raise ValueError(f"cache hash does not match manifest for {artifact.artifact_id}")
        validation = validate_artifact(artifact.artifact_id, payload)
        if validation.record_count != artifact.record_count:
            raise ValueError(f"cache record count changed for {artifact.artifact_id}")
        if artifact.artifact_id in paths:
            raise ValueError(f"duplicate cached artifact {artifact.artifact_id}")
        paths[artifact.artifact_id] = path
    return paths


def _point_geometry(longitude: float, latitude: float) -> PointGeometry:
    return PointGeometry(type="Point", coordinates=(longitude, latitude))


def _clipped_area(geometry: BaseGeometry, aoi: Polygon) -> AreaGeometry | None:
    clipped = geometry.intersection(aoi)
    if clipped.is_empty:
        return None
    if isinstance(clipped, GeometryCollection):
        polygons = [part for part in clipped.geoms if isinstance(part, (Polygon, MultiPolygon))]
        if not polygons:
            return None
        clipped = unary_union(polygons)
    if isinstance(clipped, Polygon):
        return PolygonGeometry.model_validate(mapping(clipped))
    if isinstance(clipped, MultiPolygon):
        return MultiPolygonGeometry.model_validate(mapping(clipped))
    raise ValueError(f"area clipping produced unsupported geometry {clipped.geom_type}")


def _join_address(parts: Iterable[str | int | float | None]) -> str | None:
    cleaned = []
    for part in parts:
        if part is None or part == "":
            continue
        if isinstance(part, float) and part.is_integer():
            cleaned.append(str(int(part)))
        else:
            cleaned.append(str(part))
    return ", ".join(cleaned) or None


def _process_pois(paths: dict[str, Path], aoi: Polygon) -> tuple[ProcessedPoi, ...]:
    schools = PointFeatureCollection[SchoolProperties].model_validate_json(
        paths["lausd_schools_bbox"].read_text(encoding="utf-8")
    )
    parks = PolygonFeatureCollection[ParkProperties].model_validate_json(
        paths["la_city_parks_bbox"].read_text(encoding="utf-8")
    )
    libraries = PointFeatureCollection[LibraryProperties].model_validate_json(
        paths["lapl_branches_bbox"].read_text(encoding="utf-8")
    )

    processed: list[ProcessedPoi] = []
    for school_feature in schools.features:
        point = Point(school_feature.geometry.coordinates)
        if aoi.covers(point):
            processed.append(
                ProcessedPoi(
                    id=f"school:{school_feature.properties.FID}",
                    source_id="lausd_school_sites",
                    kind="school",
                    source_record_id=str(school_feature.properties.FID),
                    name=(
                        school_feature.properties.FULLNAME
                        or school_feature.properties.MPD_NAME
                        or "Unnamed school"
                    ),
                    category=school_feature.properties.CATEGORY,
                    address=_join_address(
                        (
                            school_feature.properties.ADDRESS,
                            school_feature.properties.CITY,
                            school_feature.properties.ZIP,
                        )
                    ),
                    geometry=school_feature.geometry,
                )
            )
    for park_feature in parks.features:
        geometry = _clipped_area(shape(park_feature.geometry.model_dump()), aoi)
        if geometry is not None:
            processed.append(
                ProcessedPoi(
                    id=f"park:{park_feature.properties.FID}",
                    source_id="la_city_parks",
                    kind="park",
                    source_record_id=str(park_feature.properties.FID),
                    name=park_feature.properties.Name or "Unnamed park facility",
                    category=park_feature.properties.Type,
                    address=_join_address(
                        (
                            park_feature.properties.AddrNumber,
                            park_feature.properties.Street,
                            park_feature.properties.City,
                            park_feature.properties.Zip,
                        )
                    ),
                    geometry=geometry,
                )
            )
    for library_feature in libraries.features:
        point = Point(library_feature.geometry.coordinates)
        if aoi.covers(point):
            processed.append(
                ProcessedPoi(
                    id=f"library:{library_feature.properties.ObjectId}",
                    source_id="lapl_branches",
                    kind="library",
                    source_record_id=str(library_feature.properties.ObjectId),
                    name=library_feature.properties.Branch____Display_Name,
                    category="Public library",
                    address=_join_address(
                        (
                            library_feature.properties.Address,
                            library_feature.properties.City,
                            library_feature.properties.State,
                            library_feature.properties.Zip,
                        )
                    ),
                    geometry=library_feature.geometry,
                )
            )
    return tuple(sorted(processed, key=lambda poi: poi.id))


def _csv_rows(archive: zipfile.ZipFile, member: str) -> Iterable[dict[str, str]]:
    with archive.open(member) as stream:
        yield from csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"))


def _patronage(properties: PatronageProperties) -> PatronageSnapshot:
    return PatronageSnapshot(
        dx_ons=properties.DX_Ons,
        dx_offs=properties.DX_Offs,
        dx_trips=properties.DX_Trips,
        sa_ons=properties.SA_Ons,
        sa_offs=properties.SA_Offs,
        sa_trips=properties.SA_Trips,
        su_ons=properties.SU_Ons,
        su_offs=properties.SU_Offs,
        su_trips=properties.SU_Trips,
    )


def _process_transit(
    paths: dict[str, Path], aoi: Polygon
) -> tuple[tuple[ProcessedTransitRoute, ...], tuple[ProcessedTransitStop, ...]]:
    patronage_document = PointFeatureCollection[PatronageProperties].model_validate_json(
        paths["la_metro_patronage_bbox"].read_text(encoding="utf-8")
    )
    patronage_features = {
        feature.properties.STOPID: feature
        for feature in patronage_document.features
        if aoi.covers(Point(feature.geometry.coordinates))
    }
    if len(patronage_features) != sum(
        aoi.covers(Point(feature.geometry.coordinates))
        for feature in patronage_document.features
    ):
        raise ValueError("patronage source contains duplicate stop IDs inside the AOI")

    with zipfile.ZipFile(paths["la_metro_gtfs_bus_zip"]) as archive:
        gtfs_stops: dict[str, GtfsStop] = {}
        for row in _csv_rows(archive, "stops.txt"):
            stop = GtfsStop.model_validate(row)
            if aoi.covers(Point(stop.stop_lon, stop.stop_lat)):
                if stop.stop_id in gtfs_stops:
                    raise ValueError(f"GTFS repeats stop ID {stop.stop_id}")
                gtfs_stops[stop.stop_id] = stop

        trips: dict[str, str] = {}
        for row in _csv_rows(archive, "trips.txt"):
            trip = GtfsTrip.model_validate(row)
            trips[trip.trip_id] = trip.route_id

        route_ids_by_stop: dict[str, set[str]] = {stop_id: set() for stop_id in gtfs_stops}
        for row in _csv_rows(archive, "stop_times.txt"):
            if row.get("stop_id") not in gtfs_stops:
                continue
            stop_time = GtfsStopTime.model_validate(row)
            route_id = trips.get(stop_time.trip_id)
            if route_id is None:
                raise ValueError(f"GTFS stop time references unknown trip {stop_time.trip_id}")
            route_ids_by_stop[stop_time.stop_id].add(route_id)

        used_route_ids = set().union(*route_ids_by_stop.values()) if route_ids_by_stop else set()
        routes: list[ProcessedTransitRoute] = []
        found_route_ids: set[str] = set()
        for row in _csv_rows(archive, "routes.txt"):
            route = GtfsRoute.model_validate(row)
            if route.route_id in used_route_ids:
                found_route_ids.add(route.route_id)
                routes.append(
                    ProcessedTransitRoute(
                        id=route.route_id,
                        short_name=route.route_short_name,
                        long_name=route.route_long_name,
                        route_type=route.route_type,
                    )
                )
        if missing := used_route_ids.difference(found_route_ids):
            raise ValueError(f"GTFS trips reference missing routes: {sorted(missing)}")

    stops: list[ProcessedTransitStop] = []
    for stop_id in sorted(set(gtfs_stops) | set(patronage_features)):
        gtfs_stop = gtfs_stops.get(stop_id)
        patronage_feature = patronage_features.get(stop_id)
        if gtfs_stop is not None:
            name = gtfs_stop.stop_name
            geometry = _point_geometry(gtfs_stop.stop_lon, gtfs_stop.stop_lat)
        elif patronage_feature is not None:
            name = patronage_feature.properties.STOPNAME or f"Metro stop {stop_id}"
            geometry = patronage_feature.geometry
        else:
            raise AssertionError("transit stop union yielded no source record")
        stops.append(
            ProcessedTransitStop(
                id=f"metro-stop:{stop_id}",
                stop_id=stop_id,
                name=name,
                in_current_gtfs=gtfs_stop is not None,
                route_ids=tuple(sorted(route_ids_by_stop.get(stop_id, set()))),
                patronage=(
                    _patronage(patronage_feature.properties)
                    if patronage_feature is not None
                    else None
                ),
                geometry=geometry,
            )
        )
    return tuple(sorted(routes, key=lambda route: route.id)), tuple(stops)


def _nonnegative(value: int) -> int | None:
    return value if value >= 0 else None


def _sum_estimates(values: Iterable[int]) -> int | None:
    components = tuple(values)
    return sum(components) if all(value >= 0 for value in components) else None


def _load_acs_table(path: Path, artifact_id: str) -> dict[str, dict[str, int]]:
    fields = ACS_SUMMARY_FIELDS[artifact_id]
    rows: dict[str, dict[str, int]] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="|"):
            geography = AcsSummaryGeography.model_validate(row)
            geoid = geography.GEO_ID.removeprefix("1400000US")
            if geoid in rows:
                raise ValueError(f"ACS table {artifact_id} repeats tract {geoid}")
            rows[geoid] = {field: int(row[field]) for field in fields}
    return rows


def _process_vulnerability(
    paths: dict[str, Path], aoi: Polygon
) -> tuple[ProcessedVulnerabilityTract, ...]:
    table_ids = tuple(ACS_SUMMARY_FIELDS)
    tables = {table_id: _load_acs_table(paths[table_id], table_id) for table_id in table_ids}
    tracts = PolygonFeatureCollection[CensusTractProperties].model_validate_json(
        paths["census_tiger_acs2024_tracts_bbox"].read_text(encoding="utf-8")
    )

    processed: list[ProcessedVulnerabilityTract] = []
    for feature in tracts.features:
        geoid = feature.properties.GEOID
        geometry = _clipped_area(shape(feature.geometry.model_dump()), aoi)
        if geometry is None:
            continue
        try:
            population = tables["census_acs_2024_b01001"][geoid]
            children = tables["census_acs_2024_b09001"][geoid]
            poverty = tables["census_acs_2024_b17001"][geoid]
            vehicles = tables["census_acs_2024_b08201"][geoid]
        except KeyError as error:
            raise ValueError(f"ACS estimates are missing for intersecting tract {geoid}") from error

        older_fields = (
            *(f"B01001_E{index:03}" for index in range(20, 26)),
            *(f"B01001_E{index:03}" for index in range(44, 50)),
        )
        processed.append(
            ProcessedVulnerabilityTract(
                geoid=geoid,
                estimates=VulnerabilityEstimates(
                    total_population=_nonnegative(population["B01001_E001"]),
                    children_under_18=_nonnegative(children["B09001_E001"]),
                    older_adults_65_plus=_sum_estimates(
                        population[field] for field in older_fields
                    ),
                    poverty_universe_population=_nonnegative(poverty["B17001_E001"]),
                    population_below_poverty=_nonnegative(poverty["B17001_E002"]),
                    vehicle_availability_households=_nonnegative(vehicles["B08201_E001"]),
                    households_without_vehicle=_nonnegative(vehicles["B08201_E002"]),
                ),
                geometry=geometry,
            )
        )
    return tuple(sorted(processed, key=lambda tract: tract.geoid))


def build_public_fixture(workspace: Path) -> ProcessedPublicData:
    """Build a validated, deterministic fixture from the local raw cache."""

    manifest_path = workspace / "data" / "raw_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = CacheManifest.model_validate_json(manifest_bytes)
    paths = _validated_cache_paths(workspace, manifest)

    aoi_path = workspace / "data" / "processed" / "pacoima_aoi.geojson"
    aoi_bytes = aoi_path.read_bytes()
    aoi_document = load_boundary(aoi_path)
    aoi_geometry = shape(aoi_document.features[0].geometry.model_dump())
    if not isinstance(aoi_geometry, Polygon):
        raise ValueError("Pacoima AOI must be a polygon")

    pois = _process_pois(paths, aoi_geometry)
    routes, stops = _process_transit(paths, aoi_geometry)
    tracts = _process_vulnerability(paths, aoi_geometry)
    counts = FixtureCounts(
        pois=len(pois),
        schools=sum(poi.kind == "school" for poi in pois),
        parks=sum(poi.kind == "park" for poi in pois),
        libraries=sum(poi.kind == "library" for poi in pois),
        transit_routes=len(routes),
        transit_stops=len(stops),
        transit_stops_with_patronage=sum(stop.patronage is not None for stop in stops),
        vulnerability_tracts=len(tracts),
    )
    return ProcessedPublicData(
        source_retrieved_at=manifest.retrieved_at,
        source_manifest_sha256=_sha256(manifest_bytes),
        aoi_sha256=_sha256(aoi_bytes),
        source_ids=tuple(sorted({artifact.source_id for artifact in manifest.artifacts})),
        limitations=(
            "POI and transit proximity are evidence of access, not measured footfall.",
            "Metro DX, SA, and SU patronage prefixes are retained without inferred day meanings.",
            "ACS values are survey estimates; margins of error are not incorporated in this "
            "fixture.",
            "Park and tract geometries are clipped to the Pacoima analysis boundary.",
        ),
        counts=counts,
        pois=pois,
        transit_routes=routes,
        transit_stops=stops,
        vulnerability_tracts=tracts,
    )
