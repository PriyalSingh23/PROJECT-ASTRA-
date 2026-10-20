from datetime import timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from messaging.models import (
    Endpoint,
    Message,
    InboxItem,
    MessageEvent,
    generate_uuid,
    utcnow,
)
from messaging.state_machine import MessageState, validate_transition

MAX_PAYLOAD_BYTES = 65536  # 64 KB limit for text payload


VALID_MESSAGE_TYPES = {
    "TEXT",
    "STATUS_REPORT",
    "CHECK_IN",
    "ASSISTANCE_REQUEST",
    "INCIDENT_UPDATE",
    "TASK_ASSIGNMENT",
    "TASK_ACK",
    "DEVICE_HEALTH",
    "GATEWAY_STATUS",
    "RECEIPT",
}


class MessagingService:
    """Core domain service for message submission, deduplication, cancellation, and retrieval."""

    @classmethod
    def submit_message(
        cls,
        session: Session,
        client_idempotency_key: str,
        sender_endpoint_id: str,
        recipient_endpoint_id: str,
        payload: str,
        message_type: str = "TEXT",
        incident_id: Optional[str] = None,
        expires_in_seconds: int = 86400,
        priority: int = 1,
    ) -> Tuple[Message, bool]:
        """Submits a message to the durable outbox/queue with client idempotency deduplication.
        
        Returns:
            (message, is_newly_created)
        """
        if not payload or not str(payload).strip():
            raise ValueError("Message payload cannot be empty")
        if len(str(payload).encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Message payload exceeds maximum size ({MAX_PAYLOAD_BYTES} bytes)")

        normalized_type = str(message_type).upper().strip()
        if normalized_type not in VALID_MESSAGE_TYPES:
            raise ValueError(f"Invalid message_type: '{message_type}'. Allowed types: {sorted(list(VALID_MESSAGE_TYPES))}")

        # Validate sender and recipient endpoints
        sender = session.query(Endpoint).filter_by(endpoint_id=sender_endpoint_id).first()
        if not sender or not sender.enabled:
            raise ValueError(f"Sender endpoint '{sender_endpoint_id}' does not exist or is disabled")

        recipient = session.query(Endpoint).filter_by(endpoint_id=recipient_endpoint_id).first()
        if not recipient or not recipient.enabled:
            raise ValueError(f"Recipient endpoint '{recipient_endpoint_id}' does not exist or is disabled")

        # Idempotency check: has this sender already submitted this idempotency key?
        existing_msg = (
            session.query(Message)
            .filter_by(
                sender_endpoint_id=sender_endpoint_id,
                client_idempotency_key=client_idempotency_key,
            )
            .first()
        )

        if existing_msg:
            # Idempotent return of the already-persisted message
            return existing_msg, False

        # Create new durable message record
        now = utcnow()
        expires_at = now + timedelta(seconds=max(5, expires_in_seconds))
        msg_id = generate_uuid()

        new_msg = Message(
            message_id=msg_id,
            client_idempotency_key=client_idempotency_key,
            sender_endpoint_id=sender_endpoint_id,
            recipient_endpoint_id=recipient_endpoint_id,
            message_type=normalized_type,
            incident_id=incident_id,
            payload=payload,
            created_at=now,
            expires_at=expires_at,
            priority=priority,
            current_state=MessageState.QUEUED.value,
            attempt_count=0,
            next_attempt_at=now,  # Ready for immediate queue pickup
            accepted_at=now,
        )
        session.add(new_msg)

        # Record enqueue event in immutable timeline
        event = MessageEvent(
            event_id=generate_uuid(),
            message_id=msg_id,
            event_type="MESSAGE_ENQUEUED",
            timestamp=now,
            source_endpoint=sender_endpoint_id,
            safe_metadata={
                "sender": sender_endpoint_id,
                "recipient": recipient_endpoint_id,
                "payload_length": len(payload),
                "expires_at": expires_at.isoformat(),
                "priority": priority,
            },
        )
        session.add(event)
        session.flush()

        return new_msg, True

    @classmethod
    def cancel_message(cls, session: Session, message_id: str) -> Message:
        """Cancels a queued or retryable message before delivery completes."""
        msg = session.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            raise ValueError(f"Message '{message_id}' not found")

        cur_st = MessageState(msg.current_state)
        validate_transition(cur_st, MessageState.CANCELLED, message_id)

        now = utcnow()
        msg.current_state = MessageState.CANCELLED.value
        msg.last_error_code = "CANCELLED"
        msg.last_error_at = now

        event = MessageEvent(
            event_id=generate_uuid(),
            message_id=msg.message_id,
            event_type="MESSAGE_CANCELLED",
            timestamp=now,
            source_endpoint=msg.sender_endpoint_id,
            safe_metadata={"action": "USER_MANUAL_CANCEL"},
            error_code="CANCELLED",
        )
        session.add(event)
        return msg

    @classmethod
    def retry_message(cls, session: Session, message_id: str) -> Message:
        """Manually triggers immediate re-queueing of a failed message."""
        msg = session.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            raise ValueError(f"Message '{message_id}' not found")

        cur_st = MessageState(msg.current_state)
        validate_transition(cur_st, MessageState.QUEUED, message_id)

        now = utcnow()
        msg.current_state = MessageState.QUEUED.value
        msg.attempt_count = 0  # CRITICAL: Reset attempt counter so message gets 5 fresh attempts
        msg.next_attempt_at = now
        msg.worker_lease_id = None
        msg.lease_expires_at = None

        event = MessageEvent(
            event_id=generate_uuid(),
            message_id=msg.message_id,
            event_type="MANUAL_RETRY_REQUESTED",
            timestamp=now,
            source_endpoint=msg.sender_endpoint_id,
            safe_metadata={"action": "USER_MANUAL_RETRY"},
        )
        session.add(event)
        return msg

    @classmethod
    def get_inbox_messages(cls, session: Session, endpoint_id: str) -> List[Dict[str, Any]]:
        """Retrieves all messages received in endpoint's inbox with original payload and stored timestamp."""
        results = (
            session.query(InboxItem, Message)
            .join(Message, InboxItem.message_id == Message.message_id)
            .filter(InboxItem.recipient_endpoint_id == endpoint_id)
            .order_by(InboxItem.stored_at.desc())
            .all()
        )

        inbox_list = []
        for item, msg in results:
            inbox_list.append({
                "inbox_id": item.inbox_id,
                "message_id": msg.message_id,
                "sender_endpoint_id": msg.sender_endpoint_id,
                "recipient_endpoint_id": msg.recipient_endpoint_id,
                "message_type": msg.message_type,
                "incident_id": msg.incident_id,
                "priority": msg.priority,
                "payload": msg.payload,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "stored_at": item.stored_at.isoformat() if item.stored_at else None,
                "integrity_status": item.integrity_status,
                "processing_status": item.processing_status,
                "current_state": msg.current_state,
                "signed_ack_receipt": msg.signed_ack_receipt,
            })
        return inbox_list

    @classmethod
    def get_outbox_messages(cls, session: Session, endpoint_id: str) -> List[Dict[str, Any]]:
        """Retrieves all messages sent from an endpoint."""
        messages = (
            session.query(Message)
            .filter_by(sender_endpoint_id=endpoint_id)
            .order_by(Message.created_at.desc())
            .all()
        )
        return [m.to_dict() for m in messages]

    @classmethod
    def get_queue_stats(cls, session: Session) -> Dict[str, Any]:
        """Calculates queue statistics across all message states."""
        from sqlalchemy import func
        stats = dict(
            session.query(Message.current_state, func.count(Message.message_id))
            .group_by(Message.current_state)
            .all()
        )

        total = sum(stats.values())
        pending = (
            stats.get(MessageState.QUEUED.value, 0)
            + stats.get(MessageState.SENDING.value, 0)
            + stats.get(MessageState.AWAITING_ACK.value, 0)
            + stats.get(MessageState.FAILED_RETRYABLE.value, 0)
        )

        last_delivery = (
            session.query(func.max(Message.sender_acknowledged_at))
            .filter(Message.current_state == MessageState.DELIVERED.value)
            .scalar()
        )

        return {
            "total_messages": total,
            "pending_message_count": pending,
            "queued": stats.get(MessageState.QUEUED.value, 0),
            "queued_count": stats.get(MessageState.QUEUED.value, 0),
            "sending": stats.get(MessageState.SENDING.value, 0),
            "awaiting_ack": stats.get(MessageState.AWAITING_ACK.value, 0),
            "delivered": stats.get(MessageState.DELIVERED.value, 0),
            "delivered_count": stats.get(MessageState.DELIVERED.value, 0),
            "failed_retryable": stats.get(MessageState.FAILED_RETRYABLE.value, 0),
            "failed_final": stats.get(MessageState.FAILED_FINAL.value, 0),
            "expired": stats.get(MessageState.EXPIRED.value, 0),
            "cancelled": stats.get(MessageState.CANCELLED.value, 0),
            "last_successful_delivery": last_delivery.isoformat() if last_delivery else None,
        }
