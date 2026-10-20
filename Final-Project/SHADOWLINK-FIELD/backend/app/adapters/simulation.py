import time
import random
import threading
from typing import List, Dict, Any, Optional, Set
from app.adapters.base import (
    ICommunicationAdapter,
    AdapterCapability,
    AdapterState,
    AdapterMetadata,
    AdapterHealthReport,
    OutgoingMessagePayload,
    TransmissionResult,
)


class SimulationAdapter(ICommunicationAdapter):
    """
    Simulated RF Channel transport adapter.
    Enables software-only validation of offline message store-and-forward,
    network interruption, latency, packet drop, and lost ACK scenarios.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.is_online: bool = True
        self.latency_ms: float = 0.0
        self.drop_message_prob: float = 0.0
        self.drop_ack_prob: float = 0.0

        # Deterministic testing sets
        self.dropped_messages: Set[str] = set()
        self.dropped_acks: Set[str] = set()
        self.injected_faults: Dict[str, str] = {}

    def get_metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter_id="sim-channel-01",
            name="Virtual Tactical RF Channel (Simulation)",
            vendor="SHADOWLINK FIELD",
            version="1.0.0",
            category="SIMULATION",
            is_hardware=False,
        )

    def get_capabilities(self) -> List[AdapterCapability]:
        return [
            AdapterCapability.DIGITAL_PACKET_DATA,
            AdapterCapability.HARDWARE_ACK,
            AdapterCapability.STORE_AND_FORWARD,
        ]

    async def check_health(self) -> AdapterHealthReport:
        with self._lock:
            state = AdapterState.SIMULATION_ACTIVE if self.is_online else AdapterState.OFFLINE
            return AdapterHealthReport(
                adapter_id="sim-channel-01",
                state=state,
                ready_to_transmit=self.is_online,
                summary=f"Simulated Channel is {'ONLINE' if self.is_online else 'OFFLINE (CUT)'}",
                diagnostic_code="SIM_NORMAL" if self.is_online else "SIM_LINK_SEVERED",
                details={
                    "latency_ms": self.latency_ms,
                    "drop_message_prob": self.drop_message_prob,
                    "drop_ack_prob": self.drop_ack_prob,
                },
            )

    async def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if "is_online" in config:
                self.is_online = bool(config["is_online"])
            if "latency_ms" in config:
                self.latency_ms = max(0.0, float(config["latency_ms"]))
            if "drop_message_prob" in config:
                self.drop_message_prob = max(0.0, min(1.0, float(config["drop_message_prob"])))
            if "drop_ack_prob" in config:
                self.drop_ack_prob = max(0.0, min(1.0, float(config["drop_ack_prob"])))
            if config.get("reset"):
                self.reset()
            return self.get_status()

    async def transmit(self, message: OutgoingMessagePayload) -> TransmissionResult:
        with self._lock:
            msg_id = message.message_id
            online = self.is_online
            latency = self.latency_ms
            drop_msg = self.drop_message_prob
            drop_ack = self.drop_ack_prob
            fault = self.injected_faults.pop(msg_id, None)
            deterministic_drop_msg = msg_id in self.dropped_messages
            if deterministic_drop_msg:
                self.dropped_messages.remove(msg_id)
            deterministic_drop_ack = msg_id in self.dropped_acks
            if deterministic_drop_ack:
                self.dropped_acks.remove(msg_id)

        # 1. Check Link State
        if not online:
            return TransmissionResult(
                success=False,
                transport_state="OFFLINE",
                delivered_to_receiver=False,
                ack_delivered_to_sender=False,
                error_code="TRANSPORT_OFFLINE",
                diagnostics={"note": "Simulated link is disabled/offline"},
            )

        # 2. Inject Deterministic Fault if requested
        if fault:
            return TransmissionResult(
                success=False,
                transport_state="ONLINE",
                delivered_to_receiver=False,
                ack_delivered_to_sender=False,
                error_code=fault,
                diagnostics={"injected_fault": fault},
            )

        # 3. Simulate Propagation Latency
        if latency > 0:
            time.sleep(latency / 1000.0)

        # 4. Forward Packet Drop Check
        if deterministic_drop_msg or (drop_msg > 0 and random.random() < drop_msg):
            return TransmissionResult(
                success=False,
                transport_state="ONLINE",
                delivered_to_receiver=False,
                ack_delivered_to_sender=False,
                error_code="PACKET_DROPPED",
                diagnostics={"note": "Forward payload packet dropped in transit"},
            )

        # 5. Return ACK Drop Check
        if deterministic_drop_ack or (drop_ack > 0 and random.random() < drop_ack):
            return TransmissionResult(
                success=False,
                transport_state="ONLINE",
                delivered_to_receiver=True,
                ack_delivered_to_sender=False,
                error_code="ACK_LOST",
                diagnostics={"note": "Receiver stored payload, but return ACK was lost in transit"},
            )

        # 6. Full Success
        return TransmissionResult(
            success=True,
            transport_state="ONLINE",
            delivered_to_receiver=True,
            ack_delivered_to_sender=True,
            error_code=None,
            diagnostics={"latency_ms": latency},
        )

    async def cancel(self, correlation_id: str) -> bool:
        return True

    def reset(self):
        with self._lock:
            self.is_online = True
            self.latency_ms = 0.0
            self.drop_message_prob = 0.0
            self.drop_ack_prob = 0.0
            self.dropped_messages.clear()
            self.dropped_acks.clear()
            self.injected_faults.clear()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "adapter_id": "sim-channel-01",
                "is_online": self.is_online,
                "latency_ms": self.latency_ms,
                "drop_message_prob": self.drop_message_prob,
                "drop_ack_prob": self.drop_ack_prob,
                "mode": "SIMULATION",
            }


# Global singleton instance for simulation runtime
simulation_adapter = SimulationAdapter()
