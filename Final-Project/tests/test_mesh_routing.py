import torch  # Critical: Must precede numpy/scipy imports for Apple Silicon OpenBLAS safety
import os
import sys
import time
import uuid
import struct
import pytest

from integration.relay_nodes.manager import (
    RelayNode,
    RelayNodeType,
    RelayStatus,
    RelayNodeManager,
    relay_manager,
)
from integration.relay_nodes.mesh_router import MeshRouter
from messaging.mesh_bundle import (
    MESH_MAGIC,
    MESH_HEADER_FORMAT,
    MESH_HEADER_LEN,
    FLAG_ROUTINE,
    FLAG_FLASH,
    FLAG_IMMEDIATE,
    FLAG_CUSTODY_REQ,
    NODE_BIT_INDICES,
    MeshBundleHeader,
    wrap_mesh_bundle,
    process_hop_bundle,
    generate_custody_ack_token,
    verify_custody_ack_token,
)
from messaging.dispatch import DispatchRouter, dispatch_router
from messaging.models import MessageEvent, SecurityAuditLog


class TestMeshTopologyAndAdjacency:
    """Verifies node registration, 3D coordinates, and RF horizon tiers (MSH-01)."""

    def test_named_nodes_registration(self):
        manager = RelayNodeManager()
        # Verify > 5 named nodes are present
        required_nodes = [
            "relay-ground-01",
            "relay-ground-02",
            "relay-uav-alpha",
            "relay-uav-bravo",
            "relay-convoy-01",
            "relay-aerial-sim-01",
            "endpoint-a",
            "endpoint-b",
        ]
        for node_id in required_nodes:
            node = manager.get_node(node_id)
            assert node is not None, f"Node {node_id} must be registered"
            assert hasattr(node, "position")
            assert len(node.position) == 3
            assert hasattr(node, "sector")
            d = node.to_dict()
            assert "position" in d
            assert "sector" in d
            assert "queue_depth" in d
            assert "failsafe_cutoff_active" in d

        # Specific node positions and properties
        g1 = manager.get_node("relay-ground-01")
        assert g1.node_type == RelayNodeType.PORTABLE_GROUND
        assert g1.position == [-5.0, 0.0, -1.5]

        convoy = manager.get_node("relay-convoy-01")
        assert convoy.node_type == RelayNodeType.VEHICLE_GATEWAY
        assert convoy.position == [0.0, 0.0, 1.0]

        uav_a = manager.get_node("relay-uav-alpha")
        assert uav_a.node_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED
        assert uav_a.position == [-3.0, 4.5, 0.5]

        uav_b = manager.get_node("relay-uav-bravo")
        assert uav_b.node_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED
        assert uav_b.position == [3.0, 6.0, -0.5]

    def test_tiered_rf_range_horizons(self):
        manager = RelayNodeManager()
        router = MeshRouter(manager)

        # Ground-to-Ground: <= 15.0 km
        assert router.get_rf_max_range(RelayNodeType.PORTABLE_GROUND, RelayNodeType.PORTABLE_GROUND) == 15.0
        assert router.get_rf_max_range(RelayNodeType.PORTABLE_GROUND, RelayNodeType.VEHICLE_GATEWAY) == 15.0
        assert router.get_rf_max_range(RelayNodeType.FIXED_GATEWAY, RelayNodeType.PORTABLE_GROUND) == 15.0

        # Ground-to-UAV: <= 23.0 km
        assert router.get_rf_max_range(RelayNodeType.PORTABLE_GROUND, RelayNodeType.AERIAL_PAYLOAD_SIMULATED) == 23.0
        assert router.get_rf_max_range(RelayNodeType.FIXED_GATEWAY, RelayNodeType.AERIAL_PAYLOAD_SIMULATED) == 23.0

        # UAV-to-UAV: <= 60.0 km
        assert router.get_rf_max_range(RelayNodeType.AERIAL_PAYLOAD_SIMULATED, RelayNodeType.AERIAL_PAYLOAD_SIMULATED) == 60.0

        # Adjacency checks:
        # endpoint-a [-9, 0, 0] to relay-ground-01 [-5, 0, -1.5]: dist ~ 10.68 km <= 15.0 km -> True
        ep_a = manager.get_node("endpoint-a")
        g1 = manager.get_node("relay-ground-01")
        assert router.are_nodes_adjacent(ep_a, g1) is True

        # relay-ground-01 [-5, 0, -1.5] to relay-convoy-01 [0, 0, 1.0]: dist ~ 13.98 km <= 15.0 km -> True
        convoy = manager.get_node("relay-convoy-01")
        assert router.are_nodes_adjacent(g1, convoy) is True

        # relay-ground-01 [-5, 0, -1.5] to relay-ground-02 [+5, 0, -1.5]: dist = 25.0 km > 15.0 km -> False
        g2 = manager.get_node("relay-ground-02")
        assert router.are_nodes_adjacent(g1, g2) is False

        # relay-uav-alpha [-3, 4.5, 0.5] to relay-uav-bravo [+3, 6.0, -0.5]: dist ~ 15.66 km <= 60.0 km -> True
        uav_a = manager.get_node("relay-uav-alpha")
        uav_b = manager.get_node("relay-uav-bravo")
        assert router.are_nodes_adjacent(uav_a, uav_b) is True

    def test_direct_station_separation_requires_multihop(self):
        manager = RelayNodeManager()
        router = MeshRouter(manager)

        ep_a = manager.get_node("endpoint-a")
        ep_b = manager.get_node("endpoint-b")

        dist = router.calculate_distance(ep_a.position, ep_b.position)
        # [-9, 0, 0] to [+9, 0, 0] is 18 units * 2.5 km/unit = 45.0 km
        assert dist == 45.0
        # Direct link is impossible because 45.0 km > 15.0 km
        assert router.are_nodes_adjacent(ep_a, ep_b) is False


