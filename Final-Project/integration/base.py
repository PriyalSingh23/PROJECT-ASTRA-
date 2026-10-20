from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


class TransportReadiness(str, Enum):
    READY = "READY"
    DISCONNECTED = "DISCONNECTED"
    SIMULATION_ONLY = "SIMULATION_ONLY"
    LOCKED_OUT = "LOCKED_OUT"
    UNCONFIGURED = "UNCONFIGURED"


class TransportConnectionState(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    INTERMITTENT = "INTERMITTENT"
    STANDBY = "STANDBY"


class BaseTransportAdapter(ABC):
    """
    Common transport adapter interface for SHADOWLINK.
    
    Every adapter must declare its real verified capabilities, hardware requirements,
    operating constraints, and explicit approval status before traffic can transit.
    """

    def __init__(self, transport_id: str, display_name: str):
        self.transport_id = transport_id
        self.display_name = display_name
        self.created_at = utcnow_iso()
        self.last_operation_at: Optional[str] = None
        self.last_health_check_at: Optional[str] = None
        self.error_history: List[Dict[str, Any]] = []

    @property
    @abstractmethod
    def transport_type(self) -> str:
        """Transport category (e.g. SIMULATED, LOCAL_IP, RELAY, MOTOROLA, STARV, SDR_RESEARCH)."""
        pass

    @property
    @abstractmethod
    def supported_operations(self) -> List[str]:
        """List of supported operations (e.g. ['SEND_TEXT', 'RECEIVE_TEXT', 'ACK', 'TELEMETRY'])."""
        pass

    @property
    @abstractmethod
    def readiness(self) -> TransportReadiness:
        """Readiness state of the adapter."""
        pass

    @property
    @abstractmethod
    def connection_state(self) -> TransportConnectionState:
        """Active physical or simulated link state."""
        pass

    @abstractmethod
    def send(self, recipient_endpoint_id: str, payload_bytes: bytes, message_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempts message delivery across this transport.
        
        Returns:
            dict containing:
                success: bool
                delivery_id: str or None
                error_code: str or None
                details: str or None
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Performs a diagnostic health check and returns metrics/status."""
        pass

    def record_error(self, error_code: str, details: str):
        self.error_history.append({
            "timestamp": utcnow_iso(),
            "error_code": error_code,
            "details": details,
        })
        if len(self.error_history) > 100:
            self.error_history.pop(0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transport_id": self.transport_id,
            "display_name": self.display_name,
            "transport_type": self.transport_type,
            "supported_operations": self.supported_operations,
            "readiness": self.readiness.value,
            "connection_state": self.connection_state.value,
            "last_operation_at": self.last_operation_at,
            "last_health_check_at": self.last_health_check_at,
            "error_count": len(self.error_history),
        }
