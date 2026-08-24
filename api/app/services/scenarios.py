"""Versioned planning scenarios for deterministic local re-scoring."""

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.app.services.feature_table import PriorityWeights, TileScores

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCENARIOS_PATH = ROOT / "config" / "scenarios.json"


class ScoringPreset(StrEnum):
    BALANCED = "balanced"
    HEAT_FIRST = "heat_first"
    EQUITY_FIRST = "equity_first"
    EXPOSURE_FIRST = "exposure_first"


class ScoringScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ScoringPreset
    label: str = Field(min_length=3)
    weights: PriorityWeights


class ScoringScenarioCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^1\.0$")
    default: ScoringPreset
    scenarios: tuple[ScoringScenario, ...]

    @model_validator(mode="after")
    def validate_complete(self) -> Self:
        ids = tuple(scenario.id for scenario in self.scenarios)
        if len(ids) != len(set(ids)) or set(ids) != set(ScoringPreset):
            raise ValueError("scenario catalog must define every preset exactly once")
        if self.default not in ids:
            raise ValueError("default scenario must exist in the catalog")
        return self

    def get(self, preset: ScoringPreset) -> ScoringScenario:
        return next(scenario for scenario in self.scenarios if scenario.id == preset)


def load_scenario_catalog(
    path: Path = DEFAULT_SCENARIOS_PATH,
) -> ScoringScenarioCatalog:
    return ScoringScenarioCatalog.model_validate_json(path.read_text(encoding="utf-8"))


def scenario_priority(scores: TileScores, weights: PriorityWeights) -> float:
    return (
        scores.heat * weights.heat
        + scores.exposure * weights.exposure
        + scores.vulnerability * weights.vulnerability
        + scores.cooling_opportunity * weights.cooling_opportunity
    )
