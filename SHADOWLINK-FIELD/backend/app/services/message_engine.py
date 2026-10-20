import hashlib
from datetime import datetime, timedelta
from typing import Tuple, Optional, List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import utcnow
from app.core.state_machine import MessageState, validate_transition
from app.models.endpoint import Endpoint
from app.models.message import Message
from app.models.inbox import InboxItem
from app.models.acknowledgement import Acknowledgement
from app.models.audit import MessageEvent
from app.models.delivery_attempt import DeliveryAttempt


class MessageEngine:
    """Core domain service for persistent messaging, deduplication, and ACK tracking."""

    @classmethod
    def submit_message(
        cls,
        session: Session,
        client_idempotency_key: str,
        sender_endpoint_id: str,
        recipient_endpoint_id: str,
        payload: str,
        message_type: str = "TACTICAL_TEXT",
        expires_in_seconds: int = 86400,
        priority: int = 2,
    ) -> Tuple[Message, bool]:
        """Durably persists an outgoing message before dispatch is attempted.
        Returns: (message, is_new)
        """
        # 1. Validate payload length
        payload_bytes = payload.encode("utf-8")
        if len(payload_bytes) > settings.MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"Payload size ({len(payload_bytes)} bytes) exceeds maximum allowable limit of {settings.MAX_PAYLOAD_BYTES} bytes."
            )

        # 2. Validate Endpoints
        sender = session.query(Endpoint).filter_by(endpoint_id=sender_endpoint_id).first()
        if not sender:
            raise ValueError(f"Sender endpoint '{sender_endpoint_id}' does not exist.")

        recipient = session.query(Endpoint).filter_by(endpoint_id=recipient_endpoint_id).first()
        if not recipient:
            raise ValueError(f"Recipient endpoint '{recipient_endpoint_id}' does not exist.")

        # 3. Idempotency Check: (sender_endpoint_id, client_idempotency_key)
        existing = (
            session.query(Message)
            .filter_by(
                sender_endpoint_id=sender_endpoint_id,
                client_idempotency_key=client_idempotency_key,
            )
            .first()
        )
        if existing:
            return existing, False

        # 4. Construct Message
        now = utcnow()
        expires_at = now + timedelta(seconds=expires_in_seconds)
        digest = hashlib.sha256(payload_bytes).hexdigest()

        message = Message(
            client_idempotency_key=client_idempotency_key,
            sender_endpoint_id=sender_endpoint_id,
            recipient_endpoint_id=recipient_endpoint_id,
            message_type=message_type,
            payload=payload,
            created_at=now,
            expires_at=expires_at,
            priority=priority,
            current_state=MessageState.QUEUED.value,
            attempt_count=0,
            next_attempt_at=now,
            accepted_at=now,
        )
        session.add(message)
        session.flush()

        # 5. Log audit event
        event = MessageEvent(
            message_id=message.message_id,
            event_type="MESSAGE_ENQUEUED",
            timestamp=now,
            source_endpoint=sender_endpoint_id,
            safe_metadata={
                "client_idempotency_key": client_idempotency_key,
                "sender": sender_endpoint_id,
                "recipient": recipient_endpoint_id,
                "priority": priority,
                "payload_bytes": len(payload_bytes),
                "payload_digest": digest,
                "expires_at": expires_at.isoformat(),
            },
        )
        session.add(event)
        session.commit()
        return message, True

    @classmethod
    def process_incoming_at_receiver(
        cls, session: Session, message: Message
    ) -> Tuple[bool, Acknowledgement]:
        """Receiver inbox ingestion and durable receipt ACK generation:
        1. Checks for duplicates.
        2. Persists to inbox if new.
        3. Generates or fetches durable ACK.
        Returns: (is_new_delivery, ack_record)
        """
        # Deduplication check
        existing_inbox = (
            session.query(InboxItem)
            .filter_by(
                recipient_endpoint_id=message.recipient_endpoint_id,
                message_id=message.message_id,
            )
            .first()
        )

        is_new = False
        now = utcnow()

        if not existing_inbox:
            try:
                inbox_item = InboxItem(
                    recipient_endpoint_id=message.recipient_endpoint_id,
                    message_id=message.message_id,
                    stored_at=now,
                    integrity_status="VALID",
                    processing_status="STORED",
                )
                session.add(inbox_item)
                message.receiver_stored_at = now
                session.flush()
                is_new = True

                event = MessageEvent(
                    message_id=message.message_id,
                    event_type="INBOX_PERSISTED",
                    timestamp=now,
                    source_endpoint=message.recipient_endpoint_id,
                    safe_metadata={
                        "recipient": message.recipient_endpoint_id,
                        "action": "DURABLY_STORED",
                    },
                )
                session.add(event)
            except IntegrityError:
                session.rollback()
                is_new = False
        else:
            # Duplicate arrival
            event = MessageEvent(
                message_id=message.message_id,
                event_type="DUPLICATE_DELIVERY_IGNORED",
                timestamp=now,
                source_endpoint=message.recipient_endpoint_id,
                safe_metadata={
                    "recipient": message.recipient_endpoint_id,
                    "note": "Already stored in inbox; returning existing receipt",
                },
            )
            session.add(event)

        # Retrieve or create durable acknowledgement
        ack = (
            session.query(Acknowledgement)
            .filter_by(
                original_message_id=message.message_id,
                ack_type="RECEIVED",
            )
            .first()
        )

        if not ack:
            try:
                ack = Acknowledgement(
                    original_message_id=message.message_id,
                    ack_type="RECEIVED",
                    origin_endpoint=message.recipient_endpoint_id,
                    destination_endpoint=message.sender_endpoint_id,
                    creation_timestamp=now,
                    validation_status="VALID",
                    delivery_status="DELIVERED",
                )
                session.add(ack)
                session.flush()

                ack_event = MessageEvent(
                    message_id=message.message_id,
                    event_type="ACK_GENERATED",
                    timestamp=now,
                    source_endpoint=message.recipient_endpoint_id,
                    safe_metadata={
                        "ack_id": ack.ack_id,
                        "origin": ack.origin_endpoint,
                        "destination": ack.destination_endpoint,
                    },
                )
                session.add(ack_event)
            except IntegrityError:
                session.rollback()
                ack = (
                    session.query(Acknowledgement)
                    .filter_by(
                        original_message_id=message.message_id,
                        ack_type="RECEIVED",
                    )
                    .first()
                )

        return is_new, ack

    @classmethod
    def process_ack_at_sender(cls, session: Session, message: Message, ack: Acknowledgement) -> bool:
        """Validates and applies receipt of ACK at the sender."""
        if ack.original_message_id != message.message_id:
            raise ValueError("ACK original_message_id does not match message ID")
        if ack.origin_endpoint != message.recipient_endpoint_id:
            raise ValueError("ACK origin does not match intended message recipient")
        if ack.destination_endpoint != message.sender_endpoint_id:
            raise ValueError("ACK destination does not match sender endpoint")

        validate_transition(
            MessageState(message.current_state),
            MessageState.DELIVERED,
            message.message_id,
        )
        now = utcnow()
        message.current_state = MessageState.DELIVERED.value
        message.sender_acknowledged_at = now
        ack.delivery_status = "DELIVERED"

        event = MessageEvent(
            message_id=message.message_id,
            event_type="ACK_VALIDATED_DELIVERED",
            timestamp=now,
            source_endpoint=message.sender_endpoint_id,
            safe_metadata={
                "ack_id": ack.ack_id,
                "verified_at": now.isoformat(),
            },
        )
        session.add(event)
        return True

    @classmethod
    def retry_message(cls, session: Session, message_id: str) -> Message:
        """Manually transitions a failed message back to QUEUED."""
        msg = session.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            raise ValueError(f"Message '{message_id}' not found")

        cur_st = MessageState(msg.current_state)
        validate_transition(cur_st, MessageState.QUEUED, message_id)

        now = utcnow()
        msg.current_state = MessageState.QUEUED.value
        msg.next_attempt_at = now
        msg.worker_lease_id = None
        msg.lease_expires_at = None

        event = MessageEvent(
            message_id=msg.message_id,
            event_type="MANUAL_RETRY_REQUESTED",
            timestamp=now,
            source_endpoint=msg.sender_endpoint_id,
            safe_metadata={"action": "USER_MANUAL_RETRY"},
        )
        session.add(event)
        session.commit()
        return msg

    @classmethod
    def cancel_message(cls, session: Session, message_id: str) -> Message:
        """Cancels a queued or retrying message."""
        msg = session.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            raise ValueError(f"Message '{message_id}' not found")

        cur_st = MessageState(msg.current_state)
        validate_transition(cur_st, MessageState.CANCELLED, message_id)

        now = utcnow()
        msg.current_state = MessageState.CANCELLED.value
        msg.worker_lease_id = None
        msg.lease_expires_at = None
        msg.last_error_code = "CANCELLED"
        msg.last_error_at = now

        event = MessageEvent(
            message_id=msg.message_id,
            event_type="MESSAGE_CANCELLED",
            timestamp=now,
            source_endpoint=msg.sender_endpoint_id,
            safe_metadata={"action": "USER_MANUAL_CANCEL"},
            error_code="CANCELLED",
        )
        session.add(event)
        session.commit()
        return msg

    @classmethod
    def get_inbox_messages(cls, session: Session, endpoint_id: str) -> List[Dict[str, Any]]:
        """Retrieves stored messages from endpoint inbox."""
        results = (
            session.query(InboxItem, Message)
            .join(Message, InboxItem.message_id == Message.message_id)
            .filter(InboxItem.recipient_endpoint_id == endpoint_id)
            .order_by(InboxItem.stored_at.desc())
            .all()
        )
        inbox = []
        for item, msg in results:
            inbox.append({
                "inbox_id": item.inbox_id,
                "message_id": msg.message_id,
                "sender_endpoint_id": msg.sender_endpoint_id,
                "recipient_endpoint_id": msg.recipient_endpoint_id,
                "payload": msg.payload,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "stored_at": item.stored_at.isoformat() if item.stored_at else None,
                "integrity_status": item.integrity_status,
                "processing_status": item.processing_status,
                "current_state": msg.current_state,
            })
        return inbox

    @classmethod
    def get_outbox_messages(cls, session: Session, endpoint_id: str) -> List[Dict[str, Any]]:
        """Retrieves messages originating from endpoint."""
        messages = (
            session.query(Message)
            .filter_by(sender_endpoint_id=endpoint_id)
            .order_by(Message.created_at.desc())
            .all()
        )
        return [m.to_dict() for m in messages]

    @classmethod
    def get_queue_stats(cls, session: Session) -> Dict[str, Any]:
        """Calculates aggregated queue counts and metrics."""
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
            "sending": stats.get(MessageState.SENDING.value, 0),
            "awaiting_ack": stats.get(MessageState.AWAITING_ACK.value, 0),
            "delivered": stats.get(MessageState.DELIVERED.value, 0),
            "failed_retryable": stats.get(MessageState.FAILED_RETRYABLE.value, 0),
            "failed_final": stats.get(MessageState.FAILED_FINAL.value, 0),
            "expired": stats.get(MessageState.EXPIRED.value, 0),
            "cancelled": stats.get(MessageState.CANCELLED.value, 0),
            "last_successful_delivery": last_delivery.isoformat() if last_delivery else None,
        }
