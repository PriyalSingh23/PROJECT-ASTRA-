import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from app.core.database import get_db_context
from app.core.state_machine import MessageState
from app.models.message import Message
from app.models.inbox import InboxItem
from app.services.message_engine import MessageEngine
from app.services.worker import QueueWorker
from app.adapters.simulation import simulation_adapter


def test_01_successful_delivery_under_clean_conditions(test_db_url):
    simulation_adapter.reset()
    simulation_adapter.is_online = True

    # 1. Enqueue message
    with get_db_context(test_db_url) as session:
        msg, is_new = MessageEngine.submit_message(
            session=session,
            client_idempotency_key="clean-key-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="NOMINAL_TACTICAL_DATA",
        )
        assert is_new is True
        msg_id = msg.message_id

    # 2. Worker runs once
    worker = QueueWorker(worker_id="test-worker-01", db_url=test_db_url)
    processed = worker.run_once()
    assert processed == 1

    # 3. Verify state
    with get_db_context(test_db_url) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value
        assert msg.sender_acknowledged_at is not None
        assert msg.receiver_stored_at is not None
        assert msg.attempt_count == 1

        # Check receiver inbox
        inbox = session.query(InboxItem).filter_by(recipient_endpoint_id="endpoint-b").first()
        assert inbox is not None
        assert inbox.message_id == msg_id


def test_02_offline_transport_and_resumption(test_db_url):
    simulation_adapter.reset()
    simulation_adapter.is_online = False  # CUT LINK

    # 1. Enqueue message while offline
    with get_db_context(test_db_url) as session:
        msg, _ = MessageEngine.submit_message(
            session=session,
            client_idempotency_key="offline-key-02",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="OFFLINE_TEST_DATA",
        )
        msg_id = msg.message_id

    # 2. Worker runs while offline -> fails retryable
    worker = QueueWorker(worker_id="test-worker-02", db_url=test_db_url)
    worker.run_once()

    with get_db_context(test_db_url) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.FAILED_RETRYABLE.value
        assert msg.last_error_code == "TRANSPORT_OFFLINE"

    # 3. Restore link & reset retry timestamp to now
    simulation_adapter.is_online = True
    with get_db_context(test_db_url) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        msg.next_attempt_at = msg.created_at
        session.commit()

    # 4. Worker runs again -> delivers message
    worker.run_once()
    with get_db_context(test_db_url) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value


def test_03_lost_acknowledgement_recovery(test_db_url):
    simulation_adapter.reset()
    simulation_adapter.drop_ack_prob = 1.0  # DROP RETURN ACK

    with get_db_context(test_db_url) as session:
        msg, _ = MessageEngine.submit_message(
            session=session,
            client_idempotency_key="lost-ack-key-03",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="LOST_ACK_PAYLOAD",
        )
        msg_id = msg.message_id

    worker = QueueWorker(worker_id="test-worker-03", db_url=test_db_url)
    worker.run_once()

    # Receiver inbox MUST have stored the message, but sender is in AWAITING_ACK
    with get_db_context(test_db_url) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.AWAITING_ACK.value
        inbox_count = session.query(InboxItem).filter_by(recipient_endpoint_id="endpoint-b").count()
        assert inbox_count == 1

    # Restore ACK return link & retry
    simulation_adapter.drop_ack_prob = 0.0
    with get_db_context(test_db_url) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        msg.next_attempt_at = msg.created_at
        session.commit()

    worker.run_once()

    with get_db_context(test_db_url) as session:
        msg = session.query(Message).filter_by(message_id=msg_id).first()
        assert msg.current_state == MessageState.DELIVERED.value
        # Still exactly 1 inbox item (no duplicate created!)
        inbox_count = session.query(InboxItem).filter_by(recipient_endpoint_id="endpoint-b").count()
        assert inbox_count == 1


def test_04_two_worker_concurrency_race_condition(test_db_url):
    """Verifies that two concurrent worker processes scanning the queue
    do not double-deliver or lease collision the same message."""
    simulation_adapter.reset()
    simulation_adapter.is_online = True
    simulation_adapter.latency_ms = 10.0  # 10ms artificial delay

    # Enqueue 6 messages
    with get_db_context(test_db_url) as session:
        for i in range(6):
            MessageEngine.submit_message(
                session=session,
                client_idempotency_key=f"race-key-{i}",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=f"CONCURRENT_PACKET_{i}",
            )

    worker_a = QueueWorker(worker_id="thread-worker-A", db_url=test_db_url, poll_interval=0.01)
    worker_b = QueueWorker(worker_id="thread-worker-B", db_url=test_db_url, poll_interval=0.01)

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
    with get_db_context(test_db_url) as session:
        delivered_count = session.query(Message).filter_by(current_state=MessageState.DELIVERED.value).count()
        assert delivered_count == 6

        inbox_count = session.query(InboxItem).filter_by(recipient_endpoint_id="endpoint-b").count()
        assert inbox_count == 6
        assert count_a + count_b == 6


def test_05_rest_api_lifecycle(client):
    simulation_adapter.reset()

    # 1. Health check
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "HEALTHY"

    # 2. Submit message via REST
    key = f"api-key-{uuid.uuid4().hex[:8]}"
    res = client.post(
        "/api/v1/messages",
        json={
            "client_idempotency_key": key,
            "sender_endpoint_id": "endpoint-a",
            "recipient_endpoint_id": "endpoint-b",
            "payload": "REST_API_TACTICAL_PACKET",
            "priority": 3,
        },
    )
    assert res.status_code == 201
    msg_id = res.json()["message_id"]

    # 3. Check stats
    res = client.get("/api/v1/queue/stats")
    assert res.status_code == 200
    stats = res.json()
    assert stats["queued"] >= 1

    # 4. Check message detail
    res = client.get(f"/api/v1/messages/{msg_id}")
    assert res.status_code == 200
    assert res.json()["current_state"] == "QUEUED"

    # 5. Check events timeline
    res = client.get(f"/api/v1/messages/{msg_id}/events")
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "MESSAGE_ENQUEUED"
