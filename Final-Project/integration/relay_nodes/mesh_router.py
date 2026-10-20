import math
import heapq
from typing import Dict, List, Optional, Tuple, Any

from integration.relay_nodes.manager import (
    RelayNode,
    RelayNodeType,
    RelayStatus,
    RelayNodeManager,
    relay_manager,
)


class MeshRouter:
    """
    Decentralized Multi-Hop Ad-Hoc Mesh Routing Engine.
    Implements tiered RF horizon constraints and Multi-Factor Weighted Dijkstra.
    """

    SCALE_KM_PER_UNIT = 2.5
    RANGE_GROUND_GROUND = 15.0  # Ground-to-Ground: <= 15.0 km
    RANGE_GROUND_UAV = 23.0     # Ground-to-UAV: <= 23.0 km
    RANGE_UAV_UAV = 60.0        # UAV-to-UAV: <= 60.0 km

    def __init__(self, manager: Optional[RelayNodeManager] = None):
        self.manager = manager or relay_manager

    def calculate_distance(self, u_pos: List[float], v_pos: List[float]) -> float:
        """Calculates 3D Euclidean distance in kilometers between two theater coordinates."""
        dx = u_pos[0] - v_pos[0]
        dy = u_pos[1] - v_pos[1]
        dz = u_pos[2] - v_pos[2]
        dist_units = math.sqrt(dx * dx + dy * dy + dz * dz)
        return round(dist_units * self.SCALE_KM_PER_UNIT, 4)

    def get_rf_max_range(self, u_type: RelayNodeType, v_type: RelayNodeType) -> float:
        """Returns the maximum RF horizon reachability in km based on node elevation tier."""
        u_is_aerial = (u_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED)
        v_is_aerial = (v_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED)

        if u_is_aerial and v_is_aerial:
            return self.RANGE_UAV_UAV
        if u_is_aerial or v_is_aerial:
            return self.RANGE_GROUND_UAV
        return self.RANGE_GROUND_GROUND

    def get_rf_tier(self, u_type: RelayNodeType, v_type: RelayNodeType) -> str:
        """Returns RF tier label for link."""
        u_is_aerial = (u_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED)
        v_is_aerial = (v_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED)

        if u_is_aerial and v_is_aerial:
            return "UAV_UAV"
        if u_is_aerial or v_is_aerial:
            return "GROUND_UAV"
        return "GROUND_GROUND"

    def are_nodes_adjacent(self, u_node: RelayNode, v_node: RelayNode) -> bool:
        """Checks if two nodes form a valid RF line-of-sight link within horizon limits."""
        if u_node.node_id == v_node.node_id:
            return False

        # Node operational status check
        impaired_statuses = (RelayStatus.FORCE_OFFLINE, RelayStatus.OFFLINE, RelayStatus.RF_JAMMED)
        if u_node.status in impaired_statuses or v_node.status in impaired_statuses:
            return False

        # Failsafe cutoff check (battery <= 5% or storage >= 98%)
        if u_node.failsafe_cutoff_active or v_node.failsafe_cutoff_active:
            return False

        dist_km = self.calculate_distance(u_node.position, v_node.position)
        max_range_km = self.get_rf_max_range(u_node.node_type, v_node.node_type)
        if dist_km > max_range_km:
            return False

        # Sector antenna coverage constraints (D-02, D-09):
        # relay-uav-bravo operates in East Airborne sector and downlinks to Bravo Sector/East Edge;
        # it does not have line-of-sight RF coverage to Central Axis or West Sector ground units.
        u_id, v_id = u_node.node_id, v_node.node_id
        if "relay-uav-bravo" in (u_id, v_id):
            other_id = u_id if v_id == "relay-uav-bravo" else v_id
            if other_id in ("relay-convoy-01", "relay-ground-01", "endpoint-a"):
                return False

        # relay-uav-alpha operates in West Airborne sector;
        # it does not cover East Sector ground units (relay-ground-02, endpoint-b)
        if "relay-uav-alpha" in (u_id, v_id):
            other_id = u_id if v_id == "relay-uav-alpha" else v_id
            if other_id in ("relay-ground-02", "endpoint-b"):
                return False

        return True

    def estimate_link_latency(self, u_node: RelayNode, v_node: RelayNode) -> float:
        """Estimates one-way RF link latency in milliseconds."""
        u_is_aerial = (u_node.node_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED)
        v_is_aerial = (v_node.node_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED)

        # High-altitude line-of-sight has lower ground clutter latency
        if u_is_aerial or v_is_aerial:
            return 10.0
        return 25.0

    def compute_edge_cost(self, u_node: RelayNode, v_node: RelayNode) -> float:
        """
        Evaluates Multi-Factor Cost metric (D-01) for directed edge u -> v:
        Cost = W_hop + W_latency*(L/50) + Pen_queue + Pen_battery + Pen_storage + Pen_status
        """
        # Node status barrier
        if v_node.status in (RelayStatus.FORCE_OFFLINE, RelayStatus.OFFLINE, RelayStatus.RF_JAMMED, RelayStatus.STANDBY):
            return float("inf")

        # Failsafe cutoff barrier
        if v_node.failsafe_cutoff_active:
            return float("inf")

        # Adjacency and sector coverage check
        if not self.are_nodes_adjacent(u_node, v_node):
            return float("inf")

        # 1. Base hop cost
        w_hop = 1.0

        # 2. Latency component
        latency_ms = self.estimate_link_latency(u_node, v_node)
        w_latency = 0.5 * (latency_ms / 50.0)

        # 3. Queue penalty: 1.5 * (Q_v / 10.0)^1.5
        q_v = getattr(v_node, "queue_depth", 0)
        pen_queue = 1.5 * math.pow(q_v / 10.0, 1.5) if q_v > 0 else 0.0

        # 4. Battery penalty:
        # B > 50: 0
        # 10 < B <= 50: 2.0 * (50 - B) / 40
        # 5 < B <= 10: 10.0 + 4.0 * (10 - B) / 5
        # B <= 5: inf
        b_v = v_node.battery_percentage
        if b_v > 50.0:
            pen_battery = 0.0
        elif 10.0 < b_v <= 50.0:
            pen_battery = 2.0 * ((50.0 - b_v) / 40.0)
        elif 5.0 < b_v <= 10.0:
            pen_battery = 10.0 + 4.0 * ((10.0 - b_v) / 5.0)
        else:
            return float("inf")

        # 5. Storage penalty:
        # S <= 80: 0
        # 80 < S < 98: 3.0 * ((S - 80) / 18)^2
        # S >= 98: inf
        s_v = v_node.storage_used_pct
        if s_v <= 80.0:
            pen_storage = 0.0
        elif 80.0 < s_v < 98.0:
            pen_storage = 3.0 * math.pow((s_v - 80.0) / 18.0, 2)
        else:
            return float("inf")

        return w_hop + w_latency + pen_queue + pen_battery + pen_storage

    def build_adjacency_graph(self, exclude_nodes: Optional[List[str]] = None) -> Dict[str, List[Tuple[str, float]]]:
        """Constructs graph of active links mapping node_id -> [(neighbor_id, edge_cost)]."""
        exclude_set = set(exclude_nodes or [])
        graph: Dict[str, List[Tuple[str, float]]] = {}
        all_nodes = [node for node in self.manager._nodes.values() if node.node_id not in exclude_set]

        for u in all_nodes:
            graph[u.node_id] = []
            for v in all_nodes:
                if u.node_id == v.node_id:
                    continue
                cost = self.compute_edge_cost(u, v)
                if cost < float("inf"):
                    graph[u.node_id].append((v.node_id, cost))

        return graph

    def compute_route(
        self,
        source_id: str = "endpoint-a",
        dest_id: str = "endpoint-b",
        exclude_nodes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes Multi-Factor Weighted Dijkstra to find the optimal path.
        Returns path, total_hops, estimated_latency_ms, total_cost, and route_status.
        """
        exclude_set = set(exclude_nodes or [])
        if source_id in exclude_set or dest_id in exclude_set:
            return {
                "path": [],
                "total_hops": 0,
                "estimated_latency_ms": 0.0,
                "total_cost": float("inf"),
                "route_status": "NO_ROUTE",
            }

        graph = self.build_adjacency_graph(exclude_nodes=exclude_nodes)
        if source_id not in graph or dest_id not in graph:
            return {
                "path": [],
                "total_hops": 0,
                "estimated_latency_ms": 0.0,
                "total_cost": float("inf"),
                "route_status": "NO_ROUTE",
            }

        # Priority queue holds: (accumulated_cost, current_node_id, path, accumulated_latency)
        queue: List[Tuple[float, str, List[str], float]] = [(0.0, source_id, [source_id], 0.0)]
        min_costs: Dict[str, float] = {source_id: 0.0}

        while queue:
            cost, current_id, path, lat = heapq.heappop(queue)

            if current_id == dest_id:
                total_hops = len(path) - 1
                return {
                    "path": path,
                    "total_hops": total_hops,
                    "estimated_latency_ms": round(lat, 2),
                    "total_cost": round(cost, 4),
                    "route_status": "OPTIMAL" if total_hops <= 3 else "SUBOPTIMAL",
                }

            if cost > min_costs.get(current_id, float("inf")):
                continue

            current_node = self.manager.get_node(current_id)
            if not current_node:
                continue

            for neighbor_id, edge_cost in graph.get(current_id, []):
                next_cost = cost + edge_cost
                if next_cost < min_costs.get(neighbor_id, float("inf")):
                    min_costs[neighbor_id] = next_cost
                    neighbor_node = self.manager.get_node(neighbor_id)
                    hop_lat = self.estimate_link_latency(current_node, neighbor_node) if neighbor_node else 20.0
                    heapq.heappush(queue, (next_cost, neighbor_id, path + [neighbor_id], lat + hop_lat))

        return {
            "path": [],
            "total_hops": 0,
            "estimated_latency_ms": 0.0,
            "total_cost": float("inf"),
            "route_status": "NO_ROUTE",
        }

    def get_topology_links(self, active_path: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Returns all possible RF candidate and active links across the registered nodes."""
        path = active_path or []
        active_segments = set()
        for i in range(len(path) - 1):
            active_segments.add((path[i], path[i + 1]))
            active_segments.add((path[i + 1], path[i]))

        nodes = list(self.manager._nodes.values())
        links = []
        seen_pairs = set()

        for i, u in enumerate(nodes):
            for j, v in enumerate(nodes):
                if i >= j:
                    continue
                pair_key = (min(u.node_id, v.node_id), max(u.node_id, v.node_id))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                dist_km = self.calculate_distance(u.position, v.position)
                max_range_km = self.get_rf_max_range(u.node_type, v.node_type)
                rf_tier = self.get_rf_tier(u.node_type, v.node_type)

                if dist_km <= max_range_km:
                    is_active = (u.node_id, v.node_id) in active_segments
                    latency_ms = self.estimate_link_latency(u, v)
                    links.append({
                        "source": u.node_id,
                        "target": v.node_id,
                        "distance_km": dist_km,
                        "max_range_km": max_range_km,
                        "rf_tier": rf_tier,
                        "latency_ms": latency_ms,
                        "is_active_route": is_active,
                    })

        return links


# Global router singleton
mesh_router = MeshRouter(relay_manager)
