import asyncio
import pytest
from app.adapters.base import OutgoingMessagePayload, AdapterState
from app.adapters.sdr import SdrResearchAdapter


def test_sdr_software_evaluation_mode():
    async def run():
        adapter = SdrResearchAdapter()
        health = await adapter.check_health()

        assert health.state == AdapterState.READY
        assert health.ready_to_transmit is False  # RF disarmed
        assert health.diagnostic_code == "SDR_SOFTWARE_EVAL_ACTIVE"
        assert "metrics" in health.details
        assert health.details["metrics"]["ks_pvalue"] > 0.85

    asyncio.run(run())


def test_sdr_software_simulation_dispatch():
    async def run():
        adapter = SdrResearchAdapter()
        payload = OutgoingMessagePayload(
            message_id="msg-sdr-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="TEST_LPI_PAYLOAD",
        )

        result = await adapter.transmit(payload)
        assert result.success is True
        assert result.transport_state == "SOFTWARE_SIMULATION"
        assert result.delivered_to_receiver is True
        assert result.ack_delivered_to_sender is True
        assert result.diagnostics["mode"] == "SOFTWARE_EVALUATION"

    asyncio.run(run())


def test_sdr_rf_emission_requires_admin_token():
    async def run():
        adapter = SdrResearchAdapter()

        with pytest.raises(PermissionError) as exc:
            await adapter.validate_config({"arm_rf": True, "admin_rf_token": "INVALID_TOKEN"})

        assert "Valid authorization token required" in str(exc.value)

    asyncio.run(run())
