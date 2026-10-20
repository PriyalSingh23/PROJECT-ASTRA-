import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from app.core.database import Base, utcnow


class InboxItem(Base):
    __tablename__ = "inbox"

    inbox_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_endpoint_id = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False, index=True)
    message_id = Column(String(64), ForeignKey("messages.message_id"), nullable=False, index=True)
    stored_at = Column(DateTime, default=utcnow, nullable=False)
    integrity_status = Column(String(32), default="VALID", nullable=False)
    processing_status = Column(String(32), default="STORED", nullable=False)

    __table_args__ = (
        UniqueConstraint("recipient_endpoint_id", "message_id", name="uq_recipient_message"),
    )

    def to_dict(self):
        return {
            "inbox_id": self.inbox_id,
            "recipient_endpoint_id": self.recipient_endpoint_id,
            "message_id": self.message_id,
            "stored_at": self.stored_at.isoformat() if self.stored_at else None,
            "integrity_status": self.integrity_status,
            "processing_status": self.processing_status,
        }
