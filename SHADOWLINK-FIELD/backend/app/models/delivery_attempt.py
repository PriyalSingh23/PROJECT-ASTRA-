import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from app.core.database import Base, utcnow


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"

    attempt_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(64), ForeignKey("messages.message_id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    start_timestamp = Column(DateTime, default=utcnow, nullable=False)
    completion_timestamp = Column(DateTime, nullable=True)
    result = Column(String(32), nullable=False)  # SUCCESS, FAILED, DROPPED, ACK_LOST
    transport_type = Column(String(32), nullable=False)  # SIMULATION, MOTOROLA, STARV, SDR
    transport_state = Column(String(32), nullable=False)  # ONLINE, OFFLINE
    error_code = Column(String(64), nullable=True)
    retryability = Column(Boolean, default=False, nullable=False)
    acknowledgement_state = Column(String(32), default="NONE", nullable=False)

    def to_dict(self):
        return {
            "attempt_id": self.attempt_id,
            "message_id": self.message_id,
            "attempt_number": self.attempt_number,
            "start_timestamp": self.start_timestamp.isoformat() if self.start_timestamp else None,
            "completion_timestamp": self.completion_timestamp.isoformat() if self.completion_timestamp else None,
            "result": self.result,
            "transport_type": self.transport_type,
            "transport_state": self.transport_state,
            "error_code": self.error_code,
            "retryability": self.retryability,
            "acknowledgement_state": self.acknowledgement_state,
        }
