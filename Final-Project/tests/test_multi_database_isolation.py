import torch  # Critical on macOS Apple Silicon: MUST be imported before any other C-extensions to prevent OpenBLAS linker collision (SIGSEGV 139)
import os
import sys
import time
import uuid
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import pytest
from werkzeug.serving import make_server

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from messaging.models import (
    Base,
    Endpoint,
    Message,
    InboxItem,
    Acknowledgement,
    DeliveryAttempt,
    MessageEvent,
    SystemSetting,
    utcnow,
    generate_uuid,
)
from messaging.db import init_db, get_db_session, get_engine
from messaging.state_machine import MessageState
from messaging.transport import transport
from messaging.service import MessagingService
from messaging.worker import QueueWorker
from messaging.server import create_app


@pytest.fixture
def multi_db_setup():
    """Initializes isolated Alpha and Bravo SQLite databases and cleans them up."""
    temp_dir = tempfile.mkdtemp()
    alpha_db = os.path.join(temp_dir, f"test_alpha_{uuid.uuid4().hex[:8]}.db")
    bravo_db = os.path.join(temp_dir, f"test_bravo_{uuid.uuid4().hex[:8]}.db")

    init_db(alpha_db, station_id="endpoint-a")
    init_db(bravo_db, station_id="endpoint-b")
    transport.reset()

    yield {
        "temp_dir": temp_dir,
        "alpha_db": alpha_db,
        "bravo_db": bravo_db,
    }

    transport.reset()
    for db_path in (alpha_db, bravo_db):
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
            for suffix in ("-wal", "-shm"):
                f = f"{db_path}{suffix}"
                if os.path.exists(f):
                    os.remove(f)
        except Exception:
            pass
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass


@pytest.fixture
def alpha_app(multi_db_setup):
    app = create_app(
        db_path=multi_db_setup["alpha_db"],
        station_id="endpoint-a",
        station_name="Station Alpha",
        port=5051,
        peer_url="http://127.0.0.1:5052/api/v1",
    )
    app.config["TESTING"] = True
    return app


@pytest.fixture
def bravo_app(multi_db_setup):
    app = create_app(
        db_path=multi_db_setup["bravo_db"],
        station_id="endpoint-b",
        station_name="Station Bravo",
        port=5052,
        peer_url="http://127.0.0.1:5051/api/v1",
    )
    app.config["TESTING"] = True
    return app


@pytest.fixture
def alpha_client(alpha_app):
    with alpha_app.test_client() as client:
        yield client


@pytest.fixture
def bravo_client(bravo_app):
    with bravo_app.test_client() as client:
        yield client


# ==============================================================================
# TEST 1: DATABASE PHYSICAL ISOLATION & CONCURRENCY
# ==============================================================================
def test_database_physical_isolation(multi_db_setup):
    """Verifies that alpha.db and bravo.db are completely physically isolated,
    endpoint is_local flags reflect their station identity, data written to alpha
    does not appear in bravo, and concurrent writes run without lock contention."""
    alpha_db = multi_db_setup["alpha_db"]
    bravo_db = multi_db_setup["bravo_db"]

    # Verify is_local configuration in alpha.db
    with get_db_session(alpha_db) as session:
        ep_a = session.query(Endpoint).filter_by(endpoint_id="endpoint-a").first()
        ep_b = session.query(Endpoint).filter_by(endpoint_id="endpoint-b").first()
        assert ep_a is not None and ep_a.is_local is True
        assert ep_b is not None and ep_b.is_local is False

        # Check system_settings in alpha.db
        st_id = session.query(SystemSetting).filter_by(key="node_station_id").first()
        assert st_id is not None and st_id.value == "endpoint-a"

    # Verify is_local configuration in bravo.db
    with get_db_session(bravo_db) as session:
        ep_a = session.query(Endpoint).filter_by(endpoint_id="endpoint-a").first()
        ep_b = session.query(Endpoint).filter_by(endpoint_id="endpoint-b").first()
        assert ep_a is not None and ep_a.is_local is False
        assert ep_b is not None and ep_b.is_local is True

        # Check system_settings in bravo.db
        st_id = session.query(SystemSetting).filter_by(key="node_station_id").first()
        assert st_id is not None and st_id.value == "endpoint-b"

    # Insert a message into alpha.db
    msg_id = generate_uuid()
    with get_db_session(alpha_db) as session:
        msg = Message(
            message_id=msg_id,
            client_idempotency_key="idemp-alpha-001",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="Alpha secret tactical data",
            expires_at=utcnow() + timedelta(hours=1),
            current_state="QUEUED",
        )
        session.add(msg)

    # Verify message is present in alpha.db but NOT in bravo.db
    with get_db_session(alpha_db) as session:
        assert session.query(Message).filter_by(message_id=msg_id).first() is not None

    with get_db_session(bravo_db) as session:
        assert session.query(Message).filter_by(message_id=msg_id).first() is None

    # Test concurrent writes to both databases to verify zero lock contention
    def write_to_db(db_path, count, prefix):
        for i in range(count):
            with get_db_session(db_path) as session:
                m = Message(
                    message_id=generate_uuid(),
                    client_idempotency_key=f"{prefix}-{i}-{uuid.uuid4().hex[:6]}",
                    sender_endpoint_id="endpoint-a" if "alpha" in prefix else "endpoint-b",
                    recipient_endpoint_id="endpoint-b" if "alpha" in prefix else "endpoint-a",
                    payload=f"Payload {prefix} {i}",
                    expires_at=utcnow() + timedelta(hours=1),
                    current_state="QUEUED",
                )
                session.add(m)

    with ThreadPoolExecutor(max_workers=4) as executor:
        f1 = executor.submit(write_to_db, alpha_db, 20, "concurrent-alpha")
        f2 = executor.submit(write_to_db, bravo_db, 20, "concurrent-bravo")
        f1.result()
        f2.result()

    with get_db_session(alpha_db) as session:
        alpha_count = session.query(Message).count()
        assert alpha_count == 21  # 1 initial + 20 concurrent

    with get_db_session(bravo_db) as session:
        bravo_count = session.query(Message).count()
        assert bravo_count == 20  # 20 concurrent


