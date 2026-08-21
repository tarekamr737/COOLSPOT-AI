"""Safety preflight tests for the authenticated live-refresh coordinator."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from api.app.fortyguard_models import CreditUsage
from api.app.services.live_refresh import RefreshCoordinator, RefreshStatus


def test_refresh_preflights_both_layers_against_the_credit_reserve() -> None:
    coordinator = RefreshCoordinator()
    env = {
        "FORTYGUARD_LIVE": "1",
        "FORTYGUARD_API_KEY": "vendor-key",
        "FORTYGUARD_CREDIT_TOTAL": "2000000",
        "FORTYGUARD_CREDIT_RESERVE": "500000",
        "COOLSPOT_REFRESH_TOKEN": "admin-secret",
    }

    async def scenario() -> RefreshStatus:
        with (
            patch("api.app.services.live_refresh.load_project_env", return_value=env),
            patch(
                "api.app.services.live_refresh.FortyGuardClient.fetch_credit_usage",
                new_callable=AsyncMock,
                return_value=CreditUsage(
                    total_available_credits=2_000_000,
                    used_credits=8_440,
                    remaining_credits=1_991_560,
                ),
            ),
            patch(
                "api.app.services.live_refresh.CreditLedger.conservative_observed_cost",
                return_value=4_220,
            ),
            patch(
                "api.app.services.live_refresh.CreditLedger.find_request",
                return_value=None,
            ),
            patch.object(coordinator, "_run", new_callable=AsyncMock),
        ):
            result = await coordinator.start(
                token="admin-secret",
                analysis_date=datetime.now(UTC).date() - timedelta(days=1),
            )
            await asyncio.sleep(0)
            return result

    result = asyncio.run(scenario())
    assert result.state == "running"
    assert result.estimated_credit_cost == 8_440
    assert result.credits_remaining == 1_991_560
    assert result.hard_reserve == 500_000
