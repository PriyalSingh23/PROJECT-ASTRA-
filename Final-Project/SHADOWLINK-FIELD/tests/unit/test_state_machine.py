import pytest
from app.core.state_machine import (
    MessageState,
    validate_transition,
    InvalidStateTransitionError,
)


def test_valid_state_transitions():
    # Normal forward lifecycle
    validate_transition(MessageState.DRAFT, MessageState.LOCAL_QUEUED)
    validate_transition(MessageState.LOCAL_QUEUED, MessageState.QUEUED)
    validate_transition(MessageState.QUEUED, MessageState.SENDING)
    validate_transition(MessageState.SENDING, MessageState.AWAITING_ACK)
    validate_transition(MessageState.AWAITING_ACK, MessageState.DELIVERED)

    # Retry path
    validate_transition(MessageState.SENDING, MessageState.FAILED_RETRYABLE)
    validate_transition(MessageState.FAILED_RETRYABLE, MessageState.QUEUED)
    validate_transition(MessageState.FAILED_RETRYABLE, MessageState.FAILED_FINAL)


def test_invalid_state_transitions():
    # Cannot jump from DRAFT straight to DELIVERED
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(MessageState.DRAFT, MessageState.DELIVERED)

    # Terminal state cannot be changed
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(MessageState.DELIVERED, MessageState.QUEUED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(MessageState.CANCELLED, MessageState.SENDING)
