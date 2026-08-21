"""Validated FortyGuard feature availability for the offline-first MVP."""

import json
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CAPABILITIES_PATH = ROOT / "data" / "processed" / "fortyguard_capabilities.json"


class FortyGuardFeature(StrEnum):
    HEATMAP_TCM = "heatmap_tcm"
    HEATMAP_PERSISTENCE = "heatmap_persistence"
    HEATMAP_EXCEEDANCE = "heatmap_exceedance"
    ENVIRONMENTAL_PARAMETERS = "environmental_parameters"
    SATELLITE_SEGMENTATION = "satellite_segmentation"
    STREET_VIEW_SEGMENTATION = "street_view_segmentation"
    HEAT_INTELLIGENCE_REPORT = "heat_intelligence_report"


class AccessState(StrEnum):
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"


class CapabilityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature: FortyGuardFeature
    enabled: bool
    access: AccessState
    probe_attempted: bool
    reason: str = Field(min_length=20)
    dependency: str | None = None
    cached_artifact: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.enabled and self.access != AccessState.CONFIRMED:
            raise ValueError("enabled capability requires confirmed access")
        if self.enabled and not self.probe_attempted:
            raise ValueError("enabled capability requires a successful runtime request")
        if self.enabled and self.cached_artifact is None:
            raise ValueError("enabled capability requires a cached artifact")
        if self.access == AccessState.CONFIRMED and not self.probe_attempted:
            raise ValueError("confirmed access requires a runtime request")
        return self


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^1\.0$")
    evaluated_at: date
    optional_live_probes_made: int = Field(ge=0)
    total_credits: int = Field(default=2_000_000, ge=500_001, le=2_000_000)
    credits_used: int = Field(ge=0)
    credits_remaining: int = Field(ge=500_000)
    hard_reserve: int = Field(ge=500_000)
    capabilities: tuple[CapabilityRecord, ...]

    @model_validator(mode="after")
    def require_every_feature_once(self) -> Self:
        features = [capability.feature for capability in self.capabilities]
        if len(features) != len(set(features)):
            raise ValueError("capability features must be unique")
        if set(features) != set(FortyGuardFeature):
            raise ValueError("capability manifest must cover every known feature")
        if self.credits_used + self.credits_remaining != self.total_credits:
            raise ValueError("capability credit counters do not balance")
        core = {
            FortyGuardFeature.HEATMAP_TCM,
            FortyGuardFeature.HEATMAP_PERSISTENCE,
        }
        optional_probe_count = sum(
            item.probe_attempted for item in self.capabilities if item.feature not in core
        )
        if self.optional_live_probes_made != optional_probe_count:
            raise ValueError("optional probe count does not match capability records")
        return self

    def get(self, feature: FortyGuardFeature) -> CapabilityRecord:
        return next(item for item in self.capabilities if item.feature == feature)

    def require_enabled(self, feature: FortyGuardFeature) -> CapabilityRecord:
        capability = self.get(feature)
        if not capability.enabled:
            raise FeatureDisabledError(
                f"FortyGuard feature '{feature.value}' is disabled: {capability.reason}"
            )
        return capability


class FeatureDisabledError(RuntimeError):
    """A caller requested an intentionally disabled optional feature."""


def load_capabilities(path: Path = DEFAULT_CAPABILITIES_PATH) -> CapabilityManifest:
    return CapabilityManifest.model_validate_json(path.read_text(encoding="utf-8"))


def canonical_capability_bytes(manifest: CapabilityManifest) -> bytes:
    return (
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    ).encode()
