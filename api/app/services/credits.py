"""Persistent FortyGuard credit ledger and hard-reserve governor."""

import json
import os
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from api.app.fortyguard_models import (
    ACTIVITY_ID_PATTERN,
    SHA256_PATTERN,
    ActivityLifecycle,
    FortyGuardEndpoint,
)

MINIMUM_RESERVE = 500_000
MAXIMUM_PROJECT_ALLOCATION = 2_000_000


class CreditGovernorError(RuntimeError):
    """Base exception for denied or unverifiable credit operations."""


class LiveModeDisabledError(CreditGovernorError):
    """A live operation was attempted while demo mode is active."""


class CreditReserveError(CreditGovernorError):
    """A projected operation would breach the hard reserve."""


class DuplicateCreditRequestError(CreditGovernorError):
    """A request hash already exists in the durable credit ledger."""


class UnknownEndpointCostError(CreditGovernorError):
    """No completed observation exists for conservative batch estimation."""


class CreditSettings(BaseModel):
    """Credit safety settings loaded without a dotenv dependency."""

    model_config = ConfigDict(extra="forbid")

    live: bool = False
    credit_total: int = Field(default=MAXIMUM_PROJECT_ALLOCATION, gt=MINIMUM_RESERVE)
    credit_reserve: int = Field(default=MINIMUM_RESERVE, ge=MINIMUM_RESERVE)

    @model_validator(mode="after")
    def validate_allocation(self) -> Self:
        if self.credit_total > MAXIMUM_PROJECT_ALLOCATION:
            raise ValueError("credit total cannot exceed the 2,000,000 project allocation")
        if self.credit_reserve >= self.credit_total:
            raise ValueError("credit reserve must be below the project allocation")
        return self

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Self:
        """Load exact 0/1 live mode and bounded integer credit settings."""

        source = os.environ if environ is None else environ
        live_value = source.get("FORTYGUARD_LIVE", "0")
        if live_value not in {"0", "1"}:
            raise ValueError("FORTYGUARD_LIVE must be exactly 0 or 1")
        try:
            credit_total = int(
                source.get("FORTYGUARD_CREDIT_TOTAL", str(MAXIMUM_PROJECT_ALLOCATION))
            )
            credit_reserve = int(
                source.get("FORTYGUARD_CREDIT_RESERVE", str(MINIMUM_RESERVE))
            )
        except ValueError as error:
            raise ValueError("FortyGuard credit settings must be integers") from error
        return cls(
            live=live_value == "1",
            credit_total=credit_total,
            credit_reserve=credit_reserve,
        )


class CreditLedgerEntry(BaseModel):
    """One request's measured FortyGuard credit lifecycle."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    timestamp: datetime
    updated_at: datetime | None = None
    request_hash: str = Field(pattern=SHA256_PATTERN)
    endpoint: FortyGuardEndpoint
    request_summary: dict[str, JsonValue]
    usage_before: int = Field(ge=0)
    usage_after: int | None = Field(default=None, ge=0)
    observed_cost: int | None = Field(default=None, ge=0)
    activity_id: str = Field(pattern=ACTIVITY_ID_PATTERN)
    status: ActivityLifecycle

    @field_validator("timestamp", "updated_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("credit ledger timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_measurement(self) -> Self:
        if self.status == ActivityLifecycle.PROCESSING:
            if self.usage_after is not None or self.observed_cost is not None:
                raise ValueError("processing ledger entry cannot include an observed cost")
            return self
        if self.usage_after is None or self.observed_cost is None or self.updated_at is None:
            raise ValueError("terminal ledger entry requires after-usage, cost, and updated_at")
        if self.usage_after < self.usage_before:
            raise ValueError("credit usage cannot decrease within one measured activity")
        if self.observed_cost != self.usage_after - self.usage_before:
            raise ValueError("observed cost must equal usage_after minus usage_before")
        return self


class CreditLedgerDocument(BaseModel):
    """Versioned atomic ledger document."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    entries: tuple[CreditLedgerEntry, ...] = ()

    @model_validator(mode="after")
    def require_unique_requests_and_activities(self) -> Self:
        request_hashes = [entry.request_hash for entry in self.entries]
        activity_ids = [entry.activity_id for entry in self.entries]
        if len(request_hashes) != len(set(request_hashes)):
            raise ValueError("credit ledger request hashes must be unique")
        if len(activity_ids) != len(set(activity_ids)):
            raise ValueError("credit ledger activity IDs must be unique")
        return self


class CreditAuthorization(BaseModel):
    """Auditable result of a successful preflight reserve calculation."""

    model_config = ConfigDict(extra="forbid")

    current_usage: int = Field(ge=0)
    estimated_unit_cost: int = Field(gt=0)
    request_count: int = Field(gt=0)
    projected_cost: int = Field(gt=0)
    remaining_before: int = Field(ge=0)
    remaining_after: int = Field(ge=0)
    reserve: int = Field(ge=MINIMUM_RESERVE)


