"""Typed, versioned intervention assumptions for deterministic planning."""

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INTERVENTION_CATALOG_PATH = ROOT / "data" / "processed" / "interventions.json"


class InterventionType(StrEnum):
    SHADE_STRUCTURE = "shade_structure"
    TREE_CANOPY = "tree_canopy"
    COOL_PAVEMENT = "cool_pavement"


class SiteType(StrEnum):
    TRANSIT_STOP = "transit_stop"
    SCHOOL = "school"
    PARK = "park"
    PUBLIC_CORRIDOR = "public_corridor"
    PUBLIC_PAVED_SURFACE = "public_paved_surface"


class EvidenceKind(StrEnum):
    QUALITATIVE = "qualitative"
    OBSERVATIONAL_FIELD_STUDY = "observational_field_study"


class UncertaintyLevel(StrEnum):
    MEDIUM = "medium"
    HIGH = "high"


class CatalogSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str = Field(min_length=10)
    publisher: str = Field(min_length=3)
    url: HttpUrl
    published_at: date | None
    retrieved_at: date
    supports: tuple[str, ...] = Field(min_length=1)


class CostBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date
    currency: str = Field(pattern=r"^USD$")
    disclaimer: str = Field(min_length=40)
    shared_exclusions: tuple[str, ...] = Field(min_length=1)


class ApplicabilityRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eligible_site_types: tuple[SiteType, ...] = Field(min_length=1)
    screening_rule: str = Field(min_length=20)
    preconstruction_checks: tuple[str, ...] = Field(min_length=1)
    exclusion_rule: str = Field(min_length=20)

    @model_validator(mode="after")
    def require_unique_site_types(self) -> Self:
        if len(self.eligible_site_types) != len(set(self.eligible_site_types)):
            raise ValueError("eligible site types must be unique")
        return self


class PlanningCost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimate_usd: int = Field(gt=0)
    low_usd: int = Field(gt=0)
    high_usd: int = Field(gt=0)
    unit: str = Field(min_length=10)
    basis: str = Field(min_length=30)
    source_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if not self.low_usd <= self.estimate_usd <= self.high_usd:
            raise ValueError("planning cost estimate must fall within its range")
        return self


class BenefitEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    qualitative_benefit: str = Field(min_length=30)
    transfer_limit: str = Field(min_length=30)
    source_ids: tuple[str, ...] = Field(min_length=1)


class InterventionUncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: UncertaintyLevel
    summary: str = Field(min_length=30)
    factors: tuple[str, ...] = Field(min_length=2)


class LifespanMaintenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_lifespan: str = Field(min_length=10)
    maintenance_note: str = Field(min_length=30)
    source_ids: tuple[str, ...] = Field(min_length=1)


class InterventionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: InterventionType
    label: str = Field(min_length=4)
    description: str = Field(min_length=20)
    applicability: ApplicabilityRules
    planning_cost: PlanningCost
    benefit_evidence: BenefitEvidence
    uncertainty: InterventionUncertainty
    lifespan_maintenance: LifespanMaintenance


class InterventionCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^1\.0$")
    pilot: str = Field(pattern=r"^Pacoima, Los Angeles$")
    cost_basis: CostBasis
    sources: tuple[CatalogSource, ...] = Field(min_length=1)
    interventions: tuple[InterventionDefinition, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("catalog source IDs must be unique")

        intervention_ids = [intervention.id for intervention in self.interventions]
        if len(intervention_ids) != len(set(intervention_ids)):
            raise ValueError("intervention IDs must be unique")
        if set(intervention_ids) != set(InterventionType):
            raise ValueError("catalog must define every MVP intervention exactly once")

        known_sources = set(source_ids)
        for intervention in self.interventions:
            referenced_sources = {
                *intervention.planning_cost.source_ids,
                *intervention.benefit_evidence.source_ids,
                *intervention.lifespan_maintenance.source_ids,
            }
            unknown_sources = referenced_sources - known_sources
            if unknown_sources:
                raise ValueError(
                    f"intervention {intervention.id.value} references unknown sources: "
                    f"{sorted(unknown_sources)}"
                )
        return self

    def get(self, intervention_type: InterventionType) -> InterventionDefinition:
        return next(
            intervention
            for intervention in self.interventions
            if intervention.id == intervention_type
        )


def load_intervention_catalog(
    path: Path = DEFAULT_INTERVENTION_CATALOG_PATH,
) -> InterventionCatalog:
    return InterventionCatalog.model_validate_json(path.read_text(encoding="utf-8"))
