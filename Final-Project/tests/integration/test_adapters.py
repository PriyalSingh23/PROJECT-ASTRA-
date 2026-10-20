import torch  # Critical: Must precede numpy/scipy imports for Apple Silicon OpenBLAS safety
import os
import shutil
import struct
import tempfile
import uuid
import pytest

from integration.base import TransportReadiness, TransportConnectionState
from integration.manager import TransportManager
from integration.motorola.adapter import MotorolaMOTOTRBOAdapter
from integration.starv.adapter import StarVAdapter, StarVSafetyLockoutError
from integration.sdr_research.service import SDRResearchService
from messaging.dispatch import (
    DispatchRouter,
    chunk_frame,
    DMR_CHUNK_BYTES,
)


def test_motorola_adapter_capability_and_limits():
    adapter = MotorolaMOTOTRBOAdapter(radio_model="XPR 7550e")
    assert adapter.transport_type == "MOTOROLA_MOTOTRBO"
    assert "TMS_TEXT_MESSAGE" in adapter.supported_operations
    assert adapter.readiness == TransportReadiness.SIMULATION_ONLY

    # Send within 280-byte limit
    res = adapter.send("radio-id-1001", b"Short DMR message", {})
    assert res["success"] is True
    assert res["delivery_id"].startswith("mot-tms-")

    # Send exceeding 280-byte limit
    oversized = b"X" * 300
    res_oversized = adapter.send("radio-id-1001", oversized, {})
    assert res_oversized["success"] is False
    assert res_oversized["error_code"] == "PAYLOAD_TOO_LARGE"


def test_starv_adapter_safety_lockout():
    adapter = StarVAdapter()
    assert adapter.transport_type == "STARV_TACTICAL_SDR"
    assert adapter.readiness == TransportReadiness.LOCKED_OUT
    assert adapter.connection_state == TransportConnectionState.OFFLINE
    assert len(adapter.supported_operations) == 0

    # Sending must fail with safety lockout
    res = adapter.send("tactical-node-01", b"Classified command", {})
    assert res["success"] is False
    assert res["error_code"] == "STARV_SAFETY_LOCKOUT"
    assert "SAFETY LOCKOUT" in res["details"]


def test_starv_command_transmit_hard_lockout():
    """Verify that command_transmit unconditionally raises StarVSafetyLockoutError."""
    adapter = StarVAdapter()
    with pytest.raises(StarVSafetyLockoutError) as exc_info:
        adapter.command_transmit("KEY_TRANSMITTER", frequency_mhz=433.0)
    assert "STAR-V direct RF command rejected" in str(exc_info.value)


def test_starv_test_lockout_endpoint():
    """Verify dry-run lockout testing for soft refusal and hard command."""
    from messaging.server import create_app
    from messaging.db import init_db

    adapter = StarVAdapter()
    soft = adapter.test_safety_lockout("soft_refusal")
    assert soft["status"] == "BLOCKED"
    assert soft["test_type"] == "soft_refusal"
    assert soft["error_code"] == "STARV_SAFETY_LOCKOUT"

    hard = adapter.test_safety_lockout("hard_command")
    assert hard["status"] == "BLOCKED"
    assert hard["test_type"] == "hard_command"
    assert hard["exception_class"] == "StarVSafetyLockoutError"

    with pytest.raises(ValueError):
        adapter.test_safety_lockout("unsupported_mode")

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, f"test_starv_api_{uuid.uuid4().hex[:8]}.db")
    try:
        init_db(db_path)
        app = create_app(db_path=db_path)
        app.config["TESTING"] = True
        with app.test_client() as client:
            res_soft = client.post("/api/v1/transports/starv/test-lockout", json={"test_type": "soft_refusal"})
            assert res_soft.status_code == 200
            data_soft = res_soft.get_json()
            assert data_soft["status"] == "BLOCKED"
            assert data_soft["audit_logged"] is True

            res_hard = client.post("/api/v1/transports/starv/test-lockout", json={"test_type": "hard_command"})
            assert res_hard.status_code == 200
            data_hard = res_hard.get_json()
            assert data_hard["status"] == "BLOCKED"
            assert data_hard["audit_logged"] is True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_transport_manager_routing_decision():
    mgr = TransportManager()

    # By default, Motorola adapter is in simulation/standby, StarV is locked out
    selected = mgr.select_transport("endpoint-b")
    assert selected is not None
    assert selected.transport_id == "motorola-mototrbo-01"

    # Route and dispatch
    res = mgr.route_and_dispatch("endpoint-b", b"Automated dispatch", {"priority": 1})
    assert res["success"] is True
    assert res["adapter_used"] == "motorola-mototrbo-01"


