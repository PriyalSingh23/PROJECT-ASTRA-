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


class SdrResearchAdapter(ICommunicationAdapter):
    """
    SDR Research Adapter (LPI-CGAN Covert Waveform v4).
    Provides software-only evaluation mode without initiating RF radiation.
    Segregated from commercial and tactical radio paths.
    """

    def __init__(self, model_checkpoint: Optional[str] = None):
        self.model_checkpoint = model_checkpoint or "lpi_v4.best.pt"
        self.rf_armed: bool = False  # Strictly disarmed by default
        self.software_mode: bool = True
        self.evaluation_metrics: Dict[str, Any] = {
            "ks_pvalue": 0.8646,
            "kurtosis": 2.9907,
            "entropy": 0.9566,
            "circularity": 0.0107,
            "adversary_accuracy": 55.90,
            "cable_ber_5db": 0.0,
            "message_fer_2db": 0.0,
        }

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id="sdr-lpi-v4",
            name="LPI-CGAN Covert Waveform Engine (v4 Stack)",
            vendor="ShadowComm Research Group",
            version="4.2.0",
            category="SDR_RESEARCH",
            is_hardware=self.rf_armed,
        )

    def get_capabilities(self) -> List[AdapterCapability]:
        return [
            AdapterCapability.DIGITAL_PACKET_DATA,
            AdapterCapability.ENCRYPTION_PASS_THROUGH,
            AdapterCapability.STORE_AND_FORWARD,
        ]

    async def check_health(self) -> AdapterHealthReport:
        return AdapterHealthReport(
            adapter_id="sdr-lpi-v4",
            state=AdapterState.READY if self.software_mode else AdapterState.DEGRADED,
            ready_to_transmit=self.rf_armed,
            summary="SDR Research Engine Online (Software Evaluation Mode - RF Disarmed)",
            diagnostic_code="SDR_SOFTWARE_EVAL_ACTIVE",
            details={
                "model_checkpoint": self.model_checkpoint,
                "rf_hardware_armed": self.rf_armed,
                "software_mode": self.software_mode,
                "metrics": self.evaluation_metrics,
            },
        )

    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        if "arm_rf" in config and config["arm_rf"] is True:
            # Require explicit admin token/clearance
            auth_token = config.get("admin_rf_token")
            if auth_token != "AUTHORIZE_WPC_FIELD_TRANSMISSION":
                raise PermissionError("RF hardware arming rejected. Valid authorization token required.")
            self.rf_armed = True
        elif "arm_rf" in config and config["arm_rf"] is False:
            self.rf_armed = False

        if "checkpoint" in config:
            self.model_checkpoint = str(config["checkpoint"])
        return {
            "model_checkpoint": self.model_checkpoint,
            "rf_armed": self.rf_armed,
            "software_mode": self.software_mode,
        }

    async def transmit(self, message: OutgoingMessagePayload) -> TransmissionResult:
        if self.rf_armed:
            raise PermissionError("Physical USRP transmission disabled in this environment profile.")

        # Execute in pure software simulation mode
        return TransmissionResult(
            success=True,
            transport_state="SOFTWARE_SIMULATION",
            delivered_to_receiver=True,
            ack_delivered_to_sender=True,
            error_code=None,
            diagnostics={
                "mode": "SOFTWARE_EVALUATION",
                "model": self.model_checkpoint,
                "codec": "RS(42,34) + CRC8",
                "ks_pvalue": self.evaluation_metrics["ks_pvalue"],
                "synthetic_ber": 0.0,
            },
        )

    async def cancel(self, correlation_id: str) -> bool:
        return True
