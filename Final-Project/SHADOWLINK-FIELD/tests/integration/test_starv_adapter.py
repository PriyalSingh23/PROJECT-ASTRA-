import asyncio
import pytest
from app.adapters.base import (
    OutgoingMessagePayload,
    AdapterState,
    HardwareSafetyLockoutError,
)
from app.adapters.starv import StarVRadioAdapter


def test_starv_disabled_safety_stub():
    async def run():
        adapter = StarVRadioAdapter()
        health = await adapter.check_health()

        assert health.state == AdapterState.DISABLED_PREREQUISITES_MISSING
        assert health.ready_to_transmit is False
        assert "STAR-V integration is not configured" in health.summary
        assert health.diagnostic_code == "STARV_UNCONFIGURED_SAFETY_LOCKOUT"

    asyncio.run(run())


def test_starv_transmission_strictly_blocked():
    async def run():
        adapter = StarVRadioAdapter()
        payload = OutgoingMessagePayload(
            message_id="msg-starv-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="ATTEMPTED_STARV_DATA",
        )

        with pytest.raises(HardwareSafetyLockoutError) as exc:
            await adapter.transmit(payload)

        assert "Operation Aborted" in str(exc.value)
        assert "approved interface documentation" in str(exc.value)

    asyncio.run(run())


def test_starv_config_validation_requires_authorization():
    async def run():
        adapter = StarVRadioAdapter()

        with pytest.raises(ValueError) as exc:
            await adapter.validate_config({"exact_variant_mark": "Star-V-Mk2"})

        assert "Missing prerequisite documentation" in str(exc.value)

    asyncio.run(run())
