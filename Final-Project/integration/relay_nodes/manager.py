from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


class RelayNodeType(str, Enum):
    FIXED_GATEWAY = "FIXED_GATEWAY"
    PORTABLE_GROUND = "PORTABLE_GROUND"
    VEHICLE_GATEWAY = "VEHICLE_GATEWAY"
    AERIAL_PAYLOAD_SIMULATED = "AERIAL_PAYLOAD_SIMULATED"


class RelayStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    STANDBY = "STANDBY"
    MAINTENANCE = "MAINTENANCE"
    FORCE_OFFLINE = "FORCE_OFFLINE"
    RF_JAMMED = "RF_JAMMED"


class RelayNode:
    """
    Representation of a physical or simulated communications relay node.
    """

    def __init__(
        self,
        node_id: str,
        display_name: str,
        node_type: RelayNodeType,
        owner: str = "SHADOWLINK Ops",
        battery_percentage: float = 100.0,
        temperature_celsius: float = 25.0,
        storage_used_pct: float = 12.0,
        position: Optional[List[float]] = None,
        sector: str = "Central Sector",
    ):
        self.node_id = node_id
        self.display_name = display_name
        self.node_type = node_type
        self.owner = owner
        self.status = RelayStatus.ONLINE
        self.battery_percentage = battery_percentage
        self.temperature_celsius = temperature_celsius
        self.storage_used_pct = storage_used_pct
        self.position = list(position) if position is not None else [0.0, 0.0, 0.0]
        self.sector = sector
        self.rf_tier_ranges: Dict[str, float] = {
            "GROUND_GROUND": 15.0,
            "GROUND_UAV": 23.0,
            "UAV_UAV": 60.0,
        }
        self.custody_buffer: Dict[str, Any] = {}
        self.connected_endpoints: List[str] = []
        self.last_health_check_at = utcnow_iso()
        self.last_forwarding_at: Optional[str] = None
        self.forwarded_message_count = 0
        self.queue_depth: int = 0
        self.flight_failsafe_independent = True  # Always strictly independent!
        self.is_approved = True if node_type != RelayNodeType.AERIAL_PAYLOAD_SIMULATED else False

    @property
    def failsafe_cutoff_active(self) -> bool:
        """Returns True if battery is critically depleted (<= 5%) or storage is exhausted (>= 98%)."""
        return self.battery_percentage <= 5.0 or self.storage_used_pct >= 98.0

    def update_telemetry(
        self,
        battery: Optional[float] = None,
        temperature: Optional[float] = None,
        storage_pct: Optional[float] = None,
        status: Optional[RelayStatus] = None,
        queue_depth: Optional[int] = None,
        position: Optional[List[float]] = None,
        sector: Optional[str] = None,
    ):
        if battery is not None:
            self.battery_percentage = max(0.0, min(100.0, battery))
        if temperature is not None:
            self.temperature_celsius = temperature
        if storage_pct is not None:
            self.storage_used_pct = max(0.0, min(100.0, storage_pct))
        if status is not None:
            self.status = status
        if queue_depth is not None:
            self.queue_depth = max(0, queue_depth)
        if position is not None:
            self.position = list(position)
        if sector is not None:
            self.sector = sector
        self.last_health_check_at = utcnow_iso()

    def can_forward_to(self, recipient_endpoint_id: str) -> bool:
        if self.status != RelayStatus.ONLINE:
            return False
        if self.battery_percentage <= 5.0:
            return False
        if self.storage_used_pct >= 98.0:
            return False
        # If specific endpoints are mapped, ensure recipient is in range
        if self.connected_endpoints and recipient_endpoint_id not in self.connected_endpoints:
            return False
        return True

    def forward_message(self, message_id: str, recipient_endpoint_id: str) -> bool:
        if not self.can_forward_to(recipient_endpoint_id):
            return False
        self.forwarded_message_count += 1
        self.last_forwarding_at = utcnow_iso()
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.node_id,
            "node_id": self.node_id,
            "display_name": self.display_name,
            "node_type": self.node_type.value,
            "owner": self.owner,
            "status": self.status.value,
            "battery_percentage": round(self.battery_percentage, 1),
            "battery_level_pct": round(self.battery_percentage, 1),      # Frontend compatibility
            "temperature_celsius": round(self.temperature_celsius, 1),
            "storage_used_pct": round(self.storage_used_pct, 1),
            "storage_usage_pct": round(self.storage_used_pct, 1),        # Frontend compatibility
            "position": self.position,
            "sector": self.sector,
            "rf_tier_ranges": self.rf_tier_ranges,
            "connected_endpoints": self.connected_endpoints,
            "last_health_check_at": self.last_health_check_at,
            "last_forwarding_at": self.last_forwarding_at,
            "forwarded_message_count": self.forwarded_message_count,
            "queue_depth": getattr(self, "queue_depth", 0),
            "queued_bundles_count": getattr(self, "queue_depth", 0),    # Frontend compatibility
            "flight_failsafe_independent": self.flight_failsafe_independent,
            "is_independent_payload": self.flight_failsafe_independent, # Frontend compatibility
            "is_approved": self.is_approved,
            "failsafe_cutoff_active": self.failsafe_cutoff_active,
            "custody_count": len(self.custody_buffer),
        }


