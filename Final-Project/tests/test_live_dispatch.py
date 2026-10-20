"""Tests for live dispatch routing (worker -> transport adapter -> radio).

Covers the selection layer added so the delivery worker can hand a message to a
real Motorola MOTOTRBO adapter (and thus the Raspberry Pi / MNIS hardware
bridge) instead of the in-process simulated link.
"""
import os
import struct
import tempfile
import uuid

import pytest

from messaging.db import init_db, get_db_session
from messaging.dispatch import (
    DMR_CHUNK_BYTES,
    DispatchRouter,
    chunk_frame,
    configure_dispatch,
    resolve_dispatch,
)
from messaging.models import Message
from messaging.server import create_app
from messaging.service import MessagingService
from messaging.state_machine import MessageState
from messaging.transport import transport
from messaging.worker import QueueWorker

SIM_MSG = {
    "message_id": "00000000-0000-0000-0000-000000000001",
    "sender_endpoint_id": "endpoint-a",
    "recipient_endpoint_id": "endpoint-b",
    "message_type": "TEXT",
    "incident_id": None,
    "payload": "FIELD-CHECK",
    "created_at": "2026-10-19T00:00:00",
}


def _fresh_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, f"test_dispatch_{uuid.uuid4().hex[:8]}.db")
    init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# Router unit behaviour
# ---------------------------------------------------------------------------
def test_default_router_is_simulation():
    router = DispatchRouter()
    assert router.is_live is False
    assert router.mode == "SIMULATION"
    res = router.dispatch(dict(SIM_MSG))
    assert res["delivered_to_receiver"] is True


def test_unknown_live_transport_is_retryable():
    router = DispatchRouter("does-not-exist", auto_failover=False)
    res = router.dispatch(dict(SIM_MSG))
    assert res["delivered_to_receiver"] is False
    # Retryable so the durable queue preserves and retries the message.
    assert res["error_code"] in ("TRANSPORT_OFFLINE", "ROUTE_UNAVAILABLE")


def test_locked_out_transport_is_retryable():
    # STAR-V is permanently locked out -> must never be selected.
    router = DispatchRouter("starv-tactical-locked", auto_failover=False)
    res = router.dispatch(dict(SIM_MSG))
    assert res["delivered_to_receiver"] is False
    assert res["error_code"] in ("TRANSPORT_OFFLINE", "STARV_SAFETY_LOCKOUT_BLOCKED")


def test_locked_out_transport_with_auto_failover():
    # With auto-failover enabled (default), fails over to secondary operational adapter or simulated link
    router = DispatchRouter("starv-tactical-locked", auto_failover=True)
    res = router.dispatch(dict(SIM_MSG))
    assert res["delivered_to_receiver"] is True
    assert res.get("failover_active") is True
    assert res.get("failover_from") == "starv-tactical-locked"


def test_motorola_live_dispatch_dry_run(monkeypatch):
    monkeypatch.delenv("MOTOROLA_RADIO_APPROVED", raising=False)
    router = DispatchRouter("motorola-mototrbo-01")
    res = router.dispatch(dict(SIM_MSG))
    assert res["delivered_to_receiver"] is True
    assert res["ack_delivered_to_sender"] is True
    assert res["error_code"] is None
    assert res["transport"] == "motorola-mototrbo-01"
    assert res["chunks"] >= 1


def test_chunking_never_exceeds_dmr_ceiling():
    frame = b"z" * 1000
    chunks = chunk_frame(frame)
    assert all(len(c) <= DMR_CHUNK_BYTES for c in chunks)
    assert b"".join(c[4:] for c in chunks) == frame
    total, index = struct.unpack("<HH", chunks[0][:4])
    assert total == len(chunks)
    assert index == 0


def test_configure_dispatch_roundtrip():
    try:
        status = configure_dispatch("motorola-mototrbo-01")
        assert status["active_transport"] == "motorola-mototrbo-01"
        assert status["is_live"] is True
    finally:
        status = configure_dispatch(None)
    assert status["active_transport"] is None
    assert status["mode"] == "SIMULATION"


