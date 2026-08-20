"""Acceptance tests for the committed Pacoima public-data fixture."""

from pathlib import Path

from shapely.geometry import shape

from api.app.services.boundary import load_boundary
from api.app.services.processed_data import canonical_fixture_bytes, load_processed_fixture

ROOT = Path(__file__).parents[2]
FIXTURE_PATH = ROOT / "data" / "processed" / "pacoima_public_data.json"
AOI_PATH = ROOT / "data" / "processed" / "pacoima_aoi.geojson"


def test_committed_public_fixture_is_canonical_and_integrates_real_sources() -> None:
    document = load_processed_fixture(FIXTURE_PATH)

    assert FIXTURE_PATH.read_bytes() == canonical_fixture_bytes(document)
    assert {
        "lausd_school_sites",
        "la_city_parks",
        "lapl_branches",
        "la_metro_gtfs_bus",
        "la_metro_bus_patronage_2024",
        "census_acs_2024",
    } <= set(document.source_ids)
    assert document.counts.pois > 0
    assert document.counts.transit_stops > 0
    assert document.counts.transit_stops_with_patronage > 0
    assert document.counts.vulnerability_tracts > 0
    assert all(
        tract.estimates.total_population is not None for tract in document.vulnerability_tracts
    )


def test_every_processed_geometry_is_clipped_to_pacoima() -> None:
    document = load_processed_fixture(FIXTURE_PATH)
    boundary = load_boundary(AOI_PATH)
    aoi = shape(boundary.features[0].geometry.model_dump())
    geometries = (
        *(shape(poi.geometry.model_dump()) for poi in document.pois),
        *(shape(stop.geometry.model_dump()) for stop in document.transit_stops),
        *(shape(tract.geometry.model_dump()) for tract in document.vulnerability_tracts),
    )

    for geometry in geometries:
        if geometry.geom_type == "Point":
            assert aoi.covers(geometry)
        else:
            assert geometry.difference(aoi).area < 1e-16
