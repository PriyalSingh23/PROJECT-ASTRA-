from typing import List, Dict, Any, Optional
from app.adapters.base import (
    ICommunicationAdapter,
    AdapterCapability,
    AdapterState,
    AdapterMetadata,
    AdapterHealthReport,
    OutgoingMessagePayload,
    TransmissionResult,
    HardwareSafetyLockoutError,
)


class StarVRadioAdapter(ICommunicationAdapter):
    """
    STAR-V Tactical VHF/UHF Radio Adapter.
    Strictly configured as a disabled safety stub until official manufacturer
    technical documentation, interface pinouts, and institutional operating
    authorizations are verified.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.state = AdapterState.DISABLED_PREREQUISITES_MISSING
        self.status_message = (
            "STAR-V integration is not configured. The exact radio variant, "
            "approved interface documentation, and institutional authorizations "
            "are required before hardware operations can be enabled."
        )

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id="starv-gateway-01",
            name="STAR-V Tactical Radio Gateway (Feasibility Stub)",
            vendor="BEL / Tactical Communications",
            version="0.1.0-feasibility",
            category="MIL_TACTICAL",
            is_hardware=True,
        )

    def get_capabilities(self) -> List[AdapterCapability]:
        # Disclose theoretical target capabilities, but all active execution is blocked
        return []

    async def check_health(self) -> AdapterHealthReport:
        return AdapterHealthReport(
            adapter_id="starv-gateway-01",
            state=AdapterState.DISABLED_PREREQUISITES_MISSING,
            ready_to_transmit=False,
            summary=self.status_message,
            diagnostic_code="STARV_UNCONFIGURED_SAFETY_LOCKOUT",
            details={
                "hardware_interlock": "LOCKED",
                "documentation_status": "PENDING_MANUFACTURER_CLEARANCE",
                "radio_variant_verified": False,
            },
        )

    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        # Required parameters before ANY bench testing can be considered
        required = [
            "exact_variant_mark",
            "hardware_revision",
            "owner_unit",
            "approved_interface_doc",
            "institutional_authorization_id",
        ]
        missing = [f for f in required if f not in config]
        if missing:
            raise ValueError(
                f"STAR-V configuration rejected by safety policy. Missing prerequisite documentation: {missing}"
            )
        self.config = config
        return self.config

    async def transmit(self, message: OutgoingMessagePayload) -> TransmissionResult:
        # STRICT SAFETY GUARD: Prevent any RF transmission attempts
        raise HardwareSafetyLockoutError(
            f"Operation Aborted: {self.status_message}"
        )

    async def cancel(self, correlation_id: str) -> bool:
        return True
