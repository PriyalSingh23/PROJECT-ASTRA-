import random
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import utcnow
from app.core.state_machine import MessageState, validate_transition
from app.models.message import Message
from app.models.audit import MessageEvent

RETRYABLE_ERROR_CODES = {
    "TRANSPORT_OFFLINE",
    "PACKET_DROPPED",
    "ACK_LOST",
    "MOTO_CHANNEL_BUSY",
    "TEMPORARY_NETWORK_ERROR",
    "LEASE_EXPIRED",
    "TIMEOUT",
    "CONNECTION_REFUSED",
}

PERMANENT_ERROR_CODES = {
    "RECIPIENT_NOT_FOUND",
    "RECIPIENT_DISABLED",
    "PAYLOAD_INVALID",
    "PAYLOAD_TOO_LARGE",
    "RETRY_LIMIT_EXHAUSTED",
    "EXPIRED",
    "CANCELLED",
    "STARV_UNCONFIGURED_SAFETY_LOCKOUT",
    "UNSUPPORTED_ADAPTER_CAPABILITY",
}


class RetryScheduler:
    """Configurable retry scheduler with exponential backoff, jitter, and lease reclamation."""

    @classmethod
    def is_retryable(cls, error_code: Optional[str]) -> bool:
        if not error_code:
            return False
        return error_code in RETRYABLE_ERROR_CODES

    @classmethod
    def compute_next_attempt_at(
        cls,
        attempt_count: int,
        base_delay: float = settings.DEFAULT_BASE_DELAY_SEC,
        max_delay: float = settings.DEFAULT_MAX_DELAY_SEC,
        jitter: float = settings.DEFAULT_JITTER_SEC,
    ) -> datetime:
        """Calculates exponential backoff timestamp with random jitter: min(max_delay, base * 2^(n-1)) + jitter."""
        delay = min(max_delay, base_delay * (2 ** max(0, attempt_count - 1)))
        delay += random.uniform(0.0, jitter)
        return utcnow() + timedelta(seconds=delay)

    @classmethod
    def check_and_apply_expiry(cls, session: Session, message: Message) -> bool:
        """Checks if message has passed its expiry deadline. If expired, transitions state."""
        now = utcnow()
        if message.expires_at and message.expires_at < now:
            from_st = MessageState(message.current_state)
            if from_st not in {MessageState.DELIVERED, MessageState.EXPIRED, MessageState.CANCELLED}:
                validate_transition(from_st, MessageState.EXPIRED, message.message_id)
                message.current_state = MessageState.EXPIRED.value
                message.last_error_code = "EXPIRED"
                message.last_error_at = now

                event = MessageEvent(
                    message_id=message.message_id,
                    event_type="MESSAGE_EXPIRED",
                    timestamp=now,
                    source_endpoint="system-scheduler",
                    safe_metadata={
                        "expired_at": now.isoformat(),
                        "original_deadline": message.expires_at.isoformat(),
                    },
                    error_code="EXPIRED",
                )
                session.add(event)
                return True
        return False

    @classmethod
    def reclaim_stale_leases(cls, session: Session, lease_timeout_sec: float = settings.DEFAULT_LEASE_TIMEOUT_SEC) -> int:
        """Reclaims messages that were left in 'SENDING' state by crashed or aborted workers."""
        now = utcnow()
        stale_messages = (
            session.query(Message)
            .filter(
                Message.current_state == MessageState.SENDING.value,
                Message.lease_expires_at < now,
            )
            .all()
        )

        reclaimed_count = 0
        for msg in stale_messages:
            msg.current_state = MessageState.FAILED_RETRYABLE.value
            msg.next_attempt_at = now  # Immediately eligible
            msg.worker_lease_id = None
            msg.lease_expires_at = None
            msg.last_error_code = "LEASE_EXPIRED"
            msg.last_error_at = now

            event = MessageEvent(
                message_id=msg.message_id,
                event_type="WORKER_LEASE_RECLAIMED",
                timestamp=now,
                source_endpoint="worker-manager",
                safe_metadata={
                    "reason": "Previous worker failed to finish before lease deadline",
                    "lease_timeout_sec": lease_timeout_sec,
                },
                error_code="LEASE_EXPIRED",
            )
            session.add(event)
            reclaimed_count += 1

        if reclaimed_count > 0:
            session.commit()
        return reclaimed_count
