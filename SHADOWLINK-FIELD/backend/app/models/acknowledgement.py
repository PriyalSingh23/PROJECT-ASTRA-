import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from app.core.database import Base, utcnow


class Acknowledgement(Base):
    __tablename__ = "acknowledgements"

    ack_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_message_id = Column(String(64), ForeignKey("messages.message_id"), nullable=False, index=True)
    ack_type = Column(String(32), default="RECEIVED", nullable=False)
    origin_endpoint = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False)
    destination_endpoint = Column(String(64), ForeignKey("endpoints.endpoint_id"), nullable=False)
    creation_timestamp = Column(DateTime, default=utcnow, nullable=False)
    validation_status = Column(String(32), default="VALID", nullable=False)
    delivery_status = Column(String(32), default="DELIVERED", nullable=False)

    __table_args__ = (
        UniqueConstraint("original_message_id", "ack_type", name="uq_message_ack_type"),
    )

    def to_dict(self):
        return {
            "ack_id": self.ack_id,
            "original_message_id": self.original_message_id,
            "ack_type": self.ack_type,
            "origin_endpoint": self.origin_endpoint,
            "destination_endpoint": self.destination_endpoint,
            "creation_timestamp": self.creation_timestamp.isoformat() if self.creation_timestamp else None,
            "validation_status": self.validation_status,
            "delivery_status": self.delivery_status,
            "integrity_verified": (self.validation_status == "VALID"),
        }
