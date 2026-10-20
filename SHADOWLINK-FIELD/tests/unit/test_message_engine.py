import pytest
from app.core.database import get_db_context
from app.core.state_machine import MessageState
from app.models.message import Message
from app.models.inbox import InboxItem
from app.services.message_engine import MessageEngine


def test_idempotent_submission(test_db_url):
    with get_db_context(test_db_url) as session:
        msg1, is_new1 = MessageEngine.submit_message(
            session=session,
            client_idempotency_key="idempotency-key-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="ORIGINAL_PAYLOAD",
        )
        assert is_new1 is True
        msg1_id = msg1.message_id

        # Re-submit with same key
        msg2, is_new2 = MessageEngine.submit_message(
            session=session,
            client_idempotency_key="idempotency-key-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="ORIGINAL_PAYLOAD",
        )
        assert is_new2 is False
        assert msg2.message_id == msg1_id


def test_payload_size_enforcement(test_db_url):
    huge_payload = "X" * 70000  # Exceeds 64 KB limit
    with get_db_context(test_db_url) as session:
        with pytest.raises(ValueError) as exc:
            MessageEngine.submit_message(
                session=session,
                client_idempotency_key="too-big-key",
                sender_endpoint_id="endpoint-a",
                recipient_endpoint_id="endpoint-b",
                payload=huge_payload,
            )
        assert "exceeds maximum allowable limit" in str(exc.value)


def test_receiver_deduplication(test_db_url):
    with get_db_context(test_db_url) as session:
        msg, _ = MessageEngine.submit_message(
            session=session,
            client_idempotency_key="dedup-key-01",
            sender_endpoint_id="endpoint-a",
            recipient_endpoint_id="endpoint-b",
            payload="TEST_PACKET",
        )

        # First delivery to receiver
        is_new, ack1 = MessageEngine.process_incoming_at_receiver(session, msg)
        assert is_new is True
        assert ack1.ack_type == "RECEIVED"
        session.commit()

        # Re-delivery of same message
        is_new_again, ack2 = MessageEngine.process_incoming_at_receiver(session, msg)
        assert is_new_again is False
        assert ack2.ack_id == ack1.ack_id

        # Verify only 1 inbox item exists
        inbox_count = (
            session.query(InboxItem)
            .filter_by(recipient_endpoint_id="endpoint-b", message_id=msg.message_id)
            .count()
        )
        assert inbox_count == 1
