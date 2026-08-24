"""Tests for normalized intervention-value factors."""

import math

import pytest
from pydantic import ValidationError

from api.app.services.intervention_value import InterventionValueFactors


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        (field, invalid_value)
        for field in (
            "priority_score",
            "suitability_score",
            "feasibility_score",
            "confidence_score",
        )
        for invalid_value in (-0.000001, 1.000001, math.inf, math.nan)
    ],
)
def test_intervention_value_factors_reject_values_outside_unit_interval(
    field: str,
    invalid_value: float,
) -> None:
    payload = {
        "priority_score": 0.5,
        "suitability_score": 0.5,
        "feasibility_score": 0.5,
        "confidence_score": 0.5,
    }
    payload[field] = invalid_value

    with pytest.raises(ValidationError):
        InterventionValueFactors.model_validate(payload)


def test_modeled_benefit_stays_inside_unit_interval() -> None:
    assert (
        InterventionValueFactors(
            priority_score=0.0,
            suitability_score=1.0,
            feasibility_score=1.0,
            confidence_score=1.0,
        ).modeled_benefit()
        == 0.0
    )
    assert (
        InterventionValueFactors(
            priority_score=1.0,
            suitability_score=1.0,
            feasibility_score=1.0,
            confidence_score=1.0,
        ).modeled_benefit()
        == 1.0
    )
