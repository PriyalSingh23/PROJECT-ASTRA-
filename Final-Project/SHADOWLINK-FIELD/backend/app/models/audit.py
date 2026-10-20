import uuid
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from app.core.database import Base, utcnow


class MessageEvent(Base):
    __tablename__ = "message_events"

    event_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(64), ForeignKey("messages.message_id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    source_endpoint = Column(String(64), nullable=False)
    safe_metadata = Column(JSON, default=dict, nullable=False)
    error_code = Column(String(64), nullable=True)

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "message_id": self.message_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source_endpoint": self.source_endpoint,
            "safe_metadata": self.safe_metadata,
            "error_code": self.error_code,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=utcnow, nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=True)
    safe_details = Column(JSON, default=dict, nullable=False)
    ip_address = Column(String(45), nullable=True)

    def to_dict(self):
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "safe_details": self.safe_details,
            "ip_address": self.ip_address,
        }
