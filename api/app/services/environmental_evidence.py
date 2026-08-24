"""Versioned selection contract for concise finalist environmental evidence."""

from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENVIRONMENTAL_CONFIG_PATH = ROOT / "config" / "environmental_parameters.json"


class EnvironmentalMetricId(StrEnum):
    APPARENT_TEMPERATURE = "apparent_temperature"
    RELATIVE_HUMIDITY = "relative_humidity"
    CLEAR_SKY_GHI = "clear_sky_ghi"


class EnvironmentalMetricSource(StrEnum):
    PARAMETERS = "parameters"
    SOLAR_CLEAR_SKY = "solar_irradiance.clear_sky"


class EnvironmentalMetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: EnvironmentalMetricId
    source: EnvironmentalMetricSource
    vendor_key: str = Field(min_length=1)
    display_label: str = Field(min_length=3)
    unit_label: str = Field(min_length=1)
    planning_context: str = Field(min_length=30)
    limitation: str = Field(min_length=40)


class EnvironmentalEvidenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    metrics: tuple[EnvironmentalMetricDefinition, ...] = Field(
        min_length=1, max_length=3
    )
    selection_note: str = Field(min_length=80)

    @model_validator(mode="after")
    def require_unique_complete_selection(self) -> Self:
        metric_ids = tuple(metric.id for metric in self.metrics)
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("environmental metric IDs must be unique")
        if set(metric_ids) != set(EnvironmentalMetricId):
            raise ValueError("environmental evidence must use the three approved metrics")
        return self


def load_environmental_evidence_config(
    path: Path = DEFAULT_ENVIRONMENTAL_CONFIG_PATH,
) -> EnvironmentalEvidenceConfig:
    return EnvironmentalEvidenceConfig.model_validate_json(path.read_text(encoding="utf-8"))
