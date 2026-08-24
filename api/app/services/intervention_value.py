"""Typed factors for deterministic intervention-value calculations."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from api.app.fortyguard_models import StrictModel

UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]


class InterventionValueFactors(StrictModel):
    """Bound every multiplicative decision factor to the normalized interval."""

    priority_score: UnitInterval
    suitability_score: UnitInterval
    feasibility_score: UnitInterval
    confidence_score: UnitInterval

    def modeled_benefit(self) -> float:
        """Return the deterministic product of normalized factors."""

        return (
            self.priority_score
            * self.suitability_score
            * self.feasibility_score
            * self.confidence_score
        )
