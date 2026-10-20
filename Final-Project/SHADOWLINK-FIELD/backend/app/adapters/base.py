from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class AdapterCapability(str, Enum):
    DIGITAL_PACKET_DATA = "DIGITAL_PACKET_DATA"
    PTT_AUDIO_VOICE = "PTT_AUDIO_VOICE"
    HARDWARE_ACK = "HARDWARE_ACK"
    TELEMETRY = "TELEMETRY"
    STORE_AND_FORWARD = "STORE_AND_FORWARD"
    ENCRYPTION_PASS_THROUGH = "ENCRYPTION_PASS_THROUGH"
    CARRIER_SENSE = "CARRIER_SENSE"


class AdapterState(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    SIMULATION_ACTIVE = "SIMULATION_ACTIVE"
    DISABLED_PREREQUISITES_MISSING = "DISABLED_PREREQUISITES_MISSING"
    ARMED_RF = "ARMED_RF"


class AdapterMetadata(BaseModel):
    adapter_id: str
    name: str
    vendor: str
    version: str
    category: str  # SIMULATION, COMMERCIAL_RADIO, MIL_TACTICAL, SDR_RESEARCH
    is_hardware: bool


class AdapterHealthReport(BaseModel):
    adapter_id: str
    state: AdapterState
    ready_to_transmit: bool
    summary: str
    diagnostic_code: Optional[str] = None
    details: Dict[str, Any] = {}


class OutgoingMessagePayload(BaseModel):
    message_id: str
    sender_endpoint_id: str
    recipient_endpoint_id: str
    payload: str
    message_type: str = "TACTICAL_TEXT"
    priority: int = 2
    raw_bytes: Optional[bytes] = None


class TransmissionResult(BaseModel):
    success: bool
    transport_state: str  # ONLINE, OFFLINE
    delivered_to_receiver: bool
    ack_delivered_to_sender: bool
    error_code: Optional[str] = None
    diagnostics: Dict[str, Any] = {}


class HardwareSafetyLockoutError(Exception):
    """Raised when an operation on a locked out or unapproved radio adapter is attempted."""
    pass


class ICommunicationAdapter(ABC):
    """Common abstraction interface for all field communication adapters."""

    @abstractmethod
    def get_metadata(self) -> AdapterMetadata:
        """Returns identity, version, vendor, and transport category."""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[AdapterCapability]:
        """Discovers and returns list of supported capabilities."""
        pass

    @abstractmethod
    async def check_health(self) -> AdapterHealthReport:
        """Runs non-transmitting self-test and reports component readiness."""
        pass

    @abstractmethod
    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validates configuration parameters prior to arming or connection."""
        pass

    @abstractmethod
    async def transmit(self, message: OutgoingMessagePayload) -> TransmissionResult:
        """Attempts message transmission according to adapter capabilities."""
        pass

    @abstractmethod
    async def cancel(self, correlation_id: str) -> bool:
        """Safely terminates in-flight operation if supported."""
        pass
