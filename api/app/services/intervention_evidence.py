"""Versioned intervention-specific evidence inputs and safety gates."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from api.app.fortyguard_models import StrictModel

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INTERVENTION_EVIDENCE_CONFIG_PATH = ROOT / "config" / "intervention_evidence.json"


class InterventionEvidenceInput(StrEnum):
    """Defensible evidence inputs available to intervention screening rules."""

    HEAT_SEVERITY = "heat_severity"
    HEAT_PERSISTENCE = "heat_persistence"
    PUBLISHED_TRANSIT_EXPOSURE = "published_transit_exposure"
    STREET_TREE_CONTEXT = "street_tree_context"
    STREET_SKY_CONTEXT = "street_sky_context"
    EVIDENCE_CONFIDENCE = "evidence_confidence"
    SITE_TYPE_COMPATIBILITY = "site_type_compatibility"
    PUBLIC_SITE_COMPATIBILITY = "public_site_compatibility"
    VEGETATION_OPPORTUNITY = "vegetation_opportunity"
    ENVIRONMENTAL_CONTEXT = "environmental_context"
    VERIFIED_PUBLIC_PAVED_GEOMETRY = "verified_public_paved_geometry"


class InterventionEvidenceRule(StrictModel):
    """Permitted suitability inputs and feasibility gates for one intervention."""

    suitability_inputs: tuple[InterventionEvidenceInput, ...] = Field(min_length=1)
    feasibility_inputs: tuple[InterventionEvidenceInput, ...] = Field(min_length=1)
    required_inputs: tuple[InterventionEvidenceInput, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_and_required(self) -> Self:
        groups = (
            self.suitability_inputs,
            self.feasibility_inputs,
            self.required_inputs,
        )
        if any(len(values) != len(set(values)) for values in groups):
            raise ValueError("intervention evidence input lists must be unique")
        available = set(self.suitability_inputs) | set(self.feasibility_inputs)
        if not set(self.required_inputs) <= available:
            raise ValueError("required intervention evidence must be a configured input")
        return self


class InterventionEvidenceConfig(StrictModel):
    """Complete versioned evidence contract for the supported interventions."""

    version: Literal["1.0"]
    shade_structure: InterventionEvidenceRule
    tree_canopy: InterventionEvidenceRule
    cool_pavement: InterventionEvidenceRule


def load_intervention_evidence_config(
    path: Path = DEFAULT_INTERVENTION_EVIDENCE_CONFIG_PATH,
) -> InterventionEvidenceConfig:
    """Load the intervention-specific evidence contract."""

    return InterventionEvidenceConfig.model_validate_json(path.read_text(encoding="utf-8"))
