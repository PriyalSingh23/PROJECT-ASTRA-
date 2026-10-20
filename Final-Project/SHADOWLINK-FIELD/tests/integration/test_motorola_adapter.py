import asyncio
import pytest
from app.adapters.base import OutgoingMessagePayload, AdapterCapability
from app.adapters.motorola import MotorolaRadioAdapter


def test_motorola_profile_validation():
    async def run():
        adapter = MotorolaRadioAdapter()

        # Valid profile
        valid_cfg = {
            "manufacturer": "Motorola Solutions",
            "product_family": "MOTOTRBO",
            "model_number": "AAH56RDN9WA1AN",
            "system_type": "DMR_DIGITAL",
            "interface_type": "ACCESSORY_GPIO_PTT_AND_USB_DATA",
        }
        validated = await adapter.validate_config(valid_cfg)
        assert validated["model_number"] == "AAH56RDN9WA1AN"

        # Incomplete profile must fail
        with pytest.raises(ValueError):
            await adapter.validate_config({"manufacturer": "Motorola Solutions"})

    asyncio.run(run())


def test_motorola_audio_only_blocks_digital():
    async def run():
        audio_only_adapter = MotorolaRadioAdapter(
            profile={
                "manufacturer": "Motorola Solutions",
                "product_family": "Conventional",
                "model_number": "CM300d",
                "model_display_name": "CM300d Analogue Mobile",
                "system_type": "ANALOGUE",
                "interface_type": "ACCESSORY_AUDIO_PTT",
                "is_simulation": True,
            }
        )
        caps = audio_only_adapter.get_capabilities()
        assert AdapterCapability.DIGITAL_PACKET_DATA not in caps
        assert AdapterCapability.PTT_AUDIO_VOICE in caps

        # Attempting digital dispatch on audio-only radio must fail cleanly
        payload = OutgoingMessagePayload(
            message_id="msg-moto-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="TEST_DATA",
        )
        result = await audio_only_adapter.transmit(payload)
        assert result.success is False
        assert result.error_code == "UNSUPPORTED_ADAPTER_CAPABILITY"

    asyncio.run(run())


def test_motorola_channel_busy():
    async def run():
        adapter = MotorolaRadioAdapter()
        adapter.channel_busy = True

        payload = OutgoingMessagePayload(
            message_id="msg-moto-busy",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="TEST_DATA",
        )
        result = await adapter.transmit(payload)
        assert result.success is False
        assert result.error_code == "MOTO_CHANNEL_BUSY"

    asyncio.run(run())