class CreditLedger:
    """Small atomic file-backed ledger for measured credit deltas."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    def load(self) -> CreditLedgerDocument:
        """Load the current ledger or an empty document when none exists."""

        if not self.path.exists():
            return CreditLedgerDocument()
        return CreditLedgerDocument.model_validate_json(self.path.read_text(encoding="utf-8"))

    def find_request(self, request_hash: str) -> CreditLedgerEntry | None:
        """Find one canonical request already recorded in the ledger."""

        if not re.fullmatch(SHA256_PATTERN, request_hash):
            raise ValueError("invalid request hash")
        return next(
            (entry for entry in self.load().entries if entry.request_hash == request_hash),
            None,
        )

    def record_submission(
        self,
        *,
        timestamp: datetime,
        request_hash: str,
        endpoint: FortyGuardEndpoint,
        request_summary: dict[str, JsonValue],
        usage_before: int,
        activity_id: str,
    ) -> CreditLedgerEntry:
        """Persist the before-usage and activity ID immediately after submission."""

        document = self.load()
        if any(entry.request_hash == request_hash for entry in document.entries):
            raise DuplicateCreditRequestError(f"request {request_hash} is already in the ledger")
        entry = CreditLedgerEntry(
            timestamp=timestamp,
            request_hash=request_hash,
            endpoint=endpoint,
            request_summary=request_summary,
            usage_before=usage_before,
            activity_id=activity_id,
            status=ActivityLifecycle.PROCESSING,
        )
        self._write(CreditLedgerDocument(entries=(*document.entries, entry)))
        return entry

    def record_outcome(
        self,
        *,
        activity_id: str,
        status: Literal[ActivityLifecycle.COMPLETED, ActivityLifecycle.FAILED],
        usage_after: int,
        timestamp: datetime,
    ) -> CreditLedgerEntry:
        """Update one activity with its measured terminal credit delta."""

        document = self.load()
        matching = [entry for entry in document.entries if entry.activity_id == activity_id]
        if len(matching) != 1:
            raise KeyError(f"unknown credit-ledger activity {activity_id}")
        previous = matching[0]
        if previous.status != ActivityLifecycle.PROCESSING:
            if previous.status == status and previous.usage_after == usage_after:
                return previous
            raise ValueError("terminal credit-ledger outcome cannot be changed")
        observed_cost = usage_after - previous.usage_before
        updated = CreditLedgerEntry.model_validate(
            {
                **previous.model_dump(mode="python"),
                "updated_at": timestamp,
                "usage_after": usage_after,
                "observed_cost": observed_cost,
                "status": status,
            }
        )
        entries = tuple(
            updated if entry.activity_id == activity_id else entry
            for entry in document.entries
        )
        self._write(CreditLedgerDocument(entries=entries))
        return updated

    def conservative_observed_cost(self, endpoint: FortyGuardEndpoint) -> int:
        """Use the highest successful observed cost for future batch preflight."""

        costs = [
            entry.observed_cost
            for entry in self.load().entries
            if entry.endpoint == endpoint
            and entry.status == ActivityLifecycle.COMPLETED
            and entry.observed_cost is not None
            and entry.observed_cost > 0
        ]
        if not costs:
            raise UnknownEndpointCostError(f"no completed cost observation for {endpoint.value}")
        return max(costs)

    def _write(self, document: CreditLedgerDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.part")
        temporary_path.write_text(payload, encoding="utf-8")
        os.replace(temporary_path, self.path)


class CreditGovernor:
    """Deny live or projected work that violates project credit discipline."""

    def __init__(self, settings: CreditSettings, ledger: CreditLedger) -> None:
        self.settings = settings
        self.ledger = ledger

    def authorize_estimate(
        self,
        *,
        request_hashes: tuple[str, ...],
        current_usage: int,
        estimated_unit_cost: int,
    ) -> CreditAuthorization:
        """Authorize a known conservative unit cost while preserving the hard reserve."""

        if not self.settings.live:
            raise LiveModeDisabledError("FORTYGUARD_LIVE=0 blocks live submissions")
        if current_usage < 0 or current_usage > self.settings.credit_total:
            raise ValueError("current credit usage must fit within the project allocation")
        if estimated_unit_cost <= 0:
            raise ValueError("estimated unit cost must be positive")
        if not request_hashes or len(request_hashes) != len(set(request_hashes)):
            raise ValueError("request hashes must be non-empty and unique")
        for request_hash in request_hashes:
            if not re.fullmatch(SHA256_PATTERN, request_hash):
                raise ValueError("invalid request hash")
            if self.ledger.find_request(request_hash) is not None:
                raise DuplicateCreditRequestError(
                    f"request {request_hash} is already submitted or complete"
                )

        projected_cost = estimated_unit_cost * len(request_hashes)
        remaining_before = self.settings.credit_total - current_usage
        remaining_after = remaining_before - projected_cost
        if remaining_after < self.settings.credit_reserve:
            raise CreditReserveError(
                f"projected remaining credits {remaining_after} would breach reserve "
                f"{self.settings.credit_reserve}"
            )
        return CreditAuthorization(
            current_usage=current_usage,
            estimated_unit_cost=estimated_unit_cost,
            request_count=len(request_hashes),
            projected_cost=projected_cost,
            remaining_before=remaining_before,
            remaining_after=remaining_after,
            reserve=self.settings.credit_reserve,
        )

    def authorize_observed_batch(
        self,
        *,
        endpoint: FortyGuardEndpoint,
        request_hashes: tuple[str, ...],
        current_usage: int,
    ) -> CreditAuthorization:
        """Authorize a batch using the highest completed cost observed for its endpoint."""

        return self.authorize_estimate(
            request_hashes=request_hashes,
            current_usage=current_usage,
            estimated_unit_cost=self.ledger.conservative_observed_cost(endpoint),
        )
