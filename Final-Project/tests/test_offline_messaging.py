import os
import sys
import time
import uuid
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

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
    utcnow,
    generate_uuid,
)
from messaging.db import init_db, get_db_session, get_engine
from messaging.state_machine import MessageState, validate_transition, InvalidStateTransitionError
from messaging.transport import transport
from messaging.ack_manager import AckManager
from messaging.retry_policy import RetryPolicy
from messaging.service import MessagingService, MAX_PAYLOAD_BYTES
from messaging.worker import QueueWorker
from messaging.server import create_app


@pytest.fixture
def test_db():
    """Creates an isolated temporary SQLite database for each test."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, f"test_messaging_{uuid.uuid4().hex[:8]}.db")
    init_db(db_path)
    transport.reset()
    yield db_path
    transport.reset()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        wal_file = f"{db_path}-wal"
        shm_file = f"{db_path}-shm"
        if os.path.exists(wal_file):
            os.remove(wal_file)
        if os.path.exists(shm_file):
            os.remove(shm_file)
        os.rmdir(temp_dir)
    except Exception:
        pass


@pytest.fixture
def client(test_db):
    """Flask test client connected to the isolated test database."""
    app = create_app(db_path=test_db)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ==============================================================================
# TEST 1: SUCCESSFUL DELIVERY UNDER CLEAN CONDITIONS
# ==============================================================================
def test_01_successful_delivery_under_clean_conditions(test_db):
    """Verifies that an offline message from A to B is persisted, queued,
    leased, transmitted, received into inbox, acknowledged, and marked DELIVERED."""
    transport.reset()
    transport.set_online(True)
    transport.set_latency(0.0)

    # 1. Submit message A -> B
    with get_db_session(test_db) as session:
        msg, is_new = MessagingService.submit_message(
            session=session,
            client_idempotency_key="test-key-clean-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="CLASSIFIED_REPORT_ALPHA: Nominal transmission.",
        )
        assert is_new is True
        assert msg.current_state == MessageState.QUEUED.value
        msg_id = msg.message_id

    # 2. Run queue worker
    worker = QueueWorker(worker_id="test-worker-01", db_path=test_db)
    processed = worker.run_once()
    assert processed == 1

    # 3. Verify state and records in DB
    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value
        assert msg.sender_acknowledged_at is not None
        assert msg.receiver_stored_at is not None
        assert msg.attempt_count == 1
        assert msg.signed_ack_receipt is not None
        assert msg.signed_ack_receipt.startswith("ACK-SIG:")
        assert msg.to_dict()["signed_ack_receipt"] == msg.signed_ack_receipt

        # Check durable receiver inbox
        inbox_item = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b", message_id=msg_id)
            .first()
        )
        assert inbox_item is not None
        assert inbox_item.integrity_status == "VALID"
        assert inbox_item.processing_status == "STORED"

        # Check durable acknowledgement
        ack = session.query(Acknowledgement).filter_by(original_message_id=msg_id).first()
        assert ack is not None
        assert ack.ack_type == "RECEIVED"
        assert ack.validation_status == "VALID"
        assert ack.delivery_status == "DELIVERED"
        assert ack.origin_endpoint == "endpoint-b"
        assert ack.destination_endpoint == "endpoint-a"

        # Check delivery attempt record
        attempts = session.query(DeliveryAttempt).filter_by(message_id=msg_id).all()
        assert len(attempts) == 1
        assert attempts[0].result == "SUCCESS"
        assert attempts[0].transport_state == "ONLINE"
        assert attempts[0].acknowledgement_state == "ACK_RECEIVED"

        # Check message event audit timeline
        events = session.query(MessageEvent).filter_by(message_id=msg_id).all()
        event_types = [e.event_type for e in events]
        assert "MESSAGE_ENQUEUED" in event_types
        assert "DELIVERY_ATTEMPT_STARTED" in event_types
        assert "INBOX_PERSISTED" in event_types
        assert "ACK_GENERATED" in event_types
        assert "ACK_VALIDATED_DELIVERED" in event_types


# ==============================================================================
# TEST 2: OFFLINE TRANSPORT HANDLING AND RESUMPTION
# ==============================================================================
def test_02_offline_transport_and_resumption(test_db):
    """Verifies that when transport is offline, messages remain in queue/failed retryable
    and do NOT show in recipient inbox until transport is restored and processed."""
    transport.reset()
    transport.set_online(False)  # Transport is cut off

    # 1. Enqueue message while link is down
    with get_db_session(test_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="test-key-offline-02",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="EMERGENCY_DISPATCH: Link degraded.",
        )
        msg_id = msg.message_id

    worker = QueueWorker(worker_id="test-worker-02", db_path=test_db)

    # 2. Worker attempts delivery while transport is offline
    processed = worker.run_once()
    assert processed == 1  # Processed the attempt

    # Message should be FAILED_RETRYABLE, inbox should still be empty!
    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.FAILED_RETRYABLE.value
        assert msg.last_error_code == "TRANSPORT_OFFLINE"

        inbox_count = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b", message_id=msg_id)
            .count()
        )
        assert inbox_count == 0, "Recipient must NOT receive message while transport is offline"

        # Force next_attempt_at to past to simulate backoff elapsing
        msg.next_attempt_at = utcnow() - timedelta(seconds=1)
        session.commit()

    # 3. Restore transport and run worker again
    transport.set_online(True)
    worker.run_once()

    # 4. Message should now be delivered and verified in inbox
    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value
        assert msg.attempt_count == 2

        inbox_count = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b", message_id=msg_id)
            .count()
        )
        assert inbox_count == 1


# ==============================================================================
# TEST 3: CLIENT DISCONNECTED FROM BACKEND (OUTBOX QUEUEING & RESYNC)
# ==============================================================================
def test_03_client_disconnected_from_backend(client, test_db):
    """Simulates client outbox lifecycle:
    When backend connection is initially unavailable/interrupted, client keeps
    message in local outbox (LOCAL_QUEUED). Once backend is accessible, client
    syncs record, receives HTTP 201 QUEUED, and reconciles local record."""
    client_outbox = {}

    def client_compose_message(cid, text):
        # Client creates local record
        client_outbox[cid] = {
            "client_idempotency_key": cid,
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": text,
            "local_status": "LOCAL_QUEUED",
            "sync_attempts": 0,
            "backend_id": None,
        }

    def client_attempt_sync(cid, simulate_offline=False):
        record = client_outbox[cid]
        record["sync_attempts"] += 1
        if simulate_offline:
            # Simulated network error / unreachable backend
            record["local_status"] = "SYNC_FAILED_OFFLINE"
            return False, "CONNECTION_REFUSED"

        resp = client.post(
            "/api/v1/messages",
            json={
                "client_idempotency_key": record["client_idempotency_key"],
                "sender_endpoint_id": record["sender_endpoint_id"],
                "recipient_endpoint_id": record["recipient_endpoint_id"],
                "payload": record["payload"],
            },
        )
        if resp.status_code in (200, 201):
            data = resp.get_json()
            record["local_status"] = "SYNCED_TO_BACKEND"
            record["backend_id"] = data["message_id"]
            record["backend_state"] = data["current_state"]
            return True, data
        return False, resp.get_json()

    # Step 1: Client drafts and queues offline
    cid = "client-outbox-uuid-03"
    client_compose_message(cid, "Field operator offline note.")
    assert client_outbox[cid]["local_status"] == "LOCAL_QUEUED"

    # Step 2: Sync fails when disconnected
    success, err = client_attempt_sync(cid, simulate_offline=True)
    assert success is False
    assert client_outbox[cid]["local_status"] == "SYNC_FAILED_OFFLINE"
    assert client_outbox[cid]["sync_attempts"] == 1

    # Step 3: Backend connection restored; resync succeeds
    success, data = client_attempt_sync(cid, simulate_offline=False)
    assert success is True
    assert client_outbox[cid]["local_status"] == "SYNCED_TO_BACKEND"
    assert client_outbox[cid]["backend_id"] is not None
    assert client_outbox[cid]["backend_state"] == "QUEUED"


# ==============================================================================
# TEST 4: BACKEND RESTART WITH PENDING MESSAGES
# ==============================================================================
def test_04_backend_restart_pending_messages(test_db):
    """Verifies that messages enqueued when worker is completely stopped survive
    application and system restarts, and are processed cleanly once worker starts."""
    transport.reset()
    transport.set_online(True)

    msg_ids = []
    # 1. Enqueue 3 messages while worker is dormant
    with get_db_session(test_db) as session:
        for i in range(3):
            msg, _ = MessagingService.submit_message(
                session=session,
                client_idempotency_key=f"restart-key-{i}",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"BATTERY_STATUS_PACKET #{i}",
            )
            msg_ids.append(msg.message_id)

    # Verify all 3 are stored in QUEUED state
    with get_db_session(test_db) as session:
        queued_count = (
            session.query(Message)
            .filter(Message.message_id.in_(msg_ids), Message.current_state == "QUEUED")
            .count()
        )
        assert queued_count == 3

    # 2. Simulate complete restart: instantiate brand new worker instance
    restarted_worker = QueueWorker(worker_id="restarted-worker-04", db_path=test_db)
    while restarted_worker.run_once() > 0:
        pass

    # 3. Verify all 3 messages reached DELIVERED
    with get_db_session(test_db) as session:
        delivered_count = (
            session.query(Message)
            .filter(Message.message_id.in_(msg_ids), Message.current_state == "DELIVERED")
            .count()
        )
        assert delivered_count == 3


# ==============================================================================
# TEST 5: WORKER INTERRUPTION AND LEASE RECLAMATION
# ==============================================================================
def test_05_worker_interruption_and_lease_reclamation(test_db):
    """Verifies that if a worker process crashes or is killed mid-delivery (leaving
    a message in SENDING state), the stale lease is safely reclaimed and redelivered."""
    transport.reset()
    transport.set_online(True)

    # 1. Enqueue message
    with get_db_session(test_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="lease-reclaim-key-05",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="CRITICAL_PAYLOAD_UNCONFIRMED",
        )
        msg_id = msg.message_id

    # 2. Simulate worker 1 crashing while holding lease
    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        msg.current_state = MessageState.SENDING.value
        msg.worker_lease_id = "crashed-worker-pid-888"
        # Set lease expiry to 10 seconds in the past
        msg.lease_expires_at = utcnow() - timedelta(seconds=10)
        session.commit()

    # 3. Reclaim stale leases via RetryPolicy
    with get_db_session(test_db) as session:
        reclaimed = RetryPolicy.reclaim_stale_leases(session, lease_timeout_seconds=5.0)
        assert reclaimed == 1
        session.commit()

    # 4. Check message is returned to FAILED_RETRYABLE with lease cleared
    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.FAILED_RETRYABLE.value
        assert msg.worker_lease_id is None
        assert msg.last_error_code == "LEASE_EXPIRED"

        # Check audit event
        event = (
            session.query(MessageEvent)
            .filter_by(message_id=msg_id, event_type="WORKER_LEASE_RECLAIMED")
            .first()
        )
        assert event is not None

    # 5. Worker 2 picks up the reclaimed message and completes delivery
    worker2 = QueueWorker(worker_id="surviving-worker-05", db_path=test_db)
    worker2.run_once()

    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value


# ==============================================================================
# TEST 6: DUPLICATE SUBMISSION / IDEMPOTENCY
# ==============================================================================
def test_06_duplicate_submission_idempotency(test_db):
    """Verifies that submitting the exact same payload and client_idempotency_key
    returns the existing canonical record and does not create duplicate messages."""
    idempotency_key = "idempotent-unique-test-key-06"

    with get_db_session(test_db) as session:
        # First submission
        msg1, is_new1 = MessagingService.submit_message(
            session=session,
            client_idempotency_key=idempotency_key,
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="NAV_UPDATE_WAYPOINT_7",
        )
        assert is_new1 is True
        msg1_id = msg1.message_id

        # Second submission (identical idempotency key and sender)
        msg2, is_new2 = MessagingService.submit_message(
            session=session,
            client_idempotency_key=idempotency_key,
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="NAV_UPDATE_WAYPOINT_7",
        )
        assert is_new2 is False
        assert msg2.message_id == msg1_id

        # Verify only 1 message row exists in DB
        total_rows = (
            session.query(Message)
            .filter_by(client_idempotency_key=idempotency_key)
            .count()
        )
        assert total_rows == 1


# ==============================================================================
# TEST 7: LOST ACKNOWLEDGEMENT HANDLING
# ==============================================================================
def test_07_lost_acknowledgement_handling(test_db):
    """Verifies that when receiver stores message but ACK is dropped on return path:
    1. Worker retries.
    2. Receiver detects duplicate delivery and does NOT duplicate inbox item.
    3. Receiver re-issues existing durable ACK.
    4. Sender receives ACK and marks message DELIVERED."""
    transport.reset()
    transport.set_online(True)

    with get_db_session(test_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="lost-ack-key-07",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="TELEMETRY_PAYLOAD: ACK drop test.",
        )
        msg_id = msg.message_id

    # Configure transport to drop the ACK for this specific message on first try
    transport.drop_ack(msg_id)

    worker = QueueWorker(worker_id="test-worker-07", db_path=test_db)

    # Attempt 1: Forward delivery succeeds, return ACK is dropped
    worker.run_once()

    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.AWAITING_ACK.value
        assert msg.last_error_code == "ACK_LOST"

        # Receiver should already have the message in inbox!
        inbox_count = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b", message_id=msg_id)
            .count()
        )
        assert inbox_count == 1, "Receiver must store payload even if return ACK is lost"

        # Advance next_attempt_at to now for retry
        msg.next_attempt_at = utcnow() - timedelta(seconds=1)
        session.commit()

    # Attempt 2: Worker retries delivery
    worker.run_once()

    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value

        # Inbox must STILL have exactly 1 item (NO duplicate inbox rows!)
        inbox_count = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b", message_id=msg_id)
            .count()
        )
        assert inbox_count == 1

        # Audit events should show DUPLICATE_DELIVERY_IGNORED
        dup_event = (
            session.query(MessageEvent)
            .filter_by(message_id=msg_id, event_type="DUPLICATE_DELIVERY_IGNORED")
            .first()
        )
        assert dup_event is not None


# ==============================================================================
# TEST 8: TEMPORARY DELIVERY FAILURE AND EXPONENTIAL BACKOFF
# ==============================================================================
def test_08_temporary_delivery_failure_backoff(test_db):
    """Verifies that transient errors trigger exponential backoff scheduling."""
    transport.reset()
    transport.set_online(True)

    with get_db_session(test_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="backoff-test-key-08",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="ROUTING_TABLE_BROADCAST",
        )
        msg_id = msg.message_id

    # Inject temporary packet drop on attempt 1
    transport.drop_message(msg_id)

    worker = QueueWorker(worker_id="test-worker-08", db_path=test_db)
    worker.run_once()

    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.FAILED_RETRYABLE.value
        assert msg.attempt_count == 1
        assert msg.last_error_code == "PACKET_DROPPED"
        # next_attempt_at should be in the future
        assert msg.next_attempt_at > utcnow() - timedelta(seconds=1)

        # Advance next_attempt_at to now
        msg.next_attempt_at = utcnow() - timedelta(seconds=1)
        session.commit()

    # Attempt 2: Packet succeeds
    worker.run_once()

    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value
        assert msg.attempt_count == 2


# ==============================================================================
# TEST 9: RETRY LIMIT EXHAUSTION -> FAILED_FINAL
# ==============================================================================
def test_09_retry_limit_exhausted(test_db):
    """Verifies that after max attempts are exhausted, message transitions
    to FAILED_FINAL and is no longer queued for delivery."""
    transport.reset()
    transport.set_online(False)  # Always fail transmission

    with get_db_session(test_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="retry-limit-key-09",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="PERSISTENT_UNREACHABLE_NODE",
        )
        msg_id = msg.message_id

    worker = QueueWorker(worker_id="test-worker-09", db_path=test_db, max_attempts=3)

    # Exhaust all 3 attempts
    for expected_attempt in range(1, 4):
        worker.run_once()
        with get_db_session(test_db) as session:
            msg = session.query(Message).filter_by(message_id=msg_id).first()
            assert msg.attempt_count == expected_attempt
            if expected_attempt < 3:
                assert msg.current_state == MessageState.FAILED_RETRYABLE.value
                msg.next_attempt_at = utcnow() - timedelta(seconds=1)
                session.commit()

    # Check terminal failure state
    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.FAILED_FINAL.value
        assert msg.last_error_code == "RETRY_LIMIT_EXHAUSTED"

        # Check audit event
        event = (
            session.query(MessageEvent)
            .filter_by(message_id=msg_id, event_type="RETRY_LIMIT_EXHAUSTED")
            .first()
        )
        assert event is not None

    # Subsequent worker runs must NOT pick up this message
    processed = worker.run_once()
    assert processed == 0


# ==============================================================================
# TEST 10: MESSAGE EXPIRY BEFORE DELIVERY
# ==============================================================================
def test_10_message_expiry_before_delivery(test_db):
    """Verifies that a message with an expired TTL transitions to EXPIRED
    and is never delivered to the recipient."""
    transport.reset()
    transport.set_online(False)

    with get_db_session(test_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="expiry-key-10",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="TIME_SENSITIVE_TARGET_LOCK",
            expires_in_seconds=10,
        )
        msg_id = msg.message_id

        # Artificially set expires_at in the past
        msg.expires_at = utcnow() - timedelta(seconds=60)
        session.commit()

    worker = QueueWorker(worker_id="test-worker-10", db_path=test_db)
    worker.run_once()

    # Verify message is marked EXPIRED and never delivered
    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.EXPIRED.value
        assert msg.last_error_code == "EXPIRED"

        inbox_count = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b", message_id=msg_id)
            .count()
        )
        assert inbox_count == 0


# ==============================================================================
# TEST 11: DUPLICATE RECEIVER DELIVERY DIRECT INGESTION
# ==============================================================================
def test_11_duplicate_receiver_delivery(test_db):
    """Directly tests receiver ingestion logic: duplicate delivery calls
    produce exactly 1 inbox item and identical receipt acknowledgements."""
    with get_db_session(test_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="direct-rx-key-11",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="BEACON_HANDSHAKE_PACKET",
        )

        # Call 1: First arrival
        is_new1, ack1 = AckManager.process_incoming_at_receiver(session, msg)
        assert is_new1 is True
        assert ack1 is not None

        # Call 2: Duplicate arrival
        is_new2, ack2 = AckManager.process_incoming_at_receiver(session, msg)
        assert is_new2 is False
        assert ack2.ack_id == ack1.ack_id

        # Call 3: Another duplicate arrival
        is_new3, ack3 = AckManager.process_incoming_at_receiver(session, msg)
        assert is_new3 is False
        assert ack3.ack_id == ack1.ack_id

        # Query inbox: exactly 1 row
        inbox_rows = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b", message_id=msg.message_id)
            .all()
        )
        assert len(inbox_rows) == 1


# ==============================================================================
# TEST 12: INVALID MESSAGE AND ACK VALIDATION
# ==============================================================================
def test_12_invalid_message_and_ack_validation(test_db):
    """Verifies that invalid payloads, mismatched endpoints, corrupted ACKs,
    and illegal FSM transitions are rejected with descriptive errors."""
    with get_db_session(test_db) as session:
        # 1. Empty payload
        with pytest.raises(ValueError, match="Message payload cannot be empty"):
            MessagingService.submit_message(
                session=session,
                client_idempotency_key="err-key-empty",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload="",
            )

        # 2. Oversized payload
        oversized = "X" * (MAX_PAYLOAD_BYTES + 10)
        with pytest.raises(ValueError, match="exceeds maximum size"):
            MessagingService.submit_message(
                session=session,
                client_idempotency_key="err-key-oversized",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=oversized,
            )

        # 3. Invalid endpoints
        with pytest.raises(ValueError, match="Sender endpoint 'endpoint-z' does not exist"):
            MessagingService.submit_message(
                session=session,
                client_idempotency_key="err-key-bad-sender",
                sender_endpoint_id="endpoint-z",
                recipient_endpoint_id="endpoint-b",
                payload="Test payload",
            )

        # 4. Illegal FSM transition
        with pytest.raises(InvalidStateTransitionError):
            validate_transition(MessageState.DRAFT, MessageState.DELIVERED)

        with pytest.raises(InvalidStateTransitionError):
            validate_transition(MessageState.DELIVERED, MessageState.QUEUED)

        # 5. Corrupted ACK validation
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="corrupt-ack-key",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="Valid payload",
        )
        corrupted_ack = Acknowledgement(
            ack_id="corrupt-ack-id",
            original_message_id="mismatched-message-id",
            ack_type="RECEIVED",
            origin_endpoint="endpoint-b",
            destination_endpoint="endpoint-a",
        )
        with pytest.raises(ValueError, match="ACK message ID mismatch"):
            AckManager.process_ack_at_sender(session, msg, corrupted_ack)


# ==============================================================================
# TEST 13: TWO-WORKER CONCURRENCY RACE CONDITION PROTECTION
# ==============================================================================
def test_13_two_worker_concurrency_race_condition(test_db):
    """Verifies that two concurrent worker processes scanning the queue
    do not double-deliver or lease collision the same message."""
    transport.reset()
    transport.set_online(True)
    transport.set_latency(0.01)  # 10ms artificial delay to test concurrency window

    # Enqueue 6 messages
    with get_db_session(test_db) as session:
        for i in range(6):
            MessagingService.submit_message(
                session=session,
                client_idempotency_key=f"race-test-key-{i}",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"CONCURRENT_PACKET_{i}",
            )

    worker_a = QueueWorker(worker_id="worker-thread-A", db_path=test_db, poll_interval=0.01)
    worker_b = QueueWorker(worker_id="worker-thread-B", db_path=test_db, poll_interval=0.01)

    def worker_loop(w):
        processed_total = 0
        for _ in range(10):
            p = w.run_once()
            processed_total += p
            if p == 0:
                time.sleep(0.02)
        return processed_total

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_a = executor.submit(worker_loop, worker_a)
        f_b = executor.submit(worker_loop, worker_b)
        count_a = f_a.result()
        count_b = f_b.result()

    # All 6 messages must be delivered
    with get_db_session(test_db) as session:
        delivered_count = (
            session.query(Message)
            .filter(Message.current_state == MessageState.DELIVERED.value)
            .count()
        )
        assert delivered_count == 6

        # Inbox must have exactly 6 items (no duplicates)
        inbox_count = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b")
            .count()
        )
        assert inbox_count == 6
        assert count_a + count_b == 6


# ==============================================================================
# TEST 14: USER-INTERFACE PERSISTENCE AND STATUS RECONCILIATION
# ==============================================================================
def test_14_user_interface_persistence_and_status_reconciliation(client, test_db):
    """Verifies that REST API endpoints accurately serve the UI for:
    - Endpoint status and listing
    - Local outbox ingestion
    - Queue statistics
    - Message inspection and timeline audit events
    - Recipient inbox queries
    - Simulation transport toggles."""
    transport.reset()
    transport.set_online(True)

    # 1. Health check
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "HEALTHY"

    # 2. Endpoints listing
    res = client.get("/api/v1/endpoints")
    assert res.status_code == 200
    endpoints = res.get_json()
    ep_ids = [e["endpoint_id"] for e in endpoints]
    assert "endpoint-a" in ep_ids
    assert "endpoint-b" in ep_ids

    # 3. Submit message via API
    res = client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "ui-recon-key-14",
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "UI_RECONCILIATION_REPORT",
            "priority": 2,
        },
    )
    assert res.status_code == 201
    msg_data = res.get_json()
    msg_id = msg_data["message_id"]
    assert msg_data["current_state"] == "QUEUED"

    # 4. Check queue stats
    res = client.get("/api/v1/queue/stats")
    assert res.status_code == 200
    stats = res.get_json()
    assert stats["queued_count"] >= 1

    # 5. Run worker to deliver message
    worker = QueueWorker(worker_id="test-ui-worker-14", db_path=test_db)
    worker.run_once()

    # 6. Reconcile message status via API
    res = client.get(f"/api/v1/messages/{msg_id}")
    assert res.status_code == 200
    updated_data = res.get_json()
    assert updated_data["current_state"] == "DELIVERED"
    assert updated_data["sender_acknowledged_at"] is not None

    # 7. Check audit timeline events via API
    res = client.get(f"/api/v1/messages/{msg_id}/events")
    assert res.status_code == 200
    events = res.get_json()
    assert len(events) >= 4
    event_types = [e["event_type"] for e in events]
    assert "MESSAGE_ENQUEUED" in event_types
    assert "ACK_VALIDATED_DELIVERED" in event_types

    # 8. Check recipient inbox via API
    res = client.get("/api/v1/endpoints/endpoint-b/inbox")
    assert res.status_code == 200
    inbox = res.get_json()
    assert any(item["message_id"] == msg_id for item in inbox)

    # 9. Check sender outbox via API
    res = client.get("/api/v1/endpoints/endpoint-a/outbox")
    assert res.status_code == 200
    outbox = res.get_json()
    outbox_item = next(m for m in outbox if m["message_id"] == msg_id)
    assert outbox_item["current_state"] == "DELIVERED"

    # 10. Check simulation transport API controls
    res = client.get("/api/v1/sim/transport")
    assert res.status_code == 200
    assert res.get_json()["is_online"] is True

    res = client.post("/api/v1/sim/transport", json={"is_online": False, "latency_ms": 50})
    assert res.status_code == 200
    assert res.get_json()["is_online"] is False
    assert res.get_json()["latency_ms"] == 50.0


# ==============================================================================
# TEST 21: SIGNED ACK RECEIPT RECONCILIATION & SERIALIZATION
# ==============================================================================
def test_21_signed_ack_receipt_reconciliation(test_db):
    """Verifies that upon ACK arrival at the sender, message.signed_ack_receipt
    is populated with the cryptographic receipt signature, properly serialized
    in to_dict(), and persists to the SQLite database."""
    transport.reset()
    transport.set_online(True)

    with get_db_session(test_db) as session:
        msg, is_new = MessagingService.submit_message(
            session=session,
            client_idempotency_key="receipt-test-key-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="CLASSIFIED_PAYLOAD_FOR_RECEIPT_VERIFICATION",
        )
        assert is_new is True
        msg_id = msg.message_id
        assert msg.signed_ack_receipt is None
        assert msg.to_dict()["signed_ack_receipt"] is None

        # Simulate receiver arrival and ACK generation
        is_new, ack = AckManager.process_incoming_at_receiver(session, msg)
        assert is_new is True
        assert ack is not None

        # Simulate worker picking up message for transmission
        msg.current_state = MessageState.SENDING.value

        # Reconcile ACK at sender
        transitioned = AckManager.process_ack_at_sender(session, msg, ack)
        assert transitioned is True
        assert msg.current_state == MessageState.DELIVERED.value
        assert msg.signed_ack_receipt is not None
        assert len(msg.signed_ack_receipt) > 10
        assert msg.to_dict()["signed_ack_receipt"] == msg.signed_ack_receipt

    # Verify persistence across a fresh session
    with get_db_session(test_db) as session:
        persisted_msg = session.query(Message).filter_by(message_id=msg_id).one()
        assert persisted_msg.current_state == MessageState.DELIVERED.value
        assert persisted_msg.signed_ack_receipt is not None
        assert persisted_msg.to_dict()["signed_ack_receipt"] == persisted_msg.signed_ack_receipt


# ==============================================================================
# TEST 22: RECIPIENT INBOX REST QUERY & 4-STAGE AUDIT TIMELINE SEQUENCE
# ==============================================================================
def test_22_recipient_inbox_and_timeline_events(client, test_db):
    """Verifies that recipient inbox queries (/api/v1/endpoints/<id>/inbox) return
    durable storage records and that message audit events track the complete
    chronological sequence:
    MESSAGE_ENQUEUED -> LEASE_ACQUIRED -> INBOX_PERSISTED -> ACK_VALIDATED_DELIVERED."""
    transport.reset()
    transport.set_online(True)

    # 1. Enqueue message from Station Alpha to Station Bravo
    payload_content = "TACTICAL_REPORT_PHASE2_VERIFICATION"
    res = client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "phase2-timeline-test-key-01",
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": payload_content,
            "message_type": "STATUS_REPORT",
            "priority": 3,
        },
    )
    assert res.status_code == 201
    msg_data = res.get_json()
    msg_id = msg_data["message_id"]
    assert msg_data["current_state"] == "QUEUED"

    # 2. Execute worker to process and deliver queue
    worker = QueueWorker(worker_id="test-phase2-timeline-worker", db_path=test_db)
    worker.run_once()

    # 3. Confirm terminal delivery state and signed receipt at sender
    res = client.get(f"/api/v1/messages/{msg_id}")
    assert res.status_code == 200
    delivered_data = res.get_json()
    assert delivered_data["current_state"] == "DELIVERED"
    assert delivered_data["signed_ack_receipt"] is not None
    assert "ACK-SIG:" in delivered_data["signed_ack_receipt"]

    # 4. Verify true recipient inbox durable query for Station Bravo (UI-02)
    res = client.get("/api/v1/endpoints/endpoint-b/inbox")
    assert res.status_code == 200
    inbox_items = res.get_json()
    matching_inbox = next((item for item in inbox_items if item["message_id"] == msg_id), None)
    assert matching_inbox is not None, f"Message {msg_id} was not found in endpoint-b inbox"
    assert matching_inbox["recipient_endpoint_id"] == "endpoint-b"
    assert matching_inbox["sender_endpoint_id"] == "endpoint-a"
    assert matching_inbox["payload"] == payload_content
    assert matching_inbox["stored_at"] is not None
    assert matching_inbox["integrity_status"] == "VALID"
    assert matching_inbox["signed_ack_receipt"] == delivered_data["signed_ack_receipt"]

    # 5. Verify 4-stage chronological lifecycle timeline events (UI-03)
    res = client.get(f"/api/v1/messages/{msg_id}/events")
    assert res.status_code == 200
    events = res.get_json()
    assert len(events) >= 4

    event_types = [e["event_type"] for e in events]
    assert "MESSAGE_ENQUEUED" in event_types
    assert ("DELIVERY_ATTEMPT_STARTED" in event_types or "LEASE_ACQUIRED" in event_types)
    assert "INBOX_PERSISTED" in event_types
    assert "ACK_VALIDATED_DELIVERED" in event_types

    idx_enqueue = event_types.index("MESSAGE_ENQUEUED")
    idx_lease = event_types.index("DELIVERY_ATTEMPT_STARTED") if "DELIVERY_ATTEMPT_STARTED" in event_types else event_types.index("LEASE_ACQUIRED")
    idx_inbox = event_types.index("INBOX_PERSISTED")
    idx_ack = event_types.index("ACK_VALIDATED_DELIVERED")

    assert idx_enqueue < idx_lease < idx_inbox < idx_ack, (
        f"Lifecycle events are not in expected order: {event_types}"
    )

    # 6. Verify signed receipt is captured in terminal event details
    ack_event = next(e for e in events if e["event_type"] == "ACK_VALIDATED_DELIVERED")
    assert "signed_receipt" in ack_event["details"]
    assert ack_event["details"]["signed_receipt"] == delivered_data["signed_ack_receipt"]


# ==============================================================================
# TEST 23: TACTICAL PRESETS & SINGLE-SHOT ARMED FAULTS (FLT-01, FLT-04)
# ==============================================================================
def test_23_presets_and_single_shot_faults(client, test_db):
    """Verifies that tactical presets configure channel impairment matrix correctly,
    and single-shot armed faults (drop message, drop ACK) auto-disarm immediately
    after firing once."""
    transport.reset()

    # 1. Preset Application via REST API
    res = client.post("/api/v1/sim/transport", json={"preset": "URBAN_JAMMING"})
    assert res.status_code == 200
    st = res.get_json()
    assert st["active_preset"] == "URBAN_JAMMING"
    assert st["latency_ms"] == 50.0
    assert st["drop_message_prob"] == 0.3
    assert st["drop_ack_prob"] == 0.1

    res = client.post("/api/v1/sim/transport", json={"preset": "AIR_GAP"})
    assert res.status_code == 200
    st = res.get_json()
    assert st["active_preset"] == "AIR_GAP"
    assert st["is_online"] is False

    res = client.post("/api/v1/sim/transport", json={"preset": "NOMINAL"})
    assert res.status_code == 200
    st = res.get_json()
    assert st["active_preset"] == "NOMINAL"
    assert st["is_online"] is True
    assert st["latency_ms"] == 0.0
    assert st["drop_message_prob"] == 0.0
    assert st["drop_ack_prob"] == 0.0

    # 2. Single-Shot Message Drop Verification
    res = client.post("/api/v1/sim/faults", json={"action": "arm_drop_message"})
    assert res.status_code == 200
    fault_resp = res.get_json()
    assert fault_resp["status"] == "fault_armed"
    assert fault_resp["armed_faults"]["drop_message"] is True
    assert transport.arm_drop_next_message is True

    # Submit Packet 1 (should be dropped)
    res = client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "p23-drop-pkt-1",
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "SINGLE_SHOT_DROP_PAYLOAD_1",
        },
    )
    assert res.status_code == 201
    msg1_id = res.get_json()["message_id"]

    worker = QueueWorker(worker_id="test-worker-23", db_path=test_db)
    worker.run_once()

    # Verify msg 1 failed with PACKET_DROPPED and transport auto-disarmed
    with get_db_session(test_db) as session:
        msg1 = session.query(Message).filter_by(message_id=msg1_id).first()
        assert msg1.current_state == MessageState.FAILED_RETRYABLE.value
        assert msg1.last_error_code == "PACKET_DROPPED"

    assert transport.arm_drop_next_message is False
    assert client.get("/api/v1/sim/transport").get_json()["armed_faults"]["drop_message"] is False

    # Submit Packet 2 (should succeed without drop)
    res = client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "p23-clean-pkt-2",
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "SINGLE_SHOT_CLEAN_PAYLOAD_2",
        },
    )
    assert res.status_code == 201
    msg2_id = res.get_json()["message_id"]

    worker.run_once()

    with get_db_session(test_db) as session:
        msg2 = session.query(Message).filter_by(message_id=msg2_id).first()
        assert msg2.current_state == MessageState.DELIVERED.value

    # 3. Single-Shot ACK Drop Verification
    res = client.post("/api/v1/sim/faults", json={"action": "arm_drop_ack"})
    assert res.status_code == 200
    assert transport.arm_drop_next_ack is True

    res = client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": "p23-ack-drop-pkt-3",
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "SINGLE_SHOT_ACK_DROP_PAYLOAD_3",
        },
    )
    assert res.status_code == 201
    msg3_id = res.get_json()["message_id"]

    worker.run_once()

    # Receiver stored the message in inbox, but sender is awaiting ACK
    with get_db_session(test_db) as session:
        msg3 = session.query(Message).filter_by(message_id=msg3_id).first()
        assert msg3.current_state == MessageState.AWAITING_ACK.value
        inbox_item = session.query(InboxItem).filter_by(message_id=msg3_id).first()
        assert inbox_item is not None

    # Armed flag auto-disarmed
    assert transport.arm_drop_next_ack is False


# ==============================================================================
# TEST 24: WORKER CRASH RECOVERY, LEASE RECLAMATION & STARTUP SWEEP (FLT-04)
# ==============================================================================
def test_24_lease_reclamation_and_startup_sweep(client, test_db):
    """Verifies that expired worker leases are safely reclaimed preserving worker
    metadata in audit logs, and stranded in-flight SENDING messages are swept on startup."""
    transport.reset()
    transport.set_online(True)

    # 1. Stale Lease Reclamation with Metadata Preservation
    with get_db_session(test_db) as session:
        msg1, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="p24-lease-key-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="CRASHED_WORKER_TEST_1",
        )
        msg1.current_state = MessageState.SENDING.value
        msg1.worker_lease_id = "worker-crashed-alpha"
        msg1.lease_expires_at = utcnow() - timedelta(seconds=15)
        session.commit()
        msg1_id = msg1.message_id

    # Call /api/v1/worker/reclaim
    res = client.post("/api/v1/worker/reclaim")
    assert res.status_code == 200
    assert res.get_json()["reclaimed_count"] >= 1

    with get_db_session(test_db) as session:
        msg1 = session.query(Message).filter_by(message_id=msg1_id).first()
        assert msg1.current_state == MessageState.FAILED_RETRYABLE.value
        assert msg1.worker_lease_id is None
        assert msg1.lease_expires_at is None
        assert msg1.last_error_code == "LEASE_EXPIRED"

        # Check audit event preserves metadata
        event = (
            session.query(MessageEvent)
            .filter_by(message_id=msg1_id, event_type="WORKER_LEASE_RECLAIMED")
            .first()
        )
        assert event is not None
        assert event.safe_metadata["previous_worker_id"] == "worker-crashed-alpha"
        assert event.safe_metadata["lease_expires_at"] is not None
        assert "lease expired" in event.safe_metadata["reason"].lower()

    # 2. Startup Stranded Sweep Verification
    with get_db_session(test_db) as session:
        msg2, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="p24-startup-sweep-02",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="STRANDED_STARTUP_SWEEP_PAYLOAD",
        )
        msg2.current_state = MessageState.SENDING.value
        msg2.worker_lease_id = "dead-worker-reboot"
        # Even if lease hasn't expired yet, process reboot sweep catches all SENDING messages
        msg2.lease_expires_at = utcnow() + timedelta(seconds=60)
        session.commit()
        msg2_id = msg2.message_id

    # Simulate process reboot startup sweep
    with get_db_session(test_db) as session:
        swept = RetryPolicy.recover_stranded_leases(session)
        assert swept >= 1

    with get_db_session(test_db) as session:
        msg2 = session.query(Message).filter_by(message_id=msg2_id).first()
        assert msg2.current_state == MessageState.FAILED_RETRYABLE.value
        assert msg2.worker_lease_id is None
        assert msg2.last_error_code == "LEASE_EXPIRED"

        event2 = (
            session.query(MessageEvent)
            .filter_by(message_id=msg2_id, event_type="WORKER_LEASE_RECLAIMED")
            .order_by(MessageEvent.timestamp.desc())
            .first()
        )
        assert event2 is not None
        assert event2.safe_metadata["startup_sweep"] is True
        assert event2.safe_metadata["previous_worker_id"] == "dead-worker-reboot"


# ==============================================================================
# TEST 25: RETRY QUOTA RESET ON MANUAL OPERATOR REQUEUE (FLT-04)
# ==============================================================================
def test_25_retry_quota_reset_on_manual_requeue(client, test_db):
    """Verifies that an operator-triggered manual retry on a permanently failed message
    resets attempt_count = 0, granting a fresh quota of 5 delivery attempts."""
    transport.reset()
    transport.set_online(True)

    # 1. Create a permanently exhausted message (5/5 failed attempts)
    with get_db_session(test_db) as session:
        msg, _ = MessagingService.submit_message(
            session=session,
            client_idempotency_key="p25-exhausted-quota-key",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="TERMINAL_FAILURE_REQUIRES_OPERATOR_OVERRIDE",
        )
        msg.current_state = MessageState.FAILED_FINAL.value
        msg.attempt_count = 5
        msg.last_error_code = "RETRY_LIMIT_EXHAUSTED"
        session.commit()
        msg_id = msg.message_id

    # 2. Operator requests manual retry via REST API
    res = client.post(f"/api/v1/messages/{msg_id}/retry")
    assert res.status_code == 200
    retried_data = res.get_json()
    assert retried_data["current_state"] == "QUEUED"
    assert retried_data["attempt_count"] == 0
    assert retried_data["retry_count"] == 0

    # 3. Worker leases and delivers the message successfully (Attempt 1 of 5)
    worker = QueueWorker(worker_id="test-worker-25", db_path=test_db)
    processed = worker.run_once()
    assert processed == 1

    with get_db_session(test_db) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value
        assert msg.attempt_count == 1
        assert msg.sender_acknowledged_at is not None



