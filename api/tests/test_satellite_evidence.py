"""Tests for compact, image-free satellite surface evidence."""

from api.app.services.satellite_evidence import (
    DEFAULT_SATELLITE_EVIDENCE_PATH,
    build_satellite_evidence,
    canonical_satellite_evidence_bytes,
    load_satellite_evidence,
)


def test_satellite_evidence_is_exact_site_compact_and_reproducible() -> None:
    artifact = load_satellite_evidence()
    rebuilt = build_satellite_evidence()
    site = artifact.sites[0]

    assert artifact.site_count == 1
    assert site.candidate_id == "cool_pavement:pavement:21486"
    assert site.image_year == 2026
    assert site.surface_class_coverage.road_route_percent == 59.41
    assert site.surface_class_coverage.sidewalk_pavement_percent == 8.39
    assert site.surface_class_coverage.combined_surface_class_percent == 67.8
    assert site.assessment == "source_complete"
    assert "traction" in site.limitation
    assert DEFAULT_SATELLITE_EVIDENCE_PATH.read_bytes() == (
        canonical_satellite_evidence_bytes(rebuilt)
    )
    payload = DEFAULT_SATELLITE_EVIDENCE_PATH.read_bytes()
    assert b"image_content" not in payload
    assert b"original_images" not in payload
    assert len(payload) < 5_000
