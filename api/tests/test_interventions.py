"""Tests for the versioned intervention catalog and its planning claims."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from api.app.services.interventions import (
    InterventionCatalog,
    InterventionType,
    SiteType,
    load_intervention_catalog,
)


def test_catalog_defines_complete_traceable_mvp_interventions() -> None:
    catalog = load_intervention_catalog()

    assert catalog.version == "1.0"
    assert catalog.cost_basis.currency == "USD"
    assert "not contractor quotes" in catalog.cost_basis.disclaimer
    assert {intervention.id for intervention in catalog.interventions} == set(
        InterventionType
    )

    known_sources = {source.id for source in catalog.sources}
    assert len(known_sources) == len(catalog.sources)
    for intervention in catalog.interventions:
        cost = intervention.planning_cost
        assert cost.low_usd <= cost.estimate_usd <= cost.high_usd
        assert intervention.applicability.preconstruction_checks
        assert intervention.benefit_evidence.qualitative_benefit
        assert intervention.benefit_evidence.transfer_limit
        assert len(intervention.uncertainty.factors) >= 2
        assert intervention.lifespan_maintenance.maintenance_note
        assert set(cost.source_ids) <= known_sources
        assert set(intervention.benefit_evidence.source_ids) <= known_sources
        assert set(intervention.lifespan_maintenance.source_ids) <= known_sources


def test_applicability_does_not_infer_unobserved_site_conditions() -> None:
    catalog = load_intervention_catalog()

    assert catalog.get(InterventionType.SHADE_STRUCTURE).applicability.eligible_site_types == (
        SiteType.TRANSIT_STOP,
    )
    assert set(
        catalog.get(InterventionType.TREE_CANOPY).applicability.eligible_site_types
    ) == {SiteType.SCHOOL, SiteType.PARK}
    assert set(
        catalog.get(InterventionType.COOL_PAVEMENT).applicability.eligible_site_types
    ) == {SiteType.PUBLIC_CORRIDOR, SiteType.PUBLIC_PAVED_SURFACE}

    claims = " ".join(
        intervention.benefit_evidence.qualitative_benefit.lower()
        for intervention in catalog.interventions
    )
    for prohibited_claim in ("people protected", "lives saved", "deaths prevented"):
        assert prohibited_claim not in claims


def test_catalog_rejects_invalid_cost_range_and_unknown_source() -> None:
    payload = load_intervention_catalog().model_dump(mode="json")

    invalid_cost = deepcopy(payload)
    invalid_cost["interventions"][0]["planning_cost"]["estimate_usd"] = 1
    with pytest.raises(ValidationError, match="planning cost estimate"):
        InterventionCatalog.model_validate(invalid_cost)

    unknown_source = deepcopy(payload)
    unknown_source["interventions"][0]["benefit_evidence"]["source_ids"] = [
        "invented_source"
    ]
    with pytest.raises(ValidationError, match="unknown sources"):
        InterventionCatalog.model_validate(unknown_source)