def test_transport_manager_pinned_with_failover():
    """Verify operator-pinned transport routing with auto-failover enabled."""
    router = DispatchRouter("starv-tactical-locked", auto_failover=True)
    msg = {
        "message_id": "failover-test-01",
        "sender_endpoint_id": "endpoint-a",
        "recipient_endpoint_id": "endpoint-b",
        "payload": "FAILOVER_MSG",
    }
    res = router.dispatch(msg)
    assert res["delivered_to_receiver"] is True
    assert res.get("failover_active") is True
    assert res.get("failover_from") == "starv-tactical-locked"


def test_transport_manager_route_unavailable_hold():
    """When active transport is offline or locked out and failover is disabled, hold message."""
    # 1. Pinned to STAR-V with auto_failover=False -> STARV_SAFETY_LOCKOUT_BLOCKED
    router_starv = DispatchRouter("starv-tactical-locked", auto_failover=False)
    msg = {
        "message_id": "hold-test-01",
        "sender_endpoint_id": "endpoint-a",
        "recipient_endpoint_id": "endpoint-b",
        "payload": "HOLD_MSG",
    }
    res_starv = router_starv.dispatch(msg)
    assert res_starv["delivered_to_receiver"] is False
    assert res_starv["error_code"] == "STARV_SAFETY_LOCKOUT_BLOCKED"

    # 2. Pinned to offline/unknown transport with auto_failover=False -> ROUTE_UNAVAILABLE
    router_offline = DispatchRouter("nonexistent-radio-99", auto_failover=False)
    res_offline = router_offline.dispatch(msg)
    assert res_offline["delivered_to_receiver"] is False
    assert res_offline["error_code"] == "ROUTE_UNAVAILABLE"


def test_dmr_chunking_atomic_retry():
    """Verify multi-burst chunking splits at 276 bytes and aborts burst immediately on failure."""
    # 1. Chunk formatting
    payload = b"X" * 600
    chunks = chunk_frame(payload, 276)
    assert len(chunks) == 3
    assert all(len(c) <= DMR_CHUNK_BYTES for c in chunks)

    total, idx0 = struct.unpack("<HH", chunks[0][:4])
    assert total == 3 and idx0 == 0
    total, idx1 = struct.unpack("<HH", chunks[1][:4])
    assert total == 3 and idx1 == 1
    total, idx2 = struct.unpack("<HH", chunks[2][:4])
    assert total == 3 and idx2 == 2

    # 2. Atomic frame retry abort
    class MockFailingAdapter:
        def __init__(self):
            self.transport_id = "mock-dmr-01"
            self.sent_chunks = []

        def send(self, recipient, chunk, meta):
            idx = meta.get("chunk_index", 0)
            self.sent_chunks.append(idx)
            if idx == 1:
                return {"success": False, "error_code": "PACKET_DROPPED", "details": "Simulated drop on chunk 1"}
            return {"success": True}

    mock_adapter = MockFailingAdapter()
    router = DispatchRouter()
    msg = {
        "message_id": "atomic-test-1",
        "sender_endpoint_id": "endpoint-a",
        "recipient_endpoint_id": "endpoint-b",
        "payload": ("Y" * 600),
    }

    res = router._dispatch_with_adapter(mock_adapter, msg)
    assert res["delivered_to_receiver"] is False
    assert res["error_code"] == "PACKET_DROPPED"
    assert "Atomic burst failed at chunk 2/3" in res["detail"]
    assert 2 not in mock_adapter.sent_chunks


def test_sdr_research_service_audit():
    service = SDRResearchService()
    status = service.get_research_status()

    assert status["processing_gain_db"] == 9.03
    assert status["sample_rate_hz"] == 245760
    assert "scientific_disclaimer" in status

    audit = status["checkpoints_audit"]
    assert "root_checkpoints" in audit
    assert "v4_checkpoints" in audit
    # Root checkpoints verified
    assert "generator_lpi.pt" in audit["root_checkpoints"]
    assert audit["root_checkpoints"]["generator_lpi.pt"]["sha256"] is not None


def test_lpi_cgan_adapter_pipeline():
    from integration.lpi_cgan.adapter import LPICGANTransportAdapter
    adapter = LPICGANTransportAdapter()
    assert adapter.transport_type == "SDR_RESEARCH"
    assert "WAVEFORM_GENERATE" in adapter.supported_operations
    assert adapter.readiness in (TransportReadiness.READY, TransportReadiness.SIMULATION_ONLY)

    # Health check
    hc = adapter.health_check()
    assert hc["spreading_gain_db"] == 9.03
    assert hc["sample_rate_hz"] == 245760

    # End-to-end simulated transmission
    test_msg = b"ALPHA-COVERT-REPORT-001"
    res = adapter.send("endpoint-b", test_msg, {"snr_db": 10.0})
    assert res["success"] is True
    assert "metrics" in res
    assert res["metrics"]["processing_gain_db"] == 9.03
    assert res["metrics"]["frames"] >= 1
