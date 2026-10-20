import os
from typing import Dict, List, Any
from integration.base import (
    BaseTransportAdapter,
    TransportReadiness,
    TransportConnectionState,
    utcnow_iso,
)
from integration.motorola.hardware_bridge import MotorolaHardwareBridge


class MotorolaMOTOTRBOAdapter(BaseTransportAdapter):
    """
    Interoperability adapter for Motorola MOTOTRBO / APX digital radio data services.
    
    Adheres strictly to published Motorola application-services documentation:
    - Text Messaging Service (TMS) over XCMP / IP Peripheral Interface
    - Digital Location Reporting (LRRP / GPS)
    - Telemetry I/O states
    - Raw Data / ARS (Automatic Registration Service)
    
    Safety Boundary:
    Physical RF transmission is disabled during this phase. All operations execute in
    verified simulation mode unless explicit vendor hardware authorization is supplied.
    """

    def __init__(self, transport_id: str = "motorola-mototrbo-01", radio_model: str = "MOTOTRBO XPR 7550e / DP4801e"):
        super().__init__(transport_id, display_name=f"Motorola MOTOTRBO ({radio_model})")
        self.radio_model = radio_model
        self._is_hardware_authorized = os.environ.get("MOTOROLA_RADIO_APPROVED", "false").lower() in ("true", "1")
        self._connection_state = TransportConnectionState.STANDBY
        # Physical path (MNIS UDP or Raspberry Pi GPIO PTT). Only engaged when
        # MOTOROLA_RADIO_APPROVED=true; otherwise it stays a dry-run preview.
        self._bridge = MotorolaHardwareBridge()

    @property
    def transport_type(self) -> str:
        return "MOTOROLA_MOTOTRBO"

    @property
    def supported_operations(self) -> List[str]:
        return [
            "TMS_TEXT_MESSAGE",
            "LOCATION_REPORT",
            "TELEMETRY_IO",
            "DEVICE_DISCOVERY_ARS",
            "RAW_DATA_BURST",
        ]

    @property
    def readiness(self) -> TransportReadiness:
        if self._is_hardware_authorized:
            return TransportReadiness.READY
        return TransportReadiness.SIMULATION_ONLY

    @property
    def connection_state(self) -> TransportConnectionState:
        return self._connection_state

    def send(self, recipient_endpoint_id: str, payload_bytes: bytes, message_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches message across Motorola adapter.
        Constrained by DMR tier II payload limits (max 280 bytes per burst).
        """
        payload_len = len(payload_bytes)
        if payload_len > 280:
            err = f"Payload size {payload_len} bytes exceeds Motorola TMS DMR packet size limit of 280 bytes"
            self.record_error("PAYLOAD_TOO_LARGE", err)
            return {
                "success": False,
                "error_code": "PAYLOAD_TOO_LARGE",
                "details": err,
                "delivery_id": None,
            }

        # Hardware path: route through MNIS UDP or Raspberry Pi GPIO PTT.
        # When MOTOROLA_RADIO_APPROVED is unset the bridge runs dry-run only.
        if self._is_hardware_authorized:
            dispatch = self._bridge.transmit(recipient_endpoint_id, payload_bytes)
            self.last_operation_at = utcnow_iso()
            if dispatch.get("success"):
                self._connection_state = TransportConnectionState.ONLINE
            else:
                self.record_error(dispatch.get("error_code") or "MOTOROLA_TX_FAILED",
                                  dispatch.get("details", ""))
            return {
                "success": bool(dispatch.get("success")),
                "delivery_id": dispatch.get("delivery_id"),
                "error_code": dispatch.get("error_code"),
                "details": dispatch.get("details"),
                "radio_id": recipient_endpoint_id,
                "backend": dispatch.get("backend"),
                "bytes_on_wire": dispatch.get("bytes_on_wire"),
            }

        # Simulated dispatch
        self.last_operation_at = utcnow_iso()
        return {
            "success": True,
            "delivery_id": f"mot-tms-{os.urandom(4).hex()}",
            "error_code": None,
            "details": f"Dispatched via Motorola TMS adapter (Model: {self.radio_model}, simulated)",
            "radio_id": recipient_endpoint_id,
        }

    def bridge_probe(self) -> Dict[str, Any]:
        """Non-transmitting hardware reachability report (MNIS / GPIO)."""
        return self._bridge.probe()

    def health_check(self) -> Dict[str, Any]:
        self.last_health_check_at = utcnow_iso()
        return {
            "transport_id": self.transport_id,
            "radio_model": self.radio_model,
            "hardware_authorized": self._is_hardware_authorized,
            "readiness": self.readiness.value,
            "connection_state": self.connection_state.value,
            "supported_operations": self.supported_operations,
            "max_payload_bytes": 280,
            "last_operation_at": self.last_operation_at,
            "bridge": self._bridge.probe(),
        }
