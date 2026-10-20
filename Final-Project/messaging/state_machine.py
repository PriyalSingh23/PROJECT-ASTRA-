from enum import Enum
from typing import Dict, Set, Optional


class MessageState(str, Enum):
    DRAFT = "DRAFT"
    LOCAL_QUEUED = "LOCAL_QUEUED"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    ACCEPTED = "ACCEPTED"
    AWAITING_ACK = "AWAITING_ACK"
    RECEIVED = "RECEIVED"
    DELIVERED = "DELIVERED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


# Valid state transitions
VALID_TRANSITIONS: Dict[MessageState, Set[MessageState]] = {
    MessageState.DRAFT: {MessageState.LOCAL_QUEUED, MessageState.CANCELLED},
    MessageState.LOCAL_QUEUED: {MessageState.QUEUED, MessageState.CANCELLED},
    MessageState.QUEUED: {MessageState.SENDING, MessageState.EXPIRED, MessageState.CANCELLED},
    MessageState.SENDING: {
        MessageState.ACCEPTED,
        MessageState.AWAITING_ACK,
        MessageState.RECEIVED,
        MessageState.DELIVERED,
        MessageState.FAILED_RETRYABLE,
        MessageState.FAILED_FINAL,
        MessageState.EXPIRED,
    },
    MessageState.ACCEPTED: {
        MessageState.AWAITING_ACK,
        MessageState.RECEIVED,
        MessageState.DELIVERED,
        MessageState.FAILED_RETRYABLE,
        MessageState.FAILED_FINAL,
    },
    MessageState.AWAITING_ACK: {
        MessageState.SENDING,
        MessageState.DELIVERED,
        MessageState.FAILED_RETRYABLE,
        MessageState.FAILED_FINAL,
        MessageState.EXPIRED,
        MessageState.CANCELLED,
    },
    MessageState.RECEIVED: {
        MessageState.DELIVERED,
    },
    MessageState.FAILED_RETRYABLE: {
        MessageState.SENDING,
        MessageState.QUEUED,
        MessageState.FAILED_FINAL,
        MessageState.EXPIRED,
        MessageState.CANCELLED,
    },
    MessageState.FAILED_FINAL: {MessageState.QUEUED},  # Manual retry transition
    MessageState.DELIVERED: set(),
    MessageState.EXPIRED: set(),
    MessageState.CANCELLED: set(),
}

TERMINAL_STATES: Set[MessageState] = {
    MessageState.DELIVERED,
    MessageState.FAILED_FINAL,
    MessageState.EXPIRED,
    MessageState.CANCELLED,
}


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal message state transition is attempted."""
    def __init__(self, from_state: MessageState, to_state: MessageState, message_id: Optional[str] = None):
        msg = f"Invalid state transition: {from_state.value} -> {to_state.value}"
        if message_id:
            msg += f" (Message ID: {message_id})"
        super().__init__(msg)
        self.from_state = from_state
        self.to_state = to_state
        self.message_id = message_id


def validate_transition(from_state: MessageState, to_state: MessageState, message_id: Optional[str] = None) -> bool:
    """Verifies whether transition from `from_state` to `to_state` is permitted."""
    if from_state == to_state:
        return True  # Idempotent no-op
    allowed = VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise InvalidStateTransitionError(from_state, to_state, message_id)
    return True
