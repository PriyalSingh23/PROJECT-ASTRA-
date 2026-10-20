import torch  # Critical: Must precede numpy/scipy imports for Apple Silicon OpenBLAS safety
import os
import shutil
import tempfile
import uuid
import pytest

from integration.relay_nodes.manager import (
    RelayNode,
    RelayNodeType,
    RelayStatus,
    RelayNodeManager,
    relay_manager,
)


def test_relay_node_creation_and_telemetry():
    node = RelayNode(
        node_id="test-relay-01",
        display_name="Test Ground Relay",
        node_type=RelayNodeType.PORTABLE_GROUND,
        battery_percentage=90.0,
        temperature_celsius=28.0,
        storage_used_pct=10.0,
    )
    node.connected_endpoints = ["endpoint-a", "endpoint-b"]

    assert node.status == RelayStatus.ONLINE
    assert node.can_forward_to("endpoint-a") is True
    assert node.can_forward_to("endpoint-b") is True
    assert node.can_forward_to("unknown-endpoint") is False

    # Forward message
    ok = node.forward_message("msg-101", "endpoint-a")
    assert ok is True
    assert node.forwarded_message_count == 1
    assert node.last_forwarding_at is not None


def test_relay_failsafes_battery_and_storage():
    node = RelayNode(
        node_id="test-relay-02",
        display_name="Depleted Relay",
        node_type=RelayNodeType.PORTABLE_GROUND,
        battery_percentage=4.0,  # Below 5% threshold
    )
    node.connected_endpoints = ["endpoint-a"]
    assert node.failsafe_cutoff_active is True
    assert node.can_forward_to("endpoint-a") is False, "Relay must not forward when battery is critically depleted"

    # Restore battery, exceed storage
    node.update_telemetry(battery=80.0, storage_pct=99.0)
    assert node.failsafe_cutoff_active is True
    assert node.can_forward_to("endpoint-a") is False, "Relay must not forward when storage is full"

    # Restore storage
    node.update_telemetry(storage_pct=30.0)
    assert node.failsafe_cutoff_active is False
    assert node.can_forward_to("endpoint-a") is True


def test_simulated_aerial_relay_independence():
    manager = RelayNodeManager()
    aerial_node = manager.get_node("relay-aerial-sim-01")
    assert aerial_node is not None
    assert aerial_node.node_type == RelayNodeType.AERIAL_PAYLOAD_SIMULATED
    assert aerial_node.flight_failsafe_independent is True, (
        "Aerial relay communications payload must be strictly decoupled from flight safety control!"
    )
    assert aerial_node.is_approved is False, "Simulated aerial relay must not be marked approved before type certification"


def test_relay_serialization_compatibility():
    """Verify dual-key parity between backend model and frontend UI schemas."""
    node = RelayNode(
        node_id="test-parity-01",
        display_name="Parity Relay",
        node_type=RelayNodeType.PORTABLE_GROUND,
        battery_percentage=85.5,
        temperature_celsius=22.4,
        storage_used_pct=45.2,
    )
    node.queue_depth = 7
    d = node.to_dict()

    # Dual-key battery
    assert "battery_percentage" in d and "battery_level_pct" in d
    assert d["battery_percentage"] == 85.5
    assert d["battery_level_pct"] == 85.5

    # Dual-key storage
    assert "storage_used_pct" in d and "storage_usage_pct" in d
    assert d["storage_used_pct"] == 45.2
    assert d["storage_usage_pct"] == 45.2

    # Dual-key queue depth
    assert "queue_depth" in d and "queued_bundles_count" in d
    assert d["queue_depth"] == 7
    assert d["queued_bundles_count"] == 7

    # Dual-key flight failsafe independence
    assert "flight_failsafe_independent" in d and "is_independent_payload" in d
    assert d["flight_failsafe_independent"] is True
    assert d["is_independent_payload"] is True

    # Failsafe cutoff flag
    assert "failsafe_cutoff_active" in d
    assert d["failsafe_cutoff_active"] is False


def test_relay_telemetry_rest_api():
    """Test REST endpoints for querying, updating telemetry, and resetting relays."""
    from messaging.server import create_app
    from messaging.db import init_db

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, f"test_relay_api_{uuid.uuid4().hex[:8]}.db")
    try:
        init_db(db_path)
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True
        with app.test_client() as client:
            # 1. GET /api/v1/relays
            res_list = client.get("/api/v1/relays")
            assert res_list.status_code == 200
            nodes = res_list.get_json()
            assert any(n["node_id"] == "relay-ground-01" for n in nodes)

            # 2. GET /api/v1/relays/<id>
            res_node = client.get("/api/v1/relays/relay-ground-01")
            assert res_node.status_code == 200
            data = res_node.get_json()
            assert data["node_id"] == "relay-ground-01"

            # 3. POST /api/v1/relays/<id>/telemetry - trigger cutoff via critical battery
            res_deplete = client.post(
                "/api/v1/relays/relay-ground-01/telemetry",
                json={"battery": 3.0, "temperature": 40.0, "storage_pct": 50.0, "queue_depth": 12},
            )
            assert res_deplete.status_code == 200
            depleted_data = res_deplete.get_json()
            assert depleted_data["battery_percentage"] == 3.0
            assert depleted_data["failsafe_cutoff_active"] is True
            assert depleted_data["queue_depth"] == 12

            # 4. POST /api/v1/relays/<id>/reset - restore nominal defaults
            res_reset = client.post("/api/v1/relays/relay-ground-01/reset")
            assert res_reset.status_code == 200
            reset_data = res_reset.get_json()
            assert reset_data["battery_percentage"] == 94.5
            assert reset_data["failsafe_cutoff_active"] is False
            assert reset_data["queue_depth"] == 0

            # 404 on nonexistent relay
            assert client.get("/api/v1/relays/nonexistent").status_code == 404
            assert client.post("/api/v1/relays/nonexistent/telemetry", json={}).status_code == 404
            assert client.post("/api/v1/relays/nonexistent/reset").status_code == 404
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_relay_node_manager_routing():
    manager = RelayNodeManager()
    # Route to endpoint-a
    relay_used = manager.route_via_relay("msg-uuid-202", "endpoint-a")
    assert relay_used == "relay-ground-01"

    # Route to unreachable endpoint
    unreachable = manager.route_via_relay("msg-uuid-203", "endpoint-z")
    assert unreachable is None
