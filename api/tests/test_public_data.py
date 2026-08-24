"""Tests for public-source metadata and cache boundaries."""

from pathlib import Path

import pytest

from api.app.services.public_data import (
    ArtifactValidation,
    load_sources,
    read_or_fetch,
    validate_acs_summary,
)

ROOT = Path(__file__).parents[2]


def test_source_registry_covers_required_inputs() -> None:
    registry = load_sources(ROOT / "data" / "sources.json")
    source_ids = {source.id for source in registry.sources}

    assert {
        "pacoima_boundary",
        "la_city_street_centerlines",
        "la_city_pavement_condition",
        "lausd_school_sites",
        "la_city_parks",
        "lapl_branches",
        "la_metro_gtfs_bus",
        "la_metro_bus_patronage_2024",
        "census_acs_2024",
    } <= source_ids
    assert all(source.license_notes for source in registry.sources)
    assert all(source.limitations for source in registry.sources)

    roadway = next(
        source for source in registry.sources if source.id == "la_city_street_centerlines"
    )
    assert roadway.retrieved_at.isoformat() == "2026-08-25"
    assert roadway.license_url is not None
    assert roadway.geometry_provenance is not None
    assert roadway.geometry_provenance.record_count == 1913
    assert roadway.geometry_provenance.pagination_key == "AutoID"

    pavement = next(
        source for source in registry.sources if source.id == "la_city_pavement_condition"
    )
    assert pavement.geometry_provenance is not None
    assert pavement.geometry_provenance.record_count == 1703
    assert pavement.data_vintage.endswith("2026-08-06")


def test_read_or_fetch_reuses_successful_cache(tmp_path: Path) -> None:
    calls = 0

    def fetcher(_url: str) -> bytes:
        nonlocal calls
        calls += 1
        return b"validated response"

    def validator(payload: bytes) -> ArtifactValidation:
        return ArtifactValidation(record_count=len(payload))

    destination = tmp_path / "data" / "raw" / "response.json"
    first_payload, first_fetched, first_validation = read_or_fetch(
        destination,
        "https://example.com/data",
        refresh=False,
        fetcher=fetcher,
        validator=validator,
    )
    second_payload, second_fetched, second_validation = read_or_fetch(
        destination,
        "https://example.com/data",
        refresh=False,
        fetcher=fetcher,
        validator=validator,
    )

    assert first_payload == second_payload == b"validated response"
    assert first_fetched is True
    assert second_fetched is False
    assert first_validation == second_validation == ArtifactValidation(record_count=18)
    assert calls == 1


def test_read_or_fetch_does_not_promote_invalid_response(tmp_path: Path) -> None:
    destination = tmp_path / "data" / "raw" / "response.json"

    def reject(_payload: bytes) -> ArtifactValidation:
        raise ValueError("invalid")

    with pytest.raises(ValueError, match="invalid"):
        read_or_fetch(
            destination,
            "https://example.com/data",
            refresh=False,
            fetcher=lambda _url: b"error page",
            validator=reject,
        )

    assert not destination.exists()


def test_acs_summary_schema_requires_exact_variables_and_denominators() -> None:
    payload = (
        b"GEO_ID|B17001_E001|B17001_M001|B17001_E002|B17001_M002\n"
        b"1400000US06037104700|1000|100|250|50\n"
    )

    validation = validate_acs_summary("census_acs_2024_b17001", payload)

    assert validation.record_count == 1
    assert validation.metadata == {"table_id": "B17001"}
