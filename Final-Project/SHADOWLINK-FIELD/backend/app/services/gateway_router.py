from typing import Dict, List, Optional
from app.adapters.base import (
    ICommunicationAdapter,
    AdapterMetadata,
    OutgoingMessagePayload,
    TransmissionResult,
)
from app.adapters.simulation import simulation_adapter
from app.adapters.motorola import MotorolaRadioAdapter
from app.adapters.starv import StarVRadioAdapter
from app.adapters.sdr import SdrResearchAdapter


class GatewayRouter:
    """Manages adapter lifecycle, capability discovery, and outbound routing."""

    def __init__(self):
        self._adapters: Dict[str, ICommunicationAdapter] = {}
        # Register standard adapters
        self.register_adapter(simulation_adapter)
        self.register_adapter(MotorolaRadioAdapter())
        self.register_adapter(StarVRadioAdapter())
        self.register_adapter(SdrResearchAdapter())
        self.default_adapter_id = "sim-channel-01"

    def register_adapter(self, adapter: ICommunicationAdapter):
        meta = adapter.get_metadata()
        self._adapters[meta.adapter_id] = adapter

    def get_adapter(self, adapter_id: str) -> Optional[ICommunicationAdapter]:
        return self._adapters.get(adapter_id)

    def list_adapters(self) -> List[ICommunicationAdapter]:
        return list(self._adapters.values())

    async def route_transmit(
        self, message: OutgoingMessagePayload, adapter_id: Optional[str] = None
    ) -> TransmissionResult:
        target_id = adapter_id or self.default_adapter_id
        adapter = self.get_adapter(target_id)
        if not adapter:
            return TransmissionResult(
                success=False,
                transport_state="OFFLINE",
                delivered_to_receiver=False,
                ack_delivered_to_sender=False,
                error_code="ADAPTER_NOT_FOUND",
                diagnostics={"error": f"Adapter '{target_id}' is not registered"},
            )
        return await adapter.transmit(message)


# Global singleton router
gateway_router = GatewayRouter()