class RelayNodeManager:
    """Manages ground, aerial, and mobile relay nodes across the operations area."""

    def __init__(self):
        self._nodes: Dict[str, RelayNode] = {}
        self._seed_default_relays()

    def _seed_default_relays(self):
        # 1. Portable Ground Relay Alpha
        ground_node_01 = RelayNode(
            node_id="relay-ground-01",
            display_name="Portable Ground Relay Alpha",
            node_type=RelayNodeType.PORTABLE_GROUND,
            battery_percentage=94.5,
            temperature_celsius=31.2,
            storage_used_pct=15.4,
            position=[-5.0, 0.0, -1.5],
            sector="Alpha Sector",
        )
        ground_node_01.connected_endpoints = ["endpoint-a", "endpoint-b"]
        ground_node_01.is_approved = True
        self.register_node(ground_node_01)

        # 2. Tactical Mobile Convoy 01 (Z=1.0 guarantees <= 15.0km ground reachability to ground-01 and ground-02)
        convoy_node = RelayNode(
            node_id="relay-convoy-01",
            display_name="Tactical Mobile Convoy 01",
            node_type=RelayNodeType.VEHICLE_GATEWAY,
            battery_percentage=90.0,
            temperature_celsius=27.5,
            storage_used_pct=22.0,
            position=[0.0, 0.0, 1.0],
            sector="Central Axis",
        )
        convoy_node.connected_endpoints = ["endpoint-a", "endpoint-b"]
        convoy_node.is_approved = True
        self.register_node(convoy_node)

        # 3. Portable Ground Relay Bravo
        ground_node_02 = RelayNode(
            node_id="relay-ground-02",
            display_name="Portable Ground Relay Bravo",
            node_type=RelayNodeType.PORTABLE_GROUND,
            battery_percentage=88.0,
            temperature_celsius=29.8,
            storage_used_pct=18.2,
            position=[5.0, 0.0, -1.5],
            sector="Bravo Sector",
        )
        ground_node_02.connected_endpoints = ["endpoint-a", "endpoint-b"]
        ground_node_02.is_approved = True
        self.register_node(ground_node_02)

        # 4. Loitering Tactical Drone Alpha
        uav_alpha = RelayNode(
            node_id="relay-uav-alpha",
            display_name="Loitering Tactical Drone Alpha",
            node_type=RelayNodeType.AERIAL_PAYLOAD_SIMULATED,
            battery_percentage=98.0,
            temperature_celsius=18.5,
            storage_used_pct=5.0,
            position=[-3.0, 4.5, 0.5],
            sector="West Airborne",
        )
        uav_alpha.connected_endpoints = ["endpoint-a", "endpoint-b"]
        uav_alpha.is_approved = True  # Operational for tactical mesh routing
        self.register_node(uav_alpha)

        # 5. High-Altitude UAV Relay Bravo
        uav_bravo = RelayNode(
            node_id="relay-uav-bravo",
            display_name="High-Altitude UAV Relay Bravo",
            node_type=RelayNodeType.AERIAL_PAYLOAD_SIMULATED,
            battery_percentage=92.0,
            temperature_celsius=15.2,
            storage_used_pct=7.5,
            position=[3.0, 6.0, -0.5],
            sector="East Airborne",
        )
        uav_bravo.connected_endpoints = ["endpoint-a", "endpoint-b"]
        uav_bravo.is_approved = True  # Operational for tactical mesh routing
        self.register_node(uav_bravo)

        # 6. Simulated Aerial Relay (Legacy Compatibility / Standby)
        aerial_legacy = RelayNode(
            node_id="relay-aerial-sim-01",
            display_name="Simulated Tethered/Drone Relay (Dev Only)",
            node_type=RelayNodeType.AERIAL_PAYLOAD_SIMULATED,
            battery_percentage=100.0,
            temperature_celsius=24.0,
            storage_used_pct=8.0,
            position=[0.0, 5.0, 0.0],
            sector="Center Airborne",
        )
        aerial_legacy.connected_endpoints = ["endpoint-a", "endpoint-b"]
        aerial_legacy.status = RelayStatus.STANDBY
        aerial_legacy.is_approved = False  # Legacy test assertion expects is_approved == False
        self.register_node(aerial_legacy)

        # 7. Station Alpha Edge Gateway (endpoint-a)
        station_a = RelayNode(
            node_id="endpoint-a",
            display_name="Station Alpha Gateway",
            node_type=RelayNodeType.FIXED_GATEWAY,
            battery_percentage=100.0,
            temperature_celsius=22.0,
            storage_used_pct=10.0,
            position=[-9.0, 0.0, 0.0],
            sector="West Edge",
        )
        station_a.connected_endpoints = ["endpoint-b"]
        station_a.is_approved = True
        self.register_node(station_a)

        # 8. Station Bravo Edge Gateway (endpoint-b)
        station_b = RelayNode(
            node_id="endpoint-b",
            display_name="Station Bravo Gateway",
            node_type=RelayNodeType.FIXED_GATEWAY,
            battery_percentage=100.0,
            temperature_celsius=22.0,
            storage_used_pct=10.0,
            position=[9.0, 0.0, 0.0],
            sector="East Edge",
        )
        station_b.connected_endpoints = ["endpoint-a"]
        station_b.is_approved = True
        self.register_node(station_b)

    def register_node(self, node: RelayNode):
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[RelayNode]:
        return self._nodes.get(node_id)

    def list_nodes(self) -> List[Dict[str, Any]]:
        return [node.to_dict() for node in self._nodes.values()]

    def reset_node(self, node_id: str) -> Optional[RelayNode]:
        """Resets a relay node to nominal default telemetry values."""
        node = self._nodes.get(node_id)
        if not node:
            return None
        if node_id == "relay-ground-01":
            node.battery_percentage = 94.5
            node.temperature_celsius = 31.2
            node.storage_used_pct = 15.4
            node.status = RelayStatus.ONLINE
            node.queue_depth = 0
            node.position = [-5.0, 0.0, -1.5]
            node.sector = "Alpha Sector"
        elif node_id == "relay-convoy-01":
            node.battery_percentage = 90.0
            node.temperature_celsius = 27.5
            node.storage_used_pct = 22.0
            node.status = RelayStatus.ONLINE
            node.queue_depth = 0
            node.position = [0.0, 0.0, 1.0]
            node.sector = "Central Axis"
        elif node_id == "relay-ground-02":
            node.battery_percentage = 88.0
            node.temperature_celsius = 29.8
            node.storage_used_pct = 18.2
            node.status = RelayStatus.ONLINE
            node.queue_depth = 0
            node.position = [5.0, 0.0, -1.5]
            node.sector = "Bravo Sector"
        elif node_id == "relay-uav-alpha":
            node.battery_percentage = 98.0
            node.temperature_celsius = 18.5
            node.storage_used_pct = 5.0
            node.status = RelayStatus.ONLINE
            node.queue_depth = 0
            node.position = [-3.0, 4.5, 0.5]
            node.sector = "West Airborne"
        elif node_id == "relay-uav-bravo":
            node.battery_percentage = 92.0
            node.temperature_celsius = 15.2
            node.storage_used_pct = 7.5
            node.status = RelayStatus.ONLINE
            node.queue_depth = 0
            node.position = [3.0, 6.0, -0.5]
            node.sector = "East Airborne"
        elif node_id == "relay-aerial-sim-01":
            node.battery_percentage = 100.0
            node.temperature_celsius = 24.0
            node.storage_used_pct = 8.0
            node.status = RelayStatus.STANDBY
            node.queue_depth = 0
            node.position = [0.0, 5.0, 0.0]
            node.sector = "Center Airborne"
        elif node_id == "endpoint-a":
            node.battery_percentage = 100.0
            node.temperature_celsius = 22.0
            node.storage_used_pct = 10.0
            node.status = RelayStatus.ONLINE
            node.queue_depth = 0
            node.position = [-9.0, 0.0, 0.0]
            node.sector = "West Edge"
        elif node_id == "endpoint-b":
            node.battery_percentage = 100.0
            node.temperature_celsius = 22.0
            node.storage_used_pct = 10.0
            node.status = RelayStatus.ONLINE
            node.queue_depth = 0
            node.position = [9.0, 0.0, 0.0]
            node.sector = "East Edge"
        else:
            node.battery_percentage = 100.0
            node.temperature_celsius = 25.0
            node.storage_used_pct = 10.0
            node.status = RelayStatus.ONLINE
            node.queue_depth = 0
        node.custody_buffer.clear()
        node.last_health_check_at = utcnow_iso()
        return node

    def reset_all_nodes(self):
        """Resets all registered nodes to nominal initial states."""
        for node_id in list(self._nodes.keys()):
            self.reset_node(node_id)

    def route_via_relay(self, message_id: str, recipient_endpoint_id: str) -> Optional[str]:
        """
        Attempts to find an operational relay that can reach recipient.
        Returns relay_node_id if successfully forwarded, else None.
        """
        for node in self._nodes.values():
            if node.forward_message(message_id, recipient_endpoint_id):
                return node.node_id
        return None


# Global singleton relay manager instance
relay_manager = RelayNodeManager()
