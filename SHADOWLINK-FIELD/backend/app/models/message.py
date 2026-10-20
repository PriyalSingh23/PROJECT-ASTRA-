import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, UniqueConstraint, Index
from app.core.database import Base, utcnow


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_idempotency_key = Column(String(128), nullable=False, index=True)
    sender_endpoint_id = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False, index=True)
    recipient_endpoint_id = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False, index=True)
    message_type = Column(String(32), default="TACTICAL_TEXT", nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    priority = Column(Integer, default=2, nullable=False)  # 1-5
    current_state = Column(String(32), default="QUEUED", nullable=False, index=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    next_attempt_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    last_error_code = Column(String(64), nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    receiver_stored_at = Column(DateTime, nullable=True)
    sender_acknowledged_at = Column(DateTime, nullable=True)

    # Worker atomic leasing
    worker_lease_id = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("sender_endpoint_id", "client_idempotency_key", name="uq_sender_idempotency"),
        Index("ix_messages_queue_poll", "current_state", "next_attempt_at"),
    )

    def to_dict(self):
        return {
            "message_id": self.message_id,
            "client_idempotency_key": self.client_idempotency_key,
            "sender_endpoint_id": self.sender_endpoint_id,
            "recipient_endpoint_id": self.recipient_endpoint_id,
            "message_type": self.message_type,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "priority": self.priority,
            "current_state": self.current_state,
            "attempt_count": self.attempt_count,
            "next_attempt_at": self.next_attempt_at.isoformat() if self.next_attempt_at else None,
            "last_error_code": self.last_error_code,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "receiver_stored_at": self.receiver_stored_at.isoformat() if self.receiver_stored_at else None,
            "sender_acknowledged_at": self.sender_acknowledged_at.isoformat() if self.sender_acknowledged_at else None,
            "worker_lease_id": self.worker_lease_id,
        }