# ---------------------------------------------------------------------------
# Worker integration: the live router actually drives delivery
# ---------------------------------------------------------------------------
def test_worker_delivers_through_live_router():
    db_path = _fresh_db()
    transport.reset()
    transport.set_online(True)
    try:
        with get_db_session(db_path) as session:
            msg, _ = MessagingService.submit_message(
                session=session,
                client_idempotency_key="live-dispatch-001",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload="LIVE PATH PROOF",
            )
            msg_id = msg.message_id

        # The console/API writes the selection to shared storage. A *fresh*
        # router instance knows nothing about it — exactly like the worker
        # process in a real split deployment.
        configure_dispatch("motorola-mototrbo-01", db_path=db_path)
        router = DispatchRouter()
        worker = QueueWorker(worker_id="live-worker", db_path=db_path, router=router)
        assert worker.run_once() == 1

        # The worker learned the live path from shared storage, not local state.
        assert router.transport_id == "motorola-mototrbo-01"

        with get_db_session(db_path) as session:
            stored = session.query(Message).filter_by(message_id=msg_id).first()
            assert stored.current_state == MessageState.DELIVERED.value
            assert stored.sender_acknowledged_at is not None

            from messaging.models import MessageEvent
            modes = [
                (e.safe_metadata or {}).get("transport_mode")
                for e in session.query(MessageEvent)
                .filter_by(message_id=msg_id, event_type="DELIVERY_ATTEMPT_STARTED")
                .all()
            ]
        assert modes == ["motorola-mototrbo-01"]
    finally:
        configure_dispatch(None)
        transport.reset()
        import shutil
        shutil.rmtree(os.path.dirname(db_path), ignore_errors=True)


def test_runtime_selection_is_shared_across_processes():
    """Turning the live path off in storage must also reach a running worker."""
    db_path = _fresh_db()
    try:
        configure_dispatch("motorola-mototrbo-01", db_path=db_path)
        router = DispatchRouter()
        resolve_dispatch(db_path, router)
        assert router.is_live is True

        # Operator returns to the simulated link from the console.
        configure_dispatch(None, db_path=db_path)
        resolve_dispatch(db_path, router)
        assert router.is_live is False
        assert router.mode == "SIMULATION"
    finally:
        configure_dispatch(None)
        import shutil
        shutil.rmtree(os.path.dirname(db_path), ignore_errors=True)


# ---------------------------------------------------------------------------
# HTTP API: operators can view and flip the outbound path
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    db_path = _fresh_db()
    transport.reset()
    app = create_app(db_path=db_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    configure_dispatch(None)
    transport.reset()
    import shutil
    shutil.rmtree(os.path.dirname(db_path), ignore_errors=True)


def test_api_active_transport_defaults_to_simulation(client):
    res = client.get("/api/v1/transports/active")
    assert res.status_code == 200
    body = res.get_json()
    assert body["active_transport"] is None
    assert body["is_live"] is False
    assert body["mode"] == "SIMULATION"


def test_api_can_go_live_then_return_to_simulation(client):
    # Go live on the Motorola adapter.
    res = client.post("/api/v1/transports/active", json={"transport_id": "motorola-mototrbo-01"})
    assert res.status_code == 200
    assert res.get_json()["active_transport"] == "motorola-mototrbo-01"

    # The status endpoint now reports live, with bridge diagnostics attached.
    body = client.get("/api/v1/transports/active").get_json()
    assert body["is_live"] is True
    assert body["mode"] == "motorola-mototrbo-01"
    assert "bridge" in body

    # Return to the simulated link.
    res = client.post("/api/v1/transports/active", json={"transport_id": None})
    assert res.status_code == 200
    assert res.get_json()["is_live"] is False


def test_api_rejects_unknown_transport(client):
    res = client.post("/api/v1/transports/active", json={"transport_id": "nope"})
    assert res.status_code == 404


def test_api_transport_detail_returns_bridge_health(client):
    res = client.get("/api/v1/transports/motorola-mototrbo-01")
    assert res.status_code == 200
    body = res.get_json()
    assert body["transport_id"] == "motorola-mototrbo-01"

    # Unknown transport must 404 rather than fabricate a body.
    assert client.get("/api/v1/transports/ghost").status_code == 404
