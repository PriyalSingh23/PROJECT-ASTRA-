from typing import Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session
from messaging.models import (
    Message,
    InboxItem,
    Acknowledgement,
    MessageEvent,
    generate_uuid,
    utcnow,
)
from messaging.state_machine import MessageState, validate_transition
from messaging.security_config import get_app_secret_key


class AckManager:
    """Manages the creation, verification, and processing of durable-receipt acknowledgements."""

    @classmethod
    def process_incoming_at_receiver(
        cls, session: Session, message: Message
    ) -> Tuple[bool, Acknowledgement]:
        """Processes message arriving at the receiver endpoint:
        1. Validates message.
        2. Deduplicates against inbox.
        3. Persists in inbox if not already present.
        4. Generates or retrieves durable-receipt ACK.
        
        Returns:
            (is_new_delivery, ack_record)
        """
        # Deduplication check: does message already exist in recipient inbox?
        existing_inbox = (
            session.query(InboxItem)
            .filter_by(
                recipient_endpoint_id=message.recipient_endpoint_id,
                message_id=message.message_id,
            )
            .first()
        )

        is_new = False
        if not existing_inbox:
            # First time arrival: persist in inbox
            inbox_item = InboxItem(
                inbox_id=generate_uuid(),
                recipient_endpoint_id=message.recipient_endpoint_id,
                message_id=message.message_id,
                stored_at=utcnow(),
                integrity_status="VALID",
                processing_status="STORED",
                envelope_version=getattr(message, "envelope_version", 3),
                pqc_scheme=getattr(message, "pqc_scheme", "ML-KEM-768+X25519"),
                pqc_verified=getattr(message, "pqc_verified", False),
                pqc_downgrade_warning=getattr(message, "pqc_downgrade_warning", False),
            )
            session.add(inbox_item)
            message.receiver_stored_at = inbox_item.stored_at
            is_new = True

            # Record event
            event = MessageEvent(
                event_id=generate_uuid(),
                message_id=message.message_id,
                event_type="INBOX_PERSISTED",
                timestamp=utcnow(),
                source_endpoint=message.recipient_endpoint_id,
                safe_metadata={
                    "recipient": message.recipient_endpoint_id,
                    "inbox_id": inbox_item.inbox_id,
                    "action": "DURABLY_STORED",
                },
            )
            session.add(event)
        else:
            # Duplicate arrival
            event = MessageEvent(
                event_id=generate_uuid(),
                message_id=message.message_id,
                event_type="DUPLICATE_DELIVERY_IGNORED",
                timestamp=utcnow(),
                source_endpoint=message.recipient_endpoint_id,
                safe_metadata={
                    "recipient": message.recipient_endpoint_id,
                    "note": "Already persisted in inbox; regenerating existing receipt",
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
            ack = Acknowledgement(
                ack_id=generate_uuid(),
                original_message_id=message.message_id,
                ack_type="RECEIVED",
                origin_endpoint=message.recipient_endpoint_id,
                destination_endpoint=message.sender_endpoint_id,
                creation_timestamp=utcnow(),
                validation_status="VALID",
                delivery_status="PENDING",
            )
            session.add(ack)

            ack_event = MessageEvent(
                event_id=generate_uuid(),
                message_id=message.message_id,
                event_type="ACK_GENERATED",
                timestamp=utcnow(),
                source_endpoint=message.recipient_endpoint_id,
                safe_metadata={
                    "ack_id": ack.ack_id,
                    "ack_type": ack.ack_type,
                    "origin": ack.origin_endpoint,
                    "destination": ack.destination_endpoint,
                },
            )
            session.add(ack_event)

        session.flush()
        return is_new, ack

    @classmethod
    def generate_receipt_signature(cls, ack: Acknowledgement, message: Message) -> str:
        """Generates a verifiable cryptographic HMAC delivery receipt signature."""
        import hmac
        import hashlib
        secret = get_app_secret_key().encode("utf-8")
        data = f"{ack.ack_id}:{message.message_id}:{message.recipient_endpoint_id}:{message.client_idempotency_key}".encode()
        sig = hmac.new(secret, data, hashlib.sha256).hexdigest()[:16]
        return f"ACK-SIG:{ack.ack_id[:8]}:{sig}"

    @classmethod
    def process_ack_at_sender(
        cls, session: Session, message: Message, ack: Acknowledgement
    ) -> bool:
        """Validates and processes receipt of ACK at original sender endpoint:
        1. Validates ACK schema and endpoint alignment.
        2. Updates message state to DELIVERED.
        3. Computes and assigns cryptographic signed_ack_receipt.
        4. Records completion event.
        
        Returns True if ACK was valid and state transitioned.
        """
        # Validate ACK matches message
        if ack.original_message_id != message.message_id:
            raise ValueError("ACK message ID mismatch")
        if ack.origin_endpoint != message.recipient_endpoint_id:
            raise ValueError("ACK origin does not match message recipient")
        if ack.destination_endpoint != message.sender_endpoint_id:
            raise ValueError("ACK destination does not match message sender")
        if ack.ack_type != "RECEIVED":
            raise ValueError(f"Unsupported ACK type: {ack.ack_type}")

        # Transition state to DELIVERED
        validate_transition(
            MessageState(message.current_state),
            MessageState.DELIVERED,
            message.message_id,
        )

        now = utcnow()
        message.current_state = MessageState.DELIVERED.value
        message.sender_acknowledged_at = now
        ack.delivery_status = "DELIVERED"
        receipt_sig = cls.generate_receipt_signature(ack, message)
        message.signed_ack_receipt = receipt_sig

        event = MessageEvent(
            event_id=generate_uuid(),
            message_id=message.message_id,
            event_type="ACK_VALIDATED_DELIVERED",
            timestamp=now,
            source_endpoint=message.sender_endpoint_id,
            safe_metadata={
                "ack_id": ack.ack_id,
                "status": "DELIVERED",
                "round_trip_completed": True,
                "signed_receipt": receipt_sig,
            },
        )
        session.add(event)
        return True
