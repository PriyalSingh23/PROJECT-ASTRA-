from typing import List, Dict, Any, Optional
from app.adapters.base import (
    ICommunicationAdapter,
    AdapterCapability,
    AdapterState,
    AdapterMetadata,
    AdapterHealthReport,
    OutgoingMessagePayload,
    TransmissionResult,
)


class MotorolaRadioAdapter(ICommunicationAdapter):
    """
    Dedicated Motorola Radio Gateway Adapter.
    Supports MOTOTRBO DMR, APX P25, and Analogue Conventional radio profiles.
    Strictly differentiates between Audio/PTT and Documented Digital Data paths.
    """

    def __init__(self, profile: Optional[Dict[str, Any]] = None):
        self.profile = profile or {
            "manufacturer": "Motorola Solutions",
            "product_family": "MOTOTRBO",
            "model_number": "AAH56RDN9WA1AN",
            "model_display_name": "XPR 7550e VHF Portable",
            "system_type": "DMR_DIGITAL",
            "interface_type": "ACCESSORY_GPIO_PTT_AND_USB_DATA",
            "is_simulation": True,
        }
        self.ptt_active: bool = False
        self.connected: bool = True
        self.channel_busy: bool = False

    def get_metadata(self) -> AdapterMetadata:
        model = self.profile.get("model_display_name", "Motorola Generic")
        is_hardware = not self.profile.get("is_simulation", True)
        return AdapterMetadata(
            adapter_id="motorola-gateway-01",
            name=f"Motorola Interoperability Gateway ({model})",
            vendor="Motorola Solutions / SHADOWLINK",
            version="1.0.0",
            category="COMMERCIAL_RADIO",
            is_hardware=is_hardware,
        )

    def get_capabilities(self) -> List[AdapterCapability]:
        caps = [AdapterCapability.PTT_AUDIO_VOICE, AdapterCapability.CARRIER_SENSE]
        system_type = self.profile.get("system_type", "")
        if "DIGITAL" in system_type or "DMR" in system_type or "P25" in system_type:
            caps.append(AdapterCapability.DIGITAL_PACKET_DATA)
            caps.append(AdapterCapability.HARDWARE_ACK)
        return caps

    async def check_health(self) -> AdapterHealthReport:
        if not self.connected:
            return AdapterHealthReport(
                adapter_id="motorola-gateway-01",
                state=AdapterState.OFFLINE,
                ready_to_transmit=False,
                summary="Motorola Radio Disconnected or Gateway Unreachable",
                diagnostic_code="MOTO_CABLE_DISCONNECTED",
            )

        is_sim = self.profile.get("is_simulation", True)
        state = AdapterState.SIMULATION_ACTIVE if is_sim else AdapterState.READY
        return AdapterHealthReport(
            adapter_id="motorola-gateway-01",
            state=state,
            ready_to_transmit=True,
            summary=f"Motorola Gateway Active ({self.profile.get('model_display_name')}) [Simulated={is_sim}]",
            diagnostic_code="MOTO_PROFILE_ACTIVE",
            details={
                "model_number": self.profile.get("model_number"),
                "system_type": self.profile.get("system_type"),
                "ptt_state": "KEYED" if self.ptt_active else "IDLE",
            },
        )

    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        required = ["manufacturer", "product_family", "model_number", "system_type", "interface_type"]
        missing = [f for f in required if f not in config]
        if missing:
            raise ValueError(f"Motorola profile incomplete. Missing fields: {missing}")
        self.profile.update(config)
        return self.profile

    async def transmit(self, message: OutgoingMessagePayload) -> TransmissionResult:
        if not self.connected:
            return TransmissionResult(
                success=False,
                transport_state="OFFLINE",
                delivered_to_receiver=False,
                ack_delivered_to_sender=False,
                error_code="MOTO_RADIO_OFFLINE",
                diagnostics={"note": "Radio interface unreachable"},
            )

        if self.channel_busy:
            return TransmissionResult(
                success=False,
                transport_state="ONLINE",
                delivered_to_receiver=False,
                ack_delivered_to_sender=False,
                error_code="MOTO_CHANNEL_BUSY",
                diagnostics={"note": "Carrier detect active: Channel occupied"},
            )

        caps = self.get_capabilities()
        if AdapterCapability.DIGITAL_PACKET_DATA not in caps:
            return TransmissionResult(
                success=False,
                transport_state="ONLINE",
                delivered_to_receiver=False,
                ack_delivered_to_sender=False,
                error_code="UNSUPPORTED_ADAPTER_CAPABILITY",
                diagnostics={
                    "note": "Selected Motorola profile does not support digital data transfer. Use Operator PTT Voice."
                },
            )

        # Transmit via documented TMS protocol simulation
        return TransmissionResult(
            success=True,
            transport_state="ONLINE",
            delivered_to_receiver=True,
            ack_delivered_to_sender=True,
            error_code=None,
            diagnostics={
                "protocol": "ETSI-DMR-Tier-II-TMS",
                "radio_id": self.profile.get("model_number"),
                "rf_ack_received": True,
            },
        )

    async def set_ptt(self, active: bool) -> bool:
        """Hardware or virtual PTT control."""
        self.ptt_active = active
        return self.ptt_active

    async def cancel(self, correlation_id: str) -> bool:
        self.ptt_active = False
        return True
