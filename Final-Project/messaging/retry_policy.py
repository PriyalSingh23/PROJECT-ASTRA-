import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from messaging.models import Message, MessageEvent, generate_uuid, utcnow
from messaging.state_machine import MessageState, validate_transition

DEFAULT_BASE_DELAY = 2.0  # seconds (2s, 4s, 8s, 16s...)
DEFAULT_MAX_DELAY = 60.0  # seconds ceiling
DEFAULT_JITTER = 0.5  # seconds
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_LEASE_TIMEOUT = 30.0  # seconds

RETRYABLE_ERROR_CODES = {
    "TRANSPORT_OFFLINE",
    "PACKET_DROPPED",
    "ACK_LOST",
    "TEMPORARY_NETWORK_ERROR",
    "LEASE_EXPIRED",
    "TIMEOUT",
    "CONNECTION_REFUSED",
    "ROUTE_UNAVAILABLE",
    "STARV_SAFETY_LOCKOUT_BLOCKED",
}

PERMANENT_ERROR_CODES = {
    "RECIPIENT_NOT_FOUND",
    "RECIPIENT_DISABLED",
    "PAYLOAD_INVALID",
    "PAYLOAD_TOO_LARGE",
    "RETRY_LIMIT_EXHAUSTED",
    "EXPIRED",
    "CANCELLED",
}


def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class RetryPolicy:
    """Configurable retry scheduler with exponential backoff, jitter, and worker lease reclamation."""

    active_profile: str = "TACTICAL"
    PROFILES = {
        "FAST": {"base_delay": 0.5, "max_delay": 5.0, "jitter": 0.1},
        "TACTICAL": {"base_delay": 2.0, "max_delay": 60.0, "jitter": 0.5},
    }

    @classmethod
    def configure_profile(cls, profile: str):
        p = profile.upper()
        if p in cls.PROFILES:
            cls.active_profile = p
        else:
            raise ValueError(f"Unknown retry profile: {profile}. Must be 'FAST' or 'TACTICAL'")

    @classmethod
    def is_retryable(cls, error_code: Optional[str]) -> bool:
        if not error_code:
            return False
        return error_code in RETRYABLE_ERROR_CODES

    @classmethod
    def compute_next_attempt_at(
        cls,
        attempt_count: int,
        base_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
        jitter: Optional[float] = None,
    ) -> datetime:
        """Calculates exponential backoff timestamp with random jitter."""
        prof = cls.PROFILES.get(cls.active_profile, cls.PROFILES["TACTICAL"])
        if base_delay is None:
            base_delay = prof["base_delay"]
        if max_delay is None:
            max_delay = prof["max_delay"]
        if jitter is None:
            jitter = prof["jitter"]

        # 2^attempt backoff: attempt=1 -> 2s, attempt=2 -> 4s, attempt=3 -> 8s...
        delay = min(max_delay, base_delay * (2 ** max(0, attempt_count - 1)))
        delay += random.uniform(0.0, jitter)
        return utcnow() + timedelta(seconds=delay)

    @classmethod
    def check_and_apply_expiry(cls, session: Session, message: Message) -> bool:
        """Checks if message has passed its expiry deadline. If expired, transitions state."""
        now = to_naive_utc(utcnow())
        exp = to_naive_utc(message.expires_at)
        if exp and exp < now:
            from_st = MessageState(message.current_state)
            if from_st not in {MessageState.DELIVERED, MessageState.EXPIRED, MessageState.CANCELLED}:
                validate_transition(from_st, MessageState.EXPIRED, message.message_id)
                message.current_state = MessageState.EXPIRED.value
                message.last_error_code = "EXPIRED"
                message.last_error_at = now

                event = MessageEvent(
                    event_id=generate_uuid(),
                    message_id=message.message_id,
                    event_type="MESSAGE_EXPIRED",
                    timestamp=now,
                    source_endpoint="system-scheduler",
                    safe_metadata={
                        "expired_at": now.isoformat(),
                        "original_deadline": message.expires_at.isoformat() if message.expires_at else None,
                    },
                    error_code="EXPIRED",
                )
                session.add(event)
                return True
        return False

    @classmethod
    def reclaim_stale_leases(cls, session: Session, lease_timeout_seconds: float = DEFAULT_LEASE_TIMEOUT) -> int:
        """Reclaims messages that were left in 'SENDING' state by crashed or interrupted workers."""
        now = to_naive_utc(utcnow())
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
            prev_worker_id = msg.worker_lease_id or "unknown-worker"
            prev_lease_exp = msg.lease_expires_at.isoformat() if msg.lease_expires_at else None

            msg.current_state = MessageState.FAILED_RETRYABLE.value
            msg.next_attempt_at = now - timedelta(seconds=1)  # Eligible for immediate retry
            msg.worker_lease_id = None
            msg.lease_expires_at = None
            msg.last_error_code = "LEASE_EXPIRED"
            msg.last_error_at = now

            event = MessageEvent(
                event_id=generate_uuid(),
                message_id=msg.message_id,
                event_type="WORKER_LEASE_RECLAIMED",
                timestamp=now,
                source_endpoint="worker-manager",
                safe_metadata={
                    "previous_worker_id": prev_worker_id,
                    "lease_expires_at": prev_lease_exp,
                    "reason": "Previous worker did not finish before lease expired",
                    "lease_timeout_seconds": lease_timeout_seconds,
                },
                error_code="LEASE_EXPIRED",
            )
            session.add(event)
            reclaimed_count += 1

        return reclaimed_count

    @classmethod
    def recover_stranded_leases(cls, session: Session) -> int:
        """Scans and transitions all orphaned SENDING messages left by previously terminated processes."""
        now = to_naive_utc(utcnow())
        stranded = (
            session.query(Message)
            .filter(Message.current_state == MessageState.SENDING.value)
            .all()
        )
        count = 0
        for msg in stranded:
            prev_worker_id = msg.worker_lease_id or "orphaned-worker"
            prev_lease_exp = msg.lease_expires_at.isoformat() if msg.lease_expires_at else None
            msg.current_state = MessageState.FAILED_RETRYABLE.value
            msg.next_attempt_at = now - timedelta(seconds=1)
            msg.worker_lease_id = None
            msg.lease_expires_at = None
            msg.last_error_code = "LEASE_EXPIRED"
            msg.last_error_at = now

            event = MessageEvent(
                event_id=generate_uuid(),
                message_id=msg.message_id,
                event_type="WORKER_LEASE_RECLAIMED",
                timestamp=now,
                source_endpoint="startup-supervisor",
                safe_metadata={
                    "previous_worker_id": prev_worker_id,
                    "lease_expires_at": prev_lease_exp,
                    "reason": "Stranded in-flight lease recovered upon service startup",
                    "startup_sweep": True,
                },
                error_code="LEASE_EXPIRED",
            )
            session.add(event)
            count += 1
        if count > 0:
            session.commit()
        return count
