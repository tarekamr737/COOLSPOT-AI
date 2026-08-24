"""Tests for normalized finalist environmental evidence."""

import pytest
from pydantic import ValidationError

from api.app.services.environmental_evidence import (
    FinalistEnvironmentalEvidence,
    build_environmental_evidence,
    canonical_environmental_evidence_bytes,
    load_environmental_evidence,
)


def test_committed_environmental_evidence_rebuilds_byte_for_byte() -> None:
    committed = load_environmental_evidence()
    rebuilt = build_environmental_evidence()

    assert rebuilt == committed
    assert canonical_environmental_evidence_bytes(rebuilt) == (
        canonical_environmental_evidence_bytes(committed)
    )
    assert len(committed.sites) == 10
    assert committed.sites[0].site_name == "Van Nuys / Herrick"
    assert committed.sites[0].apparent_temperature_c == 35.3
    assert committed.sites[0].relative_humidity_percent == 24.3
    assert committed.sites[0].clear_sky_ghi_vendor_value == 779.49
    assert all(
        site.evidence_confidence.assessment == "source_complete"
        and site.evidence_confidence.configured_fields_present == "3 of 3"
        for site in committed.sites
    )


def test_normalized_environmental_values_are_raw_context_not_scores() -> None:
    artifact = load_environmental_evidence()
    dumped = artifact.model_dump(mode="json")
    field_names = set(dumped["sites"][0])

    assert not any("score" in field_name for field_name in field_names)
    assert not any("risk" in field_name for field_name in field_names)
    assert all(site.source_artifact.sha256 for site in artifact.sites)
    assert all(
        "does not establish medical risk" in site.evidence_confidence.limitation
        for site in artifact.sites
    )


def test_thermal_context_rejects_a_fabricated_medical_risk_score() -> None:
    site = load_environmental_evidence().sites[0]
    payload = site.model_dump(mode="json")
    payload["medical_risk_score"] = 0.9

    with pytest.raises(ValidationError, match="medical_risk_score"):
        FinalistEnvironmentalEvidence.model_validate(payload)
