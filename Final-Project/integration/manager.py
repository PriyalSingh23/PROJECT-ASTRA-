from typing import Dict, List, Optional, Any
from integration.base import BaseTransportAdapter, TransportReadiness, TransportConnectionState


class TransportManager:
    """
    Intelligent transport manager for SHADOWLINK.
    
    Routes messages based on destination, message priority, transport readiness,
    and verified authorization. Preserves messages when no route is available.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseTransportAdapter] = {}
        self._routing_priority: List[str] = []
        self._adapter_priorities: Dict[str, int] = {}
        self._seed_default_adapters()

    def _seed_default_adapters(self):
        from integration.motorola.adapter import MotorolaMOTOTRBOAdapter
        from integration.starv.adapter import StarVAdapter
        from integration.lpi_cgan.adapter import LPICGANTransportAdapter
        self.register_adapter(MotorolaMOTOTRBOAdapter())
        self.register_adapter(StarVAdapter())
        self.register_adapter(LPICGANTransportAdapter())

    def register_adapter(self, adapter: BaseTransportAdapter, priority: int = 10):
        """Registers an adapter. Lower ``priority`` values are preferred when
        selecting a transport (10 is the default; 1 is highest preference)."""
        self._adapters[adapter.transport_id] = adapter
        self._adapter_priorities[adapter.transport_id] = priority
        if adapter.transport_id not in self._routing_priority:
            self._routing_priority.append(adapter.transport_id)
        # Stable-sort by ascending priority so preferred transports are tried first.
        self._routing_priority.sort(key=lambda tid: self._adapter_priorities.get(tid, 10))

    def get_adapter(self, transport_id: str) -> Optional[BaseTransportAdapter]:
        return self._adapters.get(transport_id)

    def list_adapters(self) -> List[Dict[str, Any]]:
        return [adapter.to_dict() for adapter in self._adapters.values()]

    def select_transport(self, recipient_endpoint_id: str, message_priority: int = 1, exclude_id: Optional[str] = None) -> Optional[BaseTransportAdapter]:
        """
        Selects an operational, ready, and online transport adapter.
        
        Returns None if no authorized transport is operational, ensuring the message
        is safely preserved in the durable queue rather than dropped.
        """
        for transport_id in self._routing_priority:
            if exclude_id and transport_id == exclude_id:
                continue
            adapter = self._adapters.get(transport_id)
            if not adapter:
                continue
                
            # Filter out locked-out or unconfigured adapters
            if adapter.readiness not in (TransportReadiness.READY, TransportReadiness.SIMULATION_ONLY):
                continue
                
            # Check connection state
            if adapter.connection_state not in (TransportConnectionState.ONLINE, TransportConnectionState.STANDBY):
                continue

            return adapter
            
        return None

    def route_and_dispatch(self, recipient_endpoint_id: str, payload_bytes: bytes, metadata: Dict[str, Any], exclude_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Selects an adapter and dispatches the payload.
        """
        adapter = self.select_transport(recipient_endpoint_id, message_priority=metadata.get("priority", 1), exclude_id=exclude_id)
        if not adapter:
            return {
                "success": False,
                "error_code": "NO_AUTHORIZED_ROUTE_AVAILABLE",
                "details": "No operational, authorized transport adapter is currently online. Message preserved in queue.",
                "adapter_used": None,
            }
            
        result = adapter.send(recipient_endpoint_id, payload_bytes, metadata)
        result["adapter_used"] = adapter.transport_id
        return result


# Global singleton manager instance
transport_manager = TransportManager()
