"""Versioned planning-scenario identifiers shared by API and scoring services."""

from enum import StrEnum


class ScoringPreset(StrEnum):
    BALANCED = "balanced"
    HEAT_FIRST = "heat_first"
    EQUITY_FIRST = "equity_first"
    EXPOSURE_FIRST = "exposure_first"
