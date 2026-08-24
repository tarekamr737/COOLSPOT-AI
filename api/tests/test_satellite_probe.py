"""Offline tests for the single governed pavement satellite probe."""

from api.app.services.interventions import InterventionType
from api.app.services.satellite_evidence import (
    DEFAULT_SATELLITE_PROBE_PATH,
    SatelliteProbeReport,
)
from scripts.probe_fortyguard_satellite import (
    build_satellite_probe_request,
    select_probe_candidate,
)


def test_probe_targets_top_verified_pavement_candidate_deterministically() -> None:
    candidate = select_probe_candidate()
    request = build_satellite_probe_request(candidate)

    assert candidate.intervention_type == InterventionType.COOL_PAVEMENT
    assert candidate.site_source_ids == ("la_city_pavement_condition",)
    assert request.granularity == 100
    assert request.date_time.start_date.isoformat() == "2026-08-20"
    assert request.date_time.start_time is not None
    assert request.date_time.start_time.strftime("%H:%M") == "14:00"
    assert request.date_time.filter_type == 1


def test_committed_probe_is_complete_credit_safe_and_surface_specific() -> None:
    report = SatelliteProbeReport.model_validate_json(
        DEFAULT_SATELLITE_PROBE_PATH.read_text(encoding="utf-8")
    )

    assert report.status == "Completed"
    assert report.result is not None
    assert report.observed_credit_delta == 14_400
    assert report.remaining_after == 1_759_280
    assert report.remaining_after >= report.hard_reserve
    assert report.result.image_year == 2026
    assert report.result.segmentation.segments["road, route"] == 59.41
    assert report.result.segmentation.segments["sidewalk, pavement"] == 8.39
