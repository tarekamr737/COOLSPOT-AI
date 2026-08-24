"""Tests for versioned intervention-specific evidence inputs."""

from api.app.services.intervention_evidence import (
    InterventionEvidenceInput,
    load_intervention_evidence_config,
)


def test_shade_inputs_are_defensible_and_do_not_claim_measured_shade() -> None:
    rule = load_intervention_evidence_config().shade_structure

    assert set(rule.suitability_inputs) == {
        InterventionEvidenceInput.HEAT_SEVERITY,
        InterventionEvidenceInput.HEAT_PERSISTENCE,
        InterventionEvidenceInput.PUBLISHED_TRANSIT_EXPOSURE,
        InterventionEvidenceInput.STREET_TREE_CONTEXT,
        InterventionEvidenceInput.STREET_SKY_CONTEXT,
    }
    assert set(rule.feasibility_inputs) == {
        InterventionEvidenceInput.SITE_TYPE_COMPATIBILITY,
        InterventionEvidenceInput.EVIDENCE_CONFIDENCE,
    }
    assert "do not prove that a stop is unshaded" in " ".join(rule.limitations)


def test_tree_inputs_require_public_site_compatibility() -> None:
    rule = load_intervention_evidence_config().tree_canopy

    assert InterventionEvidenceInput.PUBLIC_SITE_COMPATIBILITY in rule.required_inputs
    assert InterventionEvidenceInput.VEGETATION_OPPORTUNITY in rule.suitability_inputs
    assert InterventionEvidenceInput.ENVIRONMENTAL_CONTEXT in rule.suitability_inputs


def test_cool_pavement_requires_verified_public_paved_geometry() -> None:
    rule = load_intervention_evidence_config().cool_pavement

    assert rule.required_inputs == (
        InterventionEvidenceInput.VERIFIED_PUBLIC_PAVED_GEOMETRY,
    )
    assert InterventionEvidenceInput.VERIFIED_PUBLIC_PAVED_GEOMETRY in (
        rule.suitability_inputs
    )
    assert "traction" in " ".join(rule.limitations)