# ==============================================================================
# TEST 2: IDENTITY SPOOFING REJECTION (D-03)
# ==============================================================================
def test_identity_spoofing_rejection(alpha_client, bravo_client):
    """Verifies that Station Alpha rejects drafts attempting to author as endpoint-b
    with HTTP 403 IDENTITY_SPOOFING_BLOCKED, Station Bravo rejects drafts attempting
    to author as endpoint-a with HTTP 403 IDENTITY_SPOOFING_BLOCKED, and authoring as
    the local station succeeds with HTTP 201."""
    # 1. Attempt to spoof endpoint-b on Station Alpha
    spoof_resp_a = alpha_client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "spoof-a-01",
            "sender_endpoint_id": "endpoint-b",
            "recipient_endpoint_id": "endpoint-a",
            "payload": "I am claiming to be Bravo on Alpha station",
        },
    )
    assert spoof_resp_a.status_code == 403
    data_a = spoof_resp_a.get_json()
    assert data_a["error"] == "IDENTITY_SPOOFING_BLOCKED"
    assert "endpoint-a" in data_a["detail"]

    # 2. Legitimate authoring on Station Alpha as endpoint-a
    valid_resp_a = alpha_client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "legit-a-01",
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "Valid transmission from Alpha",
        },
    )
    assert valid_resp_a.status_code == 201

    # 3. Attempt to spoof endpoint-a on Station Bravo
    spoof_resp_b = bravo_client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "spoof-b-01",
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "I am claiming to be Alpha on Bravo station",
        },
    )
    assert spoof_resp_b.status_code == 403
    data_b = spoof_resp_b.get_json()
    assert data_b["error"] == "IDENTITY_SPOOFING_BLOCKED"
    assert "endpoint-b" in data_b["detail"]

    # 4. Legitimate authoring on Station Bravo as endpoint-b
    valid_resp_b = bravo_client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "legit-b-01",
            "sender_endpoint_id": "endpoint-b",
            "recipient_endpoint_id": "endpoint-a",
            "payload": "Valid transmission from Bravo",
        },
    )
    assert valid_resp_b.status_code == 201