class TestMultiFactorDijkstra:
    """Verifies the Multi-Factor Weighted Dijkstra routing algorithm (MSH-01)."""

    def test_nominal_optimal_aerial_path(self):
        manager = RelayNodeManager()
        router = MeshRouter(manager)

        result = router.compute_route("endpoint-a", "endpoint-b")
        assert result["route_status"] == "OPTIMAL"
        # In nominal conditions, 3-hop aerial corridor is chosen:
        # endpoint-a -> relay-uav-alpha -> relay-uav-bravo -> endpoint-b
        assert result["path"] == ["endpoint-a", "relay-uav-alpha", "relay-uav-bravo", "endpoint-b"]
        assert result["total_hops"] == 3
        assert result["estimated_latency_ms"] < 60.0
        assert result["total_cost"] < 5.0

    def test_battery_depletion_reroutes_traffic(self):
        manager = RelayNodeManager()
        router = MeshRouter(manager)

        # Deplete relay-uav-alpha to 8% (triggers steep penalty: 10 + 4*(10-8)/5 = 11.6)
        uav_a = manager.get_node("relay-uav-alpha")
        uav_a.update_telemetry(battery=8.0)

        result = router.compute_route("endpoint-a", "endpoint-b")
        # Should divert to ground convoy path:
        # endpoint-a -> relay-ground-01 -> relay-convoy-01 -> relay-ground-02 -> endpoint-b
        assert result["path"] == [
            "endpoint-a",
            "relay-ground-01",
            "relay-convoy-01",
            "relay-ground-02",
            "endpoint-b",
        ]
        assert result["total_hops"] == 4
        assert "relay-uav-alpha" not in result["path"]

    def test_queue_congestion_penalty(self):
        manager = RelayNodeManager()
        router = MeshRouter(manager)

        # Congest relay-uav-alpha with Q=35
        uav_a = manager.get_node("relay-uav-alpha")
        uav_a.update_telemetry(queue_depth=35)

        result = router.compute_route("endpoint-a", "endpoint-b")
        # Queue penalty forces reroute to ground path
        assert result["path"] == [
            "endpoint-a",
            "relay-ground-01",
            "relay-convoy-01",
            "relay-ground-02",
            "endpoint-b",
        ]

    def test_failsafe_cutoff_infinite_cost(self):
        manager = RelayNodeManager()
        router = MeshRouter(manager)

        # Battery <= 5% activates failsafe cutoff
        uav_a = manager.get_node("relay-uav-alpha")
        uav_a.update_telemetry(battery=4.9)
        assert uav_a.failsafe_cutoff_active is True

        cost = router.compute_edge_cost(manager.get_node("endpoint-a"), uav_a)
        assert cost == float("inf")

        # Storage >= 98% activates failsafe cutoff
        g1 = manager.get_node("relay-ground-01")
        g1.update_telemetry(storage_pct=98.5)
        assert g1.failsafe_cutoff_active is True

        cost_g1 = router.compute_edge_cost(manager.get_node("endpoint-a"), g1)
        assert cost_g1 == float("inf")


