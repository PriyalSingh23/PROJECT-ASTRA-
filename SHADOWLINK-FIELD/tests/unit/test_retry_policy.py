from datetime import timedelta
from app.core.database import get_db_context, utcnow
from app.core.state_machine import MessageState
from app.models.message import Message
from app.services.retry_scheduler import RetryScheduler


def test_exponential_backoff_computation():
    t1 = RetryScheduler.compute_next_attempt_at(1, base_delay=2.0, max_delay=60.0, jitter=0.0)
    t2 = RetryScheduler.compute_next_attempt_at(2, base_delay=2.0, max_delay=60.0, jitter=0.0)
    t3 = RetryScheduler.compute_next_attempt_at(3, base_delay=2.0, max_delay=60.0, jitter=0.0)
    now = utcnow()

    # Attempt 1: 2s delay
    diff1 = (t1 - now).total_seconds()
    assert 1.5 <= diff1 <= 2.5

    # Attempt 2: 4s delay
    diff2 = (t2 - now).total_seconds()
    assert 3.5 <= diff2 <= 4.5

    # Attempt 3: 8s delay
    diff3 = (t3 - now).total_seconds()
    assert 7.5 <= diff3 <= 8.5


def test_retryable_classification():
    assert RetryScheduler.is_retryable("TRANSPORT_OFFLINE") is True
    assert RetryScheduler.is_retryable("PACKET_DROPPED") is True
    assert RetryScheduler.is_retryable("ACK_LOST") is True
    assert RetryScheduler.is_retryable("RECIPIENT_NOT_FOUND") is False
    assert RetryScheduler.is_retryable("PAYLOAD_TOO_LARGE") is False


def test_stale_lease_reclamation(test_db_url):
    now = utcnow()
    with get_db_context(test_db_url) as session:
        # Create a message left in SENDING with an expired lease
        stale_msg = Message(
            client_idempotency_key="stale-test-key",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="RECOVERABLE_PAYLOAD",
            current_state=MessageState.SENDING.value,
            worker_lease_id="crashed-worker-99",
            lease_expires_at=now - timedelta(seconds=10),
            expires_at=now + timedelta(hours=1),
        )
        session.add(stale_msg)
        session.commit()

        reclaimed = RetryScheduler.reclaim_stale_leases(session, lease_timeout_sec=30.0)
        assert reclaimed == 1

        # Check refreshed state
        msg = session.query(Message).filter_by(client_idempotency_key="stale-test-key").first()
        assert msg.current_state == MessageState.FAILED_RETRYABLE.value
        assert msg.worker_lease_id is None
        assert msg.last_error_code == "LEASE_EXPIRED"