# ==============================================================================
# TEST 3: PEER INCOMING INGEST (D-02)
# ==============================================================================
def test_peer_incoming_ingest(bravo_client, multi_db_setup):
    """Verifies that POST /api/v1/endpoints/incoming on Bravo persists a cross-station
    packet, creates an InboxItem for endpoint-b, and returns HTTP 201 with signed_ack_receipt."""
    bravo_db = multi_db_setup["bravo_db"]
    msg_id = generate_uuid()
    created_ts = utcnow().isoformat()
    expires_ts = (utcnow() + timedelta(hours=2)).isoformat()

    packet = {
        "message_id": msg_id,
        "client_idempotency_key": "cross-station-01",
        "sender_endpoint_id": "endpoint-a",
        "recipient_endpoint_id": "endpoint-b",
        "payload": "Tactical coordination sitrep from Alpha",
        "message_type": "TEXT",
        "priority": 2,
        "created_at": created_ts,
        "expires_at": expires_ts,
    }

    resp = bravo_client.post("/api/v1/endpoints/incoming", json=packet)
    assert resp.status_code in (200, 201)
    body = resp.get_json()

    assert body["status"] == "STORED"
    assert body["message_id"] == msg_id
    assert body["origin_endpoint"] == "endpoint-b"
    assert body["destination_endpoint"] == "endpoint-a"
    assert body["is_duplicate"] is False
    assert "ACK-SIG:" in body["signed_ack_receipt"]

    # Verify database persistence in bravo.db
    with get_db_session(bravo_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg is not None
        assert msg.current_state == "DELIVERED"
        assert msg.signed_ack_receipt == body["signed_ack_receipt"]

        inbox_item = session.query(InboxItem).filter_by(message_id=msg_id).first()
        assert inbox_item is not None
        assert inbox_item.recipient_endpoint_id == "endpoint-b"
        assert inbox_item.processing_status == "STORED"

        ack = session.query(Acknowledgement).filter_by(original_message_id=msg_id).first()
        assert ack is not None
        assert ack.ack_id == body["ack_id"]

    # Also test recipient mismatch rejection on Bravo (e.g. addressed to endpoint-a)
    mismatch_packet = dict(packet, message_id=generate_uuid(), recipient_endpoint_id="endpoint-a")
    mismatch_resp = bravo_client.post("/api/v1/endpoints/incoming", json=mismatch_packet)
    assert mismatch_resp.status_code == 422
    assert mismatch_resp.get_json()["error"] == "RECIPIENT_MISMATCH"


# ==============================================================================
# TEST 4: PEER INCOMING DUPLICATE REPLAY DEDUPLICATION (T-06-03)
# ==============================================================================
def test_peer_incoming_duplicate_replay(bravo_client, multi_db_setup):
    """Verifies that submitting the identical packet payload twice to
    POST /api/v1/endpoints/incoming generates exactly 1 InboxItem, reports is_duplicate: True,
    and returns the identical signed_ack_receipt without database duplication."""
    bravo_db = multi_db_setup["bravo_db"]
    msg_id = generate_uuid()

    packet = {
        "message_id": msg_id,
        "client_idempotency_key": "replay-key-01",
        "sender_endpoint_id": "endpoint-a",
        "recipient_endpoint_id": "endpoint-b",
        "payload": "Mission parameters v1.0",
        "message_type": "TEXT",
        "priority": 1,
        "created_at": utcnow().isoformat(),
        "expires_at": (utcnow() + timedelta(days=1)).isoformat(),
    }

    # First ingest
    resp1 = bravo_client.post("/api/v1/endpoints/incoming", json=packet)
    assert resp1.status_code in (200, 201)
    body1 = resp1.get_json()
    assert body1["is_duplicate"] is False
    sig1 = body1["signed_ack_receipt"]

    # Replay identical ingest
    resp2 = bravo_client.post("/api/v1/endpoints/incoming", json=packet)
    assert resp2.status_code == 200
    body2 = resp2.get_json()
    assert body2["is_duplicate"] is True
    sig2 = body2["signed_ack_receipt"]

    # Signatures must be identical
    assert sig1 == sig2
    assert body1["ack_id"] == body2["ack_id"]

    # Assert exactly 1 InboxItem exists in bravo.db
    with get_db_session(bravo_db) as session:
        inbox_items = session.query(InboxItem).filter_by(message_id=msg_id).all()
        assert len(inbox_items) == 1

        events = session.query(MessageEvent).filter_by(message_id=msg_id).all()
        event_types = [e.event_type for e in events]
        assert "INBOX_PERSISTED" in event_types
        assert "DUPLICATE_DELIVERY_IGNORED" in event_types


# ==============================================================================
# TEST 5: PEER CROSS-STATION END-TO-END DELIVERY (D-02)
# ==============================================================================
def test_peer_cross_station_delivery(multi_db_setup, bravo_app):
    """Verifies that Alpha worker configured with peer_url dispatches an outbound
    message over HTTP to Bravo, Bravo stores it in bravo.db inbox, and Alpha transitions
    the message to DELIVERED with signed_ack_receipt in alpha.db."""
    alpha_db = multi_db_setup["alpha_db"]
    bravo_db = multi_db_setup["bravo_db"]

    # Run Bravo Flask app on a local ephemeral test HTTP server
    server = make_server("127.0.0.1", 0, bravo_app)
    bravo_port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    peer_url = f"http://127.0.0.1:{bravo_port}/api/v1"

    try:
        # Submit message on Alpha addressed to Bravo
        with get_db_session(alpha_db) as session:
            msg, _ = MessagingService.submit_message(
                session=session,
                client_idempotency_key="cross-peer-delivery-01",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload="Immediate rendezvous at rally point Echo",
                message_type="TEXT",
                priority=1,
            )
            msg_id = msg.message_id

        # Instantiate Alpha QueueWorker with peer_url
        worker = QueueWorker(
            worker_id="alpha-test-worker",
            db_path=alpha_db,
            poll_interval=0.1,
            peer_url=peer_url,
        )

        with get_db_session(alpha_db) as session:
            leased = worker.acquire_next_message(session)
            assert leased is not None
            assert leased.message_id == msg_id

            success = worker.process_message(session, leased)
            assert success is True

        # Verify Alpha message state in alpha.db
        alpha_receipt = None
        with get_db_session(alpha_db) as session:
            alpha_msg = session.query(Message).filter_by(message_id=msg_id).first()
            assert alpha_msg.current_state == MessageState.DELIVERED.value
            assert alpha_msg.signed_ack_receipt is not None
            assert "ACK-SIG:" in alpha_msg.signed_ack_receipt
            alpha_receipt = alpha_msg.signed_ack_receipt

            # Ensure Bravo inbox item was NOT inserted into alpha.db
            assert session.query(InboxItem).filter_by(message_id=msg_id).first() is None

        # Verify Bravo inbox in bravo.db
        with get_db_session(bravo_db) as session:
            bravo_msg = session.query(Message).filter_by(message_id=msg_id).first()
            assert bravo_msg is not None
            assert bravo_msg.current_state == MessageState.DELIVERED.value

            inbox_item = session.query(InboxItem).filter_by(message_id=msg_id).first()
            assert inbox_item is not None
            assert inbox_item.recipient_endpoint_id == "endpoint-b"
            assert inbox_item.processing_status == "STORED"

            # Receipts match
            assert bravo_msg.signed_ack_receipt == alpha_receipt

    finally:
        server.shutdown()
        server_thread.join(timeout=2.0)


# ==============================================================================
# TEST 6: PEER AIR-GAP OUTAGE HANDLING (T-06-04)
# ==============================================================================
def test_peer_air_gap_outage_handling(multi_db_setup):
    """Verifies that when Station Bravo is unreachable (unopened port), Alpha's
    transmission catches the failure, transitions message to FAILED_RETRYABLE with
    error_code='TRANSPORT_OFFLINE', and schedules retry with exponential backoff."""
    alpha_db = multi_db_setup["alpha_db"]

    # Submit message on Alpha
    with get_db_session(alpha_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="airgap-outage-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="Air gap simulation packet",
            message_type="TEXT",
            priority=1,
        )
        msg_id = msg.message_id

    # Configure worker with an unreachable port
    unreachable_url = "http://127.0.0.1:59998/api/v1"
    worker = QueueWorker(
        worker_id="alpha-airgap-worker",
        db_path=alpha_db,
        poll_interval=0.1,
        peer_url=unreachable_url,
    )

    with get_db_session(alpha_db) as session:
        leased = worker.acquire_next_message(session)
        assert leased is not None
        assert leased.message_id == msg_id

        success = worker.process_message(session, leased)
        assert success is False

    # Verify Alpha message in alpha.db
    with get_db_session(alpha_db) as session:
        alpha_msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert alpha_msg.current_state == MessageState.FAILED_RETRYABLE.value
        assert alpha_msg.last_error_code == "TRANSPORT_OFFLINE"
        assert alpha_msg.worker_lease_id is None
        assert alpha_msg.next_attempt_at is not None

        attempt = session.query(DeliveryAttempt).filter_by(message_id=msg_id).first()
        assert attempt is not None
        assert attempt.result == "FAILED"
        assert attempt.error_code == "TRANSPORT_OFFLINE"
        assert attempt.retryability is True


# ==============================================================================
# TEST 7: PEER ACK LOSS RECONCILIATION (D-02, T-06-03)
# ==============================================================================
def test_peer_ack_loss_reconciliation(multi_db_setup, bravo_app):
    """Verifies that when the return ACK is dropped during cross-station delivery,
    Alpha transitions to AWAITING_ACK. On retry, the re-transmission is deduplicated
    by Bravo and reconciled to DELIVERED on Alpha."""
    alpha_db = multi_db_setup["alpha_db"]
    bravo_db = multi_db_setup["bravo_db"]

    server = make_server("127.0.0.1", 0, bravo_app)
    bravo_port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    peer_url = f"http://127.0.0.1:{bravo_port}/api/v1"

    try:
        # Submit message on Alpha
        with get_db_session(alpha_db) as session:
            msg, _ = MessagingService.submit_message(
                session=session,
                client_idempotency_key="ack-loss-reconcile-01",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload="Critical order requiring robust reconciliation",
                message_type="TEXT",
                priority=1,
            )
            msg_id = msg.message_id

        worker = QueueWorker(
            worker_id="alpha-ackloss-worker",
            db_path=alpha_db,
            poll_interval=0.1,
            peer_url=peer_url,
        )

        # 1. Arm single-shot return ACK drop
        transport.arm_drop_ack()

        with get_db_session(alpha_db) as session:
            leased = worker.acquire_next_message(session)
            assert leased is not None
            success = worker.process_message(session, leased)
            assert success is False

        # Verify Alpha is in AWAITING_ACK state
        with get_db_session(alpha_db) as session:
            alpha_msg = session.query(Message).filter_by(message_id=msg_id).first()
            assert alpha_msg.current_state == MessageState.AWAITING_ACK.value
            assert alpha_msg.last_error_code == "ACK_LOST"
            assert alpha_msg.worker_lease_id is None

            # Manually reset next_attempt_at to now to enable immediate re-leasing
            alpha_msg.next_attempt_at = utcnow() - timedelta(seconds=1)

        # Verify Bravo already has the message and 1 inbox item
        with get_db_session(bravo_db) as session:
            inbox_count = session.query(InboxItem).filter_by(message_id=msg_id).count()
            assert inbox_count == 1

        # 2. Re-acquire lease and process retry on Alpha (ACK drop disarmed)
        with get_db_session(alpha_db) as session:
            leased_retry = worker.acquire_next_message(session)
            assert leased_retry is not None
            assert leased_retry.message_id == msg_id

            success_retry = worker.process_message(session, leased_retry)
            assert success_retry is True

        # Verify Alpha reconciled to DELIVERED
        with get_db_session(alpha_db) as session:
            alpha_msg = session.query(Message).filter_by(message_id=msg_id).first()
            assert alpha_msg.current_state == MessageState.DELIVERED.value
            assert alpha_msg.signed_ack_receipt is not None
            assert "ACK-SIG:" in alpha_msg.signed_ack_receipt

        # Verify Bravo STILL has exactly 1 inbox item (no duplicate pollution)
        with get_db_session(bravo_db) as session:
            inbox_count = session.query(InboxItem).filter_by(message_id=msg_id).count()
            assert inbox_count == 1

    finally:
        server.shutdown()
        server_thread.join(timeout=2.0)


# ==============================================================================
# TEST 8: HEALTH ENDPOINT STATION METADATA
# ==============================================================================
def test_health_endpoint_station_metadata(alpha_client, bravo_client):
    """Verifies that GET /api/v1/health reports station_id, station_name, db_path,
    port, and peer_url correctly for each station."""
    # Check Alpha health
    resp_a = alpha_client.get("/api/v1/health")
    assert resp_a.status_code == 200
    data_a = resp_a.get_json()

    assert data_a["status"] == "HEALTHY"
    assert data_a["station_id"] == "endpoint-a"
    assert data_a["station_name"] == "Station Alpha"
    assert "test_alpha_" in data_a["db_path"]
    assert data_a["port"] == 5051
    assert data_a["peer_url"] == "http://127.0.0.1:5052/api/v1"

    # Check Bravo health
    resp_b = bravo_client.get("/api/v1/health")
    assert resp_b.status_code == 200
    data_b = resp_b.get_json()

    assert data_b["status"] == "HEALTHY"
    assert data_b["station_id"] == "endpoint-b"
    assert data_b["station_name"] == "Station Bravo"
    assert "test_bravo_" in data_b["db_path"]
    assert data_b["port"] == 5052
    assert data_b["peer_url"] == "http://127.0.0.1:5051/api/v1"