class TestBinaryMeshFraming:
    """Verifies the 25-byte binary mesh header serialization and deserialization (MSH-02)."""

    def test_mesh_header_pack_unpack(self):
        bundle_id = uuid.uuid4()
        header = MeshBundleHeader(
            magic=MESH_MAGIC,
            flags=FLAG_FLASH | FLAG_CUSTODY_REQ,
            initial_ttl=8,
            remaining_ttl=8,
            hop_count=0,
            visited_bitmask=0x0001,  # endpoint-a visited
            bundle_uuid=bundle_id.bytes,
        )

        packed = header.pack()
        assert len(packed) == MESH_HEADER_LEN
        assert len(packed) == 25
        assert packed[:3] == b"MSH"

        unpacked, payload = MeshBundleHeader.unpack(packed + b"SECRET_CIPHERTEXT")
        assert unpacked.magic == b"MSH"
        assert unpacked.flags == FLAG_FLASH | FLAG_CUSTODY_REQ
        assert unpacked.initial_ttl == 8
        assert unpacked.remaining_ttl == 8
        assert unpacked.hop_count == 0
        assert unpacked.visited_bitmask == 0x0001
        assert unpacked.bundle_uuid == bundle_id.bytes
        assert payload == b"SECRET_CIPHERTEXT"

    def test_inner_envelope_payload_untouched(self):
        inner_payload = b"\x03\x01\x02ENVELOPE_V3_OPAQUE_PQC_PAYLOAD_WITH_GCM_TAG"
        bundle_bytes = wrap_mesh_bundle(
            inner_payload,
            initial_ttl=6,
            priority_flag=FLAG_IMMEDIATE,
            source_node_id="endpoint-a",
        )

        # Hop 1: relay-uav-alpha
        hop1_bytes, h1, err = process_hop_bundle(bundle_bytes, "relay-uav-alpha")
        assert err is None
        assert h1.remaining_ttl == 5
        assert h1.hop_count == 1
        assert h1.has_visited("relay-uav-alpha") is True

        # Unpack and verify inner payload is byte-for-byte identical
        _, extracted_payload = MeshBundleHeader.unpack(hop1_bytes)
        assert extracted_payload == inner_payload

    def test_priority_flags(self):
        for flag in [FLAG_ROUTINE, FLAG_IMMEDIATE, FLAG_FLASH]:
            packed = wrap_mesh_bundle(b"DATA", priority_flag=flag)
            h, _ = MeshBundleHeader.unpack(packed)
            assert (h.flags & 0x03) == flag


class TestTTLAndLoopPrevention:
    """Verifies hop TTL decrements and visited bitmask loop detection (MSH-02)."""

    def test_hop_ttl_decrement_and_drop(self):
        bundle_bytes = wrap_mesh_bundle(b"PAYLOAD", initial_ttl=2, source_node_id="endpoint-a")

        # Hop 1: remaining TTL becomes 1
        hop1, h1, err1 = process_hop_bundle(bundle_bytes, "relay-uav-alpha")
        assert err1 is None
        assert h1.remaining_ttl == 1

        # Hop 2: remaining TTL becomes 0 -> dropped!
        hop2, h2, err2 = process_hop_bundle(hop1, "relay-uav-bravo")
        assert err2 == "BUNDLE_TTL_EXPIRED"
        assert hop2 == b""

    def test_visited_bitmask_loop_detection(self):
        bundle_bytes = wrap_mesh_bundle(b"PAYLOAD", initial_ttl=8, source_node_id="endpoint-a")

        # Hop 1: relay-uav-alpha
        hop1, h1, err1 = process_hop_bundle(bundle_bytes, "relay-uav-alpha")
        assert err1 is None

        # Attempt to cycle back to relay-uav-alpha
        hop_loop, h_loop, err_loop = process_hop_bundle(hop1, "relay-uav-alpha")
        assert err_loop == "ROUTING_LOOP_DETECTED"
        assert hop_loop == b""

        # Attempt to cycle back to originator endpoint-a
        hop_loop2, h_loop2, err_loop2 = process_hop_bundle(hop1, "endpoint-a")
        assert err_loop2 == "ROUTING_LOOP_DETECTED"
        assert hop_loop2 == b""


