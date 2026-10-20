from enum import Enum
from typing import Set, Dict


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


class InvalidStateTransitionError(Exception):
    """Raised when an illegal message state transition is requested."""
    pass


# Strict allowed transition mapping
ALLOWED_TRANSITIONS: Dict[MessageState, Set[MessageState]] = {
    MessageState.DRAFT: {
        MessageState.LOCAL_QUEUED,
        MessageState.QUEUED,
        MessageState.CANCELLED,
    },
    MessageState.LOCAL_QUEUED: {
        MessageState.QUEUED,
        MessageState.CANCELLED,
        MessageState.EXPIRED,
    },
    MessageState.QUEUED: {
        MessageState.SENDING,
        MessageState.CANCELLED,
        MessageState.EXPIRED,
    },
    MessageState.SENDING: {
        MessageState.ACCEPTED,
        MessageState.AWAITING_ACK,
        MessageState.DELIVERED,
        MessageState.FAILED_RETRYABLE,
        MessageState.FAILED_FINAL,
        MessageState.EXPIRED,
    },
    MessageState.ACCEPTED: {
        MessageState.AWAITING_ACK,
        MessageState.DELIVERED,
        MessageState.FAILED_RETRYABLE,
        MessageState.FAILED_FINAL,
        MessageState.EXPIRED,
    },
    MessageState.AWAITING_ACK: {
        MessageState.DELIVERED,
        MessageState.SENDING,          # Retrying to fetch lost ACK
        MessageState.FAILED_RETRYABLE,  # ACK timed out
        MessageState.FAILED_FINAL,      # Max retry attempts reached
        MessageState.EXPIRED,
    },
    MessageState.RECEIVED: {
        # Receiver-side state indicating durable storage
        MessageState.DELIVERED,
    },
    MessageState.FAILED_RETRYABLE: {
        MessageState.QUEUED,           # Manual retry or scheduler queue
        MessageState.SENDING,          # Automatic retry lease
        MessageState.FAILED_FINAL,     # Ceiling reached
        MessageState.CANCELLED,
        MessageState.EXPIRED,
    },
    MessageState.FAILED_FINAL: {
        MessageState.QUEUED,           # Explicit human operator manual retry
    },
    MessageState.DELIVERED: set(),     # Terminal success state
    MessageState.EXPIRED: set(),       # Terminal deadline state
    MessageState.CANCELLED: set(),     # Terminal operator cancel state
}


def validate_transition(from_state: MessageState, to_state: MessageState, message_id: str = ""):
    """Validates that a transition from from_state to to_state is semantically permitted."""
    if from_state == to_state:
        return

    allowed = ALLOWED_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise InvalidStateTransitionError(
            f"Illegal state transition for message '{message_id}': cannot move from {from_state.value} to {to_state.value}."
        )