class TestCustodyAndDynamicRecovery:
    """Verifies store-and-forward custody handshakes, local recovery, and REST API (MSH-02, MSH-04)."""

    def test_custody_token_verification(self):
        bundle_uuid = uuid.uuid4().bytes
        token = generate_custody_ack_token("relay-uav-alpha", bundle_uuid, hop_count=1)
        assert len(token) == 16
        assert isinstance(token, bytes)

        assert verify_custody_ack_token(token, "relay-uav-alpha", bundle_uuid, hop_count=1) is True
        assert verify_custody_ack_token(token, "relay-uav-bravo", bundle_uuid, hop_count=1) is False
        assert verify_custody_ack_token(token, "relay-uav-alpha", bundle_uuid, hop_count=2) is False

    def test_local_alternate_forwarding_on_timeout(self):
        manager = RelayNodeManager()
        router = MeshRouter(manager)
        dispatch = DispatchRouter()

        bundle_bytes = wrap_mesh_bundle(b"ENVELOPE_V3_BYTES", source_node_id="endpoint-a")

        # Simulate timeout when attempting to forward from endpoint-a to relay-uav-alpha
        result = dispatch.forward_hop(
            bundle_bytes=bundle_bytes,
            current_node="endpoint-a",
            next_hop="relay-uav-alpha",
            destination="endpoint-b",
            timeout_sec=1.5,
            simulate_ack=False,  # Unacknowledged hop triggers local reroute
        )

        assert result["success"] is True
        assert result["rerouted"] is True
        assert result["bypassed"] == "relay-uav-alpha"
        assert result["diverted_via"] == "relay-ground-01"
        assert "relay-uav-alpha" not in result["new_path"]

    def test_priority_queue_shedding(self):
        dispatch = DispatchRouter()
        bundles = [
            {"id": "b1", "priority": FLAG_ROUTINE, "payload": "routine_1"},
            {"id": "b2", "priority": FLAG_IMMEDIATE, "payload": "immediate_1"},
            {"id": "b3", "priority": FLAG_FLASH, "payload": "flash_1"},
            {"id": "b4", "priority": FLAG_ROUTINE, "payload": "routine_2"},
        ]

        # Under 90%, no bundles shed
        kept = dispatch.shed_priority_queue(bundles, storage_used_pct=85.0)
        assert len(kept) == 4

        # At 92%, routine bundles shed first
        kept_shed = dispatch.shed_priority_queue(bundles, storage_used_pct=92.0)
        assert len(kept_shed) == 2
        priorities = [b["priority"] for b in kept_shed]
        assert FLAG_ROUTINE not in priorities
        assert FLAG_IMMEDIATE in priorities
        assert FLAG_FLASH in priorities

    def test_scenarios_rest_api(self):
        from messaging.api import api_v1
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(api_v1)
        client = app.test_client()

        # 1. Check GET /api/v1/topology/mesh
        resp = client.get("/api/v1/topology/mesh")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nodes" in data
        assert "links" in data
        assert "active_route" in data
        assert len(data["nodes"]) >= 6

        # 2. POST Scenario 1: UAV-Alpha Signal Lost
        resp_s1 = client.post("/api/v1/relays/scenario", json={"scenario": "scenario_1_uav_signal_lost"})
        assert resp_s1.status_code == 200
        s1_data = resp_s1.get_json()
        assert s1_data["status"] == "CONVERGED"
        assert s1_data["convergence_latency_ms"] < 300.0
        assert "relay-uav-alpha" not in s1_data["new_path"]
        assert "relay-convoy-01" in s1_data["new_path"]

        # 3. POST Scenario 2: Ground Relays Jammed
        resp_s2 = client.post("/api/v1/relays/scenario", json={"scenario": "scenario_2_ground_relays_jammed"})
        assert resp_s2.status_code == 200
        s2_data = resp_s2.get_json()
        assert s2_data["status"] == "CONVERGED"
        assert s2_data["convergence_latency_ms"] < 300.0
        assert "relay-uav-bravo" in s2_data["new_path"]

        # 4. POST Reset Nominal
        resp_reset = client.post("/api/v1/relays/scenario", json={"scenario": "reset_nominal"})
        assert resp_reset.status_code == 200
        reset_data = resp_reset.get_json()
        assert reset_data["new_path"] == ["endpoint-a", "relay-uav-alpha", "relay-uav-bravo", "endpoint-b"]

        # 5. POST Route Simulation
        resp_sim = client.post("/api/v1/mesh/route/simulate")
        assert resp_sim.status_code == 200
        sim_data = resp_sim.get_json()
        assert sim_data["delivered"] is True
        assert len(sim_data["trace"]) == 3
